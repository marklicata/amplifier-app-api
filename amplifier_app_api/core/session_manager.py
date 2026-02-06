"""Session manager that wraps amplifier-core."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from ..config import settings
from ..models import Session, SessionMetadata, SessionStatus
from ..storage import Database
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Amplifier sessions using amplifier-core."""

    def __init__(self, db: Database):
        """Initialize session manager."""
        self.db = db
        self.config_manager = ConfigManager(
            db, session_manager=self
        )  # Pass self for cache invalidation
        self._sessions: dict[str, Any] = {}  # Active AmplifierSession instances
        self._prepared_bundles: dict[str, Any] = {}  # Cached prepared bundles by config_id

        # Import amplifier modules (will use installed packages from pyproject.toml)
        self._import_amplifier_modules()

    def invalidate_config_cache(self, config_id: str) -> None:
        """Invalidate cached prepared bundle for a config.

        Call this when a config's YAML is updated to ensure
        new sessions use the updated configuration.

        Args:
            config_id: Config identifier to invalidate
        """
        if config_id in self._prepared_bundles:
            del self._prepared_bundles[config_id]
            logger.info(f"Invalidated bundle cache for config: {config_id}")

    def _import_amplifier_modules(self) -> None:
        """Import amplifier modules from installed packages."""
        try:
            from amplifier_core import AmplifierSession  # type: ignore[import-not-found]
            from amplifier_foundation import BundleRegistry  # type: ignore[import-not-found]

            self.AmplifierSession = AmplifierSession
            self.BundleRegistry = BundleRegistry

            # Create a BundleRegistry for loading bundles
            self.registry = BundleRegistry()
            
            # Mark that we need to populate registry on first use
            self._registry_populated = False

            logger.info(
                "Successfully imported amplifier-core and amplifier-foundation from installed packages"
            )
        except ImportError as e:
            logger.error(f"Failed to import amplifier modules: {e}")
            raise RuntimeError(
                "Could not import amplifier-core or amplifier-foundation. "
                "Ensure they are installed via 'uv sync'."
            ) from e

    async def load_bundle(self, bundle_name: str) -> Any:
        """Load a bundle by name using the BundleRegistry.

        This method is used by ToolManager to load bundles for tool inspection/invocation.

        Args:
            bundle_name: Name of the bundle to load

        Returns:
            Found Bundle object

        Raises:
            ValueError: If bundle cannot be found
        """
        try:
            # Use BundleRegistry to find the bundle
            bundle = await self.registry.find(bundle_name)
            logger.info(f"Found bundle: {bundle_name}")
            return bundle
        except Exception as e:
            logger.error(f"Failed to find bundle {bundle_name}: {e}")
            raise ValueError(f"Could not find bundle '{bundle_name}': {e}") from e

    async def _ensure_foundation_available(self) -> None:
        """Ensure foundation bundle is loaded and modules are available.

        This loads the foundation bundle once per SessionManager instance,
        making core modules like loop-basic and context-simple available
        for all sessions.
        """
        if hasattr(self, "_foundation_prepared"):
            return

        try:
            logger.info("Loading foundation bundle...")

            # Load foundation through registry
            foundation_bundle = await self.registry.load("foundation")

            # Prepare it to activate modules
            await foundation_bundle.prepare(install_deps=False)

            self._foundation_prepared = True
            logger.info("Foundation bundle loaded successfully - core modules are now available")
        except Exception as e:
            logger.error(f"Failed to load foundation bundle: {e}", exc_info=True)
            raise RuntimeError(
                "Could not load required foundation bundle. "
                "This bundle provides core modules like loop-basic and context-simple. "
                f"Error: {e}"
            ) from e

    async def _get_or_prepare_config_bundle(self, config_id: str) -> Any:
        """Get or prepare a bundle from a config YAML.

        Args:
            config_id: Config identifier

        Returns:
            Prepared bundle ready to create sessions

        Raises:
            ValueError: If config not found or YAML is invalid
            RuntimeError: If bundle preparation fails
        """
        # Ensure foundation is loaded first (provides core modules like loop-basic, context-simple)
        await self._ensure_foundation_available()

        if config_id in self._prepared_bundles:
            logger.info(f"Using cached bundle for config: {config_id}")
            return self._prepared_bundles[config_id]

        # Get config from database
        config = await self.config_manager.get_config(config_id)
        if not config:
            raise ValueError(f"Config not found: {config_id}")

        try:
            # Parse YAML string to dict
            config_dict = self.config_manager.parse_yaml(config.yaml_content)
            logger.info(f"Parsed YAML for config: {config_id}")

            # Extract markdown body if present (after YAML frontmatter)
            # Config YAML can be:
            # 1. Pure YAML (no frontmatter separator)
            # 2. YAML frontmatter + markdown body (separated by "---")
            instruction = None
            if config.yaml_content.startswith("---"):
                # Has frontmatter - extract markdown body
                parts = config.yaml_content.split("---", 2)
                if len(parts) > 2:
                    instruction = parts[2].strip()

            # Import Bundle class
            from amplifier_foundation import Bundle  # type: ignore[import-not-found]

            # Create Bundle from dict (no temp file needed!)
            bundle = Bundle.from_dict(config_dict, base_path=Path.cwd())

            # Set instruction (markdown body) if present
            if instruction:
                bundle.instruction = instruction

            logger.info(f"Created Bundle from config dict: {config_id}")

            # Create source resolver that uses our registry for resolving includes
            def resolve_source(module_id: str, source: str) -> str:
                """Resolve module sources using our registry.

                This allows the bundle to resolve 'bundle: foundation' includes
                by looking them up in our registry.
                """
                # If source looks like a bundle name (no URI scheme), try registry
                if not source.startswith(("git+", "http://", "https://", "file://")):
                    # Check if it's a registered bundle
                    registry_uri = self.registry.find(source)
                    if registry_uri:
                        logger.info(f"Resolved bundle '{source}' to {registry_uri} via registry")
                        return registry_uri

                # Return original source if not found in registry
                return source

            # Prepare bundle (resolves includes, loads modules, creates mount plan)
            # install_deps=False because dependencies are already installed in Docker image
            # Pass source_resolver so bundle can resolve 'bundle: foundation' includes
            logger.info(f"Preparing bundle for config: {config_id}")
            prepared = await asyncio.wait_for(
                bundle.prepare(install_deps=False, source_resolver=resolve_source), timeout=60.0
            )
            logger.info(f"Bundle prepared for config: {config_id}")

            # Cache prepared bundle for reuse
            self._prepared_bundles[config_id] = prepared
            logger.info(f"Bundle cached for config: {config_id}")

            return prepared

        except TimeoutError:
            logger.error(f"Bundle preparation timed out for config: {config_id}")
            raise RuntimeError(
                f"Config '{config_id}' bundle preparation timed out. "
                "This may be due to network issues downloading remote dependencies."
            )
        except Exception as e:
            logger.error(f"Bundle preparation failed for config {config_id}: {e}")
            raise RuntimeError(f"Failed to prepare bundle from config: {e}") from e

    async def create_session(
        self,
        config_id: str,
        user_id: str | None = None,
        app_id: str | None = None,
    ) -> Session:
        """Create a new Amplifier session from a config.

        Args:
            config_id: Config identifier to use for this session
            user_id: Optional user identifier (from JWT 'sub' claim)
            app_id: Optional application identifier (from API key)

        Returns:
            Session: The created session

        Raises:
            ValueError: If config not found
            RuntimeError: If session creation fails
        """
        session_id = str(uuid.uuid4())

        # Verify config exists
        config = await self.config_manager.get_config(config_id)
        if not config:
            raise ValueError(f"Config not found: {config_id}")

        # Create metadata
        session_metadata = SessionMetadata(
            config_id=config_id,
        )

        # Load and prepare the bundle from config YAML
        prepared_bundle = await self._get_or_prepare_config_bundle(config_id)

        # Create the actual AmplifierSession
        amplifier_session = await prepared_bundle.create_session(
            session_id=session_id,
            session_cwd=Path.cwd(),
            is_resumed=False,
        )

        # Store the active session
        self._sessions[session_id] = amplifier_session
        logger.info(f"Created AmplifierSession: {session_id}")

        # Store in database with user_id and app_id
        await self.db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=user_id,
            status=SessionStatus.ACTIVE.value,
            created_by_app_id=app_id,
        )

        # Create session object
        session = Session(
            session_id=session_id,
            config_id=config_id,
            status=SessionStatus.ACTIVE,
            metadata=session_metadata,
        )

        logger.info(
            f"Created session: {session_id} from config: {config_id} (user: {user_id}, app: {app_id})"
        )
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        session_data = await self.db.get_session(session_id)
        if not session_data:
            return None

        # Get config_id to build metadata
        config_id = session_data["config_id"]

        return Session(
            session_id=session_data["session_id"],
            config_id=config_id,
            status=SessionStatus(session_data["status"]),
            metadata=SessionMetadata(
                config_id=config_id,
                created_at=session_data["created_at"],
                updated_at=session_data["updated_at"],
                message_count=session_data["message_count"],
            ),
            transcript=session_data["transcript"],
        )

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[Session]:
        """List all sessions."""
        sessions_data = await self.db.list_sessions(limit=limit, offset=offset)
        return [
            Session(
                session_id=s["session_id"],
                config_id=s["config_id"],
                status=SessionStatus(s["status"]),
                metadata=SessionMetadata(
                    config_id=s["config_id"],
                    created_at=s["created_at"],
                    updated_at=s["updated_at"],
                    message_count=s["message_count"],
                ),
            )
            for s in sessions_data
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session = await self.get_session(session_id)
        if not session:
            return False

        # Clean up active session if exists
        if session_id in self._sessions:
            amplifier_session = self._sessions[session_id]
            # Cleanup the amplifier session
            try:
                await amplifier_session.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up amplifier session: {e}")
            del self._sessions[session_id]

        await self.db.delete_session(session_id)
        logger.info(f"Deleted session: {session_id}")
        return True

    async def send_message(
        self, session_id: str, message: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a message to a session and get response."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get the active AmplifierSession
        amplifier_session = self._sessions.get(session_id)
        if not amplifier_session:
            # Try to resume the session if it's not in memory
            logger.info(f"Session {session_id} not in memory, attempting to resume")
            try:
                prepared_bundle = await self._get_or_prepare_config_bundle(session.config_id)

                # Create session with existing transcript
                amplifier_session = await prepared_bundle.create_session(
                    session_id=session_id,
                    session_cwd=Path.cwd(),
                    is_resumed=True,
                )

                # Restore transcript
                if session.transcript:
                    context_manager = amplifier_session.coordinator.get("context")
                    if context_manager and hasattr(context_manager, "set_messages"):
                        await context_manager.set_messages(session.transcript)
                        logger.info(f"Restored {len(session.transcript)} messages from transcript")

                self._sessions[session_id] = amplifier_session

            except Exception as e:
                logger.error(f"Failed to resume session: {e}")
                raise ValueError(f"Could not resume session: {e}") from e

        # Execute the message through amplifier-core
        try:
            response_text = await amplifier_session.execute(message)

            # Get the updated transcript from context manager
            context_manager = amplifier_session.coordinator.get("context")
            if context_manager and hasattr(context_manager, "get_messages"):
                transcript = await context_manager.get_messages()
            else:
                # Fallback: manually build transcript
                transcript = session.transcript + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ]

            # Update database
            await self.db.update_session(
                session_id=session_id,
                transcript=transcript,
                message_count=len([m for m in transcript if m.get("role") == "user"]),
            )

            return {
                "session_id": session_id,
                "response": response_text,
                "metadata": {
                    "config_id": session.config_id,
                },
            }

        except Exception as e:
            logger.error(f"Error executing message: {e}")
            raise RuntimeError(f"Failed to execute message: {e}") from e

    async def resume_session(self, session_id: str) -> Session | None:
        """Resume an existing session."""
        session = await self.get_session(session_id)
        if not session:
            return None

        # Load the session into memory if not already there
        if session_id not in self._sessions:
            try:
                prepared_bundle = await self._get_or_prepare_config_bundle(session.config_id)

                amplifier_session = await prepared_bundle.create_session(
                    session_id=session_id,
                    session_cwd=Path.cwd(),
                    is_resumed=True,
                )

                # Restore transcript
                if session.transcript:
                    context_manager = amplifier_session.coordinator.get("context")
                    if context_manager and hasattr(context_manager, "set_messages"):
                        await context_manager.set_messages(session.transcript)

                self._sessions[session_id] = amplifier_session
                logger.info(f"Resumed session into memory: {session_id}")

            except Exception as e:
                logger.error(f"Failed to resume session: {e}")
                # Return session metadata even if resume failed
                # The next send_message will try again

        return session

    async def cleanup_old_sessions(self) -> int:
        """Clean up old sessions based on max age."""
        return await self.db.cleanup_old_sessions(settings.max_session_age_days)

    async def get_amplifier_session(self, session_id: str) -> Any | None:
        """Get the active AmplifierSession instance (for streaming, etc.)."""
        return self._sessions.get(session_id)

    async def stream_message(
        self, session_id: str, message: str, context: dict[str, Any] | None = None
    ):
        """Stream a message to a session with real-time response events.

        Yields SSE-compatible event dictionaries.
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get or resume the amplifier session
        amplifier_session = self._sessions.get(session_id)
        if not amplifier_session:
            logger.info(f"Session {session_id} not in memory, attempting to resume")
            try:
                prepared_bundle = await self._get_or_prepare_config_bundle(session.config_id)

                amplifier_session = await prepared_bundle.create_session(
                    session_id=session_id,
                    session_cwd=Path.cwd(),
                    is_resumed=True,
                )

                # Restore transcript
                if session.transcript:
                    context_manager = amplifier_session.coordinator.get("context")
                    if context_manager and hasattr(context_manager, "set_messages"):
                        await context_manager.set_messages(session.transcript)

                self._sessions[session_id] = amplifier_session

            except Exception as e:
                logger.error(f"Failed to resume session: {e}")
                raise ValueError(f"Could not resume session: {e}") from e

        # Hook into amplifier-core's display system for streaming
        # We'll capture events from the coordinator's hooks
        events_queue: list[dict[str, Any]] = []

        def capture_event(event_type: str, data: dict[str, Any]) -> None:
            """Capture events for streaming.

            Ensures data is JSON-serializable by converting complex objects to dicts.
            """
            # Make a copy to avoid modifying the original
            safe_data = {}
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    safe_data[key] = value
                elif isinstance(value, (list, dict)):
                    # Lists and dicts need recursive handling, but for now just convert to string if needed
                    try:
                        import json

                        json.dumps(value)  # Test if it's JSON-safe
                        safe_data[key] = value
                    except (TypeError, ValueError):
                        safe_data[key] = str(value)
                else:
                    # Convert complex objects (like Usage, etc.) to dict or string
                    if hasattr(value, "__dict__"):
                        safe_data[key] = {
                            k: v for k, v in value.__dict__.items() if not k.startswith("_")
                        }
                    else:
                        safe_data[key] = str(value)

            events_queue.append({"type": event_type, "data": safe_data})

        # Register temporary hook to capture events
        hooks = amplifier_session.coordinator.hooks

        # Subscribe to key events for streaming
        event_types = [
            "provider:request",
            "provider:response",
            "provider:stream:start",
            "provider:stream:delta",
            "provider:stream:end",
            "tool:call",
            "tool:result",
        ]

        cleanup_handlers = []
        for event_type in event_types:
            handler = hooks.on(event_type, lambda evt, data, et=event_type: capture_event(et, data))
            cleanup_handlers.append((event_type, handler))

        try:
            # Start execution in background
            execute_task = asyncio.create_task(amplifier_session.execute(message))

            # Yield events as they come in
            while not execute_task.done():
                if events_queue:
                    event = events_queue.pop(0)
                    yield event
                await asyncio.sleep(0.05)  # Small delay to batch events

            # Drain remaining events
            while events_queue:
                event = events_queue.pop(0)
                yield event

            # Get the final response
            response_text = await execute_task

            # Yield the final response
            yield {
                "type": "response",
                "content": response_text,
            }

            # Update database with final transcript
            context_manager = amplifier_session.coordinator.get("context")
            if context_manager and hasattr(context_manager, "get_messages"):
                transcript = await context_manager.get_messages()
                await self.db.update_session(
                    session_id=session_id,
                    transcript=transcript,
                    message_count=len([m for m in transcript if m.get("role") == "user"]),
                )

        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            yield {"type": "error", "message": str(e)}
            raise

        finally:
            # Note: HookRegistry doesn't have an 'off' method for cleanup
            # Handlers will be garbage collected when the session ends
            # If needed, we could track handlers and clear them manually
            pass

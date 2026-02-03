"""Session manager that wraps amplifier-core."""

import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

from ..config import settings
from ..models import Session, SessionMetadata, SessionStatus
from ..storage import Database

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Amplifier sessions using amplifier-core."""

    def __init__(self, db: Database):
        """Initialize session manager."""
        self.db = db
        self._sessions: dict[str, Any] = {}  # Active AmplifierSession instances
        self._prepared_bundles: dict[str, Any] = {}  # Cached prepared bundles

        # Add local fork paths to Python path
        self._setup_amplifier_paths()

        # Import after paths are set up
        self._import_amplifier_modules()

    def _setup_amplifier_paths(self) -> None:
        """Add local amplifier-core and amplifier-foundation to Python path."""
        core_path = settings.amplifier_core_path.resolve()
        foundation_path = settings.amplifier_foundation_path.resolve()

        if core_path.exists():
            sys.path.insert(0, str(core_path))
            logger.info(f"Added amplifier-core to path: {core_path}")
        else:
            logger.warning(f"amplifier-core path not found: {core_path}")

        if foundation_path.exists():
            sys.path.insert(0, str(foundation_path))
            logger.info(f"Added amplifier-foundation to path: {foundation_path}")
        else:
            logger.warning(f"amplifier-foundation path not found: {foundation_path}")

    def _import_amplifier_modules(self) -> None:
        """Import amplifier modules after paths are set up."""
        try:
            from amplifier_core import AmplifierSession  # type: ignore[import-not-found]
            from amplifier_foundation import BundleRegistry  # type: ignore[import-not-found]

            self.AmplifierSession = AmplifierSession

            # Create a BundleRegistry for loading bundles
            # Register the local foundation fork so 'foundation' resolves locally
            foundation_path = settings.amplifier_foundation_path.resolve()
            self.registry = BundleRegistry()

            # Register foundation bundle from local fork
            self.registry.register(
                uri=str(foundation_path),
                name="foundation",
                explicitly_requested=True,
            )

            logger.info("Successfully imported amplifier-core and amplifier-foundation")
            logger.info(f"Registered foundation bundle at: {foundation_path}")
        except ImportError as e:
            logger.error(f"Failed to import amplifier modules: {e}")
            raise RuntimeError(
                "Could not import amplifier-core or amplifier-foundation. "
                "Check that local forks are available at configured paths."
            ) from e

    async def _get_or_prepare_bundle(self, bundle_name: str) -> Any:
        """Get or prepare a bundle by name."""
        if bundle_name in self._prepared_bundles:
            logger.info(f"Using cached bundle: {bundle_name}")
            return self._prepared_bundles[bundle_name]

        # Load bundle using the registry
        logger.info(f"Loading bundle via registry: {bundle_name}")

        try:
            # Load through registry
            bundle = await asyncio.wait_for(
                self.registry._load_single(bundle_name, auto_register=True, auto_include=True),
                timeout=60.0,  # Give time for remote bundle downloads
            )
            logger.info(f"Bundle loaded: {bundle.name}")

            logger.info(f"Preparing bundle: {bundle_name}")
            prepared = await asyncio.wait_for(bundle.prepare(), timeout=30.0)
            logger.info(f"Bundle prepared: {bundle_name}")

            # Cache it
            self._prepared_bundles[bundle_name] = prepared
            logger.info(f"Bundle cached: {bundle_name}")

            return prepared

        except TimeoutError:
            logger.error(f"Bundle loading timed out: {bundle_name}")
            raise RuntimeError(
                f"Bundle '{bundle_name}' loading timed out. "
                "This may be due to network issues downloading remote dependencies."
            )
        except Exception as e:
            logger.error(f"Bundle loading failed: {bundle_name}: {e}")
            raise

    async def create_session(
        self,
        bundle: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        config: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Session:
        """Create a new Amplifier session.

        Loads the bundle and creates AmplifierSession immediately.
        """
        session_id = str(uuid.uuid4())
        bundle_name = bundle or "foundation"

        # Create metadata
        session_metadata = SessionMetadata(
            bundle=bundle_name,
            provider=provider,
            model=model,
            tags=metadata or {},
        )

        # Load and prepare the bundle, create AmplifierSession
        prepared_bundle = await self._get_or_prepare_bundle(bundle_name)

        # Create the actual AmplifierSession
        amplifier_session = await prepared_bundle.create_session(
            session_id=session_id,
            session_cwd=Path.cwd(),
            is_resumed=False,
        )

        # Store the active session
        self._sessions[session_id] = amplifier_session
        logger.info(f"Created AmplifierSession: {session_id}")

        # Store in database
        await self.db.create_session(
            session_id=session_id,
            status=SessionStatus.ACTIVE.value,
            bundle=bundle_name,
            provider=provider,
            model=model,
            metadata=session_metadata.model_dump(),
            config=config or {},
        )

        # Create session object
        session = Session(
            session_id=session_id,
            status=SessionStatus.ACTIVE,
            metadata=session_metadata,
            config=config or {},
        )

        logger.info(f"Created session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        session_data = await self.db.get_session(session_id)
        if not session_data:
            return None

        return Session(
            session_id=session_data["session_id"],
            status=SessionStatus(session_data["status"]),
            metadata=SessionMetadata(**session_data["metadata"]),
            transcript=session_data["transcript"],
            config=session_data["config"],
        )

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[Session]:
        """List all sessions."""
        sessions_data = await self.db.list_sessions(limit=limit, offset=offset)
        return [
            Session(
                session_id=s["session_id"],
                status=SessionStatus(s["status"]),
                metadata=SessionMetadata(
                    bundle=s.get("bundle"),
                    provider=s.get("provider"),
                    model=s.get("model"),
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
                bundle_name = session.metadata.bundle or "foundation"
                prepared_bundle = await self._get_or_prepare_bundle(bundle_name)

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
                    "provider": session.metadata.provider,
                    "model": session.metadata.model,
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
                bundle_name = session.metadata.bundle or "foundation"
                prepared_bundle = await self._get_or_prepare_bundle(bundle_name)

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
                bundle_name = session.metadata.bundle or "foundation"
                prepared_bundle = await self._get_or_prepare_bundle(bundle_name)

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
            """Capture events for streaming."""
            events_queue.append({"type": event_type, "data": data})

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
            # Cleanup event handlers
            for event_type, handler in cleanup_handlers:
                hooks.off(event_type, handler)

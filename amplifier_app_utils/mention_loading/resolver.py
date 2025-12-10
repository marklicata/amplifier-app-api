"""Path resolution for @mentions with search path support."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MentionResolver:
    """Resolves @mentions to file paths with explicit prefix handling.

    Mention types supported:
    1. @collection:path - Resolves to collection resources (e.g., @foundation:context/file.md)
    2. @user:path - Shortcut to ~/.amplifier/{path}
    3. @project:path - Shortcut to .amplifier/{path}
    4. @~/path - Resolves to user home directory
    5. @path - Resolves relative to CWD or relative_to parameter

    Missing files are skipped gracefully (returns None).
    """

    def __init__(
        self,
        path_manager=None,
        relative_to: Path | None = None,
    ):
        """Initialize resolver with path manager.

        Args:
            path_manager: PathManager instance (creates default if not provided)
            relative_to: Base path for resolving relative mentions (./file)
        """
        if path_manager is None:
            from ..paths import PathManager
            path_manager = PathManager()
        
        self.path_manager = path_manager
        self.relative_to = relative_to

    def resolve(self, mention: str) -> Path | None:
        """Resolve @mention to file path.

        Mention types:
        1. @collection:path - Collection resources (e.g., @foundation:context/file.md)
           - Tries collection_path / path first (package subdirectory)
           - Falls back to collection_path.parent / path (hybrid packaging)
        2. @user:path - Shortcut to {user_dir}/{path}
        3. @project:path - Shortcut to {project_dir}/{path}
        4. @~/path - User home directory
        5. @path - Relative to CWD or relative_to

        Args:
            mention: @mention string with prefix

        Returns:
            Absolute Path if file exists, None if not found (graceful skip)
        """
        # Collection references (@collection:path)
        # Also handles shortcuts (@user:path, @project:path)
        if ":" in mention[1:] and not mention.startswith("@~/"):
            prefix, path = mention[1:].split(":", 1)

            # Security: Prevent path traversal in path component
            if ".." in path:
                logger.warning(f"Path traversal attempt blocked: {mention}")
                return None

            # Handle shortcuts first
            if prefix == "user":
                user_path = self.path_manager.user_dir / path
                if user_path.exists():
                    return user_path.resolve()
                logger.debug(f"User shortcut path not found: {user_path}")
                return None

            if prefix == "project":
                project_path = Path.cwd() / self.path_manager.project_dir / path
                if project_path.exists():
                    return project_path.resolve()
                logger.debug(f"Project shortcut path not found: {project_path}")
                return None

            # Otherwise: Collection reference
            collection_resolver = self.path_manager.create_collection_resolver()
            collection_path = collection_resolver.resolve(prefix)
            if collection_path:
                resource_path = collection_path / path

                # Try at collection path first (package subdirectory)
                if resource_path.exists():
                    return resource_path.resolve()

                # Hybrid packaging fallback
                if (collection_path / "pyproject.toml").exists():
                    parent_resource_path = collection_path.parent / path
                    if parent_resource_path.exists():
                        logger.debug(f"Collection resource found at parent: {parent_resource_path}")
                        return parent_resource_path.resolve()

                logger.debug(f"Collection resource not found: {resource_path}")
                return None

            # Collection not found
            logger.debug(f"Collection '{prefix}' not found")
            return None

        # @~/ - user home directory
        if mention.startswith("@~/"):
            path_str = mention[3:]  # Remove '@~/'
            home_path = Path.home() / path_str

            if home_path.exists():
                return home_path.resolve()

            logger.debug(f"User home path not found: {home_path}")
            return None

        # Regular @ - CWD or relative_to
        path_str = mention.lstrip("@")

        # Handle relative path syntax
        if path_str.startswith("./") or path_str.startswith("../"):
            return self._resolve_relative(path_str)

        # If relative_to set (agent/profile loading), try that first
        if self.relative_to:
            candidate = self.relative_to / path_str
            if candidate.exists():
                return candidate.resolve()

        # Try CWD (for user prompts)
        candidate = Path.cwd() / path_str
        if candidate.exists():
            return candidate.resolve()

        # Not found - graceful skip
        logger.debug(f"Project path not found: {path_str} (tried relative_to and CWD)")
        return None

    def _resolve_relative(self, path: str) -> Path | None:
        """Resolve relative path mention."""
        if self.relative_to is None:
            return None

        resolved = (self.relative_to / path).resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
        return None

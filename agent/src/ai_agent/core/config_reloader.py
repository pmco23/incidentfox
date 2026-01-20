"""
Configuration hot-reload mechanism.

Polls the config service periodically and reloads configuration when changes are detected.
"""

import asyncio
import os
from collections.abc import Callable

from .config import get_config, reload_config
from .config_service import TeamLevelConfig, get_config_service_client
from .logging import get_logger

logger = get_logger(__name__)


class ConfigReloader:
    """
    Background service that polls config service and reloads on changes.

    Features:
    - Periodic polling with configurable interval
    - Change detection via hash comparison
    - Callback support for config change events
    - Graceful shutdown
    """

    def __init__(self, poll_interval_seconds: int = 300):
        """
        Initialize config reloader.

        Args:
            poll_interval_seconds: How often to check for config changes (default 5min)
        """
        self.poll_interval = poll_interval_seconds
        self.running = False
        self._task: asyncio.Task | None = None
        self._last_config_hash: int | None = None
        self._callbacks: list[Callable[[TeamLevelConfig], None]] = []

        logger.info(
            "config_reloader_initialized", poll_interval_seconds=poll_interval_seconds
        )

    def register_callback(self, callback: Callable[[TeamLevelConfig], None]) -> None:
        """
        Register a callback to be called when config changes.

        Args:
            callback: Function to call with new config
        """
        self._callbacks.append(callback)
        logger.debug("config_callback_registered", callback_name=callback.__name__)

    async def start(self) -> None:
        """Start the config reloader background task."""
        if self.running:
            logger.warning("config_reloader_already_running")
            return

        self.running = True
        self._task = asyncio.create_task(self._reload_loop())
        logger.info("config_reloader_started")

    async def stop(self) -> None:
        """Stop the config reloader gracefully."""
        if not self.running:
            return

        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("config_reloader_stopped")

    async def _reload_loop(self) -> None:
        """Main reload loop that polls for config changes."""
        while self.running:
            try:
                await asyncio.sleep(self.poll_interval)
                await self._check_and_reload()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("config_reload_error", error=str(e), exc_info=True)
                # Continue running despite errors

    async def _check_and_reload(self) -> None:
        """Check if config changed and reload if needed."""
        try:
            config = get_config()

            if not config.use_config_service:
                logger.debug("config_service_disabled_skipping_reload")
                return
            if not os.getenv("INCIDENTFOX_TEAM_TOKEN"):
                logger.debug("shared_runtime_no_process_team_token_skipping_reload")
                return

            # Fetch fresh config from service
            client = get_config_service_client()
            new_team_config = client.fetch_effective_config()

            # Compute hash of new config
            new_hash = hash(new_team_config.model_dump_json())

            # Check if config changed
            if self._last_config_hash is None:
                # First check, just store hash
                self._last_config_hash = new_hash
                logger.debug("config_hash_initialized")
                return

            if new_hash != self._last_config_hash:
                logger.info(
                    "config_change_detected",
                    old_hash=self._last_config_hash,
                    new_hash=new_hash,
                )

                # Reload main config
                reload_config()
                self._last_config_hash = new_hash

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(new_team_config)
                    except Exception as e:
                        logger.error(
                            "config_callback_failed",
                            callback_name=callback.__name__,
                            error=str(e),
                        )

                logger.info("config_reloaded_successfully")
            else:
                logger.debug("no_config_changes_detected")

        except Exception as e:
            logger.error("failed_to_check_config", error=str(e), exc_info=True)


# Global reloader instance
_config_reloader: ConfigReloader | None = None


def get_config_reloader() -> ConfigReloader:
    """Get the global config reloader instance."""
    global _config_reloader
    if _config_reloader is None:
        _config_reloader = ConfigReloader()
    return _config_reloader


def start_config_reloader(poll_interval_seconds: int = 300) -> ConfigReloader:
    """
    Start the config reloader background service.

    Args:
        poll_interval_seconds: How often to check for changes (default 5min)

    Returns:
        ConfigReloader instance

    Example:
        # At application startup
        reloader = start_config_reloader(poll_interval_seconds=300)

        # Register callbacks for config changes
        def on_config_change(new_config):
            print(f"Config changed! New features: {new_config.feature_flags}")

        reloader.register_callback(on_config_change)
    """
    global _config_reloader
    _config_reloader = ConfigReloader(poll_interval_seconds=poll_interval_seconds)

    # Start in background (non-blocking)
    # Use ensure_future() instead of create_task() to handle cases where
    # there's no running event loop yet
    try:
        asyncio.create_task(_config_reloader.start())
    except RuntimeError:
        # No running event loop - schedule it to start when loop runs
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(_config_reloader.start())
        # Start the loop in a background thread
        import threading

        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()

    logger.info("config_reloader_service_started", poll_interval=poll_interval_seconds)
    return _config_reloader


async def stop_config_reloader() -> None:
    """Stop the config reloader service gracefully."""
    reloader = get_config_reloader()
    await reloader.stop()

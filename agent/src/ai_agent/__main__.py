"""
Main entry point for AI Agent system.

Supports multiple modes:
- API server (default) - REST API for invoking agents
- Worker - Background task processor
- CLI - Interactive testing
"""

import argparse
import signal
import sys

from .agents.registry import initialize_all_agents, reload_agents_on_config_change
from .core.config import get_config
from .core.config_reloader import start_config_reloader, stop_config_reloader
from .core.logging import get_logger, setup_logging
from .core.metrics import setup_metrics

logger = None  # Will be initialized after logging setup


def initialize() -> None:
    """Initialize all system components."""
    global logger

    # Load config first.
    # Note: whether to use the IncidentFox config service is controlled by env/config:
    # - USE_CONFIG_SERVICE=true
    # - CONFIG_BASE_URL / INCIDENTFOX_TEAM_TOKEN
    # Do NOT force-enable here; otherwise local dev breaks when tokens are not present.
    config = get_config()  # Use get_config() to ensure global singleton is set

    # Setup logging
    setup_logging(config.logging, service_name="ai-agent")
    logger = get_logger(__name__)

    logger.info(
        "ai_agent_starting",
        environment=config.environment,
        version="1.0.0",
        config_service_enabled=config.use_config_service,
    )

    # Setup metrics
    if config.metrics.enabled:
        setup_metrics(config.metrics)
        logger.info("metrics_enabled", prometheus_port=config.metrics.prometheus_port)

    # Note: We don't need vault.py - all secrets are injected as env vars by ECS
    # from AWS Secrets Manager. The vault abstraction is unnecessary.
    logger.info("secrets_loaded_from_env_vars", source="aws_secrets_manager_via_ecs")

    # Note: MCP initialization is now done per-request in agent factories
    # because in shared-runtime mode we don't have team_config at startup.
    # Each team's custom MCPs are loaded when their agents are created.

    # Initialize all agents with config from config service
    initialize_all_agents()
    logger.info("agents_initialized_from_config_service")

    # Start config reloader if config service is enabled
    # In shared-runtime mode, team-scoped config is resolved per-request (token header),
    # so a single "me/effective" reloader is not meaningful.
    if config.use_config_service and config.team_config is not None:
        reloader = start_config_reloader(poll_interval_seconds=300)  # 5 minutes

        # Register callback to reload agents when config changes
        def on_config_change(new_team_config):
            logger.info(
                "config_changed",
                mcp_servers=new_team_config.mcp_servers,
                feature_flags=new_team_config.feature_flags,
                agents_configured=len(new_team_config.agents),
            )
            # Reload agents with new configuration
            reload_agents_on_config_change()

        reloader.register_callback(on_config_change)
        logger.info("config_reloader_started", interval_seconds=300)

    logger.info("ai_agent_initialized_successfully")


def shutdown() -> None:
    """Graceful shutdown."""
    global logger
    if logger:
        logger.info("ai_agent_shutting_down")

    # Stop config reloader (if it was started). Safe no-op in shared-runtime mode.
    try:
        import asyncio

        asyncio.run(stop_config_reloader())
    except RuntimeError:
        # If we're already inside an event loop (worker mode), caller should stop it.
        pass

    if logger:
        logger.info("ai_agent_shutdown_complete")


def run_api_mode() -> None:
    """Run in API server mode."""
    from .api_server import start_api_server

    logger.info("starting_in_api_mode")

    # Sanic manages its own loop and installs signal handlers.
    # It MUST run in the main thread; running it in a thread causes:
    # ValueError: signal only works in main thread of the main interpreter
    start_api_server()


async def run_worker_mode() -> None:
    """Run in background worker mode."""
    logger.info("starting_in_worker_mode")

    # Keep running and process tasks
    while True:
        import asyncio

        await asyncio.sleep(60)


async def worker_main() -> None:
    """Async entry point for worker mode."""
    import asyncio

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(stop_config_reloader())
        )

    try:
        initialize()
        await run_worker_mode()
    finally:
        await stop_config_reloader()
        shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent System")
    parser.add_argument(
        "--mode",
        choices=["api", "worker"],
        default="api",
        help="Run mode (default: api)",
    )
    args = parser.parse_args()

    try:
        if args.mode == "api":
            # IMPORTANT: Sanic can't be started while an asyncio loop is already running
            # in the same thread ("Cannot run the event loop while another loop is running").
            initialize()
            run_api_mode()
        else:
            import asyncio

            asyncio.run(worker_main())
    except KeyboardInterrupt:
        sys.exit(0)

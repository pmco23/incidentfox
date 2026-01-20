"""
Slack Bolt app for multi-tenant webhook handling.

Integrates Slack Bolt SDK with the existing multi-tenant architecture:
- Signature verification via Bolt (automatic)
- Event handling with async background processing
- Interaction handling for feedback buttons

Note: This does NOT use Bolt's OAuth/installation store since we manage
tokens via Config Service. The signing_secret is shared across all tenants,
but bot tokens are resolved per-team via Config Service lookup.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

if TYPE_CHECKING:
    from incidentfox_orchestrator.clients import (
        AgentApiClient,
        AuditApiClient,
        ConfigServiceClient,
    )


def create_bolt_app() -> AsyncApp:
    """
    Create Slack Bolt async app for webhook handling.

    Uses SLACK_SIGNING_SECRET for signature verification.
    Does not use a bot token here - tokens are resolved per-team
    when processing events via Config Service.
    """
    signing_secret = (os.getenv("SLACK_SIGNING_SECRET") or "").strip()

    app = AsyncApp(
        signing_secret=signing_secret,
        # Don't use a global token - we resolve per-team
        token=None,
        # Process events asynchronously (important for 3s timeout)
        process_before_response=True,
    )

    return app


def create_bolt_handler(app: AsyncApp) -> AsyncSlackRequestHandler:
    """Create FastAPI request handler for the Bolt app."""
    return AsyncSlackRequestHandler(app)


class SlackBoltIntegration:
    """
    Manages Slack Bolt app lifecycle and service client references.

    This class is initialized in the FastAPI lifespan and provides
    access to service clients from within Bolt handlers.
    """

    def __init__(
        self,
        config_service: ConfigServiceClient,
        agent_api: AgentApiClient,
        audit_api: AuditApiClient | None,
    ):
        self.config_service = config_service
        self.agent_api = agent_api
        self.audit_api = audit_api

        self.app = create_bolt_app()
        self.handler = create_bolt_handler(self.app)

        # Register handlers after app is created
        from incidentfox_orchestrator.webhooks.slack_handlers import register_handlers

        register_handlers(self.app, self)

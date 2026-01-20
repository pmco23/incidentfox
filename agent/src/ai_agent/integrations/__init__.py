"""External integrations."""

from .slack_mrkdwn import chunk_mrkdwn, markdown_to_slack_mrkdwn
from .slack_ui import (
    INVESTIGATION_PHASES,
    build_all_phases_modal,
    build_investigation_dashboard,
    build_phase_modal,
)

__all__ = [
    "markdown_to_slack_mrkdwn",
    "chunk_mrkdwn",
    "build_investigation_dashboard",
    "build_phase_modal",
    "build_all_phases_modal",
    "INVESTIGATION_PHASES",
]

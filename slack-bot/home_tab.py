"""
Home Tab view builders for IncidentFox Slack Bot.

Provides the App Home tab UI for managing integrations and viewing status.
"""

from typing import Dict, List, Optional


def build_home_tab_view(
    team_id: str,
    trial_info: Optional[Dict],
    configured_integrations: Dict[str, Dict],
    available_schemas: List[Dict],
    user_is_admin: bool = False,
) -> Dict:
    """
    Build the App Home tab view.

    Args:
        team_id: Slack team ID
        trial_info: Trial status info from config_client
        configured_integrations: Dict of configured integration configs
        available_schemas: List of available integration schemas
        user_is_admin: Whether the user is a workspace admin

    Returns:
        Slack Home tab view object
    """
    blocks = []

    # Header
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "IncidentFox", "emoji": True},
        }
    )

    # Trial/subscription status banner
    if trial_info and not trial_info.get("expired"):
        days = trial_info.get("days_remaining", 0)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":gift: *Free trial active* — {days} days remaining",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Add API Key",
                        "emoji": True,
                    },
                    "action_id": "home_open_api_key_modal",
                },
            }
        )
    elif trial_info and trial_info.get("expired"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: *Trial expired* — Add your API key to continue",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Add API Key",
                        "emoji": True,
                    },
                    "action_id": "home_open_api_key_modal",
                    "style": "primary",
                },
            }
        )

    blocks.append({"type": "divider"})

    # Quick start section
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Quick Start*\n"
                    "Mention `@IncidentFox` in any channel to start investigating.\n"
                    "Share error messages, logs, or alert links for analysis."
                ),
            },
        }
    )

    blocks.append({"type": "divider"})

    # Connected integrations section
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Connected Integrations"},
        }
    )

    if configured_integrations:
        for int_id, config in configured_integrations.items():
            # Find schema for display name
            schema = next((s for s in available_schemas if s.get("id") == int_id), None)
            name = schema.get("name") if schema else int_id.title()

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f":white_check_mark: *{name}*"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit"},
                        "action_id": f"home_edit_integration_{int_id}",
                    },
                }
            )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_No integrations connected yet_"},
            }
        )

    blocks.append({"type": "divider"})

    # Available integrations section
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Available Integrations"},
        }
    )

    # Show unconfigured integrations (prioritize featured, limit to 8)
    unconfigured = [
        s for s in available_schemas if s.get("id") not in configured_integrations
    ]
    featured = [s for s in unconfigured if s.get("featured")]
    non_featured = [s for s in unconfigured if not s.get("featured")]

    # Show featured first, then non-featured, max 8 total
    to_show = featured[:8]
    if len(to_show) < 8:
        to_show.extend(non_featured[: 8 - len(to_show)])

    if to_show:
        for schema in to_show:
            description = schema.get("description", "")
            # Truncate description
            if len(description) > 60:
                description = description[:57] + "..."

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{schema.get('name', schema.get('id'))}*\n{description}",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Connect"},
                        "action_id": f"home_add_integration_{schema.get('id')}",
                        "style": "primary",
                    },
                }
            )
    elif available_schemas and len(configured_integrations) == len(available_schemas):
        # Only show this if there are schemas AND all are connected
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_All available integrations are connected!_",
                },
            }
        )
    else:
        # No schemas available at all
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No integrations available at this time._",
                },
            }
        )

    # Help footer
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        ":bulb: <https://docs.incidentfox.ai|Documentation> • "
                        "<mailto:support@incidentfox.ai|Support>"
                    ),
                }
            ],
        }
    )

    return {"type": "home", "blocks": blocks}

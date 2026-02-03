"""
Home Tab view builders for IncidentFox Slack Bot.

Provides the App Home tab UI for managing integrations and viewing status.
"""

from typing import Dict, List, Optional

from assets_config import get_integration_logo_url
from onboarding import INTEGRATIONS, get_integration_by_id


def build_home_tab_view(
    team_id: str,
    trial_info: Optional[Dict],
    configured_integrations: Dict[str, Dict],
    available_schemas: List[Dict] = None,  # Deprecated - now uses INTEGRATIONS
    user_is_admin: bool = False,
) -> Dict:
    """
    Build the App Home tab view.

    Args:
        team_id: Slack team ID
        trial_info: Trial status info from config_client
        configured_integrations: Dict of configured integration configs
        available_schemas: Deprecated - now uses INTEGRATIONS from onboarding
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
        from assets_config import get_asset_url

        done_url = get_asset_url("done")

        for int_id, config in configured_integrations.items():
            # Get integration info from INTEGRATIONS
            integration = get_integration_by_id(int_id)
            name = integration.get("name") if integration else int_id.title()
            logo_url = get_integration_logo_url(int_id)
            is_enabled = config.get("enabled", True)

            # Status indicator with done.png image for enabled, emoji for disabled
            if is_enabled and done_url:
                # Use context block with done.png image + name
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "image",
                                "image_url": done_url,
                                "alt_text": "configured",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*{name}*",
                            },
                        ],
                    }
                )
            else:
                # Disabled or no done.png - use emoji fallback
                status_emoji = ":white_circle:" if is_enabled else ":white_circle:"
                suffix = "" if is_enabled else " (disabled)"
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"{status_emoji} *{name}*{suffix}",
                            },
                        ],
                    }
                )

            # Add Edit button
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Edit"},
                            "action_id": f"home_edit_integration_{int_id}",
                        }
                    ],
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

    # Available integrations section - use INTEGRATIONS from onboarding
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Available Integrations"},
        }
    )

    # Get active integrations not yet configured
    active_integrations = [
        i
        for i in INTEGRATIONS
        if i.get("status") == "active" and i.get("id") not in configured_integrations
    ]

    if active_integrations:
        for integration in active_integrations:
            int_id = integration["id"]
            name = integration["name"]
            description = integration.get("description", "")
            logo_url = get_integration_logo_url(int_id)

            # Truncate description
            if len(description) > 60:
                description = description[:57] + "..."

            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{name}*\n{description}",
                },
            }

            # Add logo if available
            if logo_url:
                section_block["accessory"] = {
                    "type": "image",
                    "image_url": logo_url,
                    "alt_text": name,
                }
                blocks.append(section_block)
                # Add Connect button in separate actions block
                blocks.append(
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Connect"},
                                "action_id": f"home_add_integration_{int_id}",
                                "style": "primary",
                            }
                        ],
                    }
                )
            else:
                section_block["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Connect"},
                    "action_id": f"home_add_integration_{int_id}",
                    "style": "primary",
                }
                blocks.append(section_block)

        blocks.append({"type": "divider"})
    elif not active_integrations and configured_integrations:
        # All active integrations are connected
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: _All available integrations are connected!_",
                },
            }
        )
        blocks.append({"type": "divider"})

    # Coming Soon section
    coming_soon = [i for i in INTEGRATIONS if i.get("status") == "coming_soon"]
    if coming_soon:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Coming Soon*"},
            }
        )

        # Show coming soon integrations with logos in context blocks
        # Group into rows of 4 integrations
        for i in range(0, len(coming_soon), 4):
            row_integrations = coming_soon[i : i + 4]
            context_elements = []
            for integration in row_integrations:
                int_id = integration["id"]
                name = integration["name"]
                logo_url = get_integration_logo_url(int_id)
                if logo_url:
                    context_elements.append(
                        {
                            "type": "image",
                            "image_url": logo_url,
                            "alt_text": name,
                        }
                    )
                context_elements.append(
                    {
                        "type": "plain_text",
                        "text": name,
                        "emoji": True,
                    }
                )
            if context_elements:
                blocks.append(
                    {
                        "type": "context",
                        "elements": context_elements,
                    }
                )

        blocks.append({"type": "divider"})

    # Advanced Settings section
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":gear: *Advanced Settings* — Configure LLM proxy or bring your own API key",
                }
            ],
        }
    )
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Advanced Settings",
                        "emoji": True,
                    },
                    "action_id": "open_advanced_settings",
                },
            ],
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

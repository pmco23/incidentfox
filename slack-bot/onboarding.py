"""
Onboarding Flow for IncidentFox Slack Bot

Handles:
1. Workspace provisioning when OAuth completes
2. API key setup modal
3. Free trial management
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def build_api_key_modal(
    team_id: str,
    trial_info: Optional[Dict] = None,
    error_message: str = None,
) -> Dict[str, Any]:
    """
    Build the API key setup modal.

    Args:
        team_id: Slack team/workspace ID
        trial_info: Trial status if on free trial
        error_message: Error to display (e.g., invalid API key)

    Returns:
        Slack modal view object
    """
    blocks = []

    # Header section
    if trial_info and not trial_info.get("expired"):
        days = trial_info.get("days_remaining", 0)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rocket: *You're on a free trial!*\n"
                        f"You have *{days} days* remaining. "
                        f"Add your own API key to continue using IncidentFox after the trial."
                    ),
                },
            }
        )
        blocks.append({"type": "divider"})
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":key: *Set up your Anthropic API key*\n\n"
                        "IncidentFox uses Claude to investigate incidents. "
                        "Enter your Anthropic API key below to get started."
                    ),
                },
            }
        )
        blocks.append({"type": "divider"})

    # Error message if any
    if error_message:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Error:* {error_message}",
                },
            }
        )

    # API Key input
    blocks.append(
        {
            "type": "input",
            "block_id": "api_key_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "api_key_input",
                "placeholder": {"type": "plain_text", "text": "sk-ant-api..."},
            },
            "label": {"type": "plain_text", "text": "Anthropic API Key"},
            "hint": {
                "type": "plain_text",
                "text": "Get your API key from console.anthropic.com",
            },
        }
    )

    # Optional API endpoint (for enterprise ML gateways)
    blocks.append(
        {
            "type": "input",
            "block_id": "api_endpoint_block",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "api_endpoint_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": "https://api.anthropic.com (default)",
                },
            },
            "label": {"type": "plain_text", "text": "API Endpoint (Optional)"},
            "hint": {
                "type": "plain_text",
                "text": "Leave blank to use the default Anthropic API. Set this if your company uses an internal ML gateway.",
            },
        }
    )

    # Help text
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        ":lock: Your API key is encrypted and stored securely. "
                        "<https://console.anthropic.com/settings/keys|Get an API key>"
                    ),
                }
            ],
        }
    )

    return {
        "type": "modal",
        "callback_id": "api_key_submission",
        "private_metadata": team_id,  # Store team_id for submission handler
        "title": {"type": "plain_text", "text": "IncidentFox Setup"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def build_setup_required_message(
    trial_info: Optional[Dict] = None,
    show_upgrade: bool = False,
) -> list:
    """
    Build a message prompting user to set up their API key.

    Returns Block Kit blocks for the message.
    """
    blocks = []

    # Determine message based on trial status
    if trial_info and trial_info.get("expired"):
        # Trial expired
        header_text = ":warning: *Your free trial has ended*"
        if show_upgrade:
            body_text = (
                "To continue using IncidentFox, you'll need to:\n"
                "1. Upgrade to a paid subscription\n"
                "2. Add your Anthropic API key\n\n"
                "Click the button below to set up your API key, then upgrade your plan."
            )
        else:
            body_text = (
                "To continue using IncidentFox, please add your Anthropic API key.\n\n"
                "Click the button below to set up your API key."
            )
    elif trial_info and trial_info.get("days_remaining", 0) <= 3:
        # Trial expiring soon
        days = trial_info.get("days_remaining", 0)
        header_text = f":hourglass: *Your free trial expires in {days} days*"
        body_text = (
            "Add your Anthropic API key now to ensure uninterrupted service.\n\n"
            "Click the button below to set up your API key."
        )
    elif not trial_info:
        # No trial, needs setup
        header_text = ":wave: *Welcome to IncidentFox!*"
        body_text = (
            "To get started, you'll need to set up your Anthropic API key.\n\n"
            "IncidentFox uses Claude to help investigate incidents, "
            "analyze logs, and suggest remediations.\n\n"
            "Click the button below to complete setup."
        )
    else:
        # On active trial - shouldn't hit this case but handle it
        return []

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": header_text}})

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body_text}})

    # Build action buttons based on whether upgrade is needed
    action_elements = [
        {
            "type": "button",
            "action_id": "open_api_key_modal",
            "text": {
                "type": "plain_text",
                "text": ":key: Set Up API Key",
                "emoji": True,
            },
            "style": "primary",
        }
    ]

    if show_upgrade:
        action_elements.append(
            {
                "type": "button",
                "action_id": "open_upgrade_page",
                "text": {
                    "type": "plain_text",
                    "text": ":credit_card: View Pricing",
                    "emoji": True,
                },
                "url": "https://incidentfox.ai/pricing",
            }
        )
    else:
        action_elements.append(
            {
                "type": "button",
                "action_id": "dismiss_setup_message",
                "text": {"type": "plain_text", "text": "Later"},
            }
        )

    blocks.append({"type": "actions", "elements": action_elements})

    help_text = ":bulb: Need help? Visit <https://docs.incidentfox.ai|our docs> or contact support."
    if show_upgrade:
        help_text = ":bulb: Questions about pricing? Email us at support@incidentfox.ai"

    blocks.append(
        {"type": "context", "elements": [{"type": "mrkdwn", "text": help_text}]}
    )

    return blocks


def build_setup_complete_message() -> list:
    """Build a message confirming API key was saved successfully."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":white_check_mark: *Setup complete!*\n\n"
                    "Your API key has been saved. You can now mention me in any channel "
                    "to start investigating incidents.\n\n"
                    "Try it out: `@IncidentFox help me investigate this error`"
                ),
            },
        }
    ]


def build_upgrade_required_message(trial_info: Optional[Dict] = None) -> list:
    """
    Build a message prompting user to upgrade their subscription.

    This is shown when trial has expired and they have an API key but no subscription.
    They need to pay for a subscription to continue using the service.
    """
    blocks = []

    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":warning: *Subscription required*"},
        }
    )

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Your free trial has ended. We noticed you've already set up your "
                    "API key - great!\n\n"
                    "To continue using IncidentFox, please upgrade to a paid subscription. "
                    "Your API key will be used once the subscription is active."
                ),
            },
        }
    )

    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "open_upgrade_page",
                    "text": {
                        "type": "plain_text",
                        "text": ":credit_card: Upgrade",
                        "emoji": True,
                    },
                    "style": "primary",
                    "url": "https://calendly.com/d/cxd2-4hb-qgp/30-minute-demo-call-w-incidentfox",
                },
            ],
        }
    )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        ":bulb: Plans start at $X/month. "
                        "Questions? Email us at support@incidentfox.ai"
                    ),
                }
            ],
        }
    )

    return blocks


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validate an Anthropic API key format.

    Returns (is_valid, error_message).
    """
    if not api_key:
        return False, "API key is required"

    api_key = api_key.strip()

    if len(api_key) < 20:
        return False, "API key is too short"

    # Anthropic keys typically start with sk-ant-
    if not (api_key.startswith("sk-ant-") or api_key.startswith("sk-")):
        return False, "Invalid API key format. Anthropic keys start with sk-ant-"

    return True, ""


def build_welcome_message(
    trial_info: Optional[Dict] = None, team_name: str = ""
) -> list:
    """
    Build welcome message sent as DM to installer after OAuth install.

    Args:
        trial_info: Trial status info from config_client
        team_name: Name of the workspace

    Returns:
        Slack Block Kit blocks
    """
    blocks = []

    # Header
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Welcome to IncidentFox!",
                "emoji": True,
            },
        }
    )

    # Trial status banner
    if trial_info and not trial_info.get("expired"):
        days = trial_info.get("days_remaining", 7)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":gift: *Your {days}-day free trial is active!*\n\n"
                        "I'm an AI-powered SRE assistant that helps investigate incidents. "
                        "Mention `@IncidentFox` in any channel with your question, error message, or alert link."
                    ),
                },
            }
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "I'm an AI-powered SRE assistant that helps investigate incidents.\n\n"
                        "Mention `@IncidentFox` in any channel with your question, error message, or alert link."
                    ),
                },
            }
        )

    blocks.append({"type": "divider"})

    # Quick start
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Quick Start*\n"
                    "1. Go to any channel\n"
                    "2. Type `@IncidentFox why is this pod crashing?`\n"
                    "3. Share error messages, logs, or screenshots for context"
                ),
            },
        }
    )

    blocks.append({"type": "divider"})

    # Action buttons
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "open_setup_wizard",
                    "text": {
                        "type": "plain_text",
                        "text": "Set Up Integrations",
                        "emoji": True,
                    },
                    "style": "primary",
                },
                {
                    "type": "button",
                    "action_id": "dismiss_welcome",
                    "text": {"type": "plain_text", "text": "Maybe Later"},
                },
            ],
        }
    )

    # Help footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":bulb: Connect your observability tools (Datadog, CloudWatch, etc.) for richer investigations.",
                }
            ],
        }
    )

    return blocks


def build_dm_welcome_message(trial_info: Optional[Dict] = None) -> list:
    """
    Welcome message shown when a user first opens DM with the app.

    This is different from the installer welcome - this is for any user
    opening the Messages tab for the first time.

    Args:
        trial_info: Trial status info (optional)

    Returns:
        Slack Block Kit blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":wave: *Hi! I'm IncidentFox.*\n\n"
                    "I'm an AI-powered SRE assistant that helps investigate incidents.\n\n"
                    "*How to use me:*\n"
                    "• Mention `@IncidentFox` in any channel with your question\n"
                    "• Share error messages, logs, or alert links\n"
                    "• I'll analyze and help troubleshoot\n\n"
                    "Type `help` anytime for more guidance."
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":bulb: Tip: I work best when you share specific error messages or alert details.",
                }
            ],
        },
    ]


def build_help_message() -> list:
    """
    Help message for DM help command.

    Returns:
        Slack Block Kit blocks
    """
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "IncidentFox Help", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How to investigate incidents:*\n"
                    "1. Go to any channel where an incident is happening\n"
                    "2. Mention `@IncidentFox` with your question\n"
                    "3. Share relevant context (error messages, logs, screenshots)\n\n"
                    "*Example queries:*\n"
                    "• `@IncidentFox why is this pod crashing?`\n"
                    "• `@IncidentFox analyze this error: [paste error]`\n"
                    "• `@IncidentFox what changed in the last hour?`"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Connected integrations:*\n"
                    "Check the *Home* tab to see and manage your connected tools.\n\n"
                    "*Need more help?*\n"
                    "• <https://docs.incidentfox.ai|Documentation>\n"
                    "• <mailto:support@incidentfox.ai|Contact Support>"
                ),
            },
        },
    ]


def build_setup_wizard_page1(
    team_id: str, trial_info: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build page 1 of the setup wizard modal - API key configuration.

    Args:
        team_id: Slack team ID
        trial_info: Trial status info

    Returns:
        Slack modal view object
    """
    import json

    blocks = []

    # Progress indicator
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":one: *API Key*  →  :two: Integrations",
                }
            ],
        }
    )

    blocks.append({"type": "divider"})

    # Trial status / API key options
    has_trial = trial_info and not trial_info.get("expired")

    if has_trial:
        days = trial_info.get("days_remaining", 7)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":gift: *You have {days} days left on your free trial.*\n\n"
                        "You can use the trial API or add your own Anthropic API key."
                    ),
                },
            }
        )

        # Radio buttons for API key choice
        blocks.append(
            {
                "type": "input",
                "block_id": "api_choice_block",
                "element": {
                    "type": "radio_buttons",
                    "action_id": "api_choice_input",
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "Use Trial API (recommended)",
                        },
                        "value": "trial",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Use Trial API (recommended)",
                            },
                            "value": "trial",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Use My Own API Key",
                            },
                            "value": "byok",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "API Key"},
            }
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":key: *Set up your Anthropic API key*\n\n"
                        "IncidentFox uses Claude to investigate incidents. "
                        "Enter your API key below."
                    ),
                },
            }
        )

    # API Key input (optional if trial, required otherwise)
    blocks.append(
        {
            "type": "input",
            "block_id": "api_key_block",
            "optional": has_trial,
            "element": {
                "type": "plain_text_input",
                "action_id": "api_key_input",
                "placeholder": {"type": "plain_text", "text": "sk-ant-api..."},
            },
            "label": {"type": "plain_text", "text": "Anthropic API Key"},
            "hint": {
                "type": "plain_text",
                "text": "Get your API key from console.anthropic.com",
            },
        }
    )

    # Optional API endpoint
    blocks.append(
        {
            "type": "input",
            "block_id": "api_endpoint_block",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "api_endpoint_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": "https://api.anthropic.com (default)",
                },
            },
            "label": {"type": "plain_text", "text": "API Endpoint (Optional)"},
            "hint": {
                "type": "plain_text",
                "text": "Leave blank to use default. Set if using an internal ML gateway.",
            },
        }
    )

    # Help text
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":lock: Your API key is encrypted and stored securely.",
                }
            ],
        }
    )

    # Store metadata for the submission handler
    private_metadata = json.dumps(
        {
            "team_id": team_id,
            "has_trial": has_trial,
        }
    )

    return {
        "type": "modal",
        "callback_id": "setup_wizard_page1",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "IncidentFox Setup"},
        "submit": {"type": "plain_text", "text": "Next"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def build_setup_wizard_page2(
    team_id: str,
    schemas: list,
    configured: dict,
) -> Dict[str, Any]:
    """
    Build page 2 of the setup wizard modal - Integration selection.

    Args:
        team_id: Slack team ID
        schemas: List of integration schemas from config-service
        configured: Dict of already configured integrations

    Returns:
        Slack modal view object
    """
    import json

    blocks = []

    # Progress indicator (step 1 complete)
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: API Key  →  :two: *Integrations*",
                }
            ],
        }
    )

    blocks.append({"type": "divider"})

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Connect your tools* (optional)\n\n"
                    "Add integrations so I can pull logs, metrics, and deployment data "
                    "during investigations."
                ),
            },
        }
    )

    # Group integrations by category
    categories = {}
    for schema in schemas:
        cat = schema.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(schema)

    # Display order for categories
    category_order = ["observability", "cloud", "scm", "incident", "other"]
    category_labels = {
        "observability": ":chart_with_upwards_trend: Observability",
        "cloud": ":cloud: Cloud",
        "scm": ":octocat: Source Control",
        "incident": ":rotating_light: Incident Management",
        "other": ":toolbox: Other",
    }

    for cat in category_order:
        if cat not in categories:
            continue

        cat_schemas = categories[cat]
        if not cat_schemas:
            continue

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{category_labels.get(cat, cat.title())}*",
                },
            }
        )

        # Create buttons for each integration in this category (max 5 per row)
        button_elements = []
        for schema in cat_schemas[:8]:  # Limit to 8 per category
            int_id = schema.get("id")
            name = schema.get("name", int_id)
            is_configured = int_id in configured

            button = {
                "type": "button",
                "action_id": f"configure_integration_{int_id}",
                "text": {
                    "type": "plain_text",
                    "text": f"{'✓ ' if is_configured else ''}{name}",
                    "emoji": True,
                },
            }

            if is_configured:
                button["style"] = "primary"

            button_elements.append(button)

            # Slack allows max 5 buttons per actions block
            if len(button_elements) == 5:
                blocks.append({"type": "actions", "elements": button_elements})
                button_elements = []

        if button_elements:
            blocks.append({"type": "actions", "elements": button_elements})

    # Help text
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":bulb: You can always add more integrations later from the Home tab.",
                }
            ],
        }
    )

    # Store metadata
    private_metadata = json.dumps({"team_id": team_id})

    return {
        "type": "modal",
        "callback_id": "setup_wizard_page2",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "IncidentFox Setup"},
        "submit": {"type": "plain_text", "text": "Done"},
        "close": {"type": "plain_text", "text": "Back"},
        "blocks": blocks,
    }


def build_integration_config_modal(
    team_id: str,
    schema: Dict[str, Any],
    existing_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build a dynamic integration configuration modal based on schema.

    Args:
        team_id: Slack team ID
        schema: Integration schema with fields definition
        existing_config: Existing config values to pre-fill

    Returns:
        Slack modal view object
    """
    import json

    blocks = []
    existing_config = existing_config or {}

    integration_id = schema.get("id", "unknown")
    integration_name = schema.get("name", integration_id.title())
    description = schema.get("description", "")
    docs_url = schema.get("docs_url")

    # Header with integration name
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Configure {integration_name}",
                "emoji": True,
            },
        }
    )

    # Description
    if description:
        desc_text = description
        if docs_url:
            desc_text += f"\n\n<{docs_url}|View documentation>"
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": desc_text},
            }
        )

    blocks.append({"type": "divider"})

    # Track field names for submission handler
    field_names = []

    # Generate form fields from schema
    fields = schema.get("fields", [])
    for field in fields:
        field_id = field.get("id")
        field_name = field.get("name", field_id)
        field_type = field.get("type", "string")
        field_hint = field.get("hint", "")
        field_required = field.get("required", False)
        field_placeholder = field.get("placeholder", "")

        field_names.append(field_id)

        if field_type == "secret":
            # Secret fields: plain text input, don't pre-fill
            blocks.append(
                {
                    "type": "input",
                    "block_id": f"field_{field_id}",
                    "optional": not field_required,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": f"input_{field_id}",
                        "placeholder": {
                            "type": "plain_text",
                            "text": field_placeholder or "Enter value...",
                        },
                    },
                    "label": {"type": "plain_text", "text": field_name},
                    "hint": (
                        {"type": "plain_text", "text": field_hint}
                        if field_hint
                        else None
                    ),
                }
            )
            # Remove hint if None
            if not field_hint:
                del blocks[-1]["hint"]

        elif field_type == "boolean":
            # Boolean fields: checkboxes
            initial_options = []
            if existing_config.get(field_id):
                initial_options = [
                    {
                        "text": {"type": "plain_text", "text": field_name},
                        "value": "true",
                    }
                ]

            blocks.append(
                {
                    "type": "input",
                    "block_id": f"field_{field_id}",
                    "optional": True,
                    "element": {
                        "type": "checkboxes",
                        "action_id": f"input_{field_id}",
                        "options": [
                            {
                                "text": {"type": "plain_text", "text": field_name},
                                "value": "true",
                            }
                        ],
                        "initial_options": initial_options if initial_options else None,
                    },
                    "label": {"type": "plain_text", "text": field_name},
                }
            )
            # Clean up None initial_options
            if not initial_options:
                del blocks[-1]["element"]["initial_options"]

        elif field_type == "select" and field.get("options"):
            # Select fields with predefined options
            options = [
                {"text": {"type": "plain_text", "text": opt}, "value": opt}
                for opt in field.get("options", [])
            ]
            existing_value = existing_config.get(field_id)
            initial_option = None
            if existing_value:
                initial_option = {
                    "text": {"type": "plain_text", "text": existing_value},
                    "value": existing_value,
                }

            element = {
                "type": "static_select",
                "action_id": f"input_{field_id}",
                "placeholder": {
                    "type": "plain_text",
                    "text": field_placeholder or "Select...",
                },
                "options": options,
            }
            if initial_option:
                element["initial_option"] = initial_option

            blocks.append(
                {
                    "type": "input",
                    "block_id": f"field_{field_id}",
                    "optional": not field_required,
                    "element": element,
                    "label": {"type": "plain_text", "text": field_name},
                }
            )

        else:
            # Default: string field (plain text input, can pre-fill)
            existing_value = existing_config.get(field_id, "")
            element = {
                "type": "plain_text_input",
                "action_id": f"input_{field_id}",
                "placeholder": {
                    "type": "plain_text",
                    "text": field_placeholder or "Enter value...",
                },
            }
            if existing_value:
                element["initial_value"] = str(existing_value)

            input_block = {
                "type": "input",
                "block_id": f"field_{field_id}",
                "optional": not field_required,
                "element": element,
                "label": {"type": "plain_text", "text": field_name},
            }
            if field_hint:
                input_block["hint"] = {"type": "plain_text", "text": field_hint}

            blocks.append(input_block)

    # Security note
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":lock: Credentials are encrypted and stored securely.",
                }
            ],
        }
    )

    # Store metadata for submission handler
    private_metadata = json.dumps(
        {
            "team_id": team_id,
            "integration_id": integration_id,
            "field_names": field_names,
        }
    )

    return {
        "type": "modal",
        "callback_id": "integration_config_submission",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": integration_name[:24]},  # Max 24 chars
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }

"""
Asset URLs for IncidentFox Slack Bot

All assets are hosted on S3 with public read access.
This eliminates the need for per-workspace file uploads and
distributed caching of Slack file IDs.
"""

# Base URL for all assets
ASSETS_BASE_URL = "https://incidentfox-assets.s3.us-west-2.amazonaws.com/slack"

# Core UI assets
ASSET_URLS = {
    "loading": f"{ASSETS_BASE_URL}/loading.gif",
    "done": f"{ASSETS_BASE_URL}/done.png",
    "logo": f"{ASSETS_BASE_URL}/logo.png",
}

# Integration logos
INTEGRATION_LOGOS = {
    "coralogix": f"{ASSETS_BASE_URL}/integrations/coralogix.png",
    "incident_io": f"{ASSETS_BASE_URL}/integrations/incident_io.png",
    "datadog": f"{ASSETS_BASE_URL}/integrations/datadog.png",
    "cloudwatch": f"{ASSETS_BASE_URL}/integrations/cloudwatch.png",
    "aws": f"{ASSETS_BASE_URL}/integrations/aws.png",
    "github": f"{ASSETS_BASE_URL}/integrations/github.png",
    "prometheus": f"{ASSETS_BASE_URL}/integrations/prometheus.png",
    "grafana": f"{ASSETS_BASE_URL}/integrations/grafana.png",
    "opsgenie": f"{ASSETS_BASE_URL}/integrations/opsgenie.png",
    "pagerduty": f"{ASSETS_BASE_URL}/integrations/pagerduty.png",
    "kubernetes": f"{ASSETS_BASE_URL}/integrations/kubernetes.png",
}


def get_asset_url(asset_key: str) -> str:
    """Get URL for a core UI asset."""
    return ASSET_URLS.get(asset_key, "")


def get_integration_logo_url(integration_id: str) -> str:
    """Get logo URL for an integration."""
    return INTEGRATION_LOGOS.get(integration_id, "")

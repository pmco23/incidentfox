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

# Integration logos (v3 = reprocessed all icons)
INTEGRATION_LOGOS = {
    # Observability
    "coralogix": f"{ASSETS_BASE_URL}/integrations/coralogix.png?v=3",
    "datadog": f"{ASSETS_BASE_URL}/integrations/datadog.png?v=3",
    "cloudwatch": f"{ASSETS_BASE_URL}/integrations/cloudwatch.png?v=3",
    "prometheus": f"{ASSETS_BASE_URL}/integrations/prometheus.png?v=3",
    "grafana": f"{ASSETS_BASE_URL}/integrations/grafana.png?v=3",
    "splunk": f"{ASSETS_BASE_URL}/integrations/splunk.png?v=3",
    "elasticsearch": f"{ASSETS_BASE_URL}/integrations/elasticsearch.png?v=3",
    "opensearch": f"{ASSETS_BASE_URL}/integrations/opensearch.png?v=3",
    "newrelic": f"{ASSETS_BASE_URL}/integrations/new-relic.png?v=3",
    "new_relic": f"{ASSETS_BASE_URL}/integrations/new-relic.png?v=3",
    "honeycomb": f"{ASSETS_BASE_URL}/integrations/honeycomb.png?v=3",
    "dynatrace": f"{ASSETS_BASE_URL}/integrations/dynatrace.png?v=3",
    "chronosphere": f"{ASSETS_BASE_URL}/integrations/chronosphere.png?v=3",
    "victoriametrics": f"{ASSETS_BASE_URL}/integrations/victoria-metrics.png?v=3",
    "kloudfuse": f"{ASSETS_BASE_URL}/integrations/kloudfuse.png?v=3",
    "sentry": f"{ASSETS_BASE_URL}/integrations/sentry.png?v=3",
    # Incident management
    "incident_io": f"{ASSETS_BASE_URL}/integrations/incident_io.png?v=3",
    "pagerduty": f"{ASSETS_BASE_URL}/integrations/pagerduty.png?v=3",
    "pd": f"{ASSETS_BASE_URL}/integrations/pagerduty.png?v=3",
    "opsgenie": f"{ASSETS_BASE_URL}/integrations/opsgenie.png?v=3",
    # Cloud providers
    "aws": f"{ASSETS_BASE_URL}/integrations/aws.png?v=3",
    "gcp": f"{ASSETS_BASE_URL}/integrations/gcp.png?v=3",
    "azure": f"{ASSETS_BASE_URL}/integrations/azure.png?v=3",
    # Source control & collaboration
    "github": f"{ASSETS_BASE_URL}/integrations/github.png?v=3",
    "jira": f"{ASSETS_BASE_URL}/integrations/jira.png?v=3",
    "linear": f"{ASSETS_BASE_URL}/integrations/linear.png?v=3",
    "notion": f"{ASSETS_BASE_URL}/integrations/notion.png?v=3",
    "glean": f"{ASSETS_BASE_URL}/integrations/glean.png?v=3",
    "servicenow": f"{ASSETS_BASE_URL}/integrations/servicenow.png?v=3",
    # Infrastructure
    "kubernetes": f"{ASSETS_BASE_URL}/integrations/k8s.png?v=3",
    "k8s": f"{ASSETS_BASE_URL}/integrations/k8s.png?v=3",
    "temporal": f"{ASSETS_BASE_URL}/integrations/temporal.png?v=3",
    # Data
    "snowflake": f"{ASSETS_BASE_URL}/integrations/snowflake.png?v=3",
}


def get_asset_url(asset_key: str) -> str:
    """Get URL for a core UI asset."""
    return ASSET_URLS.get(asset_key, "")


def get_integration_logo_url(integration_id: str) -> str:
    """Get logo URL for an integration."""
    return INTEGRATION_LOGOS.get(integration_id, "")

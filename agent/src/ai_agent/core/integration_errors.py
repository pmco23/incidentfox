"""
Integration-specific error classes for better error handling and messaging.
"""


class IntegrationError(Exception):
    """Base class for integration-related errors."""

    def __init__(self, integration_id: str, message: str):
        self.integration_id = integration_id
        self.message = message
        super().__init__(self.format_message())

    def format_message(self) -> str:
        return f"Integration '{self.integration_id}' error: {self.message}"


class IntegrationNotConfiguredError(IntegrationError):
    """Raised when a required integration is not configured."""

    def __init__(
        self,
        integration_id: str,
        tool_id: str = None,
        missing_fields: list[str] = None,
        message: str = None,
    ):
        self.integration_id = integration_id
        self.tool_id = tool_id
        self.missing_fields = missing_fields or []

        if message is None:
            message = self._build_default_message()

        super().__init__(integration_id, message)

    def _build_default_message(self) -> str:
        parts = []

        if self.tool_id:
            parts.append(
                f"Tool '{self.tool_id}' requires '{self.integration_id}' integration"
            )
        else:
            parts.append(f"Integration '{self.integration_id}' is not configured")

        if self.missing_fields:
            parts.append(f"Missing required fields: {', '.join(self.missing_fields)}")
        else:
            parts.append("Integration has not been configured")

        parts.append(
            f"Please configure the integration at /team/settings/integrations/{self.integration_id}"
        )

        return ". ".join(parts)


class IntegrationConnectionError(IntegrationError):
    """Raised when connection to an integration service fails."""

    def __init__(
        self, integration_id: str, status_code: int = None, details: str = None
    ):
        self.status_code = status_code
        self.details = details

        message_parts = ["Failed to connect to service"]
        if status_code:
            message_parts.append(f"(HTTP {status_code})")
        if details:
            message_parts.append(f": {details}")

        super().__init__(integration_id, " ".join(message_parts))


class IntegrationAuthenticationError(IntegrationError):
    """Raised when authentication with an integration service fails."""

    def __init__(self, integration_id: str, details: str = None):
        message = "Authentication failed"
        if details:
            message += f": {details}"
        message += ". Please check your API credentials."

        super().__init__(integration_id, message)

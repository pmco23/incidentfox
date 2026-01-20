"""
API authentication middleware.

Supports:
- API keys (for programmatic access)
- Bearer tokens (for service-to-service)
- Optional authentication (configurable)
"""

import os

import httpx
from sanic.request import Request

from .config import get_config
from .logging import get_logger

logger = get_logger(__name__)


def _validate_token(token: str) -> bool:
    """
    Validate bearer token against config service.

    Args:
        token: Bearer token to validate

    Returns:
        True if token is valid, False otherwise
    """
    config_service_url = os.getenv(
        "CONFIG_SERVICE_URL", "http://incidentfox-config-service:8080"
    )

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{config_service_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                identity = resp.json()
                logger.debug(
                    "token_validated",
                    role=identity.get("role"),
                    org_id=identity.get("org_id"),
                )
                return True
            else:
                logger.debug("token_validation_failed", status=resp.status_code)
                return False
    except Exception as e:
        logger.warning("token_validation_error", error=str(e))
        # In case of network errors, fail open for now to avoid breaking service
        # In production, consider failing closed
        return True


class AuthError(Exception):
    """Authentication error."""

    pass


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key.

    Args:
        api_key: API key to validate

    Returns:
        True if valid
    """
    # Get valid API keys from environment
    valid_keys = os.getenv("API_KEYS", "").split(",")
    valid_keys = [k.strip() for k in valid_keys if k.strip()]

    if not valid_keys:
        # If no API keys configured, allow all (development mode)
        logger.debug("no_api_keys_configured_allowing_all")
        return True

    return api_key in valid_keys


def authenticate_request(request: Request) -> dict | None:
    """
    Authenticate incoming request.

    Args:
        request: Sanic request object

    Returns:
        Authentication context or None if invalid

    Raises:
        AuthError: If authentication fails
    """
    config = get_config()

    # Check if auth is required
    auth_required = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

    if not auth_required and config.environment == "development":
        logger.debug("auth_not_required_in_dev")
        return {"user": "dev", "authenticated": False}

    # Check for API key in header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if validate_api_key(api_key):
            logger.debug("authenticated_via_api_key")
            return {"user": "api_key_user", "authenticated": True, "method": "api_key"}
        else:
            raise AuthError("Invalid API key")

    # Check for Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Validate token against config service
        if _validate_token(token):
            logger.debug("authenticated_via_bearer_token")
            return {"user": "token_user", "authenticated": True, "method": "bearer"}
        else:
            logger.warning("invalid_bearer_token")
            raise AuthError("Invalid bearer token")

    # No authentication provided
    if auth_required:
        raise AuthError("Authentication required")

    # Auth not required, allow
    return {"user": "anonymous", "authenticated": False}

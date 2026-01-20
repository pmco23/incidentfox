"""
Vault integration for fetching secrets.

Supports multiple vault backends:
- HashiCorp Vault
- AWS Secrets Manager
- Direct env vars (for development)
"""

from abc import abstractmethod
from typing import Protocol

from .errors import ConfigurationError
from .logging import get_logger

logger = get_logger(__name__)


class VaultClient(Protocol):
    """Protocol for vault clients."""

    @abstractmethod
    def get_secret(self, path: str) -> str:
        """
        Fetch a secret from the vault.

        Args:
            path: Vault path (e.g., "vault://incidentfox/prod/openai")

        Returns:
            Secret value

        Raises:
            ConfigurationError: If secret cannot be fetched
        """
        ...


class EnvVarVault:
    """
    Development vault that reads from environment variables.

    Converts vault paths to env var names:
    vault://incidentfox/prod/openai -> VAULT_INCIDENTFOX_PROD_OPENAI
    """

    def get_secret(self, path: str) -> str:
        """Fetch secret from environment variable."""
        if not path.startswith("vault://"):
            raise ConfigurationError(f"Invalid vault path: {path}")

        # Convert path to env var name
        # vault://incidentfox/prod/openai -> VAULT_INCIDENTFOX_PROD_OPENAI
        env_key = "VAULT_" + path[8:].replace("/", "_").upper()

        import os

        value = os.getenv(env_key)
        if value is None:
            raise ConfigurationError(f"Secret not found in env: {env_key}")

        logger.debug("secret_fetched_from_env", path=path)
        return value


class AWSSecretsManagerVault:
    """Vault client that uses AWS Secrets Manager."""

    def __init__(
        self,
        region: str = "us-east-1",
        vault_secret_name: str = "ai-agent-vault-secrets-production",
    ):
        """
        Initialize AWS Secrets Manager client.

        Args:
            region: AWS region
            vault_secret_name: Name of the secret containing all vault paths
        """

        import boto3

        self.client = boto3.client("secretsmanager", region_name=region)
        self.vault_secret_name = vault_secret_name
        self._cache: dict = {}
        self._load_vault_secrets()

    def _load_vault_secrets(self) -> None:
        """Load all vault secrets from AWS Secrets Manager into cache."""
        try:
            response = self.client.get_secret_value(SecretId=self.vault_secret_name)
            import json

            self._cache = json.loads(response["SecretString"])
            logger.info(
                "vault_secrets_loaded",
                secret_name=self.vault_secret_name,
                keys_loaded=len(self._cache),
            )
        except self.client.exceptions.ResourceNotFoundException:
            logger.warning("vault_secret_not_found", secret_name=self.vault_secret_name)
            self._cache = {}
        except Exception as e:
            logger.error("failed_to_load_vault_secrets", error=str(e))
            self._cache = {}

    def get_secret(self, path: str) -> str:
        """
        Fetch secret from AWS Secrets Manager.

        Args:
            path: Vault path like "vault://incidentfox/prod/openai"

        Returns:
            Secret value
        """
        if not path.startswith("vault://"):
            raise ConfigurationError(f"Invalid vault path: {path}")

        # Extract key from path
        # vault://incidentfox/prod/openai -> incidentfox/prod/openai
        key = path[8:]

        if key in self._cache:
            logger.debug("secret_fetched_from_cache", path=path)
            return self._cache[key]

        # Try to reload secrets in case they were added
        self._load_vault_secrets()

        if key in self._cache:
            logger.info("secret_fetched_after_reload", path=path)
            return self._cache[key]

        raise ConfigurationError(f"Secret not found in vault: {key}")


class HashiCorpVault:
    """Vault client for HashiCorp Vault (placeholder for future implementation)."""

    def __init__(self, url: str, token: str):
        """Initialize HashiCorp Vault client."""
        self.url = url
        self.token = token
        # Implementation would use hvac library
        raise NotImplementedError("HashiCorp Vault not yet implemented")

    def get_secret(self, path: str) -> str:
        """Fetch secret from HashiCorp Vault."""
        raise NotImplementedError()


# Global vault client
_vault_client: VaultClient | None = None


def get_vault_client() -> VaultClient:
    """Get or create the global vault client."""
    global _vault_client
    if _vault_client is None:
        # Default to env var vault for development
        _vault_client = EnvVarVault()
        logger.info("vault_client_initialized", backend="env_vars")
    return _vault_client


def set_vault_client(client: VaultClient) -> None:
    """Set the global vault client."""
    global _vault_client
    _vault_client = client
    logger.info("vault_client_set", backend=type(client).__name__)


def resolve_vault_path(vault_path: str) -> str:
    """
    Resolve a vault path to the actual secret value.

    Args:
        vault_path: Path like "vault://incidentfox/prod/openai"

    Returns:
        Secret value

    Example:
        >>> api_key = resolve_vault_path("vault://incidentfox/prod/openai")
    """
    client = get_vault_client()
    return client.get_secret(vault_path)


def initialize_vault(backend: str = "env", **kwargs) -> VaultClient:
    """
    Initialize vault client with specified backend.

    Args:
        backend: "env", "aws_secrets", or "hashicorp"
        **kwargs: Backend-specific configuration

    Returns:
        Initialized vault client

    Example:
        # For development
        initialize_vault("env")

        # For production with AWS
        initialize_vault("aws_secrets", region="us-east-1")
    """
    if backend == "env":
        client = EnvVarVault()
    elif backend == "aws_secrets":
        client = AWSSecretsManagerVault(region=kwargs.get("region", "us-east-1"))
    elif backend == "hashicorp":
        client = HashiCorpVault(url=kwargs["url"], token=kwargs["token"])
    else:
        raise ValueError(f"Unknown vault backend: {backend}")

    set_vault_client(client)
    logger.info("vault_initialized", backend=backend)
    return client

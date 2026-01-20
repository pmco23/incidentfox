"""Pytest configuration and fixtures."""

import os
from unittest.mock import patch

import pytest

# Set test environment variables
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    from ai_agent.core.config import Config, OpenAIConfig

    config = Config(
        environment="test",
        debug=True,
        openai=OpenAIConfig(api_key="test-key"),
    )

    with patch("ai_agent.core.config.get_config", return_value=config):
        yield config


@pytest.fixture
def mock_metrics():
    """Mock metrics collector."""
    from unittest.mock import Mock

    metrics = Mock()
    metrics.record_agent_request = Mock()
    metrics.record_tool_call = Mock()
    metrics.record_error = Mock()

    with patch("ai_agent.core.metrics.get_metrics_collector", return_value=metrics):
        yield metrics

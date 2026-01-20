"""Unit tests for webhook signature verification."""

import hashlib
import hmac
import time

import pytest
from incidentfox_orchestrator.webhooks.signatures import (
    SignatureVerificationError,
    verify_github_signature,
    verify_incidentio_signature,
    verify_pagerduty_signature,
    verify_slack_signature,
)


class TestSlackSignature:
    """Tests for Slack signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        secret = "test-signing-secret"
        timestamp = str(int(time.time()))
        body = '{"type": "event_callback", "event": {"type": "app_mention"}}'

        # Compute valid signature
        base_string = f"v0:{timestamp}:{body}"
        digest = hmac.new(
            secret.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = f"v0={digest}"

        # Should not raise
        verify_slack_signature(
            signing_secret=secret,
            timestamp=timestamp,
            signature=signature,
            raw_body=body,
        )

    def test_missing_signing_secret(self):
        """Missing signing secret should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_slack_signature(
                signing_secret="",
                timestamp="1234567890",
                signature="v0=abc123",
                raw_body="{}",
            )
        assert exc.value.reason == "missing_signing_secret"
        assert exc.value.service == "slack"

    def test_missing_timestamp(self):
        """Missing timestamp should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_slack_signature(
                signing_secret="secret",
                timestamp=None,
                signature="v0=abc123",
                raw_body="{}",
            )
        assert exc.value.reason == "missing_timestamp_header"

    def test_missing_signature(self):
        """Missing signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_slack_signature(
                signing_secret="secret",
                timestamp="1234567890",
                signature=None,
                raw_body="{}",
            )
        assert exc.value.reason == "missing_signature_header"

    def test_stale_timestamp(self):
        """Stale timestamp should raise error."""
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago

        with pytest.raises(SignatureVerificationError) as exc:
            verify_slack_signature(
                signing_secret="secret",
                timestamp=old_timestamp,
                signature="v0=abc123",
                raw_body="{}",
            )
        assert "stale_timestamp" in exc.value.reason

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_slack_signature(
                signing_secret="secret",
                timestamp=str(int(time.time())),
                signature="v0=invalid",
                raw_body="{}",
            )
        assert exc.value.reason == "bad_signature"


class TestGitHubSignature:
    """Tests for GitHub signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        secret = "test-webhook-secret"
        body = '{"action": "opened", "pull_request": {}}'

        # Compute valid signature
        digest = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = f"sha256={digest}"

        # Should not raise
        verify_github_signature(
            webhook_secret=secret,
            signature=signature,
            raw_body=body,
        )

    def test_missing_secret(self):
        """Missing secret should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_github_signature(
                webhook_secret="",
                signature="sha256=abc123",
                raw_body="{}",
            )
        assert exc.value.reason == "missing_webhook_secret"

    def test_missing_signature(self):
        """Missing signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_github_signature(
                webhook_secret="secret",
                signature=None,
                raw_body="{}",
            )
        assert exc.value.reason == "missing_signature_header"

    def test_invalid_format(self):
        """Invalid signature format should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_github_signature(
                webhook_secret="secret",
                signature="sha1=abc123",  # Wrong prefix
                raw_body="{}",
            )
        assert exc.value.reason == "invalid_signature_format"

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_github_signature(
                webhook_secret="secret",
                signature="sha256=invalid",
                raw_body="{}",
            )
        assert exc.value.reason == "bad_signature"


class TestPagerDutySignature:
    """Tests for PagerDuty signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        secret = "test-webhook-secret"
        body = '{"messages": []}'

        # Compute valid signature
        digest = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = f"v1={digest}"

        # Should not raise
        verify_pagerduty_signature(
            webhook_secret=secret,
            signature=signature,
            raw_body=body,
        )

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_pagerduty_signature(
                webhook_secret="secret",
                signature="v1=invalid",
                raw_body="{}",
            )
        assert exc.value.reason == "bad_signature"


class TestIncidentioSignature:
    """Tests for Incident.io signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        secret = "test-webhook-secret"
        body = '{"incident": {}}'

        # Compute valid signature
        digest = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Should not raise
        verify_incidentio_signature(
            webhook_secret=secret,
            signature=digest,
            raw_body=body,
        )

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        with pytest.raises(SignatureVerificationError) as exc:
            verify_incidentio_signature(
                webhook_secret="secret",
                signature="invalid",
                raw_body="{}",
            )
        assert exc.value.reason == "bad_signature"

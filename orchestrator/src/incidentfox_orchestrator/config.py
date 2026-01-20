from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_url: str
    config_service_url: str
    ai_pipeline_api_url: str
    agent_api_url: str
    telemetry_collector_url: str | None = (
        None  # Optional: for license quota enforcement
    )
    correlation_service_url: str | None = (
        None  # Optional: for alert correlation (feature-flagged)
    )


def load_settings() -> Settings:
    # DB: allow either DATABASE_URL or DB_HOST/DB_* (aligns with other services).
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        host = (os.getenv("DB_HOST") or "").strip()
        port = int(os.getenv("DB_PORT", "5432"))
        name = (os.getenv("DB_NAME") or "").strip()
        # Prefer DB_USERNAME (matches config_service), but accept DB_USER for backwards compatibility.
        user = (os.getenv("DB_USERNAME") or os.getenv("DB_USER") or "").strip()
        password = os.getenv("DB_PASSWORD") or ""
        if host and name and user:
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"

    if not db_url:
        raise RuntimeError(
            "DATABASE_URL (or DB_HOST/DB_NAME/DB_USER/DB_PASSWORD) must be set"
        )

    config_service_url = (
        os.getenv("CONFIG_SERVICE_URL") or os.getenv("CONFIG_BASE_URL") or ""
    ).strip()
    if not config_service_url:
        raise RuntimeError(
            "CONFIG_SERVICE_URL must be set (base URL for config_service)"
        )

    ai_pipeline_api_url = (os.getenv("AI_PIPELINE_API_URL") or "").strip()
    if not ai_pipeline_api_url:
        raise RuntimeError(
            "AI_PIPELINE_API_URL must be set (base URL for ai_pipeline HTTP API)"
        )

    agent_api_url = (os.getenv("AGENT_API_URL") or "").strip()
    if not agent_api_url:
        raise RuntimeError("AGENT_API_URL must be set (base URL for agent HTTP API)")

    # Optional: telemetry collector URL (for license quota enforcement)
    telemetry_collector_url = (
        os.getenv("TELEMETRY_COLLECTOR_URL") or ""
    ).strip() or None

    # Optional: correlation service URL (for alert correlation, feature-flagged)
    correlation_service_url = (
        os.getenv("CORRELATION_SERVICE_URL") or ""
    ).strip() or None

    return Settings(
        db_url=db_url,
        config_service_url=config_service_url,
        ai_pipeline_api_url=ai_pipeline_api_url,
        agent_api_url=agent_api_url,
        telemetry_collector_url=telemetry_collector_url,
        correlation_service_url=correlation_service_url,
    )

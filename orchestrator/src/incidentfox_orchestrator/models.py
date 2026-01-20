from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, Index, String, Uuid
from sqlalchemy import text as sql_text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ProvisioningRun(Base):
    __tablename__ = "orchestrator_provisioning_runs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(128), nullable=False, index=True)
    team_node_id = Column(String(128), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    status = Column(
        String(32), nullable=False, index=True, server_default=sql_text("'running'")
    )

    # NOTE: keep this portable (sqlite for tests/dev). DB-level default is handled in db_migrate for Postgres.
    steps = Column(JSON, nullable=False, default=dict)
    error = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        # Best-effort idempotency: within a team, an idempotency key should map to a single run.
        Index(
            "ux_orch_provision_idempotency",
            "org_id",
            "team_node_id",
            "idempotency_key",
            unique=True,
        ),
    )

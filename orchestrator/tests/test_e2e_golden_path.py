from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from urllib.parse import urlparse

from e2e_apps import make_stub_agent_app, make_stub_pipeline_app
from fastapi.testclient import TestClient
from incidentfox_orchestrator.api_server import create_app as create_orchestrator_app
from incidentfox_orchestrator.clients import (
    AgentApiClient,
    ConfigServiceClient,
    PipelineApiClient,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class _UrlStrippingClient:
    """
    Adapter that lets orchestrator's httpx-based clients call into FastAPI TestClient.
    It accepts absolute URLs (http://host/path) and forwards only the path+query.
    """

    def __init__(self, tc: TestClient):
        self._tc = tc

    def _path(self, url: str) -> str:
        u = urlparse(url)
        p = u.path or "/"
        if u.query:
            p = f"{p}?{u.query}"
        return p

    def get(self, url: str, headers: dict | None = None):
        return self._tc.get(self._path(url), headers=headers)

    def post(self, url: str, headers: dict | None = None, json: dict | None = None):
        return self._tc.post(self._path(url), headers=headers, json=json)

    def put(self, url: str, headers: dict | None = None, json: dict | None = None):
        return self._tc.put(self._path(url), headers=headers, json=json)


def _make_config_service_app(monkeypatch: pytest.MonkeyPatch):
    # Import config_service app factory (module name is `src.*`)
    from src.api.main import create_app as create_config_service_app
    from src.api.routes import admin as admin_routes
    from src.api.routes import auth_me, config_me
    from src.db.base import Base
    from src.db.models import NodeConfig, NodeType, OrgNode

    # DB (sqlite in-memory)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    # Auth + impersonation
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("ADMIN_AUTH_MODE", "token")
    monkeypatch.setenv("TEAM_AUTH_MODE", "token")
    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("IMPERSONATION_JWT_SECRET", "impersonation-secret")
    monkeypatch.setenv("IMPERSONATION_JWT_AUDIENCE", "incidentfox-agent-runtime")

    # Seed org/team + config
    with SessionLocal() as s:
        s.add(
            OrgNode(
                org_id="org1",
                node_id="root",
                parent_id=None,
                node_type=NodeType.org,
                name="Root",
            )
        )
        s.add(
            OrgNode(
                org_id="org1",
                node_id="teamA",
                parent_id="root",
                node_type=NodeType.team,
                name="Team A",
            )
        )
        s.add(
            NodeConfig(
                org_id="org1",
                node_id="root",
                config_json={"knowledge_source": {"grafana": ["org"]}},
                version=1,
            )
        )
        s.add(
            NodeConfig(
                org_id="org1",
                node_id="teamA",
                config_json={"knowledge_source": {"confluence": ["team"]}},
                version=1,
            )
        )
        s.commit()

    def override_get_db():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app = create_config_service_app()
    app.dependency_overrides[admin_routes.get_db] = override_get_db
    app.dependency_overrides[config_me.get_db] = override_get_db
    app.dependency_overrides[auth_me.get_db] = override_get_db
    return app


@pytest.fixture()
def e2e_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # ---- config_service app + in-process client
    config_app = _make_config_service_app(monkeypatch)
    config_tc = TestClient(config_app)

    # ---- stub pipeline app + client
    pipeline_app = make_stub_pipeline_app()
    pipeline_tc = TestClient(pipeline_app)

    # ---- stub agent app + client
    def get_effective_config(team_token: str):
        r = config_tc.get(
            "/api/v1/config/me/effective",
            headers={"Authorization": f"Bearer {team_token}"},
        )
        r.raise_for_status()
        return r.json()

    agent_app = make_stub_agent_app(get_effective_config=get_effective_config)
    agent_tc = TestClient(agent_app)

    # ---- orchestrator app + TestClient, wired to use injected clients
    db_path = tmp_path / "orch-e2e.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("CONFIG_SERVICE_URL", "http://config")
    monkeypatch.setenv("AI_PIPELINE_API_URL", "http://pipeline")
    monkeypatch.setenv("AGENT_API_URL", "http://agent")
    monkeypatch.setenv("ORCHESTRATOR_AUTO_CREATE_TABLES", "1")
    monkeypatch.setenv("ORCHESTRATOR_DISABLE_ADVISORY_LOCKS", "1")

    orch_app = create_orchestrator_app()
    orch_client = TestClient(orch_app)
    with config_tc, pipeline_tc, agent_tc, orch_client:
        orch_app.state.config_service = ConfigServiceClient(base_url="http://config", http_client=_UrlStrippingClient(config_tc))  # type: ignore[arg-type]
        orch_app.state.pipeline_api = PipelineApiClient(base_url="http://pipeline", http_client=_UrlStrippingClient(pipeline_tc))  # type: ignore[arg-type]
        orch_app.state.agent_api = AgentApiClient(base_url="http://agent", http_client=_UrlStrippingClient(agent_tc))  # type: ignore[arg-type]
        yield orch_client


def test_e2e_orchestrator_agent_run_uses_impersonation_jwt(e2e_clients: TestClient):
    # Orchestrator mints impersonation JWT via config_service admin endpoint, then calls agent stub with it.
    r = e2e_clients.post(
        "/api/v1/admin/agents/run",
        headers={"Authorization": "Bearer admin-secret"},
        json={
            "org_id": "org1",
            "team_node_id": "teamA",
            "agent_name": "triage",
            "message": "hello",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team_node_id"] == "teamA"
    assert body["agent_name"] == "triage"
    eff = body["agent_result"]["effective_config"]
    assert eff["knowledge_source"]["grafana"] == ["org"]
    assert eff["knowledge_source"]["confluence"] == ["team"]

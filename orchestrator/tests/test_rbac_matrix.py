import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from incidentfox_orchestrator.api_server import create_app


class PermConfigService:
    def __init__(self, perms: list[str]):
        self._perms = perms

    def auth_me_admin(self, raw_token: str) -> dict:
        return {
            "role": "admin",
            "permissions": list(self._perms),
            "subject": "admin",
            "email": None,
        }

    def issue_team_impersonation_token(
        self, raw_token: str, org_id: str, team_node_id: str
    ) -> dict:
        return {"token": "imp.jwt.token"}

    def list_team_tokens(self, raw_token: str, org_id: str, team_node_id: str):
        return []

    def issue_team_token(self, raw_token: str, org_id: str, team_node_id: str) -> str:
        return "tokid.toksecret"

    def patch_node_config(
        self, raw_token: str, org_id: str, node_id: str, patch: dict
    ) -> dict:
        return {"ok": True}


class DummyPipeline:
    def bootstrap(self, raw_token: str, team_id: str) -> dict:
        return {"run_id": f"bootstrap:{team_id}"}


class DummyAgent:
    def run_agent(
        self,
        *,
        team_token: str,
        agent_name: str,
        message: str,
        context=None,
        timeout=None,
    ) -> dict:
        return {"ok": True}


def test_rbac_requires_agent_run_permission(tmp_path, monkeypatch):
    db_path = tmp_path / "orch-rbac.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("CONFIG_SERVICE_URL", "http://config")
    monkeypatch.setenv("AI_PIPELINE_API_URL", "http://pipeline")
    monkeypatch.setenv("AGENT_API_URL", "http://agent")
    monkeypatch.setenv("ORCHESTRATOR_AUTO_CREATE_TABLES", "1")
    monkeypatch.setenv("ORCHESTRATOR_DISABLE_ADVISORY_LOCKS", "1")
    monkeypatch.setenv("ORCHESTRATOR_REQUIRE_ADMIN_STAR", "0")
    monkeypatch.setenv("ORCHESTRATOR_REQUIRED_PERMISSION_AGENT_RUN", "admin:agent:run")

    app = create_app()
    c = TestClient(app)
    with c:
        app.state.config_service = PermConfigService(["admin:read"])
        app.state.pipeline_api = DummyPipeline()
        app.state.agent_api = DummyAgent()

        r = c.post(
            "/api/v1/admin/agents/run",
            headers={"Authorization": "Bearer admin"},
            json={
                "org_id": "org1",
                "team_node_id": "teamA",
                "agent_name": "triage",
                "message": "hi",
            },
        )
        assert r.status_code == 403


def test_rbac_requires_provision_permissions(tmp_path, monkeypatch):
    db_path = tmp_path / "orch-rbac2.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("CONFIG_SERVICE_URL", "http://config")
    monkeypatch.setenv("AI_PIPELINE_API_URL", "http://pipeline")
    monkeypatch.setenv("AGENT_API_URL", "http://agent")
    monkeypatch.setenv("ORCHESTRATOR_AUTO_CREATE_TABLES", "1")
    monkeypatch.setenv("ORCHESTRATOR_DISABLE_ADVISORY_LOCKS", "1")
    monkeypatch.setenv("ORCHESTRATOR_REQUIRE_ADMIN_STAR", "0")
    monkeypatch.setenv(
        "ORCHESTRATOR_REQUIRED_PERMISSION_PROVISION_TEAM", "admin:provision"
    )
    monkeypatch.setenv(
        "ORCHESTRATOR_REQUIRED_PERMISSION_PROVISION_READ", "admin:provision:read"
    )

    app = create_app()
    c = TestClient(app)
    with c:
        # No provision perms
        app.state.config_service = PermConfigService(["admin:read"])
        app.state.pipeline_api = DummyPipeline()
        app.state.agent_api = DummyAgent()

        r = c.post(
            "/api/v1/admin/provision/team",
            headers={"Authorization": "Bearer admin"},
            json={
                "org_id": "org1",
                "team_node_id": "teamA",
                "slack_channel_ids": [],
                "idempotency_key": "k",
            },
        )
        assert r.status_code == 403

        # Now allow provision
        app.state.config_service = PermConfigService(["admin:provision"])
        r2 = c.post(
            "/api/v1/admin/provision/team",
            # Use a different token value to avoid hitting orchestrator's admin auth cache.
            headers={"Authorization": "Bearer admin2"},
            json={
                "org_id": "org1",
                "team_node_id": "teamA",
                "slack_channel_ids": [],
                "idempotency_key": "k2",
            },
        )
        assert r2.status_code == 200

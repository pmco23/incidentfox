from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from incidentfox_orchestrator.api_server import create_app


class FakeConfigService:
    def auth_me_admin(self, raw_token: str) -> dict:
        return {
            "role": "admin",
            "permissions": ["admin:*"],
            "subject": "admin",
            "email": None,
        }

    def patch_node_config(
        self, raw_token: str, org_id: str, node_id: str, patch: dict
    ) -> dict:
        return {"ok": True}

    def list_team_tokens(
        self, raw_token: str, org_id: str, team_node_id: str
    ) -> list[dict]:
        return []

    def issue_team_token(self, raw_token: str, org_id: str, team_node_id: str) -> str:
        return "tokid.toksecret"

    def issue_team_impersonation_token(
        self, raw_token: str, org_id: str, team_node_id: str
    ) -> dict:
        return {"token": "imp.jwt.token", "expires_at": "2099-01-01T00:00:00Z"}


class FakePipelineApi:
    def bootstrap(self, raw_token: str, team_id: str) -> dict:
        return {"run_id": f"bootstrap:{team_id}"}


class FakeAgentApi:
    def run_agent(
        self,
        *,
        team_token: str,
        agent_name: str,
        message: str,
        context=None,
        timeout=None,
    ) -> dict:
        return {"ok": True, "agent_name": agent_name}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "orch-test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("CONFIG_SERVICE_URL", "http://config-service.invalid")
    monkeypatch.setenv("AI_PIPELINE_API_URL", "http://ai-pipeline.invalid")
    monkeypatch.setenv("AGENT_API_URL", "http://agent.invalid")
    monkeypatch.setenv("ORCHESTRATOR_AUTO_CREATE_TABLES", "1")
    monkeypatch.setenv("ORCHESTRATOR_DISABLE_ADVISORY_LOCKS", "1")

    app = create_app()
    c = TestClient(app)
    # Force startup so app.state exists, then override upstream clients.
    with c:
        app.state.config_service = FakeConfigService()
        app.state.pipeline_api = FakePipelineApi()
        app.state.agent_api = FakeAgentApi()
        yield c


def test_provision_idempotency_key_returns_same_run_id(client: TestClient):
    body = {
        "org_id": "org1",
        "team_node_id": "teamA",
        "slack_channel_ids": ["C1"],
        "idempotency_key": "k1",
    }
    r1 = client.post(
        "/api/v1/admin/provision/team",
        headers={"Authorization": "Bearer admin"},
        json=body,
    )
    assert r1.status_code == 200
    rid1 = r1.json()["provisioning_run_id"]

    r2 = client.post(
        "/api/v1/admin/provision/team",
        headers={"Authorization": "Bearer admin"},
        json=body,
    )
    assert r2.status_code == 200
    rid2 = r2.json()["provisioning_run_id"]

    assert rid1 == rid2


def test_slack_channel_conflict_returns_409_and_run_id(client: TestClient):
    # First team owns C1
    r1 = client.post(
        "/api/v1/admin/provision/team",
        headers={"Authorization": "Bearer admin"},
        json={
            "org_id": "org1",
            "team_node_id": "teamA",
            "slack_channel_ids": ["C1"],
            "idempotency_key": "a",
        },
    )
    assert r1.status_code == 200

    # Second team tries to claim C1 -> conflict
    r2 = client.post(
        "/api/v1/admin/provision/team",
        headers={"Authorization": "Bearer admin"},
        json={
            "org_id": "org1",
            "team_node_id": "teamB",
            "slack_channel_ids": ["C1"],
            "idempotency_key": "b",
        },
    )
    assert r2.status_code == 409
    assert "X-IncidentFox-Provisioning-Run-Id" in r2.headers
    body = r2.json()
    assert body["status"] == "failed"
    assert "slack_channel_already_mapped" in (body.get("error") or "")


def test_permission_denied_is_403(client: TestClient):
    # Override permissions to not include required admin:provision
    class NoPermConfigService(FakeConfigService):
        def auth_me_admin(self, raw_token: str) -> dict:
            return {
                "role": "admin",
                "permissions": ["admin:read"],
                "subject": "admin",
                "email": None,
            }

    # Swap config service on the live app
    app = client.app
    app.state.config_service = NoPermConfigService()
    r = client.post(
        "/api/v1/admin/provision/team",
        headers={"Authorization": "Bearer admin"},
        json={
            "org_id": "org1",
            "team_node_id": "teamX",
            "slack_channel_ids": [],
            "idempotency_key": "k",
        },
    )
    assert r.status_code == 403

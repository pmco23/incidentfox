from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


def make_stub_pipeline_app() -> FastAPI:
    app = FastAPI(title="Stub AI Pipeline API", version="0.0.0")

    @app.post("/api/v1/teams/{team_id}/bootstrap")
    def bootstrap(team_id: str, authorization: str = Header(default="")):
        # Minimal shape compatible with orchestrator PipelineApiClient.
        if not authorization:
            raise HTTPException(status_code=401, detail="missing_auth")
        return {"run_id": f"bootstrap:{team_id}", "status": "queued"}

    return app


class AgentRunReq(BaseModel):
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[int] = None


def make_stub_agent_app(
    *, get_effective_config: Callable[[str], dict[str, Any]]
) -> FastAPI:
    """
    Minimal agent runtime stub:
    - expects X-IncidentFox-Team-Token (impersonation JWT)
    - uses it to call config_service /api/v1/config/me/effective (via injected fetcher)
    """

    app = FastAPI(title="Stub Agent", version="0.0.0")

    @app.post("/agents/{agent_name}/run")
    def run_agent(
        agent_name: str,
        body: AgentRunReq,
        x_incidentfox_team_token: str = Header(default=""),
    ):
        if not x_incidentfox_team_token:
            raise HTTPException(status_code=401, detail="missing_team_token")
        try:
            cfg = get_effective_config(x_incidentfox_team_token)
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"config_service_error:{e}"
            ) from e
        return {"agent_name": agent_name, "echo": body.message, "effective_config": cfg}

    return app

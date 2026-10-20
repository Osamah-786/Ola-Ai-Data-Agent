"""Agent-facing API routes, backed by an injectable service."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.router_service import RouterService, get_router_service
from app.core.run_history import RunHistoryStore, get_run_history_store, record_run_safely, utc_now
from app.models.agent import AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResponse)
def run_agent(
    request: AgentRunRequest,
    service: RouterService = Depends(get_router_service),
    history: RunHistoryStore = Depends(get_run_history_store),
) -> AgentRunResponse:
    """Dispatch the requested mock or guarded live execution mode."""
    started_at = utc_now()
    try:
        response = service.run(request.message, request.execution_mode)
        success = response.status == "ok"
        workflow = response.route if response.route in {"etl", "sql"} else "workspace"
        record_run_safely(
            history,
            task_description="Workspace request",
            workflow=workflow,
            execution_mode=request.execution_mode,
            status="success" if success else "failed",
            result_summary="Request completed." if success else "Request failed.",
            started_at=started_at,
        )
        return response
    except HTTPException:
        record_run_safely(
            history, task_description="Workspace request", workflow="workspace",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Request failed.", started_at=started_at,
        )
        raise
    except Exception as exc:
        record_run_safely(
            history, task_description="Workspace request", workflow="workspace",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Request failed.", started_at=started_at,
        )
        # Do not expose exception details, which could contain secrets.
        raise HTTPException(
            status_code=500,
            detail="The agent service is temporarily unavailable.",
        ) from exc

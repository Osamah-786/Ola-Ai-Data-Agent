"""Natural-language SQL Analyst endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.run_history import RunHistoryStore, get_run_history_store, record_run_safely, utc_now
from app.core.sql_service import SqlAnalystService, get_sql_analyst_service
from app.models.agent import SqlAnalystRequest, SqlAnalystResponse

router = APIRouter(prefix="/api/sql", tags=["sql"])


@router.post("/run", response_model=SqlAnalystResponse)
def run_sql_analyst(
    request: SqlAnalystRequest,
    service: SqlAnalystService = Depends(get_sql_analyst_service),
    history: RunHistoryStore = Depends(get_run_history_store),
) -> SqlAnalystResponse:
    """Run a mock by default or a doubly-gated SQL workflow request."""
    started_at = utc_now()
    try:
        response = service.run(request.question, request.execution_mode)
        status = {
            "ok": "success", "rejected": "rejected", "error": "failed",
        }[response.status]
        record_run_safely(
            history, task_description="SQL analysis", workflow="sql",
            execution_mode=request.execution_mode, status=status,
            result_summary=(
                f"SQL request completed with {response.row_count} rows."
                if response.status == "ok"
                else "SQL request rejected by safety checks."
                if response.status == "rejected"
                else "SQL request failed."
            ),
            started_at=started_at,
        )
        return response
    except HTTPException:
        record_run_safely(
            history, task_description="SQL analysis", workflow="sql",
            execution_mode=request.execution_mode, status="failed",
            result_summary="SQL request failed.", started_at=started_at,
        )
        raise
    except Exception as exc:
        record_run_safely(
            history, task_description="SQL analysis", workflow="sql",
            execution_mode=request.execution_mode, status="failed",
            result_summary="SQL request failed.", started_at=started_at,
        )
        # Keep unexpected diagnostics and credentials out of the response.
        raise HTTPException(
            status_code=500,
            detail="The SQL analyst is temporarily unavailable.",
        ) from exc

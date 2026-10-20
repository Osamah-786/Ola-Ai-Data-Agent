"""Read-only endpoints for recent, privacy-minimized run history."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.run_history import RunHistoryStore, get_run_history_store
from app.models.run_history import RunRecord

router = APIRouter(prefix="/api/runs", tags=["run history"])


@router.get("", response_model=list[RunRecord])
def list_runs(
    limit: int = Query(50, ge=1, le=100),
    store: RunHistoryStore = Depends(get_run_history_store),
) -> list[RunRecord]:
    try:
        return store.list_recent(limit)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(status_code=503, detail="Run history is unavailable.") from exc


@router.get("/{run_id}", response_model=RunRecord)
def get_run(
    run_id: str,
    store: RunHistoryStore = Depends(get_run_history_store),
) -> RunRecord:
    try:
        record = store.get(run_id)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(status_code=503, detail="Run history is unavailable.") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Run was not found.")
    return record

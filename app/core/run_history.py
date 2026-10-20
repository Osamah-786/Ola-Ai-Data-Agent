"""SQLite persistence for bounded, privacy-minimized operation history."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

from app.models.run_history import RunRecord

logger = logging.getLogger(__name__)
RunStatus = Literal["success", "failed", "rejected"]
DEFAULT_DB = Path(__file__).resolve().parents[2] / "app_data" / "run_history.sqlite3"
MAX_HISTORY_RECORDS = 500


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunHistoryStore:
    """Connection-per-operation store; prompt/result content is never accepted."""

    def __init__(self, path: Path | None = None, max_records: int = MAX_HISTORY_RECORDS):
        self.path = Path(path or os.getenv("RUN_HISTORY_DB_PATH", DEFAULT_DB)).resolve()
        self.max_records = max(1, int(max_records))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_description TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    dataset_ids TEXT NOT NULL
                )"""
            )
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add(
        self,
        *,
        task_description: str,
        workflow: Literal["workspace", "etl", "etl_extract", "etl_transform", "sql"],
        execution_mode: str,
        status: RunStatus,
        result_summary: str,
        started_at: datetime,
        dataset_ids: list[str] | None = None,
    ) -> RunRecord:
        # Callers supply fixed, generic labels/summaries; raw prompts, answers,
        # SQL results, URLs, and exception details are intentionally not inputs.
        run_id = uuid4().hex
        completed_at = utc_now()
        datasets = [str(value) for value in (dataset_ids or []) if value]
        values = (
            run_id, task_description[:120], workflow, execution_mode[:20], status,
            started_at.astimezone(timezone.utc).isoformat(),
            completed_at.isoformat(), result_summary[:240], json.dumps(datasets),
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO runs
                (run_id, task_description, workflow, execution_mode, status,
                 started_at, completed_at, result_summary, dataset_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            connection.execute(
                "DELETE FROM runs WHERE run_id NOT IN "
                "(SELECT run_id FROM runs ORDER BY rowid DESC LIMIT ?)",
                (self.max_records,),
            )
        return RunRecord(
            run_id=run_id,
            task_description=values[1], workflow=workflow,
            execution_mode=values[3], status=status,
            started_at=started_at, completed_at=completed_at,
            result_summary=values[7], dataset_ids=datasets,
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> RunRecord:
        try:
            dataset_ids = json.loads(row["dataset_ids"])
        except (TypeError, json.JSONDecodeError):
            dataset_ids = []
        return RunRecord(
            run_id=row["run_id"], task_description=row["task_description"],
            workflow=row["workflow"], execution_mode=row["execution_mode"],
            status=row["status"], started_at=row["started_at"],
            completed_at=row["completed_at"], result_summary=row["result_summary"],
            dataset_ids=dataset_ids if isinstance(dataset_ids, list) else [],
        )

    def list_recent(self, limit: int = 50) -> list[RunRecord]:
        bounded_limit = min(max(int(limit), 1), 100)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY rowid DESC LIMIT ?", (bounded_limit,)
            ).fetchall()
        return [self._record(row) for row in rows]

    def get(self, run_id: str) -> RunRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._record(row) if row is not None else None


_store = RunHistoryStore()


def get_run_history_store() -> RunHistoryStore:
    """Dependency provider; storage is opened lazily on history use."""
    return _store


def record_run_safely(store: RunHistoryStore, **record) -> None:
    """History persistence failures must not change the operation response."""
    try:
        store.add(**record)
    except Exception as exc:
        logger.error("Could not persist run history (%s)", type(exc).__name__)

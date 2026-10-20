"""Run history tests use temporary SQLite and fake endpoint services only."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import agent as agent_api
from app.api import etl as etl_api
from app.api import runs as runs_api
from app.api import sql as sql_api
from app.core.run_history import RunHistoryStore, utc_now
from app.models.agent import AgentRunRequest, AgentRunResponse, SqlAnalystRequest, SqlAnalystResponse
from app.models.etl import ExtractRequest, TransformRequest


@pytest.fixture
def history(tmp_path: Path) -> RunHistoryStore:
    return RunHistoryStore(tmp_path / "history.sqlite3")


def add_run(store, label="Workspace request", status="success", datasets=None):
    return store.add(
        task_description=label,
        workflow="workspace",
        execution_mode="mock",
        status=status,
        result_summary="Request completed.",
        started_at=utc_now() - timedelta(seconds=1),
        dataset_ids=datasets,
    )


def test_history_persists_across_store_connections_and_returns_safe_records(history):
    success = add_run(history, datasets=["dataset-1"])
    add_run(history, status="failed")

    reopened = RunHistoryStore(history.path)
    records = reopened.list_recent()
    assert [record.status for record in records] == ["failed", "success"]
    assert reopened.get(success.run_id).dataset_ids == ["dataset-1"]
    assert not hasattr(records[0], "prompt")
    assert not hasattr(records[0], "answer")


def test_history_retention_keeps_only_most_recent_records(tmp_path):
    store = RunHistoryStore(tmp_path / "bounded.sqlite3", max_records=2)
    first = add_run(store)
    add_run(store)
    last = add_run(store)
    records = store.list_recent()
    assert len(records) == 2
    assert first.run_id not in {record.run_id for record in records}
    assert records[0].run_id == last.run_id


def test_read_api_lists_recent_runs_and_unknown_id_is_not_disclosed(history):
    created = add_run(history)
    assert runs_api.list_runs(limit=20, store=history)[0].run_id == created.run_id
    with pytest.raises(HTTPException) as error:
        runs_api.get_run("unknown-id", store=history)
    assert error.value.status_code == 404


def test_agent_endpoint_records_success_and_failure_without_prompt_content(history):
    class Success:
        def run(self, message, execution_mode):
            return AgentRunResponse(status="ok", answer="private answer", route="sql", mode="mock")

    prompt = "private prompt: do not persist this"
    response = agent_api.run_agent(AgentRunRequest(message=prompt), Success(), history)
    record = history.get(history.list_recent()[0].run_id)
    assert response.status == "ok"
    assert record.workflow == "sql" and record.status == "success"
    assert prompt not in record.task_description + record.result_summary
    assert "private answer" not in record.result_summary

    class Failure:
        def run(self, message, execution_mode):
            raise HTTPException(status_code=403, detail="disabled")

    with pytest.raises(HTTPException):
        agent_api.run_agent(AgentRunRequest(message=prompt), Failure(), history)
    assert history.list_recent()[0].status == "failed"


def test_etl_extract_records_success_and_failure_without_url(history, monkeypatch):
    monkeypatch.setattr(etl_api, "extract_dataset", lambda url, fmt, storage: {
        "file_id": "extract-id", "format": fmt, "records": 2, "columns": ["x"],
        "kind": "extract", "operations": [], "created_at": "2026-10-20T00:00:00Z",
        "pages_fetched": 1, "message": "done",
    })
    url = "https://api.example/with-sensitive-query?token=do-not-store"
    result = etl_api.extract(ExtractRequest(url=url), object(), history)
    record = history.list_recent()[0]
    assert result["file_id"] == "extract-id"
    assert record.status == "success" and record.dataset_ids == ["extract-id"]
    assert "api.example" not in record.task_description + record.result_summary

    def fail(url, fmt, storage):
        raise etl_api.ExtractionError("sensitive URL or server detail")
    monkeypatch.setattr(etl_api, "extract_dataset", fail)
    with pytest.raises(HTTPException) as error:
        etl_api.extract(ExtractRequest(url="https://api.example/private"), object(), history)
    assert error.value.status_code == 400
    assert history.list_recent()[0].status == "failed"
    assert "private" not in history.list_recent()[0].result_summary


def test_etl_transform_fake_success_and_mock_failure_are_recorded(history, monkeypatch):
    class Storage:
        def get(self, file_id):
            return ({"format": "csv"}, Path("unused.csv"))

        def create(self, frame, output_format, kind, **kwargs):
            return {
                "file_id": "output-id", "format": output_format, "records": 1,
                "columns": ["x"], "kind": kind, "source_file_id": "source-id",
                "operations": ["select_columns"], "created_at": "2026-10-20T00:00:00Z",
            }

    monkeypatch.setattr(etl_api, "live_agents_enabled", lambda: True)
    monkeypatch.setattr(etl_api, "read_frame", lambda path, fmt: "frame")
    monkeypatch.setattr(etl_api, "parse_plan", lambda raw: raw)
    monkeypatch.setattr(etl_api, "apply_plan", lambda frame, plan: ("new-frame", ["select_columns"]))
    result = etl_api.transform(
        TransformRequest(input_file_id="source-id", instruction="private instruction", execution_mode="live"),
        Storage(), lambda frame, instruction: {"fake": True}, history,
    )
    record = history.list_recent()[0]
    assert result["file_id"] == "output-id"
    assert record.status == "success" and record.dataset_ids == ["source-id", "output-id"]
    assert "private instruction" not in record.task_description + record.result_summary

    with pytest.raises(HTTPException) as error:
        etl_api.transform(
            TransformRequest(input_file_id="source-id", instruction="anything", execution_mode="mock"),
            Storage(), lambda *_: pytest.fail("mock mode cannot invoke planner"), history,
        )
    assert error.value.status_code == 409
    assert history.list_recent()[0].status == "failed"


def test_sql_endpoint_records_success_and_sanitized_failure(history):
    class Success:
        def run(self, question, mode):
            return SqlAnalystResponse(
                status="ok", answer="sensitive database answer", generated_sql="SELECT 1",
                safety_status="safe", rows=[{"private": "row"}], row_count=1,
                mode="mock",
            )

    sql_api.run_sql_analyst(SqlAnalystRequest(question="sensitive question"), Success(), history)
    record = history.list_recent()[0]
    assert record.workflow == "sql" and record.status == "success"
    assert "sensitive" not in record.task_description + record.result_summary
    assert "private" not in record.result_summary

    class Failure:
        def run(self, question, mode):
            raise HTTPException(status_code=500, detail="sensitive diagnostic")

    with pytest.raises(HTTPException):
        sql_api.run_sql_analyst(SqlAnalystRequest(question="sensitive question"), Failure(), history)
    assert history.list_recent()[0].status == "failed"
    assert "sensitive" not in history.list_recent()[0].result_summary

"""SQL Analyst API service tests; every graph/database result is injected."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.sql_service import SqlAnalystService
from app.models.agent import SqlAnalystRequest


class FakeGraph:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(self, state, config):
        self.calls.append((state, config))
        return self.result


def state(**overrides):
    values = {
        "generated_sql_query": "SELECT count(*) FROM rides",
        "is_safe": "Yes",
        "comments": "Read-only query approved.",
        "sql_query_execution_result": '[{"count": 3}]',
        "final_answer": "There are three rides.",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_mock_mode_is_default_safe_and_does_not_load_graph():
    def fail_load():
        raise AssertionError("mock mode must not load SQL integrations")

    result = SqlAnalystService(agent_loader=fail_load).run("How many rides?")
    assert result.mode == "mock"
    assert result.safety_status == "not_run"
    assert result.generated_sql is None
    assert result.rows == []
    assert "No SQL was generated" in result.answer


def test_request_schema_defaults_to_mock_mode():
    request = SqlAnalystRequest(question="How many rides?")
    assert request.execution_mode == "mock"


def test_live_request_rejected_before_agent_load_when_gate_disabled():
    calls = []
    service = SqlAnalystService(
        live_enabled=lambda: False,
        agent_loader=lambda: calls.append("loaded"),
    )
    with pytest.raises(HTTPException) as error:
        service.run("How many rides?", "live")
    assert error.value.status_code == 403
    assert calls == []


def test_safe_fake_graph_returns_bounded_rows_and_answer():
    graph = FakeGraph(state())
    result = SqlAnalystService(
        live_enabled=lambda: True, agent_loader=lambda: graph
    ).run("How many rides?", "live")
    assert result.status == "ok"
    assert result.safety_status == "safe"
    assert result.generated_sql == "SELECT count(*) FROM rides"
    assert result.rows == [{"count": 3}]
    assert result.row_count == 1
    assert result.answer == "There are three rides."
    assert graph.calls[0][0]["user_question"] == "How many rides?"


def test_json_rows_preserve_common_database_values_as_displayable_text():
    graph = FakeGraph(state(
        sql_query_execution_result='[{"created_at":"2026-10-20T12:00:00","fare":"12.50"}]',
        final_answer="The row was returned.",
    ))
    result = SqlAnalystService(
        live_enabled=lambda: True, agent_loader=lambda: graph
    ).run("Show a row", "live")
    assert result.rows == [{"created_at": "2026-10-20T12:00:00", "fare": "12.50"}]


def test_rejected_fake_query_exposes_reason_without_rows():
    graph = FakeGraph(state(
        generated_sql_query="DROP TABLE rides",
        is_safe="No",
        comments="Only SELECT queries are allowed.",
        sql_query_execution_result="",
        final_answer="Rejected by safety checks.",
    ))
    result = SqlAnalystService(
        live_enabled=lambda: True, agent_loader=lambda: graph
    ).run("remove the rides table", "live")
    assert result.status == "rejected"
    assert result.safety_status == "rejected"
    assert result.rejection_reason == "Only SELECT queries are allowed."
    assert result.rows == []


def test_empty_and_failed_fake_results_are_handled():
    empty = SqlAnalystService(
        live_enabled=lambda: True,
        agent_loader=lambda: FakeGraph(state(
            sql_query_execution_result="[]", final_answer="No matching records were found."
        )),
    ).run("Find missing value", "live")
    assert empty.status == "ok" and empty.rows == [] and empty.row_count == 0

    failed = SqlAnalystService(
        live_enabled=lambda: True,
        agent_loader=lambda: FakeGraph(state(
            sql_query_execution_result="SQL execution failed: private database detail",
            final_answer="could not execute",
        )),
    ).run("Find rides", "live")
    assert failed.status == "error"
    assert failed.answer == "The SQL request could not be completed."
    assert "private database detail" not in failed.answer


def test_final_validation_rejection_is_reported_as_rejected():
    result = SqlAnalystService(
        live_enabled=lambda: True,
        agent_loader=lambda: FakeGraph(state(
            sql_query_execution_result="Query rejected: Multiple SQL statements are not permitted.",
        )),
    ).run("Find rides", "live")
    assert result.status == "rejected"
    assert result.safety_status == "rejected"
    assert result.rejection_reason == "Multiple SQL statements are not permitted."


def test_fake_graph_failure_maps_to_controlled_http_error():
    class BrokenGraph:
        def invoke(self, state, config):
            raise RuntimeError("sensitive diagnostic")

    service = SqlAnalystService(
        live_enabled=lambda: True, agent_loader=BrokenGraph
    )
    with pytest.raises(HTTPException) as error:
        service.run("How many rides?", "live")
    assert error.value.status_code == 500
    assert "sensitive diagnostic" not in error.value.detail

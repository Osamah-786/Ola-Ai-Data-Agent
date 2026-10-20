"""Focused API tests; all service behavior is injected or mocked."""

import builtins
import asyncio
from types import SimpleNamespace

import pytest
import httpx

from app.core.router_service import get_router_service
from app.main import app
from app.models.agent import AgentRunResponse


def send_request(method: str, path: str, **kwargs) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(request())


class StubRouterService:
    def run(self, message: str, execution_mode: str = "mock") -> AgentRunResponse:
        assert message == "Summarize this dataset"
        assert execution_mode == "mock"
        return AgentRunResponse(
            status="ok",
            answer="Mock result",
            route=None,
            mode="mock",
            request_id="test-request-id",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_health_returns_expected_structure():
    response = send_request("GET", "/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ola-ai-data-agent-api",
        "mode": "mock",
    }


def test_metadata_reports_server_execution_setting(monkeypatch):
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "false")
    response = send_request("GET", "/api/metadata")

    assert response.status_code == 200
    assert response.json()["agent_execution_enabled"] is False
    assert "POST /api/agent/run" in response.json()["available_endpoints"]


def test_agent_run_uses_injected_mock_service():
    app.dependency_overrides[get_router_service] = lambda: StubRouterService()

    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "mock"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "answer": "Mock result",
        "route": None,
        "mode": "mock",
        "request_id": "test-request-id",
    }


def test_agent_run_default_is_explicitly_mocked():
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Fetch some API data"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "mock"
    assert response.json()["route"] is None
    assert "No real agent workflow" in response.json()["answer"]


@pytest.mark.parametrize("message", ["", "   "])
def test_agent_run_rejects_empty_or_blank_message(message: str):
    response = send_request("POST", "/api/agent/run", json={"message": message})

    assert response.status_code == 422


def test_agent_run_rejects_overlength_message():
    sensitive_input = "private-token-" + "x" * 4001
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": sensitive_input},
    )

    assert response.status_code == 422
    assert "private-token" not in response.text


def test_agent_run_hides_unexpected_service_exception():
    class BrokenService:
        def run(self, message: str, execution_mode: str = "mock") -> AgentRunResponse:
            raise RuntimeError("sensitive diagnostic")

    app.dependency_overrides[get_router_service] = lambda: BrokenService()

    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "The agent service is temporarily unavailable."
    }
    assert "sensitive diagnostic" not in response.text


def test_endpoint_does_not_attempt_live_integration_imports(monkeypatch):
    original_import = builtins.__import__
    blocked_roots = {"agents", "langchain_groq", "groq", "psycopg2"}
    attempted = []

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in blocked_roots:
            attempted.append(name)
            raise AssertionError(f"Live integration import attempted: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "This is a test input"},
    )

    assert response.status_code == 200
    assert attempted == []


def test_live_mode_is_rejected_when_server_gate_is_disabled(monkeypatch):
    from app.core.router_service import RouterService

    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "false")
    loader_calls = []
    service = RouterService(agent_loader=lambda: loader_calls.append("loaded"))
    app.dependency_overrides[get_router_service] = lambda: service

    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "live"},
    )

    assert response.status_code == 403
    assert "ENABLE_LIVE_AGENTS=true" in response.json()["detail"]
    assert loader_calls == []


def test_mock_mode_never_loads_graph_even_when_server_gate_is_enabled(monkeypatch):
    from app.core.router_service import RouterService

    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")

    def unexpected_load():
        raise AssertionError("mock mode must not load the graph")

    app.dependency_overrides[get_router_service] = lambda: RouterService(
        agent_loader=unexpected_load
    )
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "mock"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "mock"
    assert response.json()["route"] is None


def test_live_mode_invokes_injected_graph_and_extracts_route_and_final_answer(monkeypatch):
    from app.core.router_service import RouterService

    class GraphStub:
        def invoke(self, state, config):
            assert state["route_response"] == ""
            assert state["messages"][0].content == "Summarize this dataset"
            assert config["recursion_limit"] == 40
            return {
                "route_response": "etl",
                "messages": [
                    SimpleNamespace(type="ai", content="", tool_calls=[{}]),
                    SimpleNamespace(type="ai", content="  ETL finished.  ", tool_calls=[]),
                ],
            }

    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    app.dependency_overrides[get_router_service] = lambda: RouterService(
        agent_loader=lambda: GraphStub()
    )
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "live"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "agent"
    assert response.json()["route"] == "etl"
    assert response.json()["answer"] == "ETL finished."


def test_live_mode_rejects_empty_graph_result(monkeypatch):
    from app.core.router_service import RouterService

    class GraphStub:
        def invoke(self, state, config):
            return {"route_response": "sql", "messages": []}

    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    app.dependency_overrides[get_router_service] = lambda: RouterService(
        agent_loader=lambda: GraphStub()
    )
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "live"},
    )

    assert response.status_code == 502
    assert "usable answer" in response.json()["detail"]


def test_live_agent_exception_is_controlled_and_does_not_leak(monkeypatch):
    from app.core.router_service import RouterService

    class BrokenGraph:
        def invoke(self, state, config):
            raise RuntimeError("sensitive diagnostic")

    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    app.dependency_overrides[get_router_service] = lambda: RouterService(
        agent_loader=lambda: BrokenGraph()
    )
    response = send_request(
        "POST",
        "/api/agent/run",
        json={"message": "Summarize this dataset", "execution_mode": "live"},
    )

    assert response.status_code == 500
    assert "sensitive diagnostic" not in response.text


def test_health_and_metadata_do_not_import_agent_modules(monkeypatch):
    original_import = builtins.__import__
    blocked_roots = {"agents", "langchain_groq", "groq", "psycopg2"}
    attempted = []

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in blocked_roots:
            attempted.append(name)
            raise AssertionError(f"Live integration import attempted: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert send_request("GET", "/api/health").status_code == 200
    assert send_request("GET", "/api/metadata").status_code == 200
    assert attempted == []

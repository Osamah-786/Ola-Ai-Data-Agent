"""Mock-first service boundary for controlled LangGraph integration."""

import importlib
import logging
from collections.abc import Callable, Mapping
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import live_agents_enabled
from app.models.agent import AgentRunResponse

logger = logging.getLogger(__name__)


class RouterService:
    """Dispatch mock requests or explicitly permitted live requests."""

    def __init__(
        self,
        *,
        live_enabled: Callable[[], bool] = live_agents_enabled,
        agent_loader: Callable[[], object] | None = None,
    ) -> None:
        self._live_enabled = live_enabled
        self._agent_loader = agent_loader or self._load_data_agent

    @staticmethod
    def _load_data_agent():
        """Import the graph only after both live execution gates pass."""
        module = importlib.import_module("agents.data_agent")
        return module.data_agent

    @staticmethod
    def _state_value(state: object, name: str, default=None):
        if isinstance(state, Mapping):
            return state.get(name, default)
        return getattr(state, name, default)

    @classmethod
    def _extract_result(cls, state: object) -> tuple[str | None, str | None]:
        route = cls._state_value(state, "route_response")
        if not isinstance(route, str) or route not in {"etl", "sql"}:
            route = None

        messages = cls._state_value(state, "messages", []) or []
        for message in reversed(messages):
            content = cls._state_value(message, "content")
            message_type = cls._state_value(message, "type")
            is_ai_message = (
                message_type == "ai"
                or type(message).__name__ == "AIMessage"
                or (
                    isinstance(message, Mapping)
                    and message.get("role") == "assistant"
                )
            )
            if not is_ai_message or not isinstance(content, str):
                continue
            if cls._state_value(message, "tool_calls", []):
                continue
            answer = content.strip()
            if answer:
                return route, answer

        return route, None

    def run(self, message: str, execution_mode: str = "mock") -> AgentRunResponse:
        """Return a deterministic mock or dispatch an explicitly allowed run."""
        request_id = str(uuid4())
        if execution_mode == "mock":
            return AgentRunResponse(
                status="ok",
                answer="The API is connected. No real agent workflow was invoked.",
                route=None,
                mode="mock",
                request_id=request_id,
            )

        if execution_mode != "live":
            raise HTTPException(
                status_code=422,
                detail="Unsupported execution mode.",
            )
        if not self._live_enabled():
            raise HTTPException(
                status_code=403,
                detail=(
                    "Live agent execution is disabled. The developer must "
                    "explicitly set ENABLE_LIVE_AGENTS=true on the server."
                ),
            )

        try:
            graph = self._agent_loader()
            from langchain_core.messages import HumanMessage

            result = graph.invoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "route_response": "",
                },
                config={"recursion_limit": 40},
            )
        except Exception as exc:
            logger.error(
                "Live agent execution failed (%s); request_id=%s",
                type(exc).__name__,
                request_id,
            )
            raise HTTPException(
                status_code=500,
                detail="The live agent service could not complete this request.",
            ) from exc

        route, answer = self._extract_result(result)
        if answer is None:
            logger.error(
                "Live agent returned no usable answer; request_id=%s",
                request_id,
            )
            raise HTTPException(
                status_code=502,
                detail="The live agent did not return a usable answer.",
            )
        return AgentRunResponse(
            status="ok",
            answer=answer,
            route=route,
            mode="agent",
            request_id=request_id,
        )


_router_service = RouterService()


def get_router_service() -> RouterService:
    """FastAPI dependency provider, overridable in tests."""
    return _router_service

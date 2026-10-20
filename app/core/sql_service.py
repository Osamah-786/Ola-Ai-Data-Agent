"""Mock-first boundary for the existing, safety-checked SQL graph."""

import importlib
import json
import logging
from collections.abc import Callable, Mapping
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import live_agents_enabled
from app.models.agent import SqlAnalystResponse

logger = logging.getLogger(__name__)


class SqlAnalystService:
    """Return a safe mock or call an injected SQL graph after both gates."""

    def __init__(
        self,
        *,
        live_enabled: Callable[[], bool] = live_agents_enabled,
        agent_loader: Callable[[], object] | None = None,
    ) -> None:
        self._live_enabled = live_enabled
        self._agent_loader = agent_loader or self._load_sql_agent

    @staticmethod
    def _load_sql_agent():
        # The module (and its integrations) is imported only after live is opted in.
        module = importlib.import_module("agents.sql_analyst")
        return module.sql_analyst

    @staticmethod
    def _value(state: object, key: str, default=None):
        if isinstance(state, Mapping):
            return state.get(key, default)
        return getattr(state, key, default)

    @staticmethod
    def _rows(result: object) -> list[dict[str, object]]:
        if not isinstance(result, str) or not result.strip():
            return []
        parsed = json.loads(result)
        if not isinstance(parsed, list) or not all(
            isinstance(row, dict) for row in parsed
        ):
            raise ValueError("SQL workflow returned an invalid row set")
        # Existing workflow caps at 100 rows; enforce the API boundary as well.
        return parsed[:100]

    def run(self, question: str, execution_mode: str = "mock") -> SqlAnalystResponse:
        request_id = str(uuid4())
        if execution_mode == "mock":
            return SqlAnalystResponse(
                status="ok",
                answer="Mock SQL Analyst response. No SQL was generated or executed.",
                safety_status="not_run",
                rows=[],
                row_count=0,
                mode="mock",
                request_id=request_id,
            )

        if execution_mode != "live":
            raise HTTPException(status_code=422, detail="Unsupported execution mode.")
        if not self._live_enabled():
            raise HTTPException(
                status_code=403,
                detail=(
                    "Live SQL execution is disabled. The developer must "
                    "explicitly set ENABLE_LIVE_AGENTS=true on the server."
                ),
            )

        try:
            graph = self._agent_loader()
            result = graph.invoke(
                {
                    "messages": [],
                    "user_question": question,
                    "curated_ques": "",
                    "prompt_query_context": "",
                    "generated_sql_query": "",
                    "is_safe": "No",
                    "comments": "",
                    "sql_query_execution_result": "",
                    "final_answer": "",
                },
                config={"recursion_limit": 40},
            )

            sql = self._value(result, "generated_sql_query")
            is_safe = str(self._value(result, "is_safe", "No")).strip().lower() == "yes"
            reason = self._value(result, "comments")
            execution_result = self._value(result, "sql_query_execution_result")
            answer = self._value(result, "final_answer")
            if not isinstance(sql, str):
                sql = None
            if not is_safe:
                return SqlAnalystResponse(
                    status="rejected",
                    answer=str(answer or "The SQL query was rejected by safety checks."),
                    generated_sql=sql,
                    safety_status="rejected",
                    rejection_reason=str(reason or "The safety review rejected the query."),
                    rows=[], row_count=0, mode="agent", request_id=request_id,
                )
            if isinstance(execution_result, str) and execution_result.startswith("Query rejected:"):
                reason = execution_result.partition(":")[2].strip()
                return SqlAnalystResponse(
                    status="rejected",
                    answer="The SQL query was rejected by final validation.",
                    generated_sql=sql,
                    safety_status="rejected",
                    rejection_reason=reason or "Final SQL validation rejected the query.",
                    rows=[], row_count=0, mode="agent", request_id=request_id,
                )
            if isinstance(execution_result, str) and execution_result.startswith("SQL execution failed:"):
                return SqlAnalystResponse(
                    status="error",
                    answer="The SQL request could not be completed.",
                    generated_sql=sql,
                    safety_status="safe",
                    rows=[], row_count=0, mode="agent", request_id=request_id,
                )
            rows = self._rows(execution_result)
            if not isinstance(answer, str) or not answer.strip():
                answer = "No matching records were found." if not rows else "Query completed."
            return SqlAnalystResponse(
                status="ok", answer=answer.strip(), generated_sql=sql,
                safety_status="safe", rows=rows, row_count=len(rows),
                mode="agent", request_id=request_id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("SQL analyst execution failed (%s); request_id=%s", type(exc).__name__, request_id)
            raise HTTPException(
                status_code=500,
                detail="The SQL analyst could not complete this request.",
            ) from exc


_sql_service = SqlAnalystService()


def get_sql_analyst_service() -> SqlAnalystService:
    """FastAPI dependency provider, overridable in tests."""
    return _sql_service

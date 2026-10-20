"""Request and response schemas for agent API operations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRunRequest(BaseModel):
    """Natural-language request with an explicit, mock-first mode."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    execution_mode: Literal["mock", "live"] = "mock"

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must contain non-whitespace characters")
        return value


class AgentRunResponse(BaseModel):
    """Normalized API response; route stays unset until genuinely selected."""

    status: Literal["ok", "error"]
    answer: str
    route: Literal["etl", "sql"] | None = None
    mode: Literal["mock", "agent"]
    request_id: str | None = None


class SqlAnalystRequest(BaseModel):
    """Natural-language SQL question with mock execution as the default."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    execution_mode: Literal["mock", "live"] = "mock"

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must contain non-whitespace characters")
        return value


class SqlAnalystResponse(BaseModel):
    """Bounded SQL workflow response suitable for the Analyst UI."""

    status: Literal["ok", "rejected", "error"]
    answer: str
    generated_sql: str | None = None
    safety_status: Literal["not_run", "safe", "rejected"]
    rejection_reason: str | None = None
    rows: list[dict[str, object]] = Field(default_factory=list, max_length=100)
    row_count: int = Field(ge=0, le=100)
    mode: Literal["mock", "agent"]
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    mode: Literal["mock"]


class MetadataResponse(BaseModel):
    service: str
    version: str
    agent_execution_enabled: bool
    available_endpoints: list[str]

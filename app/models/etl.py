"""Validated request and response models for managed ETL operations."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    format: Literal["csv", "json", "parquet"] = "csv"


class TransformRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_file_id: str = Field(min_length=1, max_length=64)
    output_format: Literal["csv", "json", "parquet"] = "csv"
    instruction: str = Field(min_length=1, max_length=2000)
    execution_mode: Literal["mock", "live"] = "mock"

    @field_validator("instruction")
    @classmethod
    def instruction_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("instruction must not be blank")
        return value


class DatasetMetadata(BaseModel):
    file_id: str
    format: str
    records: int
    columns: list[str]
    kind: str
    source_file_id: str | None = None
    operations: list[str] = Field(default_factory=list)
    created_at: str


class EtlResult(DatasetMetadata):
    status: Literal["success"]
    message: str
    pages_fetched: int | None = None


class TransformResult(BaseModel):
    status: Literal["success"]
    file_id: str
    format: str
    records: int
    columns: list[str]
    kind: str
    source_file_id: str
    operations: list[str]
    created_at: str
    message: str


class PreviewResponse(BaseModel):
    file_id: str
    columns: list[str]
    page: int
    page_size: int
    total_records: int
    total_pages: int
    rows: list[dict[str, Any]]

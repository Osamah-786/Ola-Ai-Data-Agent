"""Public schemas for privacy-minimized run history records."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_description: str
    workflow: Literal["workspace", "etl", "etl_extract", "etl_transform", "sql"]
    execution_mode: str
    status: Literal["success", "failed", "rejected"]
    started_at: datetime
    completed_at: datetime
    result_summary: str
    dataset_ids: list[str] = Field(default_factory=list)

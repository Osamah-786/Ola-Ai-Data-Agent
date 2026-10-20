"""ETL extraction, controlled transformation, and managed dataset access."""

from __future__ import annotations

import json
import logging
from math import ceil
from pathlib import Path
from typing import Callable

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import live_agents_enabled
from app.core.run_history import RunHistoryStore, get_run_history_store, record_run_safely, utc_now
from app.models.etl import (
    DatasetMetadata,
    EtlResult,
    ExtractRequest,
    PreviewResponse,
    TransformRequest,
    TransformResult,
)
from app.services.etl_extraction import ExtractionError, extract_dataset
from app.services.etl_storage import (
    DatasetNotFoundError,
    DatasetStorage,
    json_value,
    read_frame,
)
from app.services.etl_transform import (
    TransformationPlanError,
    apply_plan,
    parse_plan,
    plan_example_instruction,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["etl"])
_storage = DatasetStorage()


def get_dataset_storage() -> DatasetStorage:
    return _storage


def get_plan_provider() -> Callable[[pd.DataFrame, str], object]:
    return _generate_plan


def _generate_plan(frame: pd.DataFrame, instruction: str) -> object:
    """Use fixed safe plans for UI examples; defer custom prompts to the gated LLM."""
    example_plan = plan_example_instruction(frame, instruction)
    if example_plan is not None:
        return json.dumps(example_plan)

    # This provider is only reached by the transform route after its explicit
    # request-mode and server-side ENABLE_LIVE_AGENTS checks have passed.
    from agents.etl_analyst import llm

    prompt = f"""Return only a JSON object with an operations array. Allowed operations:
select_columns(columns), drop_columns(columns), rename_columns(mapping),
drop_duplicates(columns optional), sort_values(column, ascending),
filter_rows(column, operator, value), fillna(column, value).
Use only these operation names and exact available columns. Never return code.
Columns: {json.dumps([str(column) for column in frame.columns])}
Sample: {frame.head(3).to_json(orient='records', force_ascii=False)}
Instruction: {instruction}"""
    return llm.invoke(prompt)


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail="Managed dataset was not found.")


@router.post("/api/etl/extract", response_model=EtlResult)
def extract(
    request: ExtractRequest,
    storage: DatasetStorage = Depends(get_dataset_storage),
    history: RunHistoryStore = Depends(get_run_history_store),
) -> dict:
    started_at = utc_now()
    try:
        result = extract_dataset(request.url, request.format, storage)
    except ExtractionError as exc:
        record_run_safely(
            history, task_description="Extract dataset", workflow="etl_extract",
            execution_mode="direct", status="failed", result_summary="Extraction failed.",
            started_at=started_at,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        record_run_safely(
            history, task_description="Extract dataset", workflow="etl_extract",
            execution_mode="direct", status="failed", result_summary="Extraction failed.",
            started_at=started_at,
        )
        logger.error("ETL extraction storage failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="The extracted dataset could not be stored.") from exc
    record_run_safely(
        history, task_description="Extract dataset", workflow="etl_extract",
        execution_mode="direct", status="success",
        result_summary=f"Created {result['format']} dataset with {result['records']} records.",
        started_at=started_at, dataset_ids=[result["file_id"]],
    )
    return {"status": "success", **result}


@router.post("/api/etl/transform", response_model=TransformResult)
def transform(
    request: TransformRequest,
    storage: DatasetStorage = Depends(get_dataset_storage),
    planner: Callable[[pd.DataFrame, str], object] = Depends(get_plan_provider),
    history: RunHistoryStore = Depends(get_run_history_store),
) -> dict:
    started_at = utc_now()
    if request.execution_mode == "mock":
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation did not run in mock mode.", started_at=started_at,
        )
        raise HTTPException(
            status_code=409,
            detail="Transformation is not available in mock mode; no dataset was created. Select live mode only when server-side live execution is enabled.",
        )
    if not live_agents_enabled():
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation was disabled by the server.", started_at=started_at,
        )
        raise HTTPException(
            status_code=403,
            detail="Live transformation planning is disabled. The developer must explicitly set ENABLE_LIVE_AGENTS=true on the server.",
        )
    try:
        source_metadata, source_path = storage.get(request.input_file_id)
        frame = read_frame(source_path, source_metadata["format"])
        raw_plan = planner(frame, request.instruction)
        plan = parse_plan(raw_plan)
        transformed, operations = apply_plan(frame, plan)
        if not operations:
            raise TransformationPlanError("The plan did not apply any transformation; no dataset was created.")
        result = storage.create(
            transformed,
            request.output_format,
            "transform",
            source_file_id=request.input_file_id,
            operations=operations,
        )
    except DatasetNotFoundError as exc:
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation failed.", started_at=started_at,
        )
        raise _not_found(exc) from exc
    except (TransformationPlanError, TypeError, ValueError) as exc:
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation failed.", started_at=started_at,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, ImportError) as exc:
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation failed.", started_at=started_at,
        )
        logger.error("ETL transformation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=422, detail="The dataset could not be transformed.") from exc
    except Exception as exc:
        record_run_safely(
            history, task_description="Transform dataset", workflow="etl_transform",
            execution_mode=request.execution_mode, status="failed",
            result_summary="Transformation failed.", started_at=started_at,
        )
        logger.error("ETL planner failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The transformation planner could not complete the request.") from exc
    record_run_safely(
        history, task_description="Transform dataset", workflow="etl_transform",
        execution_mode=request.execution_mode, status="success",
        result_summary=f"Created {result['format']} transformed dataset with {result['records']} records.",
        started_at=started_at,
        dataset_ids=[request.input_file_id, result["file_id"]],
    )
    return {"status": "success", **result, "source_file_id": request.input_file_id,
            "message": "Transformation completed."}


@router.get("/api/files", response_model=list[DatasetMetadata])
def list_files(storage: DatasetStorage = Depends(get_dataset_storage)) -> list[dict]:
    try:
        return storage.list()
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The dataset registry is unavailable.") from exc


@router.get("/api/files/{file_id}/preview", response_model=PreviewResponse)
def preview_file(
    file_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    storage: DatasetStorage = Depends(get_dataset_storage),
) -> dict:
    try:
        metadata, path = storage.get(file_id)
        frame = read_frame(path, metadata["format"])
    except DatasetNotFoundError as exc:
        raise _not_found(exc) from exc
    except (OSError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=422, detail="The dataset preview is unavailable.") from exc
    total = len(frame)
    start = (page - 1) * page_size
    rows = [
        {str(key): json_value(value) for key, value in row.items()}
        for row in frame.iloc[start:start + page_size].to_dict(orient="records")
    ]
    return {
        "file_id": file_id,
        "columns": [str(column) for column in frame.columns],
        "page": page,
        "page_size": page_size,
        "total_records": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "rows": rows,
    }


@router.get("/api/files/{file_id}/download")
def download_file(
    file_id: str,
    storage: DatasetStorage = Depends(get_dataset_storage),
) -> FileResponse:
    try:
        metadata, path = storage.get(file_id)
    except DatasetNotFoundError as exc:
        raise _not_found(exc) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The dataset is unavailable.") from exc
    media_types = {
        "csv": "text/csv",
        "json": "application/x-ndjson",
        "parquet": "application/vnd.apache.parquet",
    }
    return FileResponse(
        path,
        media_type=media_types[metadata["format"]],
        filename=f"ola-dataset-{file_id}.{metadata['format']}",
    )

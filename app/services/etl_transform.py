"""Pure transformation-plan validation and application shared by ETL workflows."""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd


class TransformationPlanError(ValueError):
    """Raised when a constrained transformation plan cannot be applied."""


def plan_example_instruction(frame: pd.DataFrame, instruction: str) -> dict[str, Any] | None:
    """Return deterministic plans for the ETL Studio's built-in examples.

    These exact examples have a known safe interpretation and do not need an
    LLM round trip. Return None for custom instructions so the caller can use
    its separately gated planner.
    """
    normalized = " ".join(instruction.casefold().strip().rstrip(".").split())
    plans: dict[str, dict[str, Any]] = {
        "keep only the name and url columns": {
            "operations": [{"type": "select_columns", "columns": ["name", "url"]}],
        },
        "remove duplicate rows": {
            "operations": [{"type": "drop_duplicates"}],
        },
        "sort by name in ascending order": {
            "operations": [{"type": "sort_values", "column": "name", "ascending": True}],
        },
        "keep only rows where name contains bulbasaur": {
            "operations": [{"type": "filter_rows", "column": "name", "operator": "contains", "value": "bulbasaur"}],
        },
        "fill missing values in the name column with unknown": {
            "operations": [{"type": "fillna", "column": "name", "value": "Unknown"}],
        },
    }
    plan = plans.get(normalized)
    if plan is None:
        return None

    # Validate the example against this dataset. If its schema is different,
    # leave it to the normal planner to explain or handle the custom schema.
    operation = plan["operations"][0]
    required = operation.get("columns", []) if operation["type"] == "select_columns" else [operation.get("column")]
    if operation["type"] == "drop_duplicates":
        required = []
    if any(column not in frame.columns for column in required):
        return None
    return plan


def parse_plan(value: Any) -> dict[str, Any]:
    if hasattr(value, "content"):
        value = value.content
    if isinstance(value, list):
        value = "".join(
            item.get("text", "") for item in value if isinstance(item, dict)
        )
    if not isinstance(value, str):
        raise TransformationPlanError("The planner did not return JSON text.")
    value = re.sub(r"^```(?:json)?\s*", "", value.strip(), flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value).strip()
    try:
        plan = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TransformationPlanError("The transformation plan was not valid JSON.") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("operations"), list):
        raise TransformationPlanError("The plan must contain an operations list.")
    if len(plan["operations"]) > 30:
        raise TransformationPlanError("The plan contains too many operations.")
    return plan


def apply_plan(frame: pd.DataFrame, plan: dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
    """Apply only the operations supported by the existing ETL agent."""
    if not isinstance(plan, dict) or not isinstance(plan.get("operations"), list):
        raise TransformationPlanError("The plan must contain an operations list.")
    if len(plan["operations"]) > 30:
        raise TransformationPlanError("The plan contains too many operations.")

    df = frame.copy()
    applied: list[str] = []
    for operation in plan["operations"]:
        if not isinstance(operation, dict):
            raise TransformationPlanError("Invalid transformation operation.")
        kind = operation.get("type")
        if kind == "select_columns":
            columns = operation.get("columns")
            if not isinstance(columns, list) or not columns:
                raise TransformationPlanError("select_columns requires a non-empty columns list.")
            _require_columns(df, columns)
            df = df[columns]
        elif kind == "drop_columns":
            columns = operation.get("columns")
            if not isinstance(columns, list):
                raise TransformationPlanError("drop_columns requires a columns list.")
            _require_columns(df, columns)
            df = df.drop(columns=columns)
        elif kind == "rename_columns":
            mapping = operation.get("mapping")
            if not isinstance(mapping, dict):
                raise TransformationPlanError("rename_columns requires a mapping object.")
            _require_columns(df, list(mapping))
            destinations = list(mapping.values())
            if not all(isinstance(name, str) and name for name in destinations):
                raise TransformationPlanError("Rename destinations must be non-empty strings.")
            if len(destinations) != len(set(destinations)):
                raise TransformationPlanError("Rename destinations must be unique.")
            unaffected = [column for column in df.columns if column not in mapping]
            if set(destinations) & set(unaffected):
                raise TransformationPlanError("A rename destination already exists.")
            df = df.rename(columns=mapping)
        elif kind == "drop_duplicates":
            columns = operation.get("columns")
            if columns is not None:
                if not isinstance(columns, list):
                    raise TransformationPlanError("drop_duplicates columns must be a list.")
                _require_columns(df, columns)
            df = df.drop_duplicates(subset=columns)
        elif kind == "sort_values":
            column = operation.get("column")
            _require_columns(df, [column])
            ascending = operation.get("ascending", True)
            if not isinstance(ascending, bool):
                raise TransformationPlanError("ascending must be true or false.")
            df = df.sort_values(by=column, ascending=ascending)
        elif kind == "filter_rows":
            column, operator, value = (
                operation.get("column"), operation.get("operator"), operation.get("value")
            )
            _require_columns(df, [column])
            if operator not in {"==", "!=", ">", ">=", "<", "<=", "contains"}:
                raise TransformationPlanError("Unsupported filter operator.")
            series = df[column]
            if operator == "contains":
                mask = series.astype("string").str.contains(
                    str(value), case=False, na=False, regex=False
                )
            elif operator == "==":
                mask = series == value
            elif operator == "!=":
                mask = series != value
            else:
                numeric_series = pd.to_numeric(series, errors="coerce")
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError) as exc:
                    raise TransformationPlanError("Numeric comparison requires a number.") from exc
                mask = {
                    ">": numeric_series > numeric_value,
                    ">=": numeric_series >= numeric_value,
                    "<": numeric_series < numeric_value,
                    "<=": numeric_series <= numeric_value,
                }[operator]
            df = df.loc[mask].copy()
        elif kind == "fillna":
            column = operation.get("column")
            _require_columns(df, [column])
            if "value" not in operation:
                raise TransformationPlanError("fillna requires a value.")
            df[column] = df[column].fillna(operation["value"])
        else:
            raise TransformationPlanError(f"Unsupported transformation: {kind}")
        applied.append(kind)
    return df, applied


def _require_columns(frame: pd.DataFrame, columns: list[Any]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise TransformationPlanError(f"Unknown columns: {missing}")

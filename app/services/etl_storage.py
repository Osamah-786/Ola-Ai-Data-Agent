"""Validated managed storage and persistent manifest for web ETL datasets."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import pandas as pd

FORMATS = {"csv": ".csv", "json": ".json", "parquet": ".parquet"}
MAX_DATASET_BYTES = 25 * 1024 * 1024
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "app_data" / "generated"


class DatasetNotFoundError(LookupError):
    pass


class DatasetStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or os.getenv("ETL_STORAGE_ROOT", DEFAULT_ROOT)).resolve()
        self.manifest_path = self.root / "manifest.json"
        self._lock = RLock()

    def create(self, frame: pd.DataFrame, output_format: str, kind: str,
               source_file_id: str | None = None, operations: list[str] | None = None) -> dict[str, Any]:
        if output_format not in FORMATS:
            raise ValueError("Unsupported output format.")
        if kind not in {"extract", "transform"}:
            raise ValueError("Unsupported dataset kind.")
        file_id = uuid4().hex
        folder = self.root / ("extracts" if kind == "extract" else "transforms") / file_id
        path = (folder / f"dataset{FORMATS[output_format]}").resolve()
        self._ensure_contained(path)
        folder.mkdir(parents=True, exist_ok=False)
        try:
            save_frame(frame, path, output_format)
            if path.stat().st_size > MAX_DATASET_BYTES:
                raise OSError("Generated dataset exceeds the managed size limit.")
            item = {
                "file_id": file_id,
                "format": output_format,
                "records": int(len(frame)),
                "columns": [str(column) for column in frame.columns],
                "kind": kind,
                "source_file_id": source_file_id,
                "operations": operations or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "_relative_path": path.relative_to(self.root).as_posix(),
            }
            with self._lock:
                datasets = self._read_manifest()
                datasets[file_id] = item
                self.root.mkdir(parents=True, exist_ok=True)
                temporary = self.root / f"manifest.{uuid4().hex}.tmp"
                try:
                    temporary.write_text(json.dumps(datasets, ensure_ascii=False), encoding="utf-8")
                    os.replace(temporary, self.manifest_path)
                finally:
                    temporary.unlink(missing_ok=True)
            return self.public_metadata(item)
        except Exception:
            path.unlink(missing_ok=True)
            try:
                folder.rmdir()
            except OSError:
                pass
            raise

    def get(self, file_id: str) -> tuple[dict[str, Any], Path]:
        if not ID_PATTERN.fullmatch(file_id):
            raise DatasetNotFoundError("Dataset was not found.")
        with self._lock:
            item = self._read_manifest().get(file_id)
        if not isinstance(item, dict):
            raise DatasetNotFoundError("Dataset was not found.")
        relative_path = item.get("_relative_path")
        if not isinstance(relative_path, str):
            raise DatasetNotFoundError("Dataset was not found.")
        path = (self.root / relative_path).resolve()
        self._ensure_contained(path)
        if path.suffix != FORMATS.get(item.get("format")) or not path.is_file():
            raise DatasetNotFoundError("Dataset file is unavailable.")
        return self.public_metadata(item), path

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._read_manifest().values())
        return [self.public_metadata(item) for item in items if isinstance(item, dict)]

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise OSError("Dataset registry is unavailable.") from None
        if not isinstance(data, dict):
            raise OSError("Dataset registry is invalid.")
        return data

    def _ensure_contained(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise OSError("Dataset path is outside managed storage.") from exc

    @staticmethod
    def public_metadata(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if not key.startswith("_")}


def save_frame(frame: pd.DataFrame, path: Path, output_format: str) -> None:
    if output_format == "csv":
        frame.to_csv(path, index=False)
    elif output_format == "json":
        frame.to_json(path, orient="records", lines=True, force_ascii=False, date_format="iso")
    elif output_format == "parquet":
        frame.to_parquet(path, index=False)
    else:
        raise ValueError("Unsupported output format.")


def read_frame(path: Path, output_format: str) -> pd.DataFrame:
    if output_format == "csv":
        return pd.read_csv(path)
    if output_format == "json":
        return pd.read_json(path, lines=True)
    if output_format == "parquet":
        return pd.read_parquet(path)
    raise ValueError("Unsupported dataset format.")


def json_value(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (dict, list, tuple)):
        return [json_value(item) for item in value] if isinstance(value, (list, tuple)) else {
            str(key): json_value(item) for key, item in value.items()
        }
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


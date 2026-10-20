"""ETL API tests use temporary storage, fake DNS and mocked HTTP only."""

import json
import socket
import builtins

import pandas as pd
import pytest
import requests
from fastapi import HTTPException

from app.api.etl import (
    _generate_plan,
    download_file,
    extract,
    preview_file,
    transform,
)
from app.services.etl_extraction import ExtractionError, extract_dataset, validate_public_url
from app.services.etl_storage import DatasetNotFoundError, DatasetStorage, read_frame
from app.services.etl_transform import TransformationPlanError, apply_plan
from app.main import app


@pytest.fixture
def storage(tmp_path):
    return DatasetStorage(tmp_path / "generated")


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("error")

    def iter_content(self, size):
        yield json.dumps(self.payload).encode()

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        self.urls.append(url)
        assert kwargs["allow_redirects"] is False
        return next(self.responses)


def public_dns(host, port, type):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]


def test_url_validation_rejects_unsafe_targets():
    for url in (
        "file:///etc/passwd", "http://user:password@example.com/", "http://localhost/",
        "http://127.0.0.1/", "http://10.0.0.2/", "http://169.254.169.254/latest/meta-data/",
    ):
        with pytest.raises(ExtractionError):
            validate_public_url(url, public_dns)


def test_dns_private_result_is_rejected():
    def private_dns(host, port, type):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", port))]
    with pytest.raises(ExtractionError):
        validate_public_url("https://public.example/data", private_dns)


def test_extraction_saves_mocked_paginated_response(storage):
    session = FakeSession([
        FakeResponse({"results": [{"id": 1}], "next": "https://api.example/next"}),
        FakeResponse({"results": [{"id": 2}], "next": None}),
    ])
    result = extract_dataset(
        "https://api.example/start", "csv", storage,
        session_factory=lambda: session, resolver=public_dns,
    )
    assert result["records"] == 2
    assert result["pages_fetched"] == 2
    metadata, path = storage.get(result["file_id"])
    assert metadata["columns"] == ["id"]
    assert len(read_frame(path, "csv")) == 2


def test_extraction_service_does_not_import_agent_or_groq(storage, monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"agents", "langchain_groq", "groq"}:
            raise AssertionError(f"LLM-related import attempted: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = extract_dataset(
        "https://api.example/one", "csv", storage,
        session_factory=lambda: FakeSession([FakeResponse([{"value": 1}])]),
        resolver=public_dns,
    )
    assert result["records"] == 1


def test_extract_endpoint_maps_mocked_result_without_external_request(storage, monkeypatch):
    import app.api.etl as etl_api
    from app.models.etl import ExtractRequest

    created = storage.create(pd.DataFrame([{"name": "example"}]), "csv", "extract")
    monkeypatch.setattr(etl_api, "extract_dataset", lambda url, fmt, registry: {
        **created, "pages_fetched": 1, "message": "Extraction completed."
    })
    result = extract(ExtractRequest(url="https://example.invalid/data", format="csv"), storage)
    assert result["status"] == "success"
    assert result["file_id"] == created["file_id"]
    assert result["records"] == 1
    assert result["pages_fetched"] == 1


def test_extraction_rejects_bad_format_and_redirect_to_private(storage):
    with pytest.raises(ExtractionError, match="formats"):
        extract_dataset("https://api.example", "exe", storage, resolver=public_dns)
    session = FakeSession([FakeResponse(None, 302, {"Location": "http://127.0.0.1/admin"})])
    with pytest.raises(ExtractionError):
        extract_dataset("https://api.example", "json", storage,
                       session_factory=lambda: session, resolver=public_dns)
    assert storage.list() == []


def test_extraction_rejects_malformed_json_and_repeated_pagination(storage):
    class InvalidJsonResponse(FakeResponse):
        def iter_content(self, size):
            yield b"not-json"
    with pytest.raises(ExtractionError, match="valid JSON"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: FakeSession([InvalidJsonResponse(None)]), resolver=public_dns)
    repeated = FakeSession([FakeResponse({"results": [{"x": 1}], "next": "https://api.example/one"})])
    with pytest.raises(ExtractionError, match="repeated"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: repeated, resolver=public_dns)
    assert storage.list() == []


def test_extraction_http_error_creates_no_dataset(storage):
    with pytest.raises(ExtractionError, match="HTTP 503"):
        extract_dataset("https://api.example/one", "csv", storage,
                       session_factory=lambda: FakeSession([FakeResponse({}, status=503)]), resolver=public_dns)
    assert storage.list() == []


def test_malformed_pagination_results_are_rejected_without_output(storage):
    with pytest.raises(ExtractionError, match="results must be a JSON array"):
        extract_dataset("https://api.example/one", "csv", storage,
                       session_factory=lambda: FakeSession([FakeResponse({"results": "invalid"})]),
                       resolver=public_dns)
    assert storage.list() == []


def test_extraction_enforces_response_size_limit(storage, monkeypatch):
    from app.services import etl_extraction
    monkeypatch.setattr(etl_extraction, "MAX_RESPONSE_BYTES", 5)
    with pytest.raises(ExtractionError, match="size limit"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: FakeSession([FakeResponse([{"text": "large"}])]), resolver=public_dns)
    assert storage.list() == []


def test_extraction_enforces_total_byte_page_and_record_bounds(storage, monkeypatch):
    from app.services import etl_extraction

    monkeypatch.setattr(etl_extraction, "MAX_TOTAL_RESPONSE_BYTES", 1)
    with pytest.raises(ExtractionError, match="total response-size limit"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: FakeSession([FakeResponse([{"x": 1}])]), resolver=public_dns)

    monkeypatch.setattr(etl_extraction, "MAX_TOTAL_RESPONSE_BYTES", 1024 * 1024)
    monkeypatch.setattr(etl_extraction, "MAX_PAGES", 1)
    with pytest.raises(ExtractionError, match="page limit"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: FakeSession([
                           FakeResponse({"results": [{"x": 1}], "next": "https://api.example/two"}),
                           FakeResponse({"results": [{"x": 2}], "next": None}),
                       ]), resolver=public_dns)

    monkeypatch.setattr(etl_extraction, "MAX_PAGES", 100)
    monkeypatch.setattr(etl_extraction, "MAX_RECORDS", 1)
    with pytest.raises(ExtractionError, match="record limit"):
        extract_dataset("https://api.example/one", "json", storage,
                       session_factory=lambda: FakeSession([FakeResponse([{"x": 1}, {"x": 2}])]), resolver=public_dns)
    assert storage.list() == []


def test_transform_mode_gates_before_planner_and_no_mock_dataset(storage, monkeypatch):
    calls = []
    source = storage.create(pd.DataFrame([{"name": "A"}]), "csv", "extract")
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "false")
    from app.models.etl import TransformRequest
    planner = lambda *_: calls.append("planner")
    with pytest.raises(HTTPException) as mock:
        transform(TransformRequest(input_file_id=source["file_id"], instruction="remove duplicates"), storage, planner)
    assert mock.value.status_code == 409
    with pytest.raises(HTTPException) as live:
        transform(TransformRequest(input_file_id=source["file_id"], instruction="remove duplicates", execution_mode="live"), storage, planner)
    assert live.value.status_code == 403
    assert calls == []
    assert len(storage.list()) == 1


def test_transform_endpoint_uses_fake_planner_and_creates_distinct_dataset(storage, monkeypatch):
    source = storage.create(pd.DataFrame([{"name": "A"}, {"name": "A"}, {"name": "B"}]), "csv", "extract")
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    from app.models.etl import TransformRequest
    payload = transform(TransformRequest(input_file_id=source["file_id"], instruction="Remove duplicate rows.",
        execution_mode="live", output_format="json"), storage,
        lambda *_: '{"operations": [{"type": "drop_duplicates"}]}')
    assert payload["file_id"] != source["file_id"]
    assert payload["operations"] == ["drop_duplicates"]
    _, output_path = storage.get(payload["file_id"])
    assert len(read_frame(output_path, "json")) == 2


@pytest.mark.parametrize(
    ("instruction", "expected_operation"),
    [
        ("Keep only the name and URL columns.", "select_columns"),
        ("Remove duplicate rows.", "drop_duplicates"),
        ("Sort by name in ascending order.", "sort_values"),
        ("Keep only rows where name contains bulbasaur.", "filter_rows"),
        ("Fill missing values in the name column with Unknown.", "fillna"),
    ],
)
def test_builtin_transform_examples_use_safe_plans_without_agent_import(
    storage, monkeypatch, instruction, expected_operation
):
    source = storage.create(
        pd.DataFrame(
            [
                {"name": "bulbasaur", "url": "url-1"},
                {"name": "ivysaur", "url": "url-2"},
                {"name": None, "url": "url-3"},
                {"name": "bulbasaur", "url": "url-1"},
            ]
        ),
        "csv",
        "extract",
    )
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "agents.etl_analyst":
            raise AssertionError("Built-in example unexpectedly imported the live ETL agent")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    from app.models.etl import TransformRequest

    result = transform(
        TransformRequest(
            input_file_id=source["file_id"],
            instruction=instruction,
            execution_mode="live",
            output_format="csv",
        ),
        storage,
        _generate_plan,
    )
    assert result["operations"] == [expected_operation]
    _, path = storage.get(result["file_id"])
    transformed = read_frame(path, "csv")
    if expected_operation == "select_columns":
        assert transformed.columns.tolist() == ["name", "url"]
    elif expected_operation == "drop_duplicates":
        assert len(transformed) == 3
    elif expected_operation == "sort_values":
        assert transformed["name"].dropna().tolist() == ["bulbasaur", "bulbasaur", "ivysaur"]
    elif expected_operation == "filter_rows":
        assert transformed["name"].tolist() == ["bulbasaur", "bulbasaur"]
    else:
        assert "Unknown" in transformed["name"].tolist()


def test_invalid_plan_does_not_create_output(storage, monkeypatch):
    source = storage.create(pd.DataFrame([{"name": "A"}]), "csv", "extract")
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    from app.models.etl import TransformRequest
    with pytest.raises(HTTPException) as response:
        transform(TransformRequest(input_file_id=source["file_id"], instruction="drop missing", execution_mode="live"),
                  storage, lambda *_: {"operations": [{"type": "drop_columns", "columns": ["missing"]}]})
    assert response.value.status_code == 422
    assert len(storage.list()) == 1


def test_empty_transform_plan_does_not_create_output(storage, monkeypatch):
    source = storage.create(pd.DataFrame([{"name": "A"}]), "csv", "extract")
    monkeypatch.setenv("ENABLE_LIVE_AGENTS", "true")
    from app.models.etl import TransformRequest
    with pytest.raises(HTTPException) as response:
        transform(TransformRequest(input_file_id=source["file_id"], instruction="do nothing", execution_mode="live"),
                  storage, lambda *_: '{"operations": []}')
    assert response.value.status_code == 422
    assert "no dataset was created" in response.value.detail
    assert len(storage.list()) == 1


def test_plan_application_is_constrained_and_requires_operation():
    frame = pd.DataFrame([{"name": "bulbasaur", "id": 1}, {"name": "ivysaur", "id": 2}])
    result, operations = apply_plan(frame, {"operations": [{"type": "filter_rows", "column": "name", "operator": "contains", "value": "bulba"}]})
    assert result["name"].tolist() == ["bulbasaur"]
    assert operations == ["filter_rows"]
    with pytest.raises(TransformationPlanError):
        apply_plan(frame, {"operations": [{"type": "execute_code"}]})
    unchanged, operations = apply_plan(frame, {"operations": []})
    assert unchanged.equals(frame)
    assert operations == []


def test_preview_download_pagination_and_unknown_ids(storage):
    created = storage.create(pd.DataFrame([{"value": i} for i in range(23)]), "csv", "extract")
    first = preview_file(created["file_id"], 1, 20, storage)
    second = preview_file(created["file_id"], 2, 20, storage)
    assert len(first["rows"]) == 20
    assert second["rows"] == [{"value": 20}, {"value": 21}, {"value": 22}]
    download = download_file(created["file_id"], storage)
    assert download.status_code == 200
    assert "ola-dataset-" in download.headers["content-disposition"]
    with pytest.raises(HTTPException) as missing:
        preview_file("ffffffffffffffffffffffffffffffff", 1, 20, storage)
    assert missing.value.status_code == 404


@pytest.mark.parametrize("output_format", ["csv", "json", "parquet"])
def test_managed_storage_round_trips_supported_formats(storage, output_format):
    frame = pd.DataFrame([{"value": 1, "name": "bulbasaur"}, {"value": 2, "name": "ivysaur"}])
    created = storage.create(frame, output_format, "extract")
    metadata, path = storage.get(created["file_id"])
    result = read_frame(path, metadata["format"])
    assert len(result) == 2
    assert metadata["columns"] == ["value", "name"]


def test_etl_routes_are_registered_in_api_contract():
    paths = app.openapi()["paths"]
    assert "/api/etl/extract" in paths
    assert "/api/etl/transform" in paths
    assert "/api/files/{file_id}/preview" in paths
    assert "/api/files/{file_id}/download" in paths
    parameters = paths["/api/files/{file_id}/preview"]["get"]["parameters"]
    page_size = next(parameter for parameter in parameters if parameter["name"] == "page_size")
    assert page_size["schema"]["maximum"] == 100


def test_storage_registry_survives_restart_and_rejects_corrupt_mapping(tmp_path):
    first = DatasetStorage(tmp_path / "generated")
    item = first.create(pd.DataFrame([{"value": 1}]), "csv", "extract")
    restarted = DatasetStorage(tmp_path / "generated")
    assert restarted.get(item["file_id"])[0]["records"] == 1
    manifest = restarted.manifest_path
    data = json.loads(manifest.read_text())
    data[item["file_id"]]["_relative_path"] = "../outside.csv"
    manifest.write_text(json.dumps(data))
    with pytest.raises(OSError):
        restarted.get(item["file_id"])


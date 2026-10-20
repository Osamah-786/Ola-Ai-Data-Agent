from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from utils.safe_http import (
    MAX_RESPONSE_BYTES,
    UnsafeInputError,
    request_json,
    resolve_data_path,
    validate_public_url,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def public_resolver(host, port, type):
    return [(None, None, None, None, ("93.184.216.34", port))]


def test_public_http_url_is_accepted_with_injected_dns():
    assert validate_public_url("https://example.test/api", public_resolver) == (
        "https://example.test/api"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/private",
        "http://127.0.0.1/private",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:password@example.test/",
    ],
)
def test_local_metadata_and_non_http_urls_are_rejected(url):
    with pytest.raises(UnsafeInputError):
        validate_public_url(url, public_resolver)


def test_dns_resolution_to_private_address_is_rejected():
    def private_resolver(host, port, type):
        return [(None, None, None, None, ("10.0.0.5", port))]

    with pytest.raises(UnsafeInputError):
        validate_public_url("https://internal.example/", private_resolver)


def test_redirect_to_local_address_is_rejected_before_following():
    class RedirectResponse:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/admin"}

        def close(self):
            pass

    class FakeSession:
        calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            return RedirectResponse()

    session = FakeSession()
    with pytest.raises(UnsafeInputError):
        request_json(session, "https://example.test/start", public_resolver)
    assert session.calls == 1


def test_http_response_size_is_bounded():
    class LargeResponse:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"x" * (MAX_RESPONSE_BYTES + 1)

        def close(self):
            pass

    class FakeSession:
        def get(self, *args, **kwargs):
            return LargeResponse()

    with pytest.raises(UnsafeInputError, match="size limit"):
        request_json(FakeSession(), "https://example.test/data", public_resolver)


def test_data_path_is_confined_and_rejects_absolute_escape(tmp_path):
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    assert resolve_data_path(project, "data/input.csv") == project / "data/input.csv"
    with pytest.raises(UnsafeInputError):
        resolve_data_path(project, "../outside.csv")
    with pytest.raises(UnsafeInputError):
        resolve_data_path(project, tmp_path / "outside.csv")


def test_etl_tools_have_no_arbitrary_code_execution_method():
    from utils.etl_tools import ETLTools

    assert not hasattr(ETLTools, "execute_code")


def test_legacy_etl_extract_rejects_outside_output_before_network(monkeypatch, tmp_path):
    import utils.etl_tools as legacy_etl

    def unexpected_request(*args, **kwargs):
        raise AssertionError("network request attempted")

    monkeypatch.setattr(legacy_etl, "request_json", unexpected_request)
    tool = legacy_etl.ETLTools.__new__(legacy_etl.ETLTools)
    tool.project_root = tmp_path
    result = tool.extract_load("https://example.test/", "../outside", "csv")
    assert "data directory" in result


def test_legacy_etl_context_rejects_outside_input(tmp_path):
    from utils.etl_tools import ETLTools

    tool = ETLTools.__new__(ETLTools)
    tool.project_root = tmp_path
    result = tool.transform_load_context(tmp_path / "outside.csv")
    assert "data directory" in result


def test_schema_context_uses_metadata_only_and_has_no_write_sql_method():
    from utils.database import DatabaseUtil

    class FakeCursor:
        def __init__(self):
            self.queries = []
            self.results = [
                [("records",)],
                [("record_id", "integer"), ("label", "text")],
            ]

        def execute(self, query, params=None):
            self.queries.append(str(query))

        def fetchall(self):
            return self.results.pop(0)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

    util = DatabaseUtil.__new__(DatabaseUtil)
    util.connection = FakeConnection()
    result = util.schema_details("public")

    assert "record_id" in result and "label" in result
    assert "Sample Data" not in result
    assert len(util.connection.fake_cursor.queries) == 2
    assert all("SELECT *" not in query for query in util.connection.fake_cursor.queries)
    assert not hasattr(DatabaseUtil, "execute_sql")


def test_feed_loader_import_and_missing_confirmation_do_not_connect(monkeypatch):
    import psycopg2

    def unexpected_connect(*args, **kwargs):
        raise AssertionError("database connection attempted")

    monkeypatch.setattr(psycopg2, "connect", unexpected_connect)
    loader = PROJECT_ROOT / "scripts" / "database" / "feed_db.py"
    runpy.run_path(str(loader), run_name="safe_import_check")

    monkeypatch.setattr(sys, "argv", [str(loader)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(loader), run_name="__main__")
    assert exc.value.code == 2


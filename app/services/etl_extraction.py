"""Bounded extraction from user-selected public HTTP APIs."""

from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests

from app.services.etl_storage import DatasetStorage

MAX_PAGES = 100
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_RECORDS = 100_000
TIMEOUT = (4, 12)
REDIRECT_CODES = {301, 302, 303, 307, 308}


class ExtractionError(ValueError):
    pass


def validate_public_url(url: str, resolver=socket.getaddrinfo) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ExtractionError("Only HTTP and HTTPS URLs are supported.")
        if parsed.username is not None or parsed.password is not None:
            raise ExtractionError("URLs with embedded credentials are not allowed.")
        hostname = parsed.hostname
        if not hostname:
            raise ExtractionError("A valid host is required.")
        if hostname.lower().rstrip(".") in {"localhost", "metadata.google.internal"}:
            raise ExtractionError("Local and metadata destinations are not allowed.")
        try:
            addresses = {ipaddress.ip_address(hostname)}
        except ValueError:
            try:
                results = resolver(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
                addresses = {ipaddress.ip_address(result[4][0].split("%", 1)[0]) for result in results}
            except (OSError, ValueError, IndexError, TypeError) as exc:
                raise ExtractionError("The destination host could not be resolved safely.") from exc
        if not addresses:
            raise ExtractionError("The destination host has no usable address.")
        for address in addresses:
            if not address.is_global or address.is_multicast or address.is_reserved:
                raise ExtractionError("Private, local, reserved, and metadata destinations are not allowed.")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, ExtractionError):
            raise
        raise ExtractionError("The URL is invalid.") from exc


def _request_json(session: requests.Session, url: str, resolver) -> tuple[object, str, int]:
    current = validate_public_url(url, resolver)
    seen = set()
    for _ in range(6):
        if current in seen:
            raise ExtractionError("The API returned a repeated redirect URL.")
        seen.add(current)
        try:
            response = session.get(current, timeout=TIMEOUT, stream=True, allow_redirects=False)
        except requests.RequestException as exc:
            raise ExtractionError("The selected API request failed.") from exc
        if response.status_code in REDIRECT_CODES:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ExtractionError("The API returned a redirect without a destination.")
            current = validate_public_url(urljoin(current, location), resolver)
            continue
        try:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise ExtractionError("The API response exceeded the size limit.")
                chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ExtractionError("The API response was not valid JSON.") from exc
            return data, current, size
        except requests.HTTPError as exc:
            raise ExtractionError(f"The selected API returned HTTP {response.status_code}.") from exc
        except requests.RequestException as exc:
            raise ExtractionError("The selected API response could not be read.") from exc
        finally:
            response.close()
    raise ExtractionError("The API exceeded the redirect limit.")


def extract_dataset(url: str, output_format: str, storage: DatasetStorage,
                    *, session_factory=requests.Session, resolver=socket.getaddrinfo) -> dict:
    if output_format not in {"csv", "json", "parquet"}:
        raise ExtractionError("Supported formats are csv, json, and parquet.")
    records = []
    current_url = validate_public_url(url, resolver)
    visited = set()
    pages = 0
    total_bytes = 0
    with session_factory() as session:
        while current_url:
            current_url = validate_public_url(current_url, resolver)
            if current_url in visited:
                raise ExtractionError("Pagination stopped because the next URL repeated.")
            if pages >= MAX_PAGES:
                raise ExtractionError("Pagination exceeded the page limit.")
            visited.add(current_url)
            page_data, response_url, page_bytes = _request_json(session, current_url, resolver)
            data = page_data
            total_bytes += page_bytes
            if total_bytes > MAX_TOTAL_RESPONSE_BYTES:
                raise ExtractionError("The extraction exceeded the total response-size limit.")
            pages += 1
            if isinstance(data, list):
                records.extend(data)
                current_url = ""
            elif isinstance(data, dict) and "results" in data:
                if not isinstance(data["results"], list):
                    raise ExtractionError("Paginated API results must be a JSON array.")
                records.extend(data["results"])
                next_url = data.get("next")
                if next_url is None or next_url == "":
                    current_url = ""
                elif not isinstance(next_url, str):
                    raise ExtractionError("Pagination next URL must be a string or null.")
                else:
                    current_url = urljoin(response_url, next_url)
            elif isinstance(data, dict) and pages == 1:
                records.append(data)
                current_url = ""
            else:
                raise ExtractionError("The API returned an unsupported JSON structure.")
            if len(records) > MAX_RECORDS:
                raise ExtractionError("The extraction exceeded the record limit.")
    frame = pd.json_normalize(records)
    try:
        metadata = storage.create(frame, output_format, "extract")
    except (OSError, ImportError, ValueError) as exc:
        raise ExtractionError("The extracted dataset could not be stored.") from exc
    metadata.update({"pages_fetched": pages, "message": "Extraction completed."})
    return metadata


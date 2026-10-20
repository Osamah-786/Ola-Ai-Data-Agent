"""Small safety helpers for legacy ETL HTTP and filesystem access."""

from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT = (4, 12)
REDIRECT_CODES = {301, 302, 303, 307, 308}


class UnsafeInputError(ValueError):
    """Raised when a legacy tool receives an unsafe URL or local path."""


def resolve_data_path(project_root: Path, user_path: str | Path) -> Path:
    """Resolve a path and require it to stay under the project data folder."""
    data_root = (project_root / "data").resolve()
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(data_root):
        raise UnsafeInputError("Paths must stay inside the project data directory.")
    return resolved


def validate_public_url(url: str, resolver=socket.getaddrinfo) -> str:
    """Accept only HTTP(S) URLs whose resolved addresses are public IPs."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise UnsafeInputError("Only HTTP and HTTPS URLs are supported.")
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeInputError("URLs containing credentials are not allowed.")
        hostname = parsed.hostname
        if not hostname or hostname.lower().rstrip(".") in {
            "localhost", "metadata.google.internal"
        }:
            raise UnsafeInputError("Local and metadata destinations are not allowed.")
        try:
            addresses = {ipaddress.ip_address(hostname)}
        except ValueError:
            records = resolver(
                hostname,
                parsed.port or (443 if parsed.scheme.lower() == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            addresses = {
                ipaddress.ip_address(record[4][0].split("%", 1)[0])
                for record in records
            }
        if not addresses or any(
            not address.is_global or address.is_multicast or address.is_reserved
            for address in addresses
        ):
            raise UnsafeInputError("Private, local, and reserved destinations are not allowed.")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))
    except UnsafeInputError:
        raise
    except (ValueError, UnicodeError, OSError, IndexError, TypeError) as exc:
        raise UnsafeInputError("The URL could not be validated safely.") from exc


def request_json(session: requests.Session, url: str, resolver=socket.getaddrinfo):
    """Fetch bounded JSON, validating every redirect and disabling auto-follow."""
    current = validate_public_url(url, resolver)
    seen: set[str] = set()
    for _ in range(MAX_REDIRECTS + 1):
        if current in seen:
            raise UnsafeInputError("The API returned a repeated redirect URL.")
        seen.add(current)
        response = session.get(
            current,
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=False,
        )
        if response.status_code in REDIRECT_CODES:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise UnsafeInputError("The API returned a redirect without a destination.")
            current = validate_public_url(urljoin(current, location), resolver)
            continue
        try:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise UnsafeInputError("The API response exceeded the size limit.")
                chunks.append(chunk)
            try:
                payload = json.loads(b"".join(chunks))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise UnsafeInputError("The API response was not valid JSON.") from exc
            return payload, current, total
        finally:
            response.close()
    raise UnsafeInputError("The API exceeded the redirect limit.")

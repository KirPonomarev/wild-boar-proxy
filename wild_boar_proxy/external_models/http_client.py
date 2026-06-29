"""Bounded HTTP helpers for route-level provider validation."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import errors

DEFAULT_PROVIDER_TIMEOUT_SECONDS = 5.0
RESPONSE_READ_CHUNK_BYTES = 65536
UNKNOWN_LENGTH_READ_CHUNK_BYTES = 1


@dataclass(frozen=True)
class HttpJsonResponse:
    status_code: int
    payload: Any
    latency_ms: int | None


def _open_request(request: urllib.request.Request, *, timeout_seconds: float):
    parsed = urllib.parse.urlparse(request.full_url)
    if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout_seconds)
    return urllib.request.urlopen(request, timeout=timeout_seconds)


def _set_response_socket_timeout(response: Any, timeout_seconds: float) -> None:
    candidates = [
        response,
        getattr(response, "_sock", None),
        getattr(response, "_fp", None),
        getattr(getattr(response, "_fp", None), "fp", None),
        getattr(getattr(getattr(response, "_fp", None), "fp", None), "raw", None),
        getattr(
            getattr(getattr(getattr(response, "_fp", None), "fp", None), "raw", None),
            "_sock",
            None,
        ),
        getattr(response, "fp", None),
        getattr(getattr(response, "fp", None), "raw", None),
        getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None),
    ]
    for candidate in candidates:
        setter = getattr(candidate, "settimeout", None)
        if callable(setter):
            try:
                setter(max(timeout_seconds, 0.001))
            except OSError:
                return
            return


def _response_content_length(response: Any) -> int | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        info = getattr(response, "info", None)
        if callable(info):
            headers = info()
    value = None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter("Content-Length")
    if value is None:
        return None
    try:
        length = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if length < 0:
        return None
    return length


def _is_complete_json_document(raw: bytes) -> bool:
    if not raw:
        return False
    try:
        text = raw.decode("utf-8")
        _, end = json.JSONDecoder().raw_decode(text)
    except (UnicodeDecodeError, ValueError):
        return False
    return not text[end:].strip()


def _read_response_body(
    response: Any,
    *,
    started_at: float,
    timeout_seconds: float,
) -> bytes:
    deadline = started_at + max(timeout_seconds, 0.001)
    body = bytearray()
    content_length = _response_content_length(response)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Provider response read timed out.")
        _set_response_socket_timeout(response, remaining)
        if content_length is not None:
            unread = content_length - len(body)
            if unread <= 0:
                return bytes(body)
            read_size = min(RESPONSE_READ_CHUNK_BYTES, unread)
        else:
            read_size = UNKNOWN_LENGTH_READ_CHUNK_BYTES
        chunk = response.read(read_size)
        if not chunk:
            return bytes(body)
        body.extend(chunk)
        if content_length is None and _is_complete_json_document(bytes(body)):
            return bytes(body)


def request_json(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
) -> HttpJsonResponse:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = dict(headers)
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    started_at = time.monotonic()
    try:
        with _open_request(request, timeout_seconds=timeout_seconds) as response:
            raw = _read_response_body(
                response,
                started_at=started_at,
                timeout_seconds=timeout_seconds,
            )
            parsed = json.loads(raw.decode("utf-8"))
            return HttpJsonResponse(
                status_code=response.status,
                payload=parsed,
                latency_ms=int((time.monotonic() - started_at) * 1000),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            parsed = {"raw_body": body.decode("utf-8", errors="replace")}
        return HttpJsonResponse(
            status_code=exc.code,
            payload=parsed,
            latency_ms=int((time.monotonic() - started_at) * 1000),
        )
    except urllib.error.URLError as exc:
        raise RuntimeErrorInfo(
            f"Provider network request failed: {exc.reason}",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            operator_action="retry",
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeErrorInfo(
            "Provider request timed out.",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            operator_action="retry",
        ) from exc

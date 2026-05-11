"""Bounded HTTP helpers for route-level provider validation."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import errors

DEFAULT_PROVIDER_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class HttpJsonResponse:
    status_code: int
    payload: Any
    latency_ms: int | None


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
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
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

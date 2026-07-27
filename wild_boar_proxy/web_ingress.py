# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import ipaddress
from typing import Any, Mapping
from urllib.parse import urlparse


MAX_WEB_REQUEST_BODY_BYTES = 64 * 1024
JSON_CONTENT_TYPE = "application/json"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def web_ingress_rejection_packet(
    *,
    machine_error_code: str,
    human_message: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "rejected",
        "source": "web_ingress",
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "request_rejected": True,
        "changed_files": [],
        "next_action": "fix_http_request",
    }


def unsafe_bind_requested(host: str) -> bool:
    normalized = _normalize_host(host)
    if normalized in {"0.0.0.0", "::"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_unspecified
    except ValueError:
        return False


def parse_content_length(headers: Mapping[str, str]) -> tuple[int, str | None]:
    raw_value = str(headers.get("Content-Length", "0") or "0").strip()
    try:
        length = int(raw_value)
    except ValueError:
        return 0, "WEB_INGRESS_CONTENT_LENGTH_INVALID"
    if length < 0:
        return 0, "WEB_INGRESS_CONTENT_LENGTH_INVALID"
    return length, None


def content_type_matches(headers: Mapping[str, str], expected: str) -> bool:
    raw_value = str(headers.get("Content-Type", "") or "")
    content_type = raw_value.split(";", 1)[0].strip().lower()
    return content_type == expected


def host_header_is_local(
    host_header: str | None,
    *,
    server_port: int,
) -> bool:
    parsed = _parse_host_header(host_header)
    if parsed is None:
        return False
    host, port = parsed
    if port is not None and port != server_port:
        return False
    return _is_loopback_host(host)


def origin_header_is_allowed(
    origin_header: str | None,
    *,
    host_header: str | None,
    server_port: int,
) -> bool:
    if not origin_header:
        return True
    host = _parse_host_header(host_header)
    if host is None:
        return False
    _request_host, request_port = host
    request_port = request_port or server_port
    parsed = urlparse(origin_header)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        origin_port = parsed.port
    except ValueError:
        return False
    if origin_port is None:
        origin_port = 443 if parsed.scheme == "https" else 80
    if origin_port != request_port:
        return False
    return _is_loopback_host(parsed.hostname)


def _parse_host_header(host_header: str | None) -> tuple[str, int | None] | None:
    value = str(host_header or "").strip()
    if not value:
        return None
    if "/" in value or "@" in value:
        return None
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return None
        host = value[1:end]
        rest = value[end + 1 :]
        if not rest:
            return _normalize_host(host), None
        if not rest.startswith(":"):
            return None
        return _host_with_port(host, rest[1:])
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        return _host_with_port(host, port)
    return _normalize_host(value), None


def _host_with_port(host: str, port_text: str) -> tuple[str, int | None] | None:
    if not port_text:
        return None
    try:
        port = int(port_text)
    except ValueError:
        return None
    if port <= 0 or port > 65535:
        return None
    return _normalize_host(host), port


def _normalize_host(host: str) -> str:
    return host.strip().strip("[]").rstrip(".").lower()


def _is_loopback_host(host: str) -> bool:
    normalized = _normalize_host(host)
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Server-owned web control token lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import hmac
from pathlib import Path
import secrets

from . import state_store

WEB_TOKEN_FILENAME = ".web-token"
WEB_TOKEN_MODE = 0o600
WEB_TOKEN_BYTES = 32
WEB_CSRF_BYTES = 32

WEB_AUTH_HEADER = "Authorization"
WEB_CSRF_HEADER = "X-WBP-CSRF"
WEB_TOKEN_META_NAME = "wbp-web-token"
WEB_CSRF_META_NAME = "wbp-csrf-token"
WEB_FORM_TOKEN_FIELD = "_wbp_web_token"
WEB_FORM_CSRF_FIELD = "_wbp_csrf_token"


@dataclass(frozen=True, repr=False)
class WebTokenState:
    token_path: Path | None
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)


def web_token_path(managed_dir: Path) -> Path:
    managed_root = Path(managed_dir).expanduser().resolve(strict=False)
    return managed_root / WEB_TOKEN_FILENAME


def create_web_token(managed_dir: Path) -> WebTokenState:
    token = secrets.token_urlsafe(WEB_TOKEN_BYTES)
    csrf_token = secrets.token_urlsafe(WEB_CSRF_BYTES)
    token_path = web_token_path(managed_dir)
    state_store.write_text(token_path, token, mode=WEB_TOKEN_MODE)
    return WebTokenState(token_path=token_path, token=token, csrf_token=csrf_token)


def create_in_memory_web_token() -> WebTokenState:
    return WebTokenState(
        token_path=None,
        token=secrets.token_urlsafe(WEB_TOKEN_BYTES),
        csrf_token=secrets.token_urlsafe(WEB_CSRF_BYTES),
    )


def verify_web_token(state: WebTokenState, candidate: str | None) -> bool:
    if candidate is None:
        return False
    token = str(candidate)
    if not token:
        return False
    return hmac.compare_digest(state.token, token)


def verify_web_csrf(state: WebTokenState, candidate: str | None) -> bool:
    if candidate is None:
        return False
    token = str(candidate)
    if not token:
        return False
    return hmac.compare_digest(state.csrf_token, token)


def authorization_bearer_token(value: str | None) -> str | None:
    if value is None:
        return None
    scheme, separator, token = str(value).strip().partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def web_post_token_valid(state: WebTokenState, headers: object) -> bool:
    header_get = getattr(headers, "get", None)
    if not callable(header_get):
        return False
    return verify_web_token(state, authorization_bearer_token(header_get(WEB_AUTH_HEADER)))


def web_post_csrf_valid(state: WebTokenState, headers: object) -> bool:
    header_get = getattr(headers, "get", None)
    if not callable(header_get):
        return False
    return verify_web_csrf(state, header_get(WEB_CSRF_HEADER))


def web_form_token_valid(state: WebTokenState, fields: dict[str, str]) -> bool:
    return verify_web_token(state, fields.get(WEB_FORM_TOKEN_FIELD))


def web_form_csrf_valid(state: WebTokenState, fields: dict[str, str]) -> bool:
    return verify_web_csrf(state, fields.get(WEB_FORM_CSRF_FIELD))


def delete_web_token(state: WebTokenState | None) -> None:
    if state is None or state.token_path is None:
        return
    try:
        if state.token_path.read_text(encoding="utf-8") != state.token:
            return
        state.token_path.unlink(missing_ok=True)
    except (OSError, UnicodeDecodeError):
        return

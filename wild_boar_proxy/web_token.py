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


@dataclass(frozen=True, repr=False)
class WebTokenState:
    token_path: Path
    token: str = field(repr=False)


def web_token_path(managed_dir: Path) -> Path:
    managed_root = Path(managed_dir).expanduser().resolve(strict=False)
    return managed_root / WEB_TOKEN_FILENAME


def create_web_token(managed_dir: Path) -> WebTokenState:
    token = secrets.token_urlsafe(WEB_TOKEN_BYTES)
    token_path = web_token_path(managed_dir)
    state_store.write_text(token_path, token, mode=WEB_TOKEN_MODE)
    return WebTokenState(token_path=token_path, token=token)


def verify_web_token(state: WebTokenState, candidate: str | None) -> bool:
    if candidate is None:
        return False
    token = str(candidate)
    if not token:
        return False
    return hmac.compare_digest(state.token, token)


def delete_web_token(state: WebTokenState | None) -> None:
    if state is None:
        return
    try:
        if state.token_path.read_text(encoding="utf-8") != state.token:
            return
        state.token_path.unlink(missing_ok=True)
    except (OSError, UnicodeDecodeError):
        return

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re
from typing import Literal


OK = "OK"
CONFIG_INVALID = "CONFIG_INVALID"
STATE_CORRUPT = "STATE_CORRUPT"
STATE_SCHEMA_UNSUPPORTED = "STATE_SCHEMA_UNSUPPORTED"
STATE_MIGRATION_FAILED = "STATE_MIGRATION_FAILED"
STATE_WRITE_FAILED = "STATE_WRITE_FAILED"
PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
PROCESS_FAILED = "PROCESS_FAILED"
RUNTIME_IDENTITY_MISMATCH = "RUNTIME_IDENTITY_MISMATCH"
AUTH_REQUIRED = "AUTH_REQUIRED"
ROUTE_ID_INVALID = "ROUTE_ID_INVALID"
REPAIR_REQUIRED = "REPAIR_REQUIRED"
REPAIR_FAILED = "REPAIR_FAILED"
LOCK_HELD = "LOCK_HELD"
LOCK_STALE = "LOCK_STALE"
COMMAND_PACKET_MALFORMED = "COMMAND_PACKET_MALFORMED"

CORE_MACHINE_ERROR_CODES = (
    CONFIG_INVALID,
    STATE_CORRUPT,
    STATE_SCHEMA_UNSUPPORTED,
    STATE_MIGRATION_FAILED,
    STATE_WRITE_FAILED,
    PROCESS_NOT_FOUND,
    PROCESS_TIMEOUT,
    PROCESS_FAILED,
    RUNTIME_IDENTITY_MISMATCH,
    AUTH_REQUIRED,
    ROUTE_ID_INVALID,
    REPAIR_REQUIRED,
    REPAIR_FAILED,
    LOCK_HELD,
    LOCK_STALE,
    COMMAND_PACKET_MALFORMED,
)

MachineErrorCodeClass = Literal["ok", "core", "legacy", "invalid_shape"]

_MACHINE_ERROR_CODE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def is_core_machine_error_code(code: object) -> bool:
    return isinstance(code, str) and code in CORE_MACHINE_ERROR_CODES


def is_machine_error_code_token(code: object) -> bool:
    return isinstance(code, str) and bool(_MACHINE_ERROR_CODE_TOKEN_RE.fullmatch(code))


def classify_machine_error_code(code: object) -> MachineErrorCodeClass:
    if code == OK:
        return "ok"
    if is_core_machine_error_code(code):
        return "core"
    if is_machine_error_code_token(code):
        return "legacy"
    return "invalid_shape"

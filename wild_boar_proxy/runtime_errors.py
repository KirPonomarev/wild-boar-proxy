# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations


class RuntimeErrorInfo(Exception):
    def __init__(
        self,
        message: str,
        *,
        machine_error_code: str,
        severity: str = "fatal",
        operator_action: str = "stop",
        next_action: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.machine_error_code = machine_error_code
        self.severity = severity
        self.operator_action = operator_action
        self.next_action = next_action if next_action is not None else operator_action
        self.exit_code = exit_code

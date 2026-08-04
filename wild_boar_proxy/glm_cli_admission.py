# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""GLM CLI admission evaluation (B12_ADMISSION).

Per the plan, GLM CLI is implemented only after official-client, tool,
auth, license, and Coding Plan admission; `API_ONLY` is a valid terminal
result. This module evaluates admission from local facts only (PATH
resolution), never assumes missing evidence, never touches the main Codex
surface (owner safety override), and never makes network calls.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .runtime import build_command_payload

# Declared official GLM CLI candidate names (PATH resolution only).
GLM_CLI_CANDIDATES = ("glm", "zai", "zhipu", "glm-cli", "zai-cli", "zhipu-cli")

GLM_ADMISSION_SCHEMA_VERSION = 1

GLM_ADMITTED = "ADMITTED"
GLM_NOT_ADMITTED = "NOT_ADMITTED"
GLM_API_ONLY_TERMINAL = "API_ONLY"

GLM_OK = "OK"
GLM_ADMISSION_DENIED = "GLM_CLI_ADMISSION_DENIED"


def probe_glm_cli_presence() -> dict[str, Any]:
    """PATH-only presence probe for official GLM CLI candidates.

    Never reads `~/.codex`, main auth stores, or Codex credentials.
    """
    found: dict[str, str] = {}
    checked: list[str] = []
    for candidate in GLM_CLI_CANDIDATES:
        resolved = shutil.which(candidate)
        checked.append(candidate)
        if resolved:
            found[candidate] = str(Path(resolved).resolve())
    return {
        "checked_candidates": checked,
        "found_candidates": found,
        "official_client_found": bool(found),
        "probe_surface": "path_resolution_only",
        "codex_surface_touched": False,
    }


def evaluate_glm_cli_admission() -> dict[str, Any]:
    """Evaluate GLM CLI admission from local facts.

    Decision rule: ADMITTED only when official client AND auth AND
    license/Coding Plan are all confirmed. Missing any criterion fails
    closed to NOT_ADMITTED with the terminal result API_ONLY.
    """
    presence = probe_glm_cli_presence()
    official_client_found = presence["official_client_found"]

    auth_available = False
    auth_evidence: str = "no_official_client"
    if official_client_found:
        # Auth presence is only checkable through the client's own
        # declared surface; with a client found we still require an
        # explicit auth confirmation that only the owner can provide.
        # In B12_ADMISSION, auth is not assumed from the client's
        # existence alone.
        auth_evidence = "not_confirmed_without_owner_auth_check"

    license_confirmed = False
    license_evidence: str = "no_official_client"
    if official_client_found:
        license_evidence = "not_confirmed_without_license_evidence"

    coding_plan_admitted = False
    coding_plan_evidence: str = "no_official_client"
    if official_client_found:
        coding_plan_evidence = "not_confirmed_without_coding_plan_evidence"

    criteria = {
        "official_client": {
            "confirmed": official_client_found,
            "evidence": presence["found_candidates"] if official_client_found else "not_found",
        },
        "tool": {
            "confirmed": official_client_found,
            "evidence": "client_tooling_requires_official_client",
        },
        "auth": {
            "confirmed": auth_available,
            "evidence": auth_evidence,
        },
        "license": {
            "confirmed": license_confirmed,
            "evidence": license_evidence,
        },
        "coding_plan": {
            "confirmed": coding_plan_admitted,
            "evidence": coding_plan_evidence,
        },
    }
    admitted = all(criterion["confirmed"] for criterion in criteria.values())
    return build_command_payload(
        ok=True,
        human_message=(
            "GLM CLI admission granted." if admitted
            else "GLM CLI not admitted; terminal result API_ONLY."
        ),
        machine_error_code=GLM_OK if admitted else GLM_ADMISSION_DENIED,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "schema_version": GLM_ADMISSION_SCHEMA_VERSION,
            "decision": GLM_ADMITTED if admitted else GLM_NOT_ADMITTED,
            "terminal_result": None if admitted else GLM_API_ONLY_TERMINAL,
            "criteria": criteria,
            "codex_surface_touched": presence["codex_surface_touched"],
            "probe_surface": presence["probe_surface"],
            "next_phase": "B12_CODE_IF_ADMITTED" if admitted else "NONE_API_ONLY",
            "resume_supported": False,
        },
    )

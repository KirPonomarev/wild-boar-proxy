# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Optional persistent ACP admission (B15_OPTIONAL).

Performs the physical protocol admission for the optional persistent ACP
(Agent Client Protocol) surface. If the protocol is unavailable or
unstable, the stage closes as `OPTIONAL_DEFERRED_ACP` with evidence. The
probe makes no network calls and touches no credential stores; admission
is never assumed.
"""

from __future__ import annotations

import shutil
from typing import Any

from .runtime import build_command_payload

ACP_SCHEMA_VERSION = 1

# Declared ACP server/client binary candidates (PATH resolution only).
ACP_BINARY_CANDIDATES = ("acp", "acp-server", "acp-client", "agent-client-protocol")

# Repository transport kind for ACP exists but has no runtime.
ACP_TRANSPORT_KIND = "cli_acp"

ACP_DEFERRED_TERMINAL = "OPTIONAL_DEFERRED_ACP"
ACP_ADMITTED = "ACP_ADMITTED"

ACP_OK = "OK"
ACP_NOT_ADMITTED = "ACP_PHYSICAL_ADMISSION_NOT_PASSED"


def probe_acp_availability() -> dict[str, Any]:
    """Local physical probe: binary candidates + repository presence.

    PATH resolution only; no network, no credential stores.
    """
    found: dict[str, str] = {}
    checked: list[str] = []
    for candidate in ACP_BINARY_CANDIDATES:
        resolved = shutil.which(candidate)
        checked.append(candidate)
        if resolved:
            found[candidate] = resolved
    return {
        "checked_binary_candidates": checked,
        "found_binaries": found,
        "repo_transport_kind_declared": ACP_TRANSPORT_KIND,
        "repo_acp_runtime_implemented": False,
        "physical_server_available": bool(found),
        "probe_surface": "path_resolution_only",
        "network_calls_made": False,
        "credential_stores_touched": False,
    }


def evaluate_optional_acp() -> dict[str, Any]:
    """Evaluate persistent ACP admission from local facts.

    Admitted only when a physical ACP server is available AND a stable
    repository runtime is implemented. Anything missing fails closed to
    the terminal `OPTIONAL_DEFERRED_ACP`.
    """
    facts = probe_acp_availability()
    server_available = facts["physical_server_available"]
    runtime_implemented = facts["repo_acp_runtime_implemented"]
    admitted = server_available and runtime_implemented
    criteria = {
        "physical_server": {
            "confirmed": server_available,
            "evidence": facts["found_binaries"] if server_available else "not_found",
        },
        "stable_repository_runtime": {
            "confirmed": runtime_implemented,
            "evidence": "transport_kind_enum_only",
        },
    }
    return build_command_payload(
        ok=True,
        human_message=(
            "Persistent ACP admitted." if admitted
            else "Persistent ACP unavailable/unstable; terminal result OPTIONAL_DEFERRED_ACP."
        ),
        machine_error_code=ACP_OK if admitted else ACP_NOT_ADMITTED,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "schema_version": ACP_SCHEMA_VERSION,
            "decision": ACP_ADMITTED if admitted else ACP_DEFERRED_TERMINAL,
            "terminal_result": None if admitted else ACP_DEFERRED_TERMINAL,
            "criteria": criteria,
            "probe": facts,
            "next_phase": "B15_ACP_IMPLEMENTATION" if admitted else "NONE_DEFERRED",
        },
    )


__all__ = [
    "ACP_DEFERRED_TERMINAL",
    "probe_acp_availability",
    "evaluate_optional_acp",
]

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Optional isolated Codex CLI deferral (B16_OPTIONAL).

Records the default outcome `CODEX_CLI_EXTENSION=DEFERRED`. Execution
would require a separate exact owner marker, a dedicated account, a
separate home, a file credential store, and proof of no
main-account/keyring reuse — none of which exist; the owner approval
marker is `NONE` and the owner safety override forbids the main Codex
surface. This module is probe-free: it never runs, reads, or modifies
anything under the main Codex surface.
"""

from __future__ import annotations

from typing import Any

from .runtime import build_command_payload

CODEX_CLI_DEFERRAL_SCHEMA_VERSION = 1
CODEX_CLI_DEFERRED_OUTCOME = "CODEX_CLI_EXTENSION=DEFERRED"


def evaluate_codex_cli_deferral(
    *,
    owner_marker_present: bool = False,
    dedicated_account_present: bool = False,
    separate_home_present: bool = False,
    file_credential_store_present: bool = False,
    no_main_keyring_reuse_proven: bool = False,
    safety_override_in_force: bool = True,
    codex_cli_experiment_authorized: bool = False,
) -> dict[str, Any]:
    """Record the deferral facts and return the terminal outcome.

    Fail-closed: DEFERRED unless every execution prerequisite is present
    AND the owner has granted the separate exact marker.
    """
    facts = {
        "owner_exact_marker_present": bool(owner_marker_present),
        "dedicated_account_present": bool(dedicated_account_present),
        "separate_home_present": bool(separate_home_present),
        "file_credential_store_present": bool(file_credential_store_present),
        "no_main_account_keyring_reuse_proven": bool(no_main_keyring_reuse_proven),
        "safety_override_in_force": bool(safety_override_in_force),
        "codex_cli_experiment_authorized": bool(codex_cli_experiment_authorized),
    }
    prerequisites_met = all(
        (
            facts["owner_exact_marker_present"],
            facts["dedicated_account_present"],
            facts["separate_home_present"],
            facts["file_credential_store_present"],
            facts["no_main_account_keyring_reuse_proven"],
            facts["codex_cli_experiment_authorized"],
        )
    )
    if facts["safety_override_in_force"]:
        prerequisites_met = False
    deferred = not prerequisites_met
    return build_command_payload(
        ok=True,
        human_message=(
            "Optional isolated Codex CLI deferred by default."
            if deferred
            else "Optional isolated Codex CLI admitted (unreachable without a new owner marker)."
        ),
        machine_error_code="OK" if deferred else "CODEX_CLI_ADMITTED",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "schema_version": CODEX_CLI_DEFERRAL_SCHEMA_VERSION,
            "outcome": CODEX_CLI_DEFERRED_OUTCOME if deferred else "CODEX_CLI_EXTENSION=ADMITTED",
            "deferred": deferred,
            "facts": facts,
            "codex_surface_touched": False,
            "probe_free_module": True,
        },
    )


__all__ = ["CODEX_CLI_DEFERRED_OUTCOME", "evaluate_codex_cli_deferral"]

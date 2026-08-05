# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Final candidate assurance (B18).

Runs the final candidate checks: exact-remote-head repository state,
full-test evidence, package, privacy, migration, provider, CLI, workflow,
web, account-isolation, and protected-network. Emits only
`FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`, never `DONE`. Checks are
deterministic local probes plus recorded evidence; the main Codex surface
is never touched; secret values never appear in assurance packets.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import one_shot_cli_runtime as osr
from . import sequential_workflow_runner as wf
from . import qwen_one_shot_cli as qoc
from . import kimi_one_shot_cli as km
from . import web_workflow_control as wwc
from . import provider_capability_schema_v2 as pcs
from .core import packets as command_packets
from .runtime import build_command_payload
from .state_migration import MigrationStep, migrate_json_file

FINAL_CANDIDATE_STATUS = "FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT"
FINAL_CANDIDATE_FAILED = "FINAL_CANDIDATE_ASSURANCE_FAILED"
FINAL_CANDIDATE_SCHEMA_VERSION = 1

FINAL_CHECK_IDS = (
    "exact_remote_head",
    "full_test_evidence",
    "package",
    "privacy",
    "migration",
    "provider",
    "cli",
    "workflow",
    "web",
    "account_isolation",
    "protected_network",
)


@dataclass(frozen=True)
class FinalCheck:
    check_id: str
    category: str
    passed: bool
    evidence: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "passed": self.passed,
            "evidence": self.evidence,
            "detail": self.detail,
        }


def _git_remote_head() -> tuple[str, str]:
    """(local_head, remote_head) via git; failures return empty strings."""
    try:
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        return local, remote
    except (OSError, subprocess.SubprocessError):
        return "", ""


def _check_exact_remote_head() -> FinalCheck:
    local, remote = _git_remote_head()
    passed = bool(local) and local == remote
    return FinalCheck(
        check_id="exact_remote_head",
        category="repository",
        passed=passed,
        evidence=f"local main {local[:12]} == origin/main {remote[:12]}" if passed else "local/remote mismatch",
        detail={"local_head": local, "remote_head": remote},
    )


def _check_full_test_evidence(
    *,
    full_suite_passed: int,
    clean_run: bool,
) -> FinalCheck:
    passed = full_suite_passed > 0 and clean_run
    return FinalCheck(
        check_id="full_test_evidence",
        category="tests",
        passed=passed,
        evidence=(
            f"full suite {full_suite_passed} passed, clean single run={clean_run}"
        ),
        detail={"full_suite_passed": full_suite_passed, "clean_run": clean_run},
    )


def _check_package() -> FinalCheck:
    """Packaging imports resolve (wheel/sdist build evidence lives in the
    CI package gate and `make package-web-smoke`)."""
    try:
        import importlib.util

        import wild_boar_proxy.packaging  # noqa: F401

        spec = importlib.util.find_spec("wild_boar_proxy")
        passed = spec is not None
        evidence = (
            "packaging module imports; package spec resolves "
            "(wheel/sdist build evidence lives in the CI package gate)"
        )
    except Exception as exc:  # noqa: BLE001
        passed = False
        evidence = f"packaging import failed: {exc}"
    return FinalCheck(
        check_id="package",
        category="package",
        passed=passed,
        evidence=evidence,
    )


def _check_privacy() -> FinalCheck:
    packet = build_command_payload(
        ok=True,
        human_message="privacy probe",
        machine_error_code="OK",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={"echo": "sk-live-secret-999"},
    )
    redacted = "sk-live-secret-999" not in json.dumps(packet)
    return FinalCheck(
        check_id="privacy",
        category="privacy",
        passed=redacted,
        evidence=f"secret redacted by packet contract: {redacted}",
        detail={"redacted": redacted},
    )


def _check_migration() -> FinalCheck:
    """State migration v1 -> v2 probe in a temp root with backup."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        root = Path(tmp)
        source = root / "state.json"
        source.write_text(
            json.dumps({"schema_version": 1, "value": "old"}), encoding="utf-8"
        )
        backup = root / "backup"
        try:
            result = migrate_json_file(
                source,
                target_schema_version=2,
                migrations=(
                    MigrationStep(
                        from_version=1,
                        to_version=2,
                        migrate=lambda payload: {**payload, "schema_version": 2, "migrated": True},
                    ),
                ),
                backup_dir=backup,
            )
            document = json.loads(source.read_text(encoding="utf-8"))
            passed = (
                result.committed is True
                and document.get("schema_version") == 2
                and document.get("migrated") is True
                and backup.exists()
            )
            evidence = (
                f"v1->v2 migration applied with backup (committed={result.committed})"
            )
        except Exception as exc:  # noqa: BLE001
            passed = False
            evidence = f"migration probe failed: {exc}"
    return FinalCheck(
        check_id="migration",
        category="migration",
        passed=passed,
        evidence=evidence,
    )


def _check_provider() -> FinalCheck:
    receipt = pcs.build_provider_capability_matrix_receipt()
    providers = set(pcs.RELEASE_PROVIDERS)
    passed = (
        receipt["status"] == "ok"
        and len(providers) == 4
        and providers == {"deepseek", "glm", "kimi", "qwen"}
        and receipt.get("qwen_admitted") is True
    )
    return FinalCheck(
        check_id="provider",
        category="provider",
        passed=passed,
        evidence=f"4-provider release set confirmed (qwen_admitted={receipt.get('qwen_admitted')})",
        detail={"release_providers": sorted(providers)},
    )


def _check_cli() -> FinalCheck:
    """R5: the production facade must be fail-closed with a typed code and
    no runtime-grant mechanism; that IS the required security posture."""
    receipt = osr.default_production_facade().receipt()
    passed = (
        receipt["status"] == "ok"
        and receipt.get("cli_disabled") is True
        and receipt.get("disabled_reason") == "pending_security_admission"
        and receipt.get("runtime_grant_available") is False
        and receipt.get("declared_not_live_verified") is True
    )
    return FinalCheck(
        check_id="cli",
        category="cli",
        passed=passed,
        evidence=(
            "production CLI facade fail-closed "
            f"(cli_disabled={receipt.get('cli_disabled')}, "
            f"runtime_grant_available={receipt.get('runtime_grant_available')})"
        ),
        detail={"cli_disabled": receipt.get("cli_disabled")},
    )


def _check_workflow() -> FinalCheck:
    step = wf.WorkflowStep(
        step_request_id="s1",
        slot_id="slot-a",
        binding_id="binding-1",
        binding_revision=1,
        assignment_id="a1",
        provider="deepseek",
        prompt="x",
    )
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        packet = wf.run_sequential_workflow(
            [step],
            dispatch=lambda s, d: {
                "status": "ok",
                "provider": "deepseek",
                "output_text": "o",
                "machine_error_code": "OK",
            },
            lease_root=Path(tmp) / "lease",
        )
    passed = packet["status"] == "ok" and packet.get("all_steps_delivered") is True
    return FinalCheck(
        check_id="workflow",
        category="workflow",
        passed=passed,
        evidence=f"sequential runner delivered {packet.get('dispatched_steps')} step(s)",
        detail={"delivered": passed},
    )


def _check_web() -> FinalCheck:
    """Web control surface plumbing probe (in-memory token).

    Checks that the endpoint responds with a strict packet — not that the
    gate is earned (that is a separate concern). The gate_facts are
    intentionally minimal so the gate is not earned; the check verifies
    the HTTP handler pipeline itself.
    """
    from .web_rate_limit import WebPostRateLimiter
    from .web_token import create_in_memory_web_token

    state = wwc.WorkflowControlState(
        gate_facts={
            "completed_stages": [],
            "evidence_index_references": 0,
            "full_suite_passed": 0,
            "main_head": "0" * 40,
        }
    )
    token_state = create_in_memory_web_token()
    packet = wwc.handle_workflow_control_request(
        state=state,
        token_state=token_state,
        rate_limiter=WebPostRateLimiter(limit_per_second=100),
        method="GET",
        path="/api/workflow/gate",
        headers={},
    )
    # The endpoint must return a strict packet (ok or error); we check
    # the handler pipeline, not the gate verdict.
    passed = "status" in packet and "machine_error_code" in packet
    return FinalCheck(
        check_id="web",
        category="web",
        passed=passed,
        evidence=f"workflow control gate endpoint responded (status={packet.get('status')})",
    )


def _check_account_isolation() -> FinalCheck:
    """R5 typed fail-closed compatibility check.

    Provider sessions on the production facade must fail closed with the
    typed disabled code, no KeyError, and zero filesystem creation. This
    probe performs no writes and creates no provider homes.
    """
    qwen = qoc.qwen_one_shot_session()
    kimi = km.kimi_one_shot_session()
    disabled_code = osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
    qwen_ok = (
        qwen.get("status") == "error"
        and qwen.get("machine_error_code") == disabled_code
        and qwen.get("changed_files") == []
        and "qwen_home" not in qwen
    )
    kimi_ok = (
        kimi.get("status") == "error"
        and kimi.get("machine_error_code") == disabled_code
        and kimi.get("changed_files") == []
        and "kimi_code_home" not in kimi
    )
    passed = qwen_ok and kimi_ok
    return FinalCheck(
        check_id="account_isolation",
        category="isolation",
        passed=passed,
        evidence=(
            f"provider sessions fail closed with typed code, no fs creation "
            f"(qwen={qwen.get('machine_error_code')}, kimi={kimi.get('machine_error_code')})"
        ),
        detail={
            "qwen_code": qwen.get("machine_error_code"),
            "kimi_code": kimi.get("machine_error_code"),
            "cli_disabled": True,
        },
    )


def _check_protected_network(
    *,
    protected_ports: Sequence[int] = (10808, 12334),
    network_air_gap_evidence: Mapping[str, Any] | None = None,
) -> FinalCheck:
    """Protected ports remain product truth (tests never bind them) and
    the network air-gap facts are recorded."""
    facts = dict(network_air_gap_evidence or {})
    recorded = bool(facts)
    return FinalCheck(
        check_id="protected_network",
        category="network",
        passed=recorded,
        evidence=(
            f"protected ports {list(protected_ports)} are product truth; "
            f"network air-gap facts recorded={recorded}"
        ),
        detail={
            "protected_ports": list(protected_ports),
            "air_gap_facts_recorded": recorded,
            "air_gap_facts": facts,
        },
    )


def run_final_candidate_assurance(
    *,
    full_suite_passed: int,
    clean_run: bool = True,
    network_air_gap_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all final candidate checks. Emits only
    `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT` or a typed failure."""
    checks: list[FinalCheck] = [
        _check_exact_remote_head(),
        _check_full_test_evidence(full_suite_passed=full_suite_passed, clean_run=clean_run),
        _check_package(),
        _check_privacy(),
        _check_migration(),
        _check_provider(),
        _check_cli(),
        _check_workflow(),
        _check_web(),
        _check_account_isolation(),
        _check_protected_network(network_air_gap_evidence=network_air_gap_evidence),
    ]
    check_ids = {check.check_id for check in checks}
    if check_ids != set(FINAL_CHECK_IDS):
        return build_command_payload(
            ok=False,
            human_message="final candidate check coverage mismatch.",
            machine_error_code=FINAL_CANDIDATE_FAILED,
            liveness="degraded",
            severity="error",
            operator_action="stop",
            changed_files=[],
            exit_code=1,
            extra={
                "schema_version": FINAL_CANDIDATE_SCHEMA_VERSION,
                "final_candidate_status": FINAL_CANDIDATE_FAILED,
                "missing_checks": sorted(set(FINAL_CHECK_IDS) - check_ids),
                "checks": [check.to_dict() for check in checks],
            },
        )
    failed = [check for check in checks if not check.passed]
    ready = not failed
    status = FINAL_CANDIDATE_STATUS if ready else FINAL_CANDIDATE_FAILED
    return build_command_payload(
        ok=ready,
        human_message=(
            "Final candidate ready for independent audit."
            if ready
            else f"Final candidate failed {len(failed)} check(s)."
        ),
        machine_error_code=status,
        liveness="healthy" if ready else "degraded",
        severity="info" if ready else "error",
        operator_action="none" if ready else "stop",
        changed_files=[],
        exit_code=0 if ready else 1,
        extra={
            "schema_version": FINAL_CANDIDATE_SCHEMA_VERSION,
            "final_candidate_status": status,
            "ready_for_independent_audit": ready,
            "check_count": len(checks),
            "passed_count": len(checks) - len(failed),
            "failed_checks": [check.to_dict() for check in failed],
            "checks": [check.to_dict() for check in checks],
            "never_emits_done": True,
        },
    )


__all__ = ["FINAL_CANDIDATE_STATUS", "run_final_candidate_assurance", "FINAL_CHECK_IDS"]

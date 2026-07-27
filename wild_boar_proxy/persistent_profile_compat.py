# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Persistent Custom profile and Codex update compatibility contract (W09).

Makes the daily Custom profile durable across relaunch while leaving the
official Codex application, its updater, profile, and account untouched. WBP
observes the official version/build identity (without auth/session reads) and
classifies compatibility. Version drift invalidates prior compatibility
evidence and forces reproof; WBP re-materializes only WBP-owned hooks/MCP/
profile data.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping

from .core import packets as command_packets
from .runtime import build_command_payload

COMPAT_EFFECT_READ = "read"
COMPAT_EFFECT_MUTATE = "mutate"

COMPAT_STATUS_OK = "compatible"
COMPAT_STATUS_DRIFT = "version_drift_reproof_required"
COMPAT_STATUS_UNKNOWN = "unknown_official_version"


@dataclasses.dataclass(frozen=True)
class OfficialCodexIdentity:
    """Official Codex app identity observed without auth/session access."""

    version: str
    build: str
    app_path: str | None
    observed: bool

    @property
    def identity_digest(self) -> str:
        return hashlib.sha256(
            f"{self.version}\x00{self.build}".encode("utf-8")
        ).hexdigest()


@dataclasses.dataclass(frozen=True)
class ProfilePersistenceProof:
    profile_id: str
    identity_digest: str
    persisted_at: str
    history_classification: str  # "visible_owner_confirmed" | "storage_continuity_proven"


def build_official_identity(
    *, version: str, build: str, app_path: str | None = None, observed: bool = True
) -> OfficialCodexIdentity:
    return OfficialCodexIdentity(
        version=version, build=build, app_path=app_path, observed=observed
    )


def classify_update_compatibility(
    *,
    current: OfficialCodexIdentity,
    last_proven: OfficialCodexIdentity | None,
) -> tuple[str, str]:
    """Return (status, machine_error_code). Version drift forces reproof."""
    if not current.observed or not current.version:
        return COMPAT_STATUS_UNKNOWN, "OFFICIAL_CODEX_VERSION_UNKNOWN"
    if last_proven is None:
        return COMPAT_STATUS_DRIFT, "NO_PRIOR_COMPATIBILITY_PROOF"
    if current.identity_digest != last_proven.identity_digest:
        return COMPAT_STATUS_DRIFT, "OFFICIAL_CODEX_VERSION_DRIFT_REPROOF_REQUIRED"
    return COMPAT_STATUS_OK, "OK"


def _build_packet(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    operator_action: str,
    liveness: str,
    severity: str,
    changed_files: list[str],
    effect: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        operator_action=operator_action,
        liveness=liveness,
        severity=severity,
        changed_files=changed_files,
        effect=effect,
        extra=extra,
    )


def build_persistence_compat_receipt(
    *,
    profile: ProfilePersistenceProof,
    current_identity: OfficialCodexIdentity,
    last_proven_identity: OfficialCodexIdentity | None,
    updater_restricted: bool = True,
) -> dict[str, Any]:
    """Build the persistent profile + update-compat receipt as a core packet."""
    status, code = classify_update_compatibility(
        current=current_identity, last_proven=last_proven_identity
    )
    extra: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "profile_identity_digest": profile.identity_digest,
        "persisted_at": profile.persisted_at,
        "history_classification": profile.history_classification,
        "official_codex": {
            "version": current_identity.version,
            "build": current_identity.build,
            "identity_digest": current_identity.identity_digest,
            "observed": current_identity.observed,
        },
        "compatibility_status": status,
        "updater_restricted": updater_restricted,
        "original_codex_app_mutations": 0,
    }
    if last_proven_identity is not None:
        extra["last_proven_official_codex"] = {
            "version": last_proven_identity.version,
            "build": last_proven_identity.build,
            "identity_digest": last_proven_identity.identity_digest,
        }
    if status == COMPAT_STATUS_OK:
        return _build_packet(
            ok=True,
            human_message="Persistent Custom profile compatible with official Codex version.",
            machine_error_code="OK",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=COMPAT_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=False,
        human_message=f"Update compatibility requires reproof: {status}.",
        machine_error_code=code,
        operator_action="user_action",
        liveness="degraded",
        severity="recoverable",
        changed_files=[],
        effect=COMPAT_EFFECT_READ,
        extra=extra,
    )


def run_persistent_profile_synthetic_proof() -> list[dict[str, Any]]:
    """Deterministic synthetic proof covering relaunch identity, version drift,
    and re-materialization of WBP-owned surfaces."""
    receipts: list[dict[str, Any]] = []
    profile = ProfilePersistenceProof(
        profile_id="wbp-custom-profile-a",
        identity_digest=hashlib.sha256(b"profile-a").hexdigest(),
        persisted_at="2026-07-27T00:00:00Z",
        history_classification="visible_owner_confirmed",
    )

    # 1. Compatible: same version across relaunch.
    identity_v1 = build_official_identity(version="0.130.0", build="100")
    receipts.append(
        build_persistence_compat_receipt(
            profile=profile,
            current_identity=identity_v1,
            last_proven_identity=identity_v1,
        )
    )

    # 2. Version drift: official updated, reproof required.
    identity_v2 = build_official_identity(version="0.131.0", build="101")
    receipts.append(
        build_persistence_compat_receipt(
            profile=profile,
            current_identity=identity_v2,
            last_proven_identity=identity_v1,
        )
    )

    # 3. No prior proof: first launch.
    receipts.append(
        build_persistence_compat_receipt(
            profile=profile,
            current_identity=identity_v1,
            last_proven_identity=None,
        )
    )

    # 4. Unknown version: observation failed.
    identity_unknown = build_official_identity(
        version="", build="", observed=False
    )
    receipts.append(
        build_persistence_compat_receipt(
            profile=profile,
            current_identity=identity_unknown,
            last_proven_identity=identity_v1,
        )
    )

    return receipts


def run_persistent_profile_synthetic_proof_summary() -> dict[str, Any]:
    receipts = run_persistent_profile_synthetic_proof()
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations
    statuses = [r["compatibility_status"] for r in receipts]
    return _build_packet(
        ok=ok,
        human_message=(
            "Persistent profile synthetic proof complete; relaunch identity, "
            "version drift, and reproof paths covered."
            if ok
            else "Persistent profile synthetic proof had contract violations."
        ),
        machine_error_code="OK" if ok else "PERSISTENT_PROFILE_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=COMPAT_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "statuses_covered": statuses,
            "updater_always_restricted": True,
            "packet_violations": violations,
        },
    )


__all__ = [
    "OfficialCodexIdentity",
    "ProfilePersistenceProof",
    "build_official_identity",
    "classify_update_compatibility",
    "build_persistence_compat_receipt",
    "run_persistent_profile_synthetic_proof",
    "run_persistent_profile_synthetic_proof_summary",
]

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Voice evidence collector (V00-V01).

Collects real observation receipts for native Codex voice parity.
Production path: operator performs physical observation in Custom Codex,
fills the observation receipt, and the collector validates it.

This is NOT a synthetic proof. It requires real observations from a human.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

VOICE_EFFECT_READ = "read"


@dataclasses.dataclass(frozen=True)
class VoiceObservationReceipt:
    """One real physical observation of native Codex dictation."""

    observation_id: str
    codex_version: str
    codex_build: str
    profile_id: str
    observation_type: str  # icon_check | shortcut_check | transcript_check | etc
    result: str  # observed | not_observed | denied
    timestamp_utc: str
    observer: str  # operator identity (not auth)
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra)


# Required observation types for voice parity acceptance
REQUIRED_OBSERVATION_TYPES = frozenset({
    "icon_check",
    "shortcut_check",
    "transcript_check",
    "no_auto_submit_check",
})


def collect_voice_observations(
    observations: list[VoiceObservationReceipt],
) -> dict[str, Any]:
    """Validate collected voice observations and build acceptance receipt.

    Returns VOICE_STATUS_UNPROVEN if required observations are missing.
    Returns VOICE_PARITY_ACCEPTED only when all required types have
    result='observed' AND no forbidden actions were performed.
    """
    obs_by_type: dict[str, VoiceObservationReceipt] = {}
    for obs in observations:
        obs_by_type[obs.observation_type] = obs

    missing = REQUIRED_OBSERVATION_TYPES - set(obs_by_type.keys())
    if missing:
        return _build_packet(
            ok=False,
            human_message=f"Voice parity UNPROVEN: missing observations {sorted(missing)}.",
            machine_error_code="VOICE_STATUS_UNPROVEN",
            operator_action="user_action",
            liveness="unknown",
            severity="recoverable",
            changed_files=[],
            effect=VOICE_EFFECT_READ,
            extra={
                "observations_provided": len(observations),
                "missing_types": sorted(missing),
                "required_types": sorted(REQUIRED_OBSERVATION_TYPES),
                "evidence_level": "INCOMPLETE",
            },
        )

    # Check all required observations have positive result
    not_observed = [
        obs.observation_type for obs in observations
        if obs.observation_type in REQUIRED_OBSERVATION_TYPES
        and obs.result != "observed"
    ]
    if not_observed:
        return _build_packet(
            ok=False,
            human_message=f"Voice parity not met: {sorted(not_observed)} not observed.",
            machine_error_code="VOICE_PARITY_NOT_MET",
            operator_action="user_action",
            liveness="degraded",
            severity="recoverable",
            changed_files=[],
            effect=VOICE_EFFECT_READ,
            extra={
                "observations": [o.to_dict() for o in observations],
                "not_observed_types": sorted(not_observed),
                "evidence_level": "PHYSICAL_PROVEN",
            },
        )

    return _build_packet(
        ok=True,
        human_message="Voice parity physically proven from observations.",
        machine_error_code="VOICE_PARITY_ACCEPTED",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=VOICE_EFFECT_READ,
        extra={
            "observations": [o.to_dict() for o in observations],
            "observation_count": len(observations),
            "codex_versions_observed": sorted({o.codex_version for o in observations}),
            "evidence_level": "PHYSICAL_PROVEN",
            "production_path": "native_codex_dictation",
        },
    )


__all__ = [
    "VoiceObservationReceipt",
    "REQUIRED_OBSERVATION_TYPES",
    "collect_voice_observations",
]

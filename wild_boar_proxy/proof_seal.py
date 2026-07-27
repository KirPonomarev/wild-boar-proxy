# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .core import packets
from .router_hook_entry import _safe_text
from .runtime import write_json_atomic


PROOF_SEAL_SCHEMA_VERSION = 1
PROOF_SEAL_KIND = "wbp_proof_seal_v1"
PROOF_SEAL_CREATE_PACKET_KIND = "wbp_proof_seal_create"
PROOF_SEAL_VERIFY_PACKET_KIND = "wbp_proof_seal_verify"

PROOF_SEAL_OK = "OK"
PROOF_SEAL_PACKET_INVALID = "WBP_PROOF_SEAL_PACKET_INVALID"
PROOF_SEAL_INVALID = "WBP_PROOF_SEAL_INVALID"
PROOF_SEAL_HASH_MISMATCH = "WBP_PROOF_SEAL_HASH_MISMATCH"
PROOF_SEAL_INPUT_MISMATCH = "WBP_PROOF_SEAL_INPUT_MISMATCH"
PROOF_SEAL_UNSAFE_CLAIM = "WBP_PROOF_SEAL_UNSAFE_CLAIM"

_UNSAFE_TRUE_FIELDS = {
    "raw_prompt_recorded": "seal_raw_prompt_recorded",
    "prompt_text_recorded": "seal_prompt_text_recorded",
    "natural_phrase_recorded": "seal_natural_phrase_recorded",
    "raw_route_id_recorded": "seal_raw_route_id_recorded",
    "selected_api_route_id_recorded": "seal_selected_route_recorded",
    "route_candidate_recorded": "seal_route_candidate_recorded",
    "raw_provider_response_recorded": "seal_raw_provider_response_recorded",
    "provider_response_text_recorded": "seal_provider_response_text_recorded",
    "provider_response_preview_recorded": "seal_provider_response_preview_recorded",
    "raw_backend_details_exposed": "seal_raw_backend_details_exposed",
    "secret_value_exposed": "seal_secret_value_exposed",
    "custom_codex_ui_visibility_proven": "seal_custom_ui_must_not_be_claimed",
    "delivery_counts_as_custom_codex_ui": "seal_custom_ui_delivery_must_not_be_claimed",
    "native_free_chat_router_proven": "seal_native_router_must_not_be_claimed",
    "product_ready": "seal_product_ready_must_not_be_claimed",
}


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def default_seal_path(packet_file: str | Path) -> Path:
    path = Path(packet_file).expanduser()
    name = path.name
    if name.endswith(".packet.json"):
        return path.with_name(name[: -len(".packet.json")] + ".seal.json")
    if name.endswith(".json"):
        return path.with_name(name[: -len(".json")] + ".seal.json")
    return path.with_name(f"{name}.seal.json")


def read_json_mapping_file(
    path: Path,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_required": True,
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_error_code": "",
        f"{prefix}_file_path_recorded": False,
        f"{prefix}_file_sha256": "",
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_sha256"] = hashlib.sha256(raw).hexdigest()
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(encoded)


def _packet_kind(packet: Mapping[str, Any]) -> str:
    return _safe_text(packet.get("packet_kind"), limit=120)


def _input_hashes(input_packet_files: Sequence[str | Path] | None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for index, raw_path in enumerate(input_packet_files or []):
        path = Path(raw_path).expanduser()
        packet, metadata = read_json_mapping_file(path, prefix="input_packet")
        kind = _packet_kind(packet) or f"input_{index}"
        key = kind
        if key in hashes:
            key = f"{kind}:{index}"
        hashes[key] = _hex_sha256(metadata.get("input_packet_file_sha256"))
    return hashes


def build_proof_seal_manifest(
    *,
    sealed_packet: Mapping[str, Any],
    sealed_packet_sha256: str,
    producer_kind: str,
    producer_command_digest: str,
    producer_inputs_digest: str = "",
    input_packet_hashes: Mapping[str, str] | None = None,
    runtime_context_digest: str = "",
    hook_ledger_digest: str = "",
    profile_hook_config_digest: str = "",
    git_commit_sha: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": PROOF_SEAL_SCHEMA_VERSION,
        "seal_kind": PROOF_SEAL_KIND,
        "sealed_packet_kind": _packet_kind(sealed_packet),
        "sealed_packet_sha256": _hex_sha256(sealed_packet_sha256),
        "producer_kind": _safe_text(producer_kind, limit=120),
        "producer_command_digest": _hex_sha256(producer_command_digest),
        "producer_inputs_digest": _hex_sha256(producer_inputs_digest),
        "input_packet_hashes": {
            _safe_text(key, limit=120): _hex_sha256(value)
            for key, value in dict(input_packet_hashes or {}).items()
        },
        "runtime_context_digest": _hex_sha256(runtime_context_digest),
        "hook_ledger_digest": _hex_sha256(hook_ledger_digest),
        "profile_hook_config_digest": _hex_sha256(profile_hook_config_digest),
        "git_commit_sha": _safe_text(git_commit_sha, limit=80),
        "raw_command_recorded": False,
        "command_path_recorded": False,
        "packet_file_path_recorded": False,
        "seal_file_path_recorded": False,
        "input_packet_paths_recorded": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "route_candidate_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "cryptographic_authenticity_proven": False,
        "source_file_unforgeable": False,
    }


def _unsafe_seal_failures(
    seal: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None = None,
) -> list[str]:
    failures = {
        reason
        for field, reason in _UNSAFE_TRUE_FIELDS.items()
        if seal.get(field) is True
    }
    for field, reason in (
        ("raw_command_recorded", "seal_raw_command_recorded"),
        ("command_path_recorded", "seal_command_path_recorded"),
        ("packet_file_path_recorded", "seal_packet_path_recorded"),
        ("seal_file_path_recorded", "seal_path_recorded"),
        ("input_packet_paths_recorded", "seal_input_paths_recorded"),
    ):
        if seal.get(field) is True:
            failures.add(reason)
    if packets.command_packet_has_secret_leak(dict(seal), secret_values=list(secret_values or [])):
        failures.add("seal_secret_like_value_present")
    return sorted(failures)


def proof_seal_failures(
    *,
    packet: Mapping[str, Any],
    packet_metadata: Mapping[str, Any],
    seal: Mapping[str, Any],
    seal_metadata: Mapping[str, Any],
    expected_packet_kind: str = "",
    expected_input_packet_hashes: Mapping[str, str] | None = None,
    expected_runtime_context_digest: str = "",
    expected_hook_ledger_digest: str = "",
    expected_profile_hook_config_digest: str = "",
    secret_values: Sequence[str] | None = None,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unsafe_failures = _unsafe_seal_failures(seal, secret_values=secret_values)
    if packet_metadata.get("sealed_packet_file_read") is not True:
        failures.append("sealed_packet_file_not_read")
    if packet_metadata.get("sealed_packet_file_valid_json") is not True:
        failures.append("sealed_packet_file_json_not_valid")
    if packet_metadata.get("sealed_packet_file_mapping") is not True:
        failures.append("sealed_packet_file_not_mapping")
    if seal_metadata.get("proof_seal_file_read") is not True:
        failures.append("proof_seal_file_not_read")
    if seal_metadata.get("proof_seal_file_valid_json") is not True:
        failures.append("proof_seal_file_json_not_valid")
    if seal_metadata.get("proof_seal_file_mapping") is not True:
        failures.append("proof_seal_file_not_mapping")
    if seal.get("schema_version") != PROOF_SEAL_SCHEMA_VERSION:
        failures.append("proof_seal_schema_version_invalid")
    if seal.get("seal_kind") != PROOF_SEAL_KIND:
        failures.append("proof_seal_kind_invalid")
    packet_kind = _packet_kind(packet)
    sealed_packet_kind = _safe_text(seal.get("sealed_packet_kind"), limit=120)
    if not sealed_packet_kind:
        failures.append("sealed_packet_kind_missing")
    elif packet_kind and sealed_packet_kind != packet_kind:
        failures.append("sealed_packet_kind_mismatch")
    if expected_packet_kind and sealed_packet_kind != expected_packet_kind:
        failures.append("sealed_packet_kind_not_expected")
    packet_sha = _hex_sha256(packet_metadata.get("sealed_packet_file_sha256"))
    seal_packet_sha = _hex_sha256(seal.get("sealed_packet_sha256"))
    if not packet_sha:
        failures.append("sealed_packet_file_sha256_missing")
    if not seal_packet_sha:
        failures.append("proof_seal_packet_sha256_missing")
    if packet_sha and seal_packet_sha and packet_sha != seal_packet_sha:
        failures.append("sealed_packet_sha256_mismatch")
    if not _safe_text(seal.get("producer_kind"), limit=120):
        failures.append("producer_kind_missing")
    if not _hex_sha256(seal.get("producer_command_digest")):
        failures.append("producer_command_digest_missing")
    if not _hex_sha256(seal.get("producer_inputs_digest")):
        failures.append("producer_inputs_digest_missing")
    input_hashes = seal.get("input_packet_hashes")
    input_hash_map = dict(input_hashes) if isinstance(input_hashes, Mapping) else {}
    if input_hashes is not None and not isinstance(input_hashes, Mapping):
        failures.append("input_packet_hashes_not_mapping")
    normalized_input_hash_map = {
        _safe_text(key, limit=120): _hex_sha256(value)
        for key, value in input_hash_map.items()
    }
    for key, actual_hash in input_hash_map.items():
        if not _hex_sha256(actual_hash):
            failures.append(f"input_packet_hash_invalid:{_safe_text(key, limit=120)}")
    actual_inputs_digest = _canonical_digest(
        {"input_packet_hashes": normalized_input_hash_map}
    )
    producer_inputs_digest = _hex_sha256(seal.get("producer_inputs_digest"))
    if producer_inputs_digest and producer_inputs_digest != actual_inputs_digest:
        failures.append("producer_inputs_digest_mismatch")
    if expected_input_packet_hashes is not None:
        expected_input_hash_map = {
            _safe_text(key, limit=120): _hex_sha256(value)
            for key, value in dict(expected_input_packet_hashes).items()
        }
        actual_keys = set(normalized_input_hash_map)
        expected_keys = set(expected_input_hash_map)
        for key in sorted(actual_keys - expected_keys):
            failures.append(f"input_packet_hash_unexpected:{key}")
        for key in sorted(expected_keys - actual_keys):
            failures.append(f"input_packet_hash_missing:{key}")
        for key in sorted(actual_keys & expected_keys):
            actual = normalized_input_hash_map.get(key, "")
            expected = expected_input_hash_map.get(key, "")
            if actual != expected:
                failures.append(f"input_packet_hash_mismatch:{key}")
    for field, expected, reason in (
        ("runtime_context_digest", expected_runtime_context_digest, "runtime_context_digest_mismatch"),
        ("hook_ledger_digest", expected_hook_ledger_digest, "hook_ledger_digest_mismatch"),
        (
            "profile_hook_config_digest",
            expected_profile_hook_config_digest,
            "profile_hook_config_digest_mismatch",
        ),
    ):
        expected_digest = _hex_sha256(expected)
        actual_digest = _hex_sha256(seal.get(field))
        if expected_digest and not actual_digest:
            failures.append(f"{field}_missing")
        elif expected_digest and actual_digest != expected_digest:
            failures.append(reason)
    failures.extend(unsafe_failures)
    return sorted(set(failures)), unsafe_failures


def verify_proof_seal(
    *,
    packet_file: str | Path,
    seal_file: str | Path | None = None,
    expected_packet_kind: str = "",
    expected_input_packet_hashes: Mapping[str, str] | None = None,
    expected_runtime_context_digest: str = "",
    expected_hook_ledger_digest: str = "",
    expected_profile_hook_config_digest: str = "",
    secret_values: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet_path = Path(packet_file).expanduser()
    seal_path = Path(seal_file).expanduser() if seal_file else default_seal_path(packet_path)
    packet, packet_metadata = read_json_mapping_file(packet_path, prefix="sealed_packet")
    seal, seal_metadata = read_json_mapping_file(seal_path, prefix="proof_seal")
    failures, unsafe_failures = proof_seal_failures(
        packet=packet,
        packet_metadata=packet_metadata,
        seal=seal,
        seal_metadata=seal_metadata,
        expected_packet_kind=expected_packet_kind,
        expected_input_packet_hashes=expected_input_packet_hashes,
        expected_runtime_context_digest=expected_runtime_context_digest,
        expected_hook_ledger_digest=expected_hook_ledger_digest,
        expected_profile_hook_config_digest=expected_profile_hook_config_digest,
        secret_values=secret_values,
    )
    verified = not failures
    extra = {
        **packet_metadata,
        **seal_metadata,
        "schema_version": PROOF_SEAL_SCHEMA_VERSION,
        "packet_kind": PROOF_SEAL_VERIFY_PACKET_KIND,
        "proof_seal_verified": verified,
        "source_file_authenticity_proven": verified,
        "source_file_unforgeable": False,
        "cryptographic_authenticity_proven": False,
        "sealed_packet_kind": _safe_text(seal.get("sealed_packet_kind"), limit=120),
        "sealed_packet_sha256": _hex_sha256(seal.get("sealed_packet_sha256")),
        "producer_kind": _safe_text(seal.get("producer_kind"), limit=120),
        "producer_command_digest": _hex_sha256(seal.get("producer_command_digest")),
        "producer_inputs_digest": _hex_sha256(seal.get("producer_inputs_digest")),
        "runtime_context_digest": _hex_sha256(seal.get("runtime_context_digest")),
        "hook_ledger_digest": _hex_sha256(seal.get("hook_ledger_digest")),
        "profile_hook_config_digest": _hex_sha256(
            seal.get("profile_hook_config_digest")
        ),
        "git_commit_sha_recorded": bool(_safe_text(seal.get("git_commit_sha"), limit=80)),
        "seal_input_packet_hashes_digest": _canonical_digest(
            dict(seal.get("input_packet_hashes"))
            if isinstance(seal.get("input_packet_hashes"), Mapping)
            else {}
        ),
        "proof_seal_failures": failures,
        "proof_seal_unsafe_failures": unsafe_failures,
        "blocking_reasons": failures,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=verified,
        human_message=(
            "WBP verified proof seal against packet hash and declared inputs."
            if verified
            else "WBP blocked proof seal verification."
        ),
        machine_error_code=_machine_error_code(failures, unsafe_failures),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if verified else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    ), seal


def _machine_error_code(
    failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if not failures:
        return PROOF_SEAL_OK
    if unsafe_failures:
        return PROOF_SEAL_UNSAFE_CLAIM
    if any("sha256_mismatch" in failure for failure in failures):
        return PROOF_SEAL_HASH_MISMATCH
    if any(
        "input_packet_hash" in failure or failure == "producer_inputs_digest_mismatch"
        for failure in failures
    ):
        return PROOF_SEAL_INPUT_MISMATCH
    if any(failure.startswith("sealed_packet_") for failure in failures):
        return PROOF_SEAL_PACKET_INVALID
    return PROOF_SEAL_INVALID


def run_proof_seal_create_command(
    *,
    packet_file: str,
    seal_file: str | None = None,
    producer_kind: str,
    producer_command_digest: str,
    producer_inputs_digest: str = "",
    input_packet_files: Sequence[str] | None = None,
    runtime_context_digest: str = "",
    hook_ledger_digest: str = "",
    profile_hook_config_digest: str = "",
    git_commit_sha: str = "",
) -> dict[str, Any]:
    packet_path = Path(packet_file).expanduser()
    target_seal_path = Path(seal_file).expanduser() if seal_file else default_seal_path(packet_path)
    packet, packet_metadata = read_json_mapping_file(packet_path, prefix="sealed_packet")
    input_hashes = _input_hashes(input_packet_files)
    effective_inputs_digest = (
        _hex_sha256(producer_inputs_digest)
        or _canonical_digest({"input_packet_hashes": input_hashes})
    )
    packet_sha = _hex_sha256(packet_metadata.get("sealed_packet_file_sha256"))
    manifest = build_proof_seal_manifest(
        sealed_packet=packet,
        sealed_packet_sha256=packet_sha,
        producer_kind=producer_kind,
        producer_command_digest=producer_command_digest,
        producer_inputs_digest=effective_inputs_digest,
        input_packet_hashes=input_hashes,
        runtime_context_digest=runtime_context_digest,
        hook_ledger_digest=hook_ledger_digest,
        profile_hook_config_digest=profile_hook_config_digest,
        git_commit_sha=git_commit_sha,
    )
    failures, unsafe_failures = proof_seal_failures(
        packet=packet,
        packet_metadata=packet_metadata,
        seal=manifest,
        seal_metadata={
            "proof_seal_file_read": True,
            "proof_seal_file_valid_json": True,
            "proof_seal_file_mapping": True,
        },
        expected_packet_kind=_packet_kind(packet),
    )
    changed_files: list[str] = []
    if not failures:
        write_json_atomic(target_seal_path, manifest)
        changed_files = [str(target_seal_path)]
    extra = {
        **packet_metadata,
        "schema_version": PROOF_SEAL_SCHEMA_VERSION,
        "packet_kind": PROOF_SEAL_CREATE_PACKET_KIND,
        "proof_seal_written": not failures,
        "proof_seal_verified": not failures,
        "seal_file_path_recorded": False,
        "sealed_packet_kind": manifest["sealed_packet_kind"],
        "sealed_packet_sha256": manifest["sealed_packet_sha256"],
        "producer_kind": manifest["producer_kind"],
        "producer_command_digest": manifest["producer_command_digest"],
        "producer_inputs_digest": manifest["producer_inputs_digest"],
        "runtime_context_digest": manifest["runtime_context_digest"],
        "hook_ledger_digest": manifest["hook_ledger_digest"],
        "profile_hook_config_digest": manifest["profile_hook_config_digest"],
        "input_packet_hashes_digest": _canonical_digest(input_hashes),
        "source_file_unforgeable": False,
        "cryptographic_authenticity_proven": False,
        "proof_seal_failures": failures,
        "proof_seal_unsafe_failures": unsafe_failures,
        "blocking_reasons": failures,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=not failures,
        human_message=(
            "WBP wrote proof seal manifest."
            if not failures
            else "WBP blocked proof seal creation."
        ),
        machine_error_code=_machine_error_code(failures, unsafe_failures),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if not failures else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=[],
        extra=extra,
    )


def run_proof_seal_verify_command(
    *,
    packet_file: str,
    seal_file: str | None = None,
    expected_packet_kind: str = "",
) -> dict[str, Any]:
    packet, _ = verify_proof_seal(
        packet_file=packet_file,
        seal_file=seal_file,
        expected_packet_kind=expected_packet_kind,
    )
    return packet

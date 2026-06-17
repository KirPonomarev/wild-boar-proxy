# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
from typing import Any

from .codex_transcript_delivery_observation import (
    _codex_exec_transcript_digest,
    _read_jsonl_events_file,
)
from .codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    run_codex_working_flow_delivery_proof_command,
)
from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .core import packets
from .custom_codex_hook_origin_proof import (
    CUSTOM_CODEX_HOOK_ORIGIN_PROOF_PACKET_KIND,
    run_custom_codex_hook_origin_proof_command,
)
from .proof_seal import (
    sha256_file,
    run_proof_seal_create_command,
    verify_proof_seal,
)
from .real_custom_codex_hook_proof import (
    REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    run_real_custom_codex_hook_proof_command,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import (
    RuntimePaths,
    build_launcher_subprocess_env,
    snapshot_path_state,
    write_json_atomic,
    write_text_atomic,
)
from .user_prompt_submit_hook_producer import hook_ledger_path


CUSTOM_CODEX_ADMISSION_PACKET_KIND = "wbp_repeatable_custom_codex_admission"
LIVE_PROVIDER_EXTRACT_PACKET_KIND = "wbp_custom_codex_admission_live_provider_extract"

ADMISSION_OK = "OK"
ADMISSION_CODEX_LAUNCH_FAILED = "WBP_CUSTOM_CODEX_ADMISSION_CODEX_LAUNCH_FAILED"
ADMISSION_LIVE_PROVIDER_NOT_OBSERVED = (
    "WBP_CUSTOM_CODEX_ADMISSION_LIVE_PROVIDER_NOT_OBSERVED"
)
ADMISSION_HOOK_PROOF_FAILED = "WBP_CUSTOM_CODEX_ADMISSION_HOOK_PROOF_FAILED"
ADMISSION_WORKING_FLOW_FAILED = "WBP_CUSTOM_CODEX_ADMISSION_WORKING_FLOW_FAILED"
ADMISSION_SEAL_FAILED = "WBP_CUSTOM_CODEX_ADMISSION_SEAL_FAILED"
ADMISSION_ORIGIN_FAILED = "WBP_CUSTOM_CODEX_ADMISSION_ORIGIN_FAILED"
ADMISSION_SAME_TURN_BINDING_FAILED = (
    "WBP_CUSTOM_CODEX_ADMISSION_SAME_TURN_BINDING_FAILED"
)
ADMISSION_RUNTIME_TRUTH_MUTATED = "WBP_CUSTOM_CODEX_ADMISSION_RUNTIME_TRUTH_MUTATED"
ADMISSION_UNSAFE_PACKET = "WBP_CUSTOM_CODEX_ADMISSION_UNSAFE_PACKET"

DEFAULT_EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"
DEFAULT_SANDBOX = "danger-full-access"
DEFAULT_TIMEOUT_SECONDS = 300
RUNNER_LAUNCH_SURFACE = "wild-boar-proxy codex-runner admission"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(
            dict(value),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _input_hashes_digest(input_hashes: Mapping[str, str]) -> str:
    return _canonical_digest({"input_packet_hashes": dict(input_hashes)})


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _runtime_secret_values(runtime_context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    allowed = runtime_context.get("allowed_api_route_ids")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        values.extend(route for route in allowed if isinstance(route, str) and route)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(route for route in routes.values() if isinstance(route, str) and route)
    return sorted(set(values))


def _proof_dir(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "router-hook" / "admission" / f"custom-codex-{stamp}"


def _codex_bin(raw_codex_bin: str | None) -> tuple[str, str]:
    if raw_codex_bin:
        return raw_codex_bin, "argument"
    env_value = os.environ.get("WBP_CODEX_BIN", "")
    if env_value:
        return env_value, "env.WBP_CODEX_BIN"
    resolved = shutil.which("codex")
    if resolved:
        return resolved, "PATH.codex"
    return "codex", "fallback.codex"


def _runtime_context_route_ids(runtime_context: Mapping[str, Any]) -> set[str]:
    route_ids: set[str] = set()
    allowed = runtime_context.get("allowed_api_route_ids")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        route_ids.update(route for route in allowed if isinstance(route, str) and route)
    agent_routes = runtime_context.get("agent_id_to_route")
    if isinstance(agent_routes, Mapping):
        route_ids.update(
            route for route in agent_routes.values() if isinstance(route, str) and route
        )
    return route_ids


def _routes_file_contains_any_route(routes_file: Path, route_ids: set[str]) -> bool:
    if not route_ids or not routes_file.exists():
        return False
    try:
        parsed = json.loads(routes_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    routes = parsed.get("routes") if isinstance(parsed, Mapping) else None
    if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)):
        return False
    for route in routes:
        if not isinstance(route, Mapping):
            continue
        route_id = route.get("route_id")
        if isinstance(route_id, str) and route_id in route_ids:
            return True
    return False


def _select_external_models_dir(
    paths: RuntimePaths,
    runtime_context: Mapping[str, Any],
) -> tuple[Path, str]:
    explicit = os.environ.get("WBP_EXTERNAL_MODELS_DIR")
    if explicit:
        return Path(explicit).expanduser(), "env.WBP_EXTERNAL_MODELS_DIR"
    route_ids = _runtime_context_route_ids(runtime_context)
    managed_candidate = paths.managed_dir / "external-models"
    global_candidate = Path("~/.wild-boar-proxy/external-models").expanduser()
    if _routes_file_contains_any_route(managed_candidate / "routes.json", route_ids):
        return managed_candidate, "profile_managed_route_registry"
    if _routes_file_contains_any_route(global_candidate / "routes.json", route_ids):
        return global_candidate, "default_server_owned_route_registry"
    return managed_candidate, "profile_managed_default"


def _runner_env(paths: RuntimePaths, runtime_context: Mapping[str, Any]) -> dict[str, str]:
    env = build_launcher_subprocess_env(paths)
    external_models_dir, _ = _select_external_models_dir(paths, runtime_context)
    env["WBP_EXTERNAL_MODELS_DIR"] = str(external_models_dir)
    env["CODEX_HOME"] = str(paths.profile_dir)
    env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
    env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
    env.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    env.setdefault("no_proxy", env["NO_PROXY"])
    return env


def _runtime_truth_snapshots(paths: RuntimePaths) -> dict[str, dict[str, Any]]:
    return {
        "supervisor_state": snapshot_path_state(paths.state_file),
        "runtime_effective_mode": snapshot_path_state(paths.runtime_effective_mode_file),
        "config_toml": snapshot_path_state(paths.config_toml),
        "managed_config": snapshot_path_state(paths.managed_config_file),
    }


def _runtime_truth_unchanged(
    paths: RuntimePaths,
    before: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, list[str], dict[str, bool]]:
    candidates = {
        "supervisor_state": paths.state_file,
        "runtime_effective_mode": paths.runtime_effective_mode_file,
        "config_toml": paths.config_toml,
        "managed_config": paths.managed_config_file,
    }
    unchanged: dict[str, bool] = {}
    mutated: list[str] = []
    for key, path in candidates.items():
        current = snapshot_path_state(path)
        ok = dict(before.get(key, {"state": "missing"})) == current
        unchanged[key] = ok
        if not ok:
            mutated.append(key)
    return not mutated, mutated, unchanged


def _codex_exec_command(
    *,
    codex_bin: str,
    codex_cwd: Path,
    sandbox: str,
    prompt_text: str,
) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--json",
        "--sandbox",
        sandbox,
        "-C",
        str(codex_cwd),
        prompt_text,
    ]


def _redacted_command_digest(command: Sequence[str], *, prompt_text: str) -> str:
    redacted = [
        "<prompt-sha256>" if part == prompt_text else str(part)
        for part in command
    ]
    return _sha256_text(
        json.dumps(redacted, ensure_ascii=True, separators=(",", ":"))
    )


def _live_provider_packet_from_events(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_text: str,
) -> tuple[dict[str, Any], bool]:
    for event in events:
        item = event.get("item")
        if not isinstance(item, Mapping):
            continue
        if _safe_text(item.get("type"), limit=128) != "command_execution":
            continue
        command = _safe_text(item.get("command"), limit=65536)
        if "external-models" not in command or "live-format-check" not in command:
            continue
        try:
            parsed = json.loads(_safe_text(item.get("aggregated_output"), limit=65536))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, Mapping):
            continue
        packet = dict(parsed)
        data = packet.get("data")
        data_mapping = data if isinstance(data, Mapping) else {}
        if (
            packet.get("status") == "ok"
            and packet.get("machine_error_code") == ADMISSION_OK
            and data_mapping.get("expected_text_observed") is True
            and _safe_text(data_mapping.get("response_preview_bounded"), limit=512)
            == expected_text
        ):
            return packet, True
    return _live_provider_extract_error_packet(), False


def _live_provider_extract_error_packet() -> dict[str, Any]:
    return packets.build_command_packet(
        ok=False,
        human_message="WBP did not observe a live external-models provider packet in Codex exec JSONL.",
        machine_error_code=ADMISSION_LIVE_PROVIDER_NOT_OBSERVED,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra={
            "schema_version": 1,
            "packet_kind": LIVE_PROVIDER_EXTRACT_PACKET_KIND,
            "live_provider_packet_observed": False,
            "product_ready": False,
            "raw_prompt_recorded": False,
            "raw_route_id_recorded": False,
            "raw_provider_response_recorded": False,
            "secret_value_exposed": False,
            "state_written": False,
            "evidence_written": False,
            "file_mutation_attempted": False,
            "blocking_reasons": ["live_provider_packet_not_observed"],
        },
    )


def _write_packet(path: Path, packet: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(packet))
    return str(path)


def _create_and_verify_seal(
    *,
    packet_file: Path,
    seal_file: Path,
    producer_kind: str,
    producer_command_digest: str,
    input_packet_files: Sequence[Path],
    runtime_context_digest: str,
    hook_ledger_digest: str,
    profile_hook_config_digest: str,
    expected_packet_kind: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    input_hashes = {
        _safe_text(_read_json_mapping(path).get("packet_kind"), limit=120)
        or f"input_{index}": sha256_file(path)
        for index, path in enumerate(input_packet_files)
    }
    create_packet = run_proof_seal_create_command(
        packet_file=str(packet_file),
        seal_file=str(seal_file),
        producer_kind=producer_kind,
        producer_command_digest=producer_command_digest,
        producer_inputs_digest=_input_hashes_digest(input_hashes),
        input_packet_files=[str(path) for path in input_packet_files],
        runtime_context_digest=runtime_context_digest,
        hook_ledger_digest=hook_ledger_digest,
        profile_hook_config_digest=profile_hook_config_digest,
        git_commit_sha="",
    )
    verify_packet, _seal = verify_proof_seal(
        packet_file=str(packet_file),
        seal_file=str(seal_file),
        expected_packet_kind=expected_packet_kind,
        expected_input_packet_hashes=input_hashes,
        expected_runtime_context_digest=runtime_context_digest,
        expected_hook_ledger_digest=hook_ledger_digest,
        expected_profile_hook_config_digest=profile_hook_config_digest,
    )
    changed_files = []
    changed_files.extend(create_packet.get("changed_files", []))
    return create_packet, verify_packet, [str(path) for path in changed_files]


def _machine_error_code(
    *,
    codex_exit_ok: bool,
    provider_observed: bool,
    source_ok: bool,
    working_ok: bool,
    source_seal_ok: bool,
    working_seal_ok: bool,
    origin_ok: bool,
    same_turn_ok: bool,
    runtime_truth_ok: bool,
    unsafe: bool,
) -> str:
    if (
        codex_exit_ok
        and provider_observed
        and source_ok
        and working_ok
        and source_seal_ok
        and working_seal_ok
        and origin_ok
        and same_turn_ok
        and runtime_truth_ok
        and not unsafe
    ):
        return ADMISSION_OK
    if unsafe:
        return ADMISSION_UNSAFE_PACKET
    if not runtime_truth_ok:
        return ADMISSION_RUNTIME_TRUTH_MUTATED
    if not codex_exit_ok:
        return ADMISSION_CODEX_LAUNCH_FAILED
    if not provider_observed:
        return ADMISSION_LIVE_PROVIDER_NOT_OBSERVED
    if not source_ok:
        return ADMISSION_HOOK_PROOF_FAILED
    if not working_ok:
        return ADMISSION_WORKING_FLOW_FAILED
    if not source_seal_ok or not working_seal_ok:
        return ADMISSION_SEAL_FAILED
    if not origin_ok:
        return ADMISSION_ORIGIN_FAILED
    if not same_turn_ok:
        return ADMISSION_SAME_TURN_BINDING_FAILED
    return ADMISSION_UNSAFE_PACKET


def run_custom_codex_admission_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    expected_text: str = DEFAULT_EXPECTED_TEXT,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    proof_root = _proof_dir(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    changed_files: list[str] = []
    codex_bin_value, codex_bin_source = _codex_bin(codex_bin)
    cwd = Path(codex_cwd).expanduser() if codex_cwd else Path.cwd()
    safe_expected_text = _safe_text(expected_text, limit=128)
    prompt = str(prompt_text)
    runtime_context_file = runtime_context_path(paths=paths, runtime_context_file=None)
    runtime_context, _ = load_runtime_context_packet(runtime_context_file)
    secret_values = [prompt, safe_expected_text] + _runtime_secret_values(runtime_context)
    external_models_dir, external_models_dir_source = _select_external_models_dir(
        paths,
        runtime_context,
    )

    before_truth = _runtime_truth_snapshots(paths)
    ledger_path = hook_ledger_path(paths)
    ledger_was_cleared = False
    try:
        ledger_path.unlink(missing_ok=True)
        ledger_was_cleared = True
    except OSError:
        ledger_was_cleared = False

    admission_run_id = secrets.token_urlsafe(32)
    admission_run_id_digest = _sha256_text(admission_run_id)
    command = _codex_exec_command(
        codex_bin=codex_bin_value,
        codex_cwd=cwd,
        sandbox=sandbox,
        prompt_text=prompt,
    )
    stdout_path = proof_root / "codex-exec.jsonl"
    stderr_path = proof_root / "codex-exec.stderr.txt"
    process_returncode: int | None = None
    process_timeout = False
    process_error = ""
    try:
        runner_env = _runner_env(paths, runtime_context)
        runner_env["WBP_ADMISSION_RUN_ID"] = admission_run_id
        result = subprocess.run(
            command,
            cwd=cwd,
            env=runner_env,
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        process_returncode = result.returncode
        write_text_atomic(stdout_path, result.stdout.rstrip("\n"))
        write_text_atomic(stderr_path, result.stderr.rstrip("\n"))
    except subprocess.TimeoutExpired as exc:
        process_timeout = True
        process_returncode = None
        write_text_atomic(stdout_path, _safe_text(exc.stdout, limit=65536))
        write_text_atomic(stderr_path, _safe_text(exc.stderr, limit=65536))
    except OSError as exc:
        process_error = type(exc).__name__
        process_returncode = None
        write_text_atomic(stdout_path, "")
        write_text_atomic(stderr_path, _safe_text(str(exc), limit=4096))
    changed_files.extend([str(stdout_path), str(stderr_path)])

    events, jsonl_metadata = _read_jsonl_events_file(stdout_path)
    live_provider_packet, provider_observed = _live_provider_packet_from_events(
        events,
        expected_text=safe_expected_text,
    )
    live_provider_packet_path = proof_root / "live-provider-from-codex-exec.packet.json"
    changed_files.append(_write_packet(live_provider_packet_path, live_provider_packet))

    source_packet = run_real_custom_codex_hook_proof_command(
        paths=paths,
        prompt_text=prompt,
        hook_ledger_file=str(ledger_path),
        runtime_context_file=str(runtime_context_file),
        live_provider_expected_text=safe_expected_text,
        live_provider_proof_file=str(live_provider_packet_path),
    )
    source_packet_path = proof_root / "user-prompt-submit-proof.packet.json"
    changed_files.append(_write_packet(source_packet_path, source_packet))

    working_flow_packet = run_codex_working_flow_delivery_proof_command(
        integrated_live_provider_proof_file=str(source_packet_path),
        codex_exec_jsonl_file=str(stdout_path),
    )
    working_flow_packet_path = proof_root / "working-flow-delivery-proof.packet.json"
    changed_files.append(_write_packet(working_flow_packet_path, working_flow_packet))

    runtime_digest = _safe_text(source_packet.get("runtime_context_digest"), limit=80)
    hook_digest = sha256_file(ledger_path)
    hook_config_digest = _safe_text(
        source_packet.get("trusted_hook_config_sha256")
        or source_packet.get("loaded_hook_config_sha256"),
        limit=80,
    )

    source_seal_path = proof_root / "user-prompt-submit-proof.seal.json"
    source_seal_create, source_seal_verify, source_seal_changed = _create_and_verify_seal(
        packet_file=source_packet_path,
        seal_file=source_seal_path,
        producer_kind="wbp_custom_codex_admission_runner",
        producer_command_digest=_sha256_text("custom-codex-admission:user-prompt-submit-proof:v1"),
        input_packet_files=[],
        runtime_context_digest=runtime_digest,
        hook_ledger_digest=hook_digest,
        profile_hook_config_digest=hook_config_digest,
        expected_packet_kind=REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    )
    source_seal_verify_path = proof_root / "user-prompt-submit-proof.seal-verify.packet.json"
    changed_files.extend(source_seal_changed)
    changed_files.append(_write_packet(source_seal_verify_path, source_seal_verify))

    working_seal_path = proof_root / "working-flow-delivery-proof.seal.json"
    working_seal_create, working_seal_verify, working_seal_changed = _create_and_verify_seal(
        packet_file=working_flow_packet_path,
        seal_file=working_seal_path,
        producer_kind="wbp_custom_codex_admission_runner",
        producer_command_digest=_sha256_text("custom-codex-admission:working-flow-delivery-proof:v1"),
        input_packet_files=[source_packet_path],
        runtime_context_digest=runtime_digest,
        hook_ledger_digest=hook_digest,
        profile_hook_config_digest=hook_config_digest,
        expected_packet_kind=CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    )
    working_seal_verify_path = proof_root / "working-flow-delivery-proof.seal-verify.packet.json"
    changed_files.extend(working_seal_changed)
    changed_files.append(_write_packet(working_seal_verify_path, working_seal_verify))

    origin_packet = run_custom_codex_hook_origin_proof_command(
        paths=paths,
        integrated_live_provider_proof_file=str(source_packet_path),
        working_flow_delivery_proof_file=str(working_flow_packet_path),
        strict_sealed_evidence=True,
        integrated_live_provider_proof_seal_file=str(source_seal_path),
        working_flow_delivery_proof_seal_file=str(working_seal_path),
    )
    origin_packet_path = proof_root / "custom-origin-proof.strict-sealed.packet.json"
    changed_files.append(_write_packet(origin_packet_path, origin_packet))

    runtime_truth_ok, mutated_truth, unchanged_truth = _runtime_truth_unchanged(
        paths,
        before_truth,
    )
    codex_exit_ok = bool(process_returncode == 0 and not process_timeout and not process_error)
    source_ok = source_packet.get("status") == "ok"
    working_ok = working_flow_packet.get("status") == "ok"
    source_seal_ok = source_seal_verify.get("status") == "ok"
    working_seal_ok = working_seal_verify.get("status") == "ok"
    origin_ok = origin_packet.get("status") == "ok"

    hook_ledger_sha256 = sha256_file(ledger_path)
    source_proof_sha256 = sha256_file(source_packet_path)
    working_flow_proof_sha256 = sha256_file(working_flow_packet_path)
    origin_proof_sha256 = sha256_file(origin_packet_path)
    ledger_packet = _read_json_mapping(ledger_path)
    prompt_digest = _sha256_text(prompt)
    source_prompt_digest = _safe_text(source_packet.get("prompt_digest"), limit=80)
    ledger_prompt_digest = _safe_text(ledger_packet.get("prompt_digest"), limit=80)
    source_runtime_digest = _safe_text(
        source_packet.get("runtime_context_digest"),
        limit=80,
    )
    ledger_runtime_digest = _safe_text(
        ledger_packet.get("runtime_context_digest"),
        limit=80,
    )
    session_digest = _safe_text(ledger_packet.get("session_digest"), limit=80)
    thread_digest = _safe_text(ledger_packet.get("thread_digest"), limit=80)
    turn_digest = _safe_text(ledger_packet.get("turn_digest"), limit=80)
    ledger_admission_run_id_digest = _safe_text(
        ledger_packet.get("admission_run_id_digest"),
        limit=80,
    )
    source_admission_run_id_digest = _safe_text(
        source_packet.get("hook_admission_run_id_digest"),
        limit=80,
    )
    source_session_digest = _safe_text(source_packet.get("hook_session_digest"), limit=80)
    source_thread_digest = _safe_text(source_packet.get("hook_thread_digest"), limit=80)
    source_turn_digest = _safe_text(source_packet.get("hook_turn_digest"), limit=80)
    recomputed_codex_exec_transcript_digest = (
        _codex_exec_transcript_digest(events) if events else ""
    )
    working_flow_transcript_digest = _safe_text(
        working_flow_packet.get("codex_exec_transcript_sha256"),
        limit=80,
    )
    source_seal_expected_input_hashes: dict[str, str] = {}
    working_seal_expected_input_hashes = {
        REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND: source_proof_sha256,
    }
    source_seal_expected_input_digest = _canonical_digest(
        source_seal_expected_input_hashes
    )
    working_seal_expected_input_digest = _canonical_digest(
        working_seal_expected_input_hashes
    )
    source_seal_input_hashes_bound = bool(
        source_seal_verify.get("status") == "ok"
        and _safe_text(
            source_seal_verify.get("seal_input_packet_hashes_digest"),
            limit=80,
        )
        == source_seal_expected_input_digest
    )
    source_seal_declared_input_packet_hashes_empty = source_seal_input_hashes_bound
    source_seal_runtime_context_digest_bound = bool(
        source_seal_verify.get("status") == "ok"
        and _safe_text(source_seal_verify.get("runtime_context_digest"), limit=80)
        == runtime_digest
        and bool(runtime_digest)
    )
    source_seal_hook_ledger_digest_bound = bool(
        source_seal_verify.get("status") == "ok"
        and _safe_text(source_seal_verify.get("hook_ledger_digest"), limit=80)
        == hook_digest
        and bool(hook_digest)
    )
    source_seal_profile_hook_config_digest_bound = bool(
        source_seal_verify.get("status") == "ok"
        and _safe_text(source_seal_verify.get("profile_hook_config_digest"), limit=80)
        == hook_config_digest
        and bool(hook_config_digest)
    )
    working_flow_seal_input_hashes_bound = bool(
        working_seal_verify.get("status") == "ok"
        and _safe_text(
            working_seal_verify.get("seal_input_packet_hashes_digest"),
            limit=80,
        )
        == working_seal_expected_input_digest
    )
    prompt_digest_bound = bool(
        prompt_digest
        and source_prompt_digest == prompt_digest
        and ledger_prompt_digest == prompt_digest
    )
    runtime_context_digest_bound = bool(
        source_runtime_digest
        and ledger_runtime_digest == source_runtime_digest
        and source_packet.get("hook_runtime_context_digest_bound") is True
    )
    admission_run_id_digest_bound = bool(
        admission_run_id_digest
        and ledger_admission_run_id_digest == admission_run_id_digest
        and source_admission_run_id_digest == admission_run_id_digest
    )
    session_or_turn_digest_bound = bool(
        source_packet.get("thread_or_turn_digest_bound") is True
        and (session_digest or thread_digest or turn_digest)
        and (thread_digest or turn_digest)
        and source_session_digest == session_digest
        and source_thread_digest == thread_digest
        and source_turn_digest == turn_digest
    )
    codex_exec_transcript_bound = bool(
        jsonl_metadata.get("codex_exec_jsonl_file_read") is True
        and jsonl_metadata.get("codex_exec_jsonl_file_valid_jsonl") is True
        and sha256_file(stdout_path)
        and recomputed_codex_exec_transcript_digest
        and working_flow_transcript_digest == recomputed_codex_exec_transcript_digest
    )
    run_graph_digest = _canonical_digest(
        {
            "hook_ledger_sha256": hook_ledger_sha256,
            "source_proof_sha256": source_proof_sha256,
            "working_flow_proof_sha256": working_flow_proof_sha256,
            "origin_proof_sha256": origin_proof_sha256,
            "codex_exec_jsonl_sha256": sha256_file(stdout_path),
            "codex_exec_transcript_sha256": _safe_text(
                working_flow_packet.get("codex_exec_transcript_sha256"),
                limit=80,
            ),
            "prompt_digest": prompt_digest,
            "runtime_context_digest": source_runtime_digest,
            "admission_run_id_digest": admission_run_id_digest,
        }
    )
    run_id_bound = bool(
        admission_run_id_digest_bound
        and hook_ledger_sha256
        and source_proof_sha256
        and working_flow_proof_sha256
        and origin_proof_sha256
        and run_graph_digest
    )
    same_turn_binding_failures: list[str] = []
    if not run_id_bound:
        same_turn_binding_failures.append("run_id_not_bound")
    if not admission_run_id_digest_bound:
        same_turn_binding_failures.append("admission_run_id_digest_not_bound")
    if not ledger_was_cleared:
        same_turn_binding_failures.append("hook_ledger_not_cleared_before_run")
    if not hook_ledger_sha256:
        same_turn_binding_failures.append("hook_ledger_sha256_missing")
    if not prompt_digest_bound:
        same_turn_binding_failures.append("prompt_digest_not_bound")
    if not runtime_context_digest_bound:
        same_turn_binding_failures.append("runtime_context_digest_not_bound")
    if not session_or_turn_digest_bound:
        same_turn_binding_failures.append("session_or_turn_digest_not_bound")
    if not codex_exec_transcript_bound:
        same_turn_binding_failures.append("codex_exec_transcript_not_bound")
    if not source_proof_sha256:
        same_turn_binding_failures.append("source_proof_sha256_missing")
    if not working_flow_proof_sha256:
        same_turn_binding_failures.append("working_flow_proof_sha256_missing")
    if not source_seal_input_hashes_bound:
        same_turn_binding_failures.append("source_seal_input_hashes_not_declared_empty")
    if not source_seal_runtime_context_digest_bound:
        same_turn_binding_failures.append("source_seal_runtime_context_digest_not_bound")
    if not source_seal_hook_ledger_digest_bound:
        same_turn_binding_failures.append("source_seal_hook_ledger_digest_not_bound")
    if not source_seal_profile_hook_config_digest_bound:
        same_turn_binding_failures.append(
            "source_seal_profile_hook_config_digest_not_bound"
        )
    if not working_flow_seal_input_hashes_bound:
        same_turn_binding_failures.append("working_flow_seal_input_hashes_not_bound")
    same_turn_ok = not same_turn_binding_failures

    admission_proven = bool(
        codex_exit_ok
        and provider_observed
        and source_ok
        and working_ok
        and source_seal_ok
        and working_seal_ok
        and origin_ok
        and same_turn_ok
        and runtime_truth_ok
    )
    blocking_reasons: list[str] = []
    if not codex_exit_ok:
        blocking_reasons.append("codex_exec_failed")
    if not provider_observed:
        blocking_reasons.append("live_provider_packet_not_observed")
    if not source_ok:
        blocking_reasons.append("user_prompt_submit_proof_not_ok")
    if not working_ok:
        blocking_reasons.append("working_flow_delivery_proof_not_ok")
    if not source_seal_ok:
        blocking_reasons.append("source_proof_seal_not_ok")
    if not working_seal_ok:
        blocking_reasons.append("working_flow_proof_seal_not_ok")
    if not origin_ok:
        blocking_reasons.append("custom_origin_proof_not_ok")
    blocking_reasons.extend(same_turn_binding_failures)
    for truth_key in mutated_truth:
        blocking_reasons.append(f"runtime_truth_mutated:{truth_key}")

    unsafe = packets.command_packet_has_secret_leak(
        {
            "packet_kind": CUSTOM_CODEX_ADMISSION_PACKET_KIND,
            "proof_artifacts": changed_files,
            "origin_packet_sha256": sha256_file(origin_packet_path),
        },
        secret_values=secret_values,
    )
    machine_error_code = _machine_error_code(
        codex_exit_ok=codex_exit_ok,
        provider_observed=provider_observed,
        source_ok=source_ok,
        working_ok=working_ok,
        source_seal_ok=source_seal_ok,
        working_seal_ok=working_seal_ok,
        origin_ok=origin_ok,
        same_turn_ok=same_turn_ok,
        runtime_truth_ok=runtime_truth_ok,
        unsafe=unsafe,
    )
    if unsafe:
        blocking_reasons.append("admission_packet_secret_leak")
    admission_packet_path = proof_root / "custom-codex-admission.packet.json"
    changed_files.append(str(admission_packet_path))

    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_ADMISSION_PACKET_KIND,
        "runner_launch_surface": RUNNER_LAUNCH_SURFACE,
        "runner_launch_surface_kind": "custom_codex_cli_exec",
        "admission_scope": "repeatable_custom_codex_runtime_proof",
        "admission_proven": admission_proven,
        "repeatable_custom_codex_admission_proven": admission_proven,
        "same_turn_proof_runner_v1": True,
        "same_turn_custom_codex_flow_proven": admission_proven,
        "same_turn_claim_ceiling": (
            "custom_codex_exec_working_flow_only_no_ui_no_native_router_no_product"
        ),
        "run_id_bound": run_id_bound,
        "admission_run_id_digest_bound": admission_run_id_digest_bound,
        "admission_run_id_digest": admission_run_id_digest,
        "admission_run_id_recorded": False,
        "run_graph_digest": run_graph_digest,
        "session_or_turn_digest_bound": session_or_turn_digest_bound,
        "session_digest_present": bool(session_digest),
        "thread_digest_present": bool(thread_digest),
        "turn_digest_present": bool(turn_digest),
        "session_digest_bound_to_source": bool(
            source_session_digest == session_digest and bool(session_digest)
        ),
        "thread_digest_bound_to_source": bool(
            source_thread_digest == thread_digest and bool(thread_digest)
        ),
        "turn_digest_bound_to_source": bool(
            source_turn_digest == turn_digest and bool(turn_digest)
        ),
        "prompt_digest_bound": prompt_digest_bound,
        "runtime_context_digest_bound": runtime_context_digest_bound,
        "hook_ledger_fresh": bool(
            ledger_was_cleared
            and source_packet.get("hook_producer_ledger_proven") is True
        ),
        "hook_ledger_sha256": hook_ledger_sha256,
        "source_proof_sha256": source_proof_sha256,
        "working_flow_proof_sha256": working_flow_proof_sha256,
        "origin_proof_sha256": origin_proof_sha256,
        "codex_exec_transcript_bound": codex_exec_transcript_bound,
        "recomputed_codex_exec_transcript_sha256": (
            recomputed_codex_exec_transcript_digest
        ),
        "working_flow_codex_exec_transcript_sha256": working_flow_transcript_digest,
        "source_seal_input_hashes_bound": source_seal_input_hashes_bound,
        "source_seal_declared_input_packet_hashes_empty": (
            source_seal_declared_input_packet_hashes_empty
        ),
        "source_seal_runtime_context_digest_bound": (
            source_seal_runtime_context_digest_bound
        ),
        "source_seal_hook_ledger_digest_bound": source_seal_hook_ledger_digest_bound,
        "source_seal_profile_hook_config_digest_bound": (
            source_seal_profile_hook_config_digest_bound
        ),
        "source_seal_input_hashes_digest": _safe_text(
            source_seal_verify.get("seal_input_packet_hashes_digest"),
            limit=80,
        ),
        "source_seal_expected_input_hashes_digest": source_seal_expected_input_digest,
        "working_flow_seal_input_hashes_bound": (
            working_flow_seal_input_hashes_bound
        ),
        "working_flow_seal_input_hashes_digest": _safe_text(
            working_seal_verify.get("seal_input_packet_hashes_digest"),
            limit=80,
        ),
        "working_flow_expected_seal_input_hashes_digest": (
            working_seal_expected_input_digest
        ),
        "same_turn_binding_failures": same_turn_binding_failures,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_proven": False,
        "does_not_prove_custom_codex_ui": True,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "custom_codex_profile_env_present": True,
        "code_home_bound_to_custom_profile": True,
        "wbp_profile_dir_bound_to_custom_profile": True,
        "codex_exec_command_sha256": _redacted_command_digest(command, prompt_text=prompt),
        "codex_exec_prompt_digest": _sha256_text(prompt),
        "codex_exec_prompt_recorded": False,
        "codex_exec_timeout": process_timeout,
        "codex_exec_process_error": _safe_text(process_error, limit=80),
        "codex_exec_returncode_zero": process_returncode == 0,
        "codex_exec_jsonl_sha256": sha256_file(stdout_path),
        "codex_exec_stderr_sha256": sha256_file(stderr_path),
        "codex_exec_jsonl_file_read": jsonl_metadata.get("codex_exec_jsonl_file_read")
        is True,
        "codex_exec_jsonl_file_valid_jsonl": jsonl_metadata.get(
            "codex_exec_jsonl_file_valid_jsonl"
        )
        is True,
        "codex_exec_transcript_sha256": _safe_text(
            working_flow_packet.get("codex_exec_transcript_sha256"),
            limit=80,
        ),
        "same_codex_exec_jsonl_bound": codex_exec_transcript_bound,
        "codex_exec_event_count": int(jsonl_metadata.get("codex_exec_event_count") or 0),
        "codex_bin_source": _safe_text(codex_bin_source, limit=80),
        "codex_bin_path_recorded": False,
        "external_models_dir_source": _safe_text(
            external_models_dir_source,
            limit=80,
        ),
        "external_models_dir_path_recorded": False,
        "external_models_dir_route_registry_selected": bool(external_models_dir),
        "proof_dir_path_recorded": False,
        "ledger_cleared_before_run": ledger_was_cleared,
        "declared_write_surfaces": [
            "proof_dir",
            "custom_profile_hook_ledger",
            "proof_packets",
            "proof_seals",
        ],
        "runtime_effective_truth_unchanged": runtime_truth_ok,
        "supervisor_state_unchanged": unchanged_truth.get("supervisor_state") is True,
        "runtime_effective_mode_unchanged": unchanged_truth.get("runtime_effective_mode")
        is True,
        "config_toml_unchanged": unchanged_truth.get("config_toml") is True,
        "managed_config_unchanged": unchanged_truth.get("managed_config") is True,
        "runtime_truth_mutated_surfaces": mutated_truth,
        "live_provider_packet_observed": provider_observed,
        "live_provider_packet_sha256": sha256_file(live_provider_packet_path),
        "user_prompt_submit_proof_packet_kind": _safe_text(
            source_packet.get("packet_kind"),
            limit=80,
        ),
        "user_prompt_submit_hook_ran": source_packet.get("user_prompt_submit_hook_ran")
        is True,
        "hook_ledger_bound": source_packet.get("hook_producer_ledger_proven") is True,
        "hook_prompt_digest_bound": source_packet.get("hook_prompt_digest_bound") is True,
        "runtime_context_bound": source_packet.get("hook_runtime_context_digest_bound")
        is True,
        "hook_runtime_context_digest_bound": source_packet.get(
            "hook_runtime_context_digest_bound"
        )
        is True,
        "hook_config_digest_bound": source_packet.get("hook_config_digest_bound") is True,
        "alias_context_read": source_packet.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": source_packet.get(
            "allowed_api_route_ids_enforced"
        )
        is True,
        "route_id_allowed": source_packet.get("route_id_allowed") is True,
        "server_issued_cli_command_bound": source_packet.get(
            "live_provider_cli_command_route_bound"
        )
        is True,
        "api_lane_called": bool(
            provider_observed
            and source_ok
            and working_ok
            and
            source_packet.get("api_lane_called") is True
            and working_flow_packet.get("api_lane_called") is True
        ),
        "live_provider_response_proven": bool(
            source_packet.get("live_provider_response_proven") is True
            and working_flow_packet.get("live_provider_response_proven") is True
        ),
        "external_live_provider_response_proven": bool(
            source_packet.get("external_live_provider_response_proven") is True
            and working_flow_packet.get("external_live_provider_response_proven")
            is True
        ),
        "approved_handoff_proven": bool(
            source_packet.get("approved_handoff_ready") is True
            and working_flow_packet.get("approved_handoff_ready") is True
            and working_flow_packet.get("handoff_delivered") is True
        ),
        "approved_delivery_surface_proven": working_flow_packet.get(
            "approved_delivery_surface_proven"
        )
        is True,
        "handoff_delivered": working_flow_packet.get("handoff_delivered") is True,
        "working_flow_delivery_proof_packet_kind": _safe_text(
            working_flow_packet.get("packet_kind"),
            limit=80,
        ),
        "codex_working_flow_delivery_proven": working_flow_packet.get(
            "codex_working_flow_delivery_proven"
        )
        is True,
        "codex_exec_assistant_continuation_proven": working_flow_packet.get(
            "codex_exec_assistant_continuation_proven"
        )
        is True,
        "assistant_response_after_tool_result": working_flow_packet.get(
            "assistant_response_after_tool_result"
        )
        is True,
        "assistant_response_bound_to_handoff_digest": working_flow_packet.get(
            "assistant_response_bound_to_handoff_digest"
        )
        is True,
        "command_assistant_response_after_command": working_flow_packet.get(
            "command_assistant_response_after_command"
        )
        is True,
        "command_assistant_response_bound_to_live_provider_digest": (
            working_flow_packet.get(
                "command_assistant_response_bound_to_live_provider_digest"
            )
            is True
        ),
        "custom_codex_hook_origin_proof_packet_kind": _safe_text(
            origin_packet.get("packet_kind"),
            limit=80,
        ),
        "command_origin_proven": origin_packet.get("command_origin_proven") is True,
        "custom_codex_flow_proven": origin_packet.get("custom_codex_flow_proven") is True,
        "strict_sealed_evidence": origin_packet.get("strict_sealed_evidence") is True,
        "proof_seal_verified": bool(source_seal_ok and working_seal_ok),
        "source_file_authenticity_proven": origin_packet.get(
            "source_file_authenticity_proven"
        )
        is True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_expected_text_recorded": False,
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "browser_can_supply_admission_authority": False,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "proof_dir_written": True,
        "hook_ledger_written": source_packet.get("hook_ledger_written") is True,
        "transcript_written": True,
        "user_prompt_submit_proof_written": True,
        "working_flow_delivery_proof_written": True,
        "proof_seal_written": True,
        "admission_packet_written": True,
        "source_proof_machine_error_code": _safe_text(
            source_packet.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_machine_error_code": _safe_text(
            working_flow_packet.get("machine_error_code"),
            limit=96,
        ),
        "source_seal_create_machine_error_code": _safe_text(
            source_seal_create.get("machine_error_code"),
            limit=96,
        ),
        "working_seal_create_machine_error_code": _safe_text(
            working_seal_create.get("machine_error_code"),
            limit=96,
        ),
        "source_seal_machine_error_code": _safe_text(
            source_seal_verify.get("machine_error_code"),
            limit=96,
        ),
        "working_seal_machine_error_code": _safe_text(
            working_seal_verify.get("machine_error_code"),
            limit=96,
        ),
        "origin_proof_machine_error_code": _safe_text(
            origin_packet.get("machine_error_code"),
            limit=96,
        ),
        "blocking_reasons": sorted(set(blocking_reasons)),
        "changed_files": sorted(set(changed_files)),
    }
    packet = packets.build_command_packet(
        ok=admission_proven and not unsafe,
        human_message=(
            "WBP proved repeatable Custom Codex admission through hook, live API lane, sealed evidence, and working-flow delivery."
            if admission_proven and not unsafe
            else "WBP blocked repeatable Custom Codex admission before product readiness."
        ),
        machine_error_code=machine_error_code,
        liveness="network_dependent",
        severity="recoverable",
        operator_action="none" if admission_proven and not unsafe else "stop",
        changed_files=sorted(set(changed_files)),
        effect=EFFECT_MUTATE,
        secret_values=secret_values,
        extra=extra,
    )
    write_json_atomic(admission_packet_path, packet)
    return packet

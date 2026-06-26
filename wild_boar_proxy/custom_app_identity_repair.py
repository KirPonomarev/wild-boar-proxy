# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from typing import Any

from .command_effects import EFFECT_PROBE, EFFECT_REPAIR
from .core import packets
from .custom_ui_origin_admission import (
    default_custom_codex_app_path,
    default_stock_codex_app_path,
)
from .runtime import RuntimePaths


CUSTOM_APP_IDENTITY_REPAIR_PACKET_KIND = "wbp_custom_app_identity_repair"

CUSTOM_APP_IDENTITY_OK = "OK"
CUSTOM_APP_IDENTITY_READY = "WBP_CUSTOM_APP_IDENTITY_REPAIR_READY"
CUSTOM_APP_IDENTITY_NOT_NEEDED = "WBP_CUSTOM_APP_IDENTITY_REPAIR_NOT_NEEDED"
CUSTOM_APP_IDENTITY_NOT_ADMITTED = "WBP_CUSTOM_APP_IDENTITY_REPAIR_NOT_ADMITTED"
CUSTOM_APP_IDENTITY_CODESIGN_FAILED = "WBP_CUSTOM_APP_IDENTITY_CODESIGN_FAILED"
CUSTOM_APP_IDENTITY_INVALID = "WBP_CUSTOM_APP_IDENTITY_REPAIR_INVALID"

DESIRED_CUSTOM_BUNDLE_ID = "com.wildboarproxy.codex.wbpclean"
DESIRED_CUSTOM_BUNDLE_NAME = "Codex WBP Clean"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return ""


def _bundle_integrity_digest(app_path: Path) -> str:
    digest = hashlib.sha256()
    relative_files = [
        Path("Contents/Info.plist"),
        Path("Contents/MacOS/Codex"),
        Path("Contents/Resources/app.asar"),
    ]
    signature_dir = app_path / "Contents" / "_CodeSignature"
    if signature_dir.is_dir():
        relative_files.extend(
            path.relative_to(app_path)
            for path in sorted(signature_dir.rglob("*"))
            if path.is_file()
        )
    for relative_file in sorted(set(relative_files)):
        path = app_path / relative_file
        digest.update(str(relative_file).encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def _read_plist(path: Path) -> tuple[dict[str, Any], str]:
    try:
        with path.open("rb") as handle:
            parsed = plistlib.load(handle)
    except FileNotFoundError:
        return {}, "plist_missing"
    except (OSError, plistlib.InvalidFileException, ValueError):
        return {}, "plist_invalid"
    if not isinstance(parsed, dict):
        return {}, "plist_not_mapping"
    return parsed, ""


def _fsync_parent_best_effort(parent: Path) -> None:
    try:
        parent_fd = os.open(parent, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(parent_fd)
        except OSError:
            return
    finally:
        os.close(parent_fd)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    target = Path(path)
    temp_path = ""
    fd = -1
    mode: int | None = None
    try:
        try:
            mode = target.stat().st_mode & 0o777
        except OSError:
            mode = None
        fd, temp_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=".wbp-tmp-",
            suffix=f".{target.name}",
        )
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            if mode is not None:
                os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        temp_path = ""
        _fsync_parent_best_effort(target.parent)
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _write_plist_atomic(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        plistlib.dumps(payload, sort_keys=False),
    )


def _restore_plist_atomic(path: Path, original_bytes: bytes) -> bool:
    try:
        _atomic_write_bytes(path, original_bytes)
    except OSError:
        return False
    return True


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _default_backup_dir(paths: RuntimePaths) -> Path:
    return paths.profile_dir / "managed" / "custom-app-identity-backups"


def _codesign_verify(app_path: Path) -> tuple[bool, int, str]:
    completed = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(
        item for item in (completed.stdout.strip(), completed.stderr.strip()) if item
    )
    return completed.returncode == 0, completed.returncode, output[:4000]


def _codesign_ad_hoc(app_path: Path) -> tuple[bool, int, str]:
    completed = subprocess.run(
        ["codesign", "--force", "--sign", "-", str(app_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(
        item for item in (completed.stdout.strip(), completed.stderr.strip()) if item
    )
    return completed.returncode == 0, completed.returncode, output[:4000]


def _identity_values(plist: dict[str, Any]) -> dict[str, str]:
    return {
        "bundle_id": str(plist.get("CFBundleIdentifier", "") or ""),
        "bundle_name": str(plist.get("CFBundleName", "") or ""),
        "bundle_display_name": str(plist.get("CFBundleDisplayName", "") or ""),
        "bundle_executable": str(plist.get("CFBundleExecutable", "") or ""),
    }


def build_custom_app_identity_repair_packet(
    *,
    paths: RuntimePaths,
    apply: bool,
    stock_app_path: str | None = None,
    custom_app_path: str | None = None,
    backup_dir: str | None = None,
    desired_bundle_id: str = DESIRED_CUSTOM_BUNDLE_ID,
    desired_bundle_name: str = DESIRED_CUSTOM_BUNDLE_NAME,
) -> dict[str, Any]:
    stock_app = Path(stock_app_path).expanduser() if stock_app_path else default_stock_codex_app_path()
    custom_app = (
        Path(custom_app_path).expanduser()
        if custom_app_path
        else default_custom_codex_app_path()
    )
    backup_root = Path(backup_dir).expanduser() if backup_dir else _default_backup_dir(paths)

    stock_plist_path = stock_app / "Contents" / "Info.plist"
    custom_plist_path = custom_app / "Contents" / "Info.plist"
    stock_plist, stock_read_error = _read_plist(stock_plist_path)
    custom_plist, custom_read_error = _read_plist(custom_plist_path)
    stock_identity = _identity_values(stock_plist)
    custom_identity = _identity_values(custom_plist)

    stock_bin = stock_app / "Contents" / "MacOS" / "Codex"
    custom_bin = custom_app / "Contents" / "MacOS" / "Codex"
    stock_asar = stock_app / "Contents" / "Resources" / "app.asar"
    custom_asar = custom_app / "Contents" / "Resources" / "app.asar"
    stock_bin_hash = _file_sha256(stock_bin)
    custom_bin_hash = _file_sha256(custom_bin)
    stock_asar_hash = _file_sha256(stock_asar)
    custom_asar_hash = _file_sha256(custom_asar)
    binary_hash_matches_stock = bool(stock_bin_hash and stock_bin_hash == custom_bin_hash)
    asar_hash_matches_stock = bool(stock_asar_hash and stock_asar_hash == custom_asar_hash)
    custom_path_distinct_from_stock = (
        custom_app.resolve(strict=False) != stock_app.resolve(strict=False)
    )
    backup_under_profile = _is_subpath(backup_root, paths.profile_dir)
    custom_codesign_valid_before, _, custom_codesign_verify_output_before = (
        _codesign_verify(custom_app)
    )
    pre_repair_integrity_digest = _bundle_integrity_digest(custom_app)
    custom_codesign_verify_output_before_digest = _sha256_bytes(
        custom_codesign_verify_output_before.encode("utf-8")
    )
    custom_identity_desired_before = (
        custom_identity["bundle_id"] == desired_bundle_id
        and custom_identity["bundle_name"] == desired_bundle_name
        and custom_identity["bundle_display_name"] == desired_bundle_name
    )
    binary_hash_mismatch_allowed_as_wbp_signature_mutation = bool(
        not binary_hash_matches_stock
        and asar_hash_matches_stock
        and custom_codesign_valid_before
        and custom_identity_desired_before
    )

    desired_plist = dict(custom_plist)
    desired_plist["CFBundleIdentifier"] = desired_bundle_id
    desired_plist["CFBundleName"] = desired_bundle_name
    desired_plist["CFBundleDisplayName"] = desired_bundle_name
    desired_plist["CFBundleExecutable"] = custom_identity["bundle_executable"] or "Codex"

    identity_changes_needed = {
        "CFBundleIdentifier": custom_identity["bundle_id"] != desired_bundle_id,
        "CFBundleName": custom_identity["bundle_name"] != desired_bundle_name,
        "CFBundleDisplayName": (
            custom_identity["bundle_display_name"] != desired_bundle_name
        ),
    }
    codesign_repair_needed = not custom_codesign_valid_before
    repair_needed = any(identity_changes_needed.values()) or codesign_repair_needed

    admission_failures: list[str] = []
    if stock_read_error:
        admission_failures.append(f"stock_{stock_read_error}")
    if custom_read_error:
        admission_failures.append(f"custom_{custom_read_error}")
    if not custom_path_distinct_from_stock:
        admission_failures.append("custom_app_path_matches_stock_app_path")
    if custom_identity["bundle_executable"] not in {"", "Codex"}:
        admission_failures.append("custom_bundle_executable_not_preserved")
    if (
        not binary_hash_matches_stock
        and not binary_hash_mismatch_allowed_as_wbp_signature_mutation
    ):
        admission_failures.append("custom_binary_hash_mismatch")
    if not asar_hash_matches_stock:
        admission_failures.append("custom_asar_hash_mismatch")
    if not backup_under_profile:
        admission_failures.append("backup_dir_not_profile_owned")
    if not desired_bundle_id or desired_bundle_id == stock_identity["bundle_id"]:
        admission_failures.append("desired_bundle_id_not_distinct_from_stock")
    if not desired_bundle_name:
        admission_failures.append("desired_bundle_name_missing")

    backup_path = backup_root / (
        f"Info.plist.{_utc_stamp()}.{_file_sha256(custom_plist_path)[:12]}.bak"
    )
    changed_files: list[str] = []
    mutation_attempted = False
    backup_written = False
    plist_written = False
    codesign_attempted = False
    codesign_ok = False
    codesign_exit_code = 0
    codesign_output_digest = ""
    plist_rollback_restored = False

    if apply and not admission_failures and repair_needed:
        mutation_attempted = True
        original_bytes = custom_plist_path.read_bytes()
        backup_root.mkdir(parents=True, exist_ok=True)
        try:
            _atomic_write_bytes(backup_path, original_bytes)
            backup_written = True
            changed_files.append(str(backup_path))
            if any(identity_changes_needed.values()):
                _write_plist_atomic(custom_plist_path, desired_plist)
                plist_written = True
                changed_files.append(str(custom_plist_path))
            codesign_attempted = True
            codesign_ok, codesign_exit_code, codesign_output = _codesign_ad_hoc(
                custom_app
            )
            codesign_output_digest = _sha256_bytes(codesign_output.encode("utf-8"))
            changed_files.append(str(custom_app))
            if not codesign_ok:
                plist_rollback_restored = _restore_plist_atomic(
                    custom_plist_path, original_bytes
                )
                if not plist_rollback_restored:
                    admission_failures.append("plist_restore_failed")
                admission_failures.append("codesign_failed")
        except OSError:
            if backup_written:
                plist_rollback_restored = _restore_plist_atomic(
                    custom_plist_path, original_bytes
                )
                if not plist_rollback_restored:
                    admission_failures.append("plist_restore_failed")
            admission_failures.append(
                "backup_write_failed" if not backup_written else "plist_write_failed"
            )

    post_custom_plist, post_read_error = _read_plist(custom_plist_path)
    post_identity = _identity_values(post_custom_plist)
    binary_hash_matches_stock_after = bool(
        stock_bin_hash and stock_bin_hash == _file_sha256(custom_bin)
    )
    asar_hash_matches_stock_after = bool(
        stock_asar_hash and stock_asar_hash == _file_sha256(custom_asar)
    )
    custom_codesign_valid_after, custom_codesign_exit_code_after, custom_codesign_verify_output_after = (
        _codesign_verify(custom_app)
    )
    custom_codesign_verify_output_after_digest = _sha256_bytes(
        custom_codesign_verify_output_after.encode("utf-8")
    )
    post_repair_integrity_digest = _bundle_integrity_digest(custom_app)
    codesign_failure_side_effects_detected = bool(
        apply
        and codesign_attempted
        and not codesign_ok
        and pre_repair_integrity_digest != post_repair_integrity_digest
    )
    rollback_restored = bool(
        plist_rollback_restored and not codesign_failure_side_effects_detected
    )
    identity_distinct_after = (
        bool(post_identity["bundle_id"])
        and post_identity["bundle_id"] != stock_identity["bundle_id"]
    )
    identity_repaired = (
        identity_distinct_after
        and post_identity["bundle_id"] == desired_bundle_id
        and post_identity["bundle_name"] == desired_bundle_name
        and post_identity["bundle_display_name"] == desired_bundle_name
        and not post_read_error
    )

    if apply and repair_needed and not identity_repaired:
        admission_failures.append("identity_not_repaired")
    if apply and repair_needed and not asar_hash_matches_stock_after:
        admission_failures.append("custom_asar_hash_changed")
    if apply and repair_needed and not custom_codesign_valid_after:
        admission_failures.append("codesign_invalid_after_repair")
    if codesign_failure_side_effects_detected:
        admission_failures.append("codesign_side_effects_after_failure")

    repair_ready = not apply and repair_needed and not admission_failures
    ok = not admission_failures and (identity_repaired or not repair_needed or repair_ready)
    if admission_failures:
        if "codesign_failed" in admission_failures:
            machine_error_code = CUSTOM_APP_IDENTITY_CODESIGN_FAILED
        elif any(reason.endswith("_missing") or reason.endswith("_invalid") for reason in admission_failures):
            machine_error_code = CUSTOM_APP_IDENTITY_INVALID
        else:
            machine_error_code = CUSTOM_APP_IDENTITY_NOT_ADMITTED
    elif repair_ready:
        machine_error_code = CUSTOM_APP_IDENTITY_READY
    elif not repair_needed:
        machine_error_code = CUSTOM_APP_IDENTITY_NOT_NEEDED
    else:
        machine_error_code = CUSTOM_APP_IDENTITY_OK

    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_APP_IDENTITY_REPAIR_PACKET_KIND,
        "apply": bool(apply),
        "dry_run": not apply,
        "proof_scope": "wbp_owned_custom_codex_app_identity_repair_only",
        "stock_app_present": stock_app.exists(),
        "custom_app_present": custom_app.exists(),
        "stock_app_path_recorded": False,
        "custom_app_path_recorded": False,
        "stock_info_plist_present": stock_plist_path.exists(),
        "custom_info_plist_present": custom_plist_path.exists(),
        "stock_bundle_id": stock_identity["bundle_id"],
        "custom_bundle_id_before": custom_identity["bundle_id"],
        "custom_bundle_id_after": post_identity["bundle_id"],
        "desired_custom_bundle_id": desired_bundle_id,
        "custom_bundle_name_before": custom_identity["bundle_name"],
        "custom_bundle_name_after": post_identity["bundle_name"],
        "desired_custom_bundle_name": desired_bundle_name,
        "custom_bundle_display_name_before": custom_identity["bundle_display_name"],
        "custom_bundle_display_name_after": post_identity["bundle_display_name"],
        "custom_bundle_executable_before": custom_identity["bundle_executable"],
        "custom_bundle_executable_after": post_identity["bundle_executable"],
        "custom_path_distinct_from_stock": custom_path_distinct_from_stock,
        "binary_hash_matches_stock": binary_hash_matches_stock,
        "asar_hash_matches_stock": asar_hash_matches_stock,
        "binary_hash_matches_stock_after": binary_hash_matches_stock_after,
        "asar_hash_matches_stock_after": asar_hash_matches_stock_after,
        "binary_hash_mismatch_allowed_as_wbp_signature_mutation": (
            binary_hash_mismatch_allowed_as_wbp_signature_mutation
        ),
        "app_asar_mutated": False,
        "app_binary_mutated": codesign_attempted and not binary_hash_matches_stock_after,
        "app_binary_signature_mutated": codesign_attempted,
        "stock_app_mutated": False,
        "custom_app_identity_distinct_after": identity_distinct_after,
        "identity_changes_needed": identity_changes_needed,
        "codesign_repair_needed": codesign_repair_needed,
        "repair_needed": repair_needed,
        "repair_ready": repair_ready,
        "identity_repaired": identity_repaired,
        "backup_under_profile": backup_under_profile,
        "backup_written": backup_written,
        "backup_path_recorded": False,
        "changed_files_path_recorded": bool(changed_files),
        "mutation_attempted": mutation_attempted,
        "plist_written": plist_written,
        "custom_codesign_valid_before": custom_codesign_valid_before,
        "custom_codesign_valid_after": custom_codesign_valid_after,
        "custom_codesign_verify_output_recorded": False,
        "custom_codesign_verify_output_before_digest": (
            custom_codesign_verify_output_before_digest
        ),
        "custom_codesign_verify_output_after_digest": (
            custom_codesign_verify_output_after_digest
        ),
        "codesign_attempted": codesign_attempted,
        "codesign_ok": codesign_ok,
        "codesign_exit_code": (
            codesign_exit_code
            if codesign_attempted
            else custom_codesign_exit_code_after
        ),
        "codesign_output_recorded": False,
        "codesign_output_digest": codesign_output_digest,
        "plist_rollback_restored": plist_rollback_restored,
        "rollback_restored": rollback_restored,
        "codesign_failure_side_effects_detected": (
            codesign_failure_side_effects_detected
        ),
        "api_lane_called": False,
        "dispatch_attempted": False,
        "product_ready": False,
        "custom_ui_origin_admitted": False,
        "fresh_user_prompt_submit_ledger_proven": False,
        "does_not_prove_custom_ui_origin": True,
        "does_not_prove_dispatch": True,
        "does_not_prove_product_ready": True,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": mutation_attempted,
        "blocking_reasons": sorted(set(admission_failures)),
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP repaired the custom Codex app identity."
            if apply and identity_repaired and repair_needed
            else "WBP custom Codex app identity repair is ready."
            if repair_ready
            else "WBP custom Codex app identity repair was not needed."
            if ok
            else "WBP blocked custom Codex app identity repair."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_REPAIR if apply else EFFECT_PROBE,
        extra=extra,
    )

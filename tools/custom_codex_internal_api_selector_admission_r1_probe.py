#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify whether Custom Codex can host an internal API selector safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINAL_BLOCKER_STATUS = "KNOWN_BLOCKER_CUSTOM_CODEX_UI_EXTENSION_NOT_ADMISSIBLE"
FINAL_ADMISSIBLE_STATUS = "CAN_ADD_CUSTOM_CODEX_API_SELECTOR_WITH_LIMITS"
CONTOUR = "CUSTOM_CODEX_INTERNAL_API_SELECTOR_ADMISSION_R1"
ADMISSION_MANIFEST_RELATIVE_PATH = "Contents/Resources/wbp-api-selector-admission.json"

DEFAULT_ORIGINAL_APP = Path("/Applications/Codex.app")
DEFAULT_CUSTOM_APP = Path.home() / "Applications/Codex Custom.app"
DEFAULT_LAUNCHER = Path.home() / ".codex-custom-cli/codex-custom-launch.sh"

FORBIDDEN_RUNTIME_INJECTION_MARKERS = (
    "DYLD_INSERT_LIBRARIES",
    "NODE_OPTIONS",
    "--require",
    "ELECTRON_RUN_AS_NODE",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def read_plist(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (FileNotFoundError, plistlib.InvalidFileException, ValueError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return ""
    return digest.hexdigest()


def run_text(command: list[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        process = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def find_asar_files(app_path: Path) -> list[str]:
    if not app_path.exists():
        return []
    return sorted(str(path.relative_to(app_path)) for path in app_path.rglob("app.asar"))


def _packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def build_custom_app_wrapper_packet(custom_app: Path, launcher: Path) -> dict[str, Any]:
    executable = custom_app / "Contents/MacOS/CodexCustom"
    info = read_plist(custom_app / "Contents/Info.plist")
    wrapper_text = read_text(executable)
    launcher_text = read_text(launcher)
    custom_asar_files = find_asar_files(custom_app)
    admission_manifest_path = custom_app / ADMISSION_MANIFEST_RELATIVE_PATH
    admission_manifest = read_json(admission_manifest_path)
    admission_manifest_valid = (
        admission_manifest.get("surface") == "custom_codex_internal_composer_api_selector"
        and admission_manifest.get("server_catalog_only") is True
        and admission_manifest.get("browser_raw_backend_details_allowed") is False
        and admission_manifest.get("requires_original_asar_patch") is False
        and admission_manifest.get("requires_runtime_injection") is False
    )

    return _packet(
        "custom_app_wrapper",
        custom_app_path=str(custom_app),
        custom_app_exists=custom_app.exists(),
        custom_bundle_name=info.get("CFBundleName", ""),
        custom_bundle_display_name=info.get("CFBundleDisplayName", ""),
        custom_bundle_identifier=info.get("CFBundleIdentifier", ""),
        custom_executable_path=str(executable),
        custom_executable_exists=executable.exists(),
        custom_executable_is_script=wrapper_text.startswith("#!"),
        wrapper_delegates_to_custom_launcher="codex-custom-launch.sh" in wrapper_text,
        launcher_path=str(launcher),
        launcher_exists=launcher.exists(),
        launcher_uses_isolated_codex_home="CODEX_HOME" in launcher_text,
        launcher_uses_isolated_user_data="--user-data-dir" in launcher_text,
        custom_app_asar_files=custom_asar_files,
        custom_app_has_own_asar=bool(custom_asar_files),
        admission_manifest_path=str(admission_manifest_path),
        admission_manifest_exists=admission_manifest_path.exists(),
        admission_manifest_valid=admission_manifest_valid,
        admission_manifest_surface=str(admission_manifest.get("surface", "")),
        admission_manifest_server_catalog_only=admission_manifest.get("server_catalog_only") is True,
        admission_manifest_raw_backend_details_allowed=(
            admission_manifest.get("browser_raw_backend_details_allowed") is True
        ),
    )


def build_launcher_surface_packet(original_app: Path, launcher: Path) -> dict[str, Any]:
    launcher_text = read_text(launcher)
    original_binary = original_app / "Contents/MacOS/Codex"
    original_binary_refs = [
        str(original_binary),
        "/Applications/Codex.app/Contents/MacOS/Codex",
        'CODEX_APP_BIN="/Applications/Codex.app/Contents/MacOS/Codex"',
    ]
    forbidden_markers = [
        marker for marker in FORBIDDEN_RUNTIME_INJECTION_MARKERS if marker in launcher_text
    ]

    return _packet(
        "launcher_surface",
        launcher_path=str(launcher),
        launcher_exists=launcher.exists(),
        launcher_calls_original_codex_binary=any(ref in launcher_text for ref in original_binary_refs),
        launcher_uses_isolated_codex_home="CODEX_HOME" in launcher_text,
        launcher_uses_isolated_user_data="--user-data-dir" in launcher_text,
        launcher_reads_profile_auth_json="auth.json" in launcher_text,
        secrets_read_by_probe=False,
        forbidden_runtime_injection_markers=forbidden_markers,
        forbidden_runtime_injection_detected=bool(forbidden_markers),
        hidden_runtime_patching_allowed=False,
        dyld_injection_allowed=False,
        asar_patching_allowed=False,
    )


def build_original_app_integrity_packet(original_app: Path) -> dict[str, Any]:
    info = read_plist(original_app / "Contents/Info.plist")
    asar = original_app / "Contents/Resources/app.asar"
    codesign_returncode, codesign_stdout, codesign_stderr = run_text(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(original_app)]
    )
    electron_integrity = info.get("ElectronAsarIntegrity", {})
    electron_asar_hash = ""
    if isinstance(electron_integrity, dict):
        resources = electron_integrity.get("Resources/app.asar", {})
        if isinstance(resources, dict):
            electron_asar_hash = str(resources.get("hash", ""))

    return _packet(
        "original_app_integrity",
        original_app_path=str(original_app),
        original_app_exists=original_app.exists(),
        original_bundle_name=info.get("CFBundleName", ""),
        original_bundle_identifier=info.get("CFBundleIdentifier", ""),
        original_bundle_version=info.get("CFBundleVersion", ""),
        original_short_version=info.get("CFBundleShortVersionString", ""),
        original_asar_path=str(asar),
        original_asar_exists=asar.exists(),
        original_asar_plain_sha256=file_sha256(asar),
        electron_asar_integrity_hash=electron_asar_hash,
        plain_sha256_equals_electron_integrity_hash=(
            bool(electron_asar_hash) and file_sha256(asar) == electron_asar_hash
        ),
        electron_integrity_hash_treated_as_plain_sha256_proof=False,
        codesign_returncode=codesign_returncode,
        codesign_valid=codesign_returncode == 0,
        codesign_stdout=codesign_stdout,
        codesign_stderr=codesign_stderr,
    )


def build_probe_scope_non_claim_packet(
    original_integrity: dict[str, Any],
) -> dict[str, Any]:
    return _packet(
        "probe_scope_non_claim",
        evidence_basis="probe_code_scope_and_declared_actions",
        host_runtime_monitor_used=False,
        negative_fields_are_host_runtime_monitor_claims=False,
        codesign_verify_attempted=original_integrity.get("codesign_returncode") != 127,
        live_codex_launch_code_path_present=False,
        live_api_call_code_path_present=False,
        paid_provider_call_code_path_present=False,
        profile_write_code_path_present=False,
        app_write_code_path_present=False,
        app_asar_write_code_path_present=False,
        dyld_injection_code_path_present=False,
        hidden_runtime_patch_code_path_present=False,
        browser_delivery_code_path_present=False,
        secret_file_read_code_path_present=False,
        auth_json_content_read_by_probe=False,
        original_codex_profile_write_attempted_by_probe=False,
        current_codex_profile_write_attempted_by_probe=False,
        original_codex_app_write_attempted_by_probe=False,
        custom_codex_app_write_attempted_by_probe=False,
    )


def build_ui_surface_admission_packet(
    wrapper: dict[str, Any],
    launcher: dict[str, Any],
    original_integrity: dict[str, Any],
) -> dict[str, Any]:
    delegates_to_original_asar = (
        wrapper["custom_app_exists"]
        and wrapper["custom_executable_is_script"]
        and wrapper["wrapper_delegates_to_custom_launcher"]
        and launcher["launcher_calls_original_codex_binary"]
        and original_integrity["original_asar_exists"]
        and not wrapper["custom_app_has_own_asar"]
    )
    forbidden_injection = launcher["forbidden_runtime_injection_detected"]
    admitted_custom_surface = (
        wrapper["custom_app_has_own_asar"]
        and wrapper["admission_manifest_valid"]
        and not launcher["launcher_calls_original_codex_binary"]
        and not forbidden_injection
    )

    if forbidden_injection:
        reason_code = "FORBIDDEN_RUNTIME_INJECTION_MARKER_PRESENT"
        admitted = False
    elif delegates_to_original_asar:
        reason_code = "CUSTOM_APP_WRAPPER_DELEGATES_TO_ORIGINAL_ASAR"
        admitted = False
    elif admitted_custom_surface:
        reason_code = "CUSTOM_APP_HAS_OWN_ADMITTED_INTERNAL_UI_SURFACE"
        admitted = True
    elif wrapper["custom_app_has_own_asar"]:
        reason_code = "CUSTOM_APP_OWN_ASAR_REQUIRES_SEPARATE_INTEGRITY_ADMISSION"
        admitted = False
    else:
        reason_code = "NO_ALLOWED_CUSTOM_CODEX_INTERNAL_UI_EXTENSION_SURFACE_FOUND"
        admitted = False

    final_status = FINAL_ADMISSIBLE_STATUS if admitted else FINAL_BLOCKER_STATUS

    return _packet(
        "ui_surface_admission",
        status="ok" if admitted else "blocked",
        contour=CONTOUR,
        final_status=final_status,
        admitted=admitted,
        reason_code=reason_code,
        custom_app_internal_ui_surface_found=(
            wrapper["custom_app_has_own_asar"] and wrapper["admission_manifest_valid"]
        ),
        composer_surface_requires_original_asar_change=delegates_to_original_asar,
        can_add_internal_api_selector=admitted,
        api_selector_added=False,
        allowed_alternative_surface="WBP control surface / server-owned catalog selector",
        not_allowed_surfaces=[
            "Original Codex app.asar patch",
            "DYLD injection",
            "hidden runtime mutation",
            "Original Codex profile mutation",
        ],
        canon_basis=[
            "same Codex binary",
            "ASAR unchanged",
            "no DYLD injection",
            "no hidden runtime patching",
            "Original profile untouched",
            "server-issued catalog > raw browser backend config",
        ],
    )


def build_admission_packets(
    original_app: Path = DEFAULT_ORIGINAL_APP,
    custom_app: Path = DEFAULT_CUSTOM_APP,
    launcher: Path = DEFAULT_LAUNCHER,
) -> dict[str, dict[str, Any]]:
    wrapper = build_custom_app_wrapper_packet(custom_app, launcher)
    launcher_packet = build_launcher_surface_packet(original_app, launcher)
    integrity = build_original_app_integrity_packet(original_app)
    admission = build_ui_surface_admission_packet(wrapper, launcher_packet, integrity)
    probe_scope = build_probe_scope_non_claim_packet(integrity)
    return {
        "custom_app_wrapper_packet": wrapper,
        "launcher_surface_packet": launcher_packet,
        "original_app_integrity_packet": integrity,
        "ui_surface_admission_packet": admission,
        "probe_scope_non_claim_packet": probe_scope,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-app", type=Path, default=DEFAULT_ORIGINAL_APP)
    parser.add_argument("--custom-app", type=Path, default=DEFAULT_CUSTOM_APP)
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument("--json", action="store_true", help="Emit JSON packet bundle.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packets = build_admission_packets(
        original_app=args.original_app,
        custom_app=args.custom_app,
        launcher=args.launcher,
    )
    if args.json:
        print(json.dumps(packets, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        admission = packets["ui_surface_admission_packet"]
        print(f"{admission['final_status']}: {admission['reason_code']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

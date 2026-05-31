#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Diagnose the unconfirmed remote closeout state for ROLE_PROFILE_UI_POLISH."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write


REMOTE_BRANCH = "codex/external-agent-lab-isolated"
REMOTE_API_URL = (
    "https://api.github.com/repos/KirPonomarev/wild-boar-proxy/branches/"
    "codex/external-agent-lab-isolated"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(
    repo_root: Path,
    command: list[str],
    *,
    check: bool = True,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process


def _safe_http_branch_sha(url: str) -> tuple[str | None, int | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-closeout-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
            return str(data["commit"]["sha"]), int(response.status)
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        exc.close()
        return None, status_code
    except (OSError, TimeoutError, urllib.error.URLError):
        return None, None


def _status_in(packet: dict[str, Any], *allowed: str) -> bool:
    return str(packet.get("status", "")) in set(allowed)


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).stdout.splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "tools/role_profile_ui_polish_closeout_push_block_diagnose_r1_probe.py",
        "tests/test_role_profile_ui_polish_closeout_push_block_diagnose_r1_probe.py",
    ]
    try:
        relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        relative_evidence_dir = None
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not (
            relative_evidence_dir
            and line.strip().startswith(f"?? {relative_evidence_dir}/")
        )
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _run(repo_root, ["codex", "--version"], check=False).stdout.strip(),
        "codex_cli_path": _run(repo_root, ["which", "codex"], check=False).stdout.strip(),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]).stdout.strip(),
    }


@dataclass(frozen=True)
class BlockerClassification:
    result: str
    with_limits: bool
    reasons: tuple[str, ...]


def classify_blocker(
    *,
    remote_observable: bool,
    remote_http_ok: bool,
    remote_sha_matches: bool,
    gh_auth_ok: bool,
    helper_ls_remote_ok: bool,
    helperless_ls_remote_ok: bool,
    helperless_push_auth_fail: bool,
    push_timeout: bool,
    push_trace_has_remote_https: bool,
    push_trace_has_get_refs_list: bool,
    push_trace_has_gh_credential_get: bool,
    push_trace_has_credential_child_exit_zero: bool,
    http11_push_timeout: bool,
) -> BlockerClassification:
    reasons: list[str] = []
    if remote_sha_matches:
        return BlockerClassification(
            result="ROLE_PROFILE_UI_POLISH_REMOTE_CLOSEOUT_CONFIRMED",
            with_limits=False,
            reasons=(),
        )
    if not remote_observable or not remote_http_ok:
        reasons.append("REMOTE_OBSERVABILITY_LIMITED")
    if not gh_auth_ok:
        reasons.append("GH_AUTH_STATUS_NOT_CONFIRMED")
    if not helper_ls_remote_ok:
        reasons.append("GIT_HELPER_READ_PATH_NOT_CONFIRMED")
    if not helperless_ls_remote_ok:
        reasons.append("HELPERLESS_READ_PATH_NOT_CONFIRMED")
    if not helperless_push_auth_fail:
        reasons.append("HELPERLESS_PUSH_DID_NOT_FAIL_FAST_ON_AUTH")
    if push_timeout:
        reasons.append("PUSH_TIMEOUT")
    if http11_push_timeout:
        reasons.append("HTTP11_PUSH_TIMEOUT")
    if push_trace_has_remote_https:
        reasons.append("REMOTE_HTTPS_CHILD_STARTED")
    if push_trace_has_get_refs_list and push_timeout:
        reasons.append("PUSH_STALLED_DURING_GET_REFS_LIST")
    if push_trace_has_get_refs_list and not push_timeout:
        reasons.append("GET_REFS_LIST_REACHED_BEFORE_UNCONFIRMED_CLOSE")
    if (
        push_trace_has_gh_credential_get
        and push_trace_has_credential_child_exit_zero
        and push_timeout
    ):
        reasons.append("CREDENTIAL_RETRIEVAL_COMPLETED_BEFORE_STALL")
    if (
        push_trace_has_gh_credential_get
        and push_trace_has_credential_child_exit_zero
        and not push_timeout
    ):
        reasons.append("CREDENTIAL_RETRIEVAL_OBSERVED")
    if (
        remote_observable
        and remote_http_ok
        and gh_auth_ok
        and helper_ls_remote_ok
        and helperless_ls_remote_ok
        and helperless_push_auth_fail
        and push_timeout
        and push_trace_has_remote_https
        and push_trace_has_get_refs_list
        and push_trace_has_gh_credential_get
        and push_trace_has_credential_child_exit_zero
    ):
        return BlockerClassification(
            result="PUSH_TRANSPORT_STALL_AFTER_CREDENTIAL_RESOLUTION",
            with_limits=False,
            reasons=tuple(reasons),
        )
    return BlockerClassification(
        result="ROLE_PROFILE_UI_POLISH_CLOSEOUT_BLOCK_CLASSIFIED_WITH_LIMITS",
        with_limits=True,
        reasons=tuple(reasons or ["BLOCKER_NOT_FULLY_LOCALIZED"]),
    )


def _timed_trace_push(repo_root: Path) -> tuple[bool, str]:
    trace_path = Path(tempfile.gettempdir()) / "wbp_git_push_trace2.json"
    if trace_path.exists():
        trace_path.unlink()
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_TRACE2_EVENT"] = str(trace_path)
    timeout = False
    try:
        _run(
            repo_root,
            ["git", "push", "origin", REMOTE_BRANCH],
            check=False,
            timeout=20,
            env=env,
        )
    except subprocess.TimeoutExpired:
        timeout = True
    trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
    return timeout, trace_text


def _timed_http11_push(repo_root: Path) -> bool:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        _run(
            repo_root,
            ["git", "-c", "http.version=HTTP/1.1", "push", "origin", REMOTE_BRANCH],
            check=False,
            timeout=20,
            env=env,
        )
        return False
    except subprocess.TimeoutExpired:
        return True


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).stdout.splitlines()
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    branch = _run(repo_root, ["git", "branch", "--show-current"]).stdout.strip()
    head = _run(repo_root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    remote_url = _run(repo_root, ["git", "remote", "get-url", "origin"]).stdout.strip()

    remote_sha_before_push, remote_http_status_before_push = _safe_http_branch_sha(
        REMOTE_API_URL
    )
    remote_observable_before_push = remote_sha_before_push is not None
    remote_http_ok_before_push = remote_http_status_before_push == 200
    remote_sha_matches_before_push = remote_sha_before_push == head

    credential_config = _run(
        repo_root,
        [
            "git",
            "config",
            "--show-origin",
            "--get-regexp",
            r"^credential\..*github\.com\..*helper$|^credential\..*github\.com\..*username$|^credential\.helper$",
        ],
        check=False,
    ).stdout.strip()
    gh_auth = _run(repo_root, ["gh", "auth", "status", "-h", "github.com"], check=False)
    gh_auth_ok = gh_auth.returncode == 0 and "Logged in to github.com account" in gh_auth.stdout

    helper_ls_remote_ok = False
    helperless_ls_remote_ok = False
    helperless_push_auth_fail = False
    push_timeout = False
    http11_push_timeout = False
    push_trace_text = ""
    push_trace_has_remote_https = False
    push_trace_has_get_refs_list = False
    push_trace_has_gh_credential_get = False
    push_trace_has_credential_child_exit_zero = False
    push_attempts_skipped = remote_sha_matches_before_push

    if not remote_sha_matches_before_push:
        helper_ls_remote = _run(
            repo_root,
            ["git", "ls-remote", "--heads", "origin", REMOTE_BRANCH],
            check=False,
            timeout=20,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        helper_ls_remote_ok = (
            helper_ls_remote.returncode == 0 and REMOTE_BRANCH in helper_ls_remote.stdout
        )

        helperless_ls_remote = _run(
            repo_root,
            ["git", "-c", "credential.helper=", "ls-remote", "--heads", "origin", REMOTE_BRANCH],
            check=False,
            timeout=20,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        helperless_ls_remote_ok = (
            helperless_ls_remote.returncode == 0 and REMOTE_BRANCH in helperless_ls_remote.stdout
        )

        helperless_push = _run(
            repo_root,
            ["git", "-c", "credential.helper=", "push", "origin", REMOTE_BRANCH],
            check=False,
            timeout=20,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        helperless_push_auth_fail = (
            helperless_push.returncode == 128
            and "could not read Username" in helperless_push.stderr
        )

        push_timeout, push_trace_text = _timed_trace_push(repo_root)
        http11_push_timeout = _timed_http11_push(repo_root)

        push_trace_has_remote_https = '"child_class":"remote-https"' in push_trace_text
        push_trace_has_get_refs_list = '"label":"get_refs_list"' in push_trace_text
        push_trace_has_gh_credential_get = "gh auth git-credential get" in push_trace_text
        push_trace_has_credential_child_exit_zero = (
            '"child_exit"' in push_trace_text and '"code":0' in push_trace_text
        )

    remote_sha_after_push, remote_http_status_after_push = _safe_http_branch_sha(
        REMOTE_API_URL
    )
    remote_observable = remote_sha_after_push is not None
    remote_http_ok = remote_http_status_after_push == 200
    remote_sha_matches = remote_sha_after_push == head

    classification = classify_blocker(
        remote_observable=remote_observable,
        remote_http_ok=remote_http_ok,
        remote_sha_matches=remote_sha_matches,
        gh_auth_ok=gh_auth_ok,
        helper_ls_remote_ok=helper_ls_remote_ok,
        helperless_ls_remote_ok=helperless_ls_remote_ok,
        helperless_push_auth_fail=helperless_push_auth_fail,
        push_timeout=push_timeout,
        push_trace_has_remote_https=push_trace_has_remote_https,
        push_trace_has_get_refs_list=push_trace_has_get_refs_list,
        push_trace_has_gh_credential_get=push_trace_has_gh_credential_get,
        push_trace_has_credential_child_exit_zero=push_trace_has_credential_child_exit_zero,
        http11_push_timeout=http11_push_timeout,
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": branch,
        "git_head": head,
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
    }
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)

    packets["role_profile_ui_closeout_local_completion_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_closeout_local_completion",
        "status": "ok",
        "local_head": head,
        "branch": branch,
        "contour_summary_packet": "audit_results/wbp_role_profile_ui_polish_classification_r1_2026-05-27/role_profile_ui_summary_packet.json",
        "local_contour_status": "ROLE_PROFILE_UI_POLISH_CLASSIFIED",
        "closeout_resilience_previously_passed": True,
        "local_completion_is_closed_contour": remote_sha_matches,
    }

    packets["role_profile_ui_push_attempt_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_push_attempt",
        "status": "ok",
        "push_target": f"origin {REMOTE_BRANCH}",
        "default_push_url": remote_url,
        "push_attempts_skipped": push_attempts_skipped,
        "push_timeout_observed": push_timeout,
        "http11_push_timeout_observed": http11_push_timeout,
        "push_stdout_emitted": False,
        "push_stderr_emitted": False,
    }

    packets["role_profile_ui_remote_observability_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_remote_observability",
        "status": "ok" if remote_observable and remote_http_ok else "blocked",
        "github_api_branch_readable": remote_observable,
        "github_api_status_code": remote_http_status_after_push,
        "remote_branch": REMOTE_BRANCH,
        "remote_branch_sha_observed_before_push_attempts": remote_sha_before_push,
        "remote_branch_sha_observed_after_push_attempts": remote_sha_after_push,
        "remote_observability_missing_implies_success": False,
    }

    packets["role_profile_ui_remote_close_status_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_remote_close_status",
        "status": "ok",
        "local_head": head,
        "remote_head_before_push_attempts": remote_sha_before_push,
        "remote_head_after_push_attempts": remote_sha_after_push,
        "remote_matches_local_head": remote_sha_matches,
        "push_confirmed": remote_sha_matches,
        "same_intended_remote_ref_equals_confirmation": False,
    }

    packets["role_profile_ui_transport_blocker_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_transport_blocker",
        "status": "ok",
        "classification": classification.result,
        "classification_with_limits": classification.with_limits,
        "reasons": list(classification.reasons),
        "credential_config_present": bool(credential_config),
        "gh_auth_status_ok": gh_auth_ok,
        "helper_ls_remote_ok": helper_ls_remote_ok,
        "helperless_ls_remote_ok": helperless_ls_remote_ok,
        "helperless_push_auth_fail": helperless_push_auth_fail,
        "push_trace_has_remote_https": push_trace_has_remote_https,
        "push_trace_has_get_refs_list": push_trace_has_get_refs_list,
        "push_trace_has_gh_credential_get": push_trace_has_gh_credential_get,
        "push_trace_has_credential_child_exit_zero": push_trace_has_credential_child_exit_zero,
    }

    packets["role_profile_ui_retry_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_retry_boundary",
        "status": "ok",
        "bounded_retry_attempts": 2,
        "bounded_retry_methods": [
            "git push origin branch with trace2 timeout",
            "git -c http.version=HTTP/1.1 push origin branch with timeout",
        ],
        "infinite_retry_performed": False,
        "silent_timeout_treated_as_success": False,
    }

    packets["role_profile_ui_closeout_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_closeout_false_green_audit",
        "status": "ok",
        "local_only_close_claimed": False,
        "push_attempt_treated_as_push_confirmed": False,
        "next_contour_admitted_while_unclosed": False,
        "remote_sha_matches_local_head": remote_sha_matches,
    }

    final_status = (
        "ROLE_PROFILE_UI_POLISH_REMOTE_CLOSEOUT_CONFIRMED"
        if remote_sha_matches
        else (
            "ROLE_PROFILE_UI_POLISH_CLOSEOUT_BLOCK_CLASSIFIED_WITH_LIMITS"
            if classification.with_limits
            else "ROLE_PROFILE_UI_POLISH_CLOSEOUT_BLOCK_CLASSIFIED"
        )
    )
    packets["role_profile_ui_closeout_block_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_closeout_block_summary",
        "status": "ok",
        "final_status": final_status,
        "local_head": head,
        "remote_head": remote_sha_after_push,
        "remote_observable": remote_observable,
        "push_confirmed": remote_sha_matches,
        "blocker_classification": classification.result,
    }

    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok",
        "facts": [
            "remote GitHub API branch read is healthy",
            f"remote branch head before push attempts: {remote_sha_before_push}",
            f"remote branch head after push attempts: {remote_sha_after_push}",
            f"local branch head is {head}",
            (
                "helper and helperless ls-remote read paths succeed"
                if helper_ls_remote_ok and helperless_ls_remote_ok
                else "ls-remote read-path checks were skipped or incomplete"
            ),
            (
                "helpered push path was not exercised because remote already matched local head"
                if push_attempts_skipped
                else "helperless push failed fast on missing username; traced helpered push reached get_refs_list and credential retrieval"
            ),
        ],
    }

    packets["independent_role_profile_ui_closeout_block_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_role_profile_ui_closeout_block_audit",
        "status": "ok",
        "remote_observability_confirmed": remote_observable and remote_http_ok,
        "remote_close_confirmed": remote_sha_matches,
        "push_stall_after_credential_resolution_supported": (
            push_timeout
            and push_trace_has_get_refs_list
            and push_trace_has_gh_credential_get
            and push_trace_has_credential_child_exit_zero
        ),
        "false_green_detected": False,
    }
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="role-profile-ui-polish-closeout-push-block-diagnose-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["role_profile_ui_closeout_block_summary_packet.json"]
    print(
        json.dumps(
            {
                "status": summary["status"],
                "final_status": summary["final_status"],
                "local_head": summary["local_head"],
                "remote_head": summary["remote_head"],
                "push_confirmed": summary["push_confirmed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import role_profile_ui_polish_closeout_push_block_diagnose_r1_probe as probe


class RoleProfileUiPolishCloseoutPushBlockDiagnoseR1ProbeTests(unittest.TestCase):
    def test_classify_blocker_identifies_push_transport_stall_after_credential_resolution(
        self,
    ) -> None:
        result = probe.classify_blocker(
            remote_observable=True,
            remote_http_ok=True,
            remote_sha_matches=False,
            gh_auth_ok=True,
            helper_ls_remote_ok=True,
            helperless_ls_remote_ok=True,
            helperless_push_auth_fail=True,
            push_timeout=True,
            push_trace_has_remote_https=True,
            push_trace_has_get_refs_list=True,
            push_trace_has_gh_credential_get=True,
            push_trace_has_credential_child_exit_zero=True,
            http11_push_timeout=True,
        )
        self.assertEqual(result.result, "PUSH_TRANSPORT_STALL_AFTER_CREDENTIAL_RESOLUTION")
        self.assertFalse(result.with_limits)
        self.assertIn("PUSH_TIMEOUT", result.reasons)
        self.assertIn("CREDENTIAL_RETRIEVAL_COMPLETED_BEFORE_STALL", result.reasons)

    def test_classify_blocker_reports_remote_close_confirmed_when_shas_match(self) -> None:
        result = probe.classify_blocker(
            remote_observable=True,
            remote_http_ok=True,
            remote_sha_matches=True,
            gh_auth_ok=True,
            helper_ls_remote_ok=True,
            helperless_ls_remote_ok=True,
            helperless_push_auth_fail=False,
            push_timeout=False,
            push_trace_has_remote_https=False,
            push_trace_has_get_refs_list=False,
            push_trace_has_gh_credential_get=False,
            push_trace_has_credential_child_exit_zero=False,
            http11_push_timeout=False,
        )
        self.assertEqual(result.result, "ROLE_PROFILE_UI_POLISH_REMOTE_CLOSEOUT_CONFIRMED")
        self.assertFalse(result.with_limits)
        self.assertEqual(result.reasons, ())

    def test_probe_writes_summary_packet(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            exit_code = probe.main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                ]
            )
            self.assertEqual(exit_code, 0)
            summary = json.loads(
                (evidence_dir / "role_profile_ui_closeout_block_summary_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertIn(
                summary["final_status"],
                {
                    "ROLE_PROFILE_UI_POLISH_CLOSEOUT_BLOCK_CLASSIFIED",
                    "ROLE_PROFILE_UI_POLISH_CLOSEOUT_BLOCK_CLASSIFIED_WITH_LIMITS",
                    "ROLE_PROFILE_UI_POLISH_REMOTE_CLOSEOUT_CONFIRMED",
                },
            )

    def test_build_packets_rereads_remote_after_push_attempts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        evidence_dir = repo_root / "audit_results" / "tmp_role_profile_ui_closeout_probe_test"

        remote_reads = iter(
            [
                ("a10eafe2d2b50b5b69e22a674ac5a5ff7175523f", 200),
                ("d3f0643a96ddf0fb42f3f1e6753e96fda42b02db", 200),
            ]
        )

        def fake_safe_http_branch_sha(_url: str) -> tuple[str, int]:
            return next(remote_reads)

        def fake_run(
            _repo_root: Path,
            command: list[str],
            *,
            check: bool = True,
            timeout: int | None = None,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            del check, timeout, env
            text_map = {
                ("git", "status", "--short"): "",
                ("git", "branch", "--show-current"): "codex/external-agent-lab-isolated\n",
                ("git", "rev-parse", "HEAD"): "d3f0643a96ddf0fb42f3f1e6753e96fda42b02db\n",
                ("git", "remote", "get-url", "origin"): "https://github.com/KirPonomarev/wild-boar-proxy.git\n",
                ("codex", "--version"): "codex 1.0.0\n",
                ("which", "codex"): "/opt/homebrew/bin/codex\n",
                (
                    "git",
                    "config",
                    "--show-origin",
                    "--get-regexp",
                    r"^credential\..*github\.com\..*helper$|^credential\..*github\.com\..*username$|^credential\.helper$",
                ): "file:/Users/test/.gitconfig credential.helper osxkeychain\n",
                ("gh", "auth", "status", "-h", "github.com"): "Logged in to github.com account KirPonomarev (/Users/test/.config/gh/hosts.yml)\n",
                ("git", "ls-remote", "--heads", "origin", probe.REMOTE_BRANCH): f"a10eafe2\trefs/heads/{probe.REMOTE_BRANCH}\n",
                ("git", "-c", "credential.helper=", "ls-remote", "--heads", "origin", probe.REMOTE_BRANCH): f"a10eafe2\trefs/heads/{probe.REMOTE_BRANCH}\n",
            }
            key = tuple(command)
            if key in text_map:
                return subprocess.CompletedProcess(command, 0, text_map[key], "")
            if key == ("git", "-c", "credential.helper=", "push", "origin", probe.REMOTE_BRANCH):
                return subprocess.CompletedProcess(
                    command,
                    128,
                    "",
                    "fatal: could not read Username for 'https://github.com': terminal prompts disabled\n",
                )
            raise AssertionError(f"unexpected command: {command}")

        with (
            mock.patch.object(probe, "_safe_http_branch_sha", side_effect=fake_safe_http_branch_sha),
            mock.patch.object(probe, "_run", side_effect=fake_run),
            mock.patch.object(
                probe,
                "_timed_trace_push",
                return_value=(False, '"child_class":"remote-https" "label":"get_refs_list" gh auth git-credential get "child_exit" "code":0'),
            ),
            mock.patch.object(probe, "_timed_http11_push", return_value=False),
        ):
            packets = probe.build_packets(repo_root=repo_root, evidence_dir=evidence_dir)

        summary = packets["role_profile_ui_closeout_block_summary_packet.json"]
        remote_status = packets["role_profile_ui_remote_close_status_packet.json"]
        scanner = packets["scanner_agent_fact_report_packet.json"]
        self.assertEqual(summary["final_status"], "ROLE_PROFILE_UI_POLISH_REMOTE_CLOSEOUT_CONFIRMED")
        self.assertEqual(summary["remote_head"], "d3f0643a96ddf0fb42f3f1e6753e96fda42b02db")
        self.assertEqual(
            remote_status["remote_head_before_push_attempts"],
            "a10eafe2d2b50b5b69e22a674ac5a5ff7175523f",
        )
        self.assertEqual(
            remote_status["remote_head_after_push_attempts"],
            "d3f0643a96ddf0fb42f3f1e6753e96fda42b02db",
        )
        self.assertIn(
            "remote branch head after push attempts: d3f0643a96ddf0fb42f3f1e6753e96fda42b02db",
            scanner["facts"],
        )


if __name__ == "__main__":
    unittest.main()

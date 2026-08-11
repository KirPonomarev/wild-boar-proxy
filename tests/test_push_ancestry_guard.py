# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "tools" / "check_push_ancestry.py"

spec = importlib.util.spec_from_file_location("check_push_ancestry", CHECKER_PATH)
assert spec is not None
checker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


def _git(
    repo_root: Path,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
        input=input_text,
    )


def _commit(repo_root: Path, marker: str) -> str:
    history = repo_root / "history.txt"
    with history.open("a", encoding="utf-8") as stream:
        stream.write(marker + "\n")
    _git(repo_root, "add", history.name)
    _git(repo_root, "commit", "-m", marker)
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


class PushAncestryGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo_root = Path(self.temporary.name)
        _git(self.repo_root, "init", "-b", "main")
        _git(self.repo_root, "config", "user.name", "Wild Boar Test")
        _git(
            self.repo_root,
            "config",
            "user.email",
            "wild-boar-test@example.invalid",
        )
        self.base_sha = _commit(self.repo_root, "base")

    def _update(self, local_sha: str, remote_sha: str) -> object:
        return checker.PushUpdate(
            local_ref="refs/heads/main",
            local_sha=local_sha,
            remote_ref="refs/heads/main",
            remote_sha=remote_sha,
        )

    def test_fast_forward_update_passes(self) -> None:
        head_sha = _commit(self.repo_root, "head")

        result = checker.inspect_update(
            self.repo_root,
            self._update(head_sha, self.base_sha),
        )

        self.assertEqual("ok", result["status"])
        self.assertEqual(checker.OK, result["code"])

    def test_divergent_update_is_blocked(self) -> None:
        _git(self.repo_root, "switch", "-c", "remote-line")
        remote_sha = _commit(self.repo_root, "remote")
        _git(self.repo_root, "switch", "-c", "local-line", self.base_sha)
        local_sha = _commit(self.repo_root, "local")

        result = checker.inspect_update(
            self.repo_root,
            self._update(local_sha, remote_sha),
        )

        self.assertEqual("blocked", result["status"])
        self.assertEqual(checker.PUSH_NON_FAST_FORWARD_BLOCKED, result["code"])

    def test_new_branch_requires_a_commit(self) -> None:
        allowed = checker.inspect_update(
            self.repo_root,
            self._update(self.base_sha, "0" * 40),
        )
        blob_sha = _git(
            self.repo_root,
            "hash-object",
            "-w",
            "--stdin",
            input_text="not a commit",
        ).stdout.strip()
        blocked = checker.inspect_update(
            self.repo_root,
            self._update(blob_sha, "0" * 40),
        )

        self.assertEqual(checker.OK, allowed["code"])
        self.assertEqual(checker.PUSH_ANCESTRY_UNPROVEN, blocked["code"])

    def test_branch_deletion_is_blocked(self) -> None:
        result = checker.inspect_update(
            self.repo_root,
            self._update("0" * 40, self.base_sha),
        )

        self.assertEqual("blocked", result["status"])
        self.assertEqual(checker.PUSH_BRANCH_DELETE_BLOCKED, result["code"])

    def test_missing_remote_object_fails_closed(self) -> None:
        head_sha = _commit(self.repo_root, "head")

        result = checker.inspect_update(
            self.repo_root,
            self._update(head_sha, "a" * 40),
        )

        self.assertEqual("blocked", result["status"])
        self.assertEqual(checker.PUSH_ANCESTRY_UNPROVEN, result["code"])

    def test_non_branch_ref_is_ignored(self) -> None:
        update = checker.PushUpdate(
            local_ref="refs/tags/v1",
            local_sha=self.base_sha,
            remote_ref="refs/tags/v1",
            remote_sha="0" * 40,
        )

        result = checker.inspect_update(self.repo_root, update)

        self.assertEqual(checker.OK, result["code"])
        self.assertEqual("ignored", result["disposition"])

    def test_malformed_pre_push_input_returns_typed_packet(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER_PATH)],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
            input="malformed input\n",
        )
        packet = json.loads(result.stdout)

        self.assertEqual(1, result.returncode)
        self.assertEqual("blocked", packet["status"])
        self.assertEqual(checker.PUSH_INPUT_INVALID, packet["code"])

    def test_ci_mode_matches_pre_push_ancestry_semantics(self) -> None:
        head_sha = _commit(self.repo_root, "head")
        result = subprocess.run(
            [
                sys.executable,
                str(CHECKER_PATH),
                "--previous",
                self.base_sha,
                "--current",
                head_sha,
                "--ref",
                "refs/heads/main",
            ],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        packet = json.loads(result.stdout)

        self.assertEqual(0, result.returncode)
        self.assertEqual("ci", packet["mode"])
        self.assertEqual(checker.OK, packet["code"])

    def test_hook_installer_and_workflow_enforce_guard(self) -> None:
        hook = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
        installer = (ROOT / "tools" / "install_git_hooks.sh").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github" / "workflows" / "repo-hygiene.yml").read_text(
            encoding="utf-8"
        )
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("tools/check_push_ancestry.py", hook)
        self.assertNotIn("BYPASS", hook.upper())
        self.assertIn("git config core.hooksPath .githooks", installer)
        self.assertNotIn('$repo_root/.githooks', installer)
        self.assertIn("tools/check_push_ancestry.py", workflow)
        self.assertIn("github.event.before", workflow)
        self.assertIn("github.event.after", workflow)
        self.assertIn('EVENT_ACTION: ${{ github.event.action }}', workflow)
        self.assertIn("tests/test_push_ancestry_guard.py", makefile)


if __name__ == "__main__":
    unittest.main()

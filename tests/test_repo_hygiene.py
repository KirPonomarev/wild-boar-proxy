import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "tools" / "check_repo_hygiene.py"


spec = importlib.util.spec_from_file_location("check_repo_hygiene", CHECKER_PATH)
assert spec is not None
checker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo_root: Path, message: str) -> str:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Wild Boar Test",
            "-c",
            "user.email=wild-boar-test@example.invalid",
            "commit",
            "-m",
            message,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


def _finding_checks(report: dict[str, object]) -> set[str]:
    findings = report.get("findings")
    assert isinstance(findings, list)
    return {
        str(finding.get("check"))
        for finding in findings
        if isinstance(finding, dict)
    }


class RepoHygieneTests(unittest.TestCase):
    def test_tracked_repository_does_not_store_plan_files(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
        forbidden = [
            path
            for path in result.stdout.splitlines()
            if checker.FORBIDDEN_PLAN_FILE_PATTERN.search(path)
        ]
        self.assertEqual([], forbidden)

    def test_tracked_production_package_does_not_store_personal_paths(self) -> None:
        result = subprocess.run(
            [
                "git",
                "grep",
                "-n",
                "-I",
                *(
                    argument
                    for literal in checker.FORBIDDEN_PERSONAL_PATH_LITERALS
                    for decoded in (literal.decode("utf-8"),)
                    for argument in ("-e", decoded)
                ),
                "--",
                "wild_boar_proxy",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertIn(result.returncode, (0, 1), msg=result.stderr)
        self.assertEqual("", result.stdout.strip(), msg=result.stdout)

    def test_pre_commit_hook_runs_repo_hygiene_staged_only(self) -> None:
        text = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", text)
        self.assertIn("tools/check_closeout_resilience.py", text)
        self.assertIn("tools/check_repo_hygiene.py", text)
        self.assertGreaterEqual(text.count("--staged-only"), 2)

    def test_repo_hygiene_workflow_runs_git_range_mode(self) -> None:
        text = (ROOT / ".github" / "workflows" / "repo-hygiene.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("tools/check_repo_hygiene.py", text)
        self.assertIn("--git-range", text)
        self.assertIn("tests/test_repo_hygiene.py", text)

    def test_staged_only_ignores_unstaged_historical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            dirty = repo_root / "audit_results" / "dirty.log"
            dirty.parent.mkdir()
            dirty.write_text("api_key=" + ("x" * 40), encoding="utf-8")

            report = checker.inspect_staged_repo_hygiene(repo_root)

        self.assertEqual("ok", report["status"])
        self.assertEqual([], report["checked_files"])

    def test_staged_secret_scan_blocks_without_raw_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            secret = "sk-" + ("a" * 40)
            path = repo_root / "leak.txt"
            path.write_text("token=" + secret, encoding="utf-8")
            _git(repo_root, "add", "leak.txt")

            report = checker.inspect_staged_repo_hygiene(repo_root)
            rendered = checker.render_text_report(report)

        serialized = json.dumps(report, sort_keys=True) + rendered
        self.assertEqual("blocked", report["status"])
        self.assertIn("secret_scan", _finding_checks(report))
        self.assertNotIn(secret, serialized)
        self.assertIn("sha256:", serialized)

    def test_staged_large_file_blocks_by_blob_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            path = repo_root / "large.bin"
            path.write_bytes(b"x" * 17)
            _git(repo_root, "add", "large.bin")

            report = checker.inspect_staged_repo_hygiene(repo_root, max_bytes=16)

        self.assertEqual("blocked", report["status"])
        self.assertIn("large_file", _finding_checks(report))

    def test_staged_plan_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            path = repo_root / "NEXT_CONTOUR_CANON_PLAN.md"
            path.write_text("future work", encoding="utf-8")
            _git(repo_root, "add", path.name)

            report = checker.inspect_staged_repo_hygiene(repo_root)

        self.assertEqual("blocked", report["status"])
        self.assertIn("repo_plan_file", _finding_checks(report))

    def test_staged_personal_path_blocks_in_production_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            package_path = repo_root / "wild_boar_proxy" / "personal_path.py"
            package_path.parent.mkdir()
            package_path.write_text(
                'OWNER_HOME = "/Users/kirillponomarev/project"\n',
                encoding="utf-8",
            )
            _git(repo_root, "add", "wild_boar_proxy/personal_path.py")

            report = checker.inspect_staged_repo_hygiene(repo_root)

        self.assertEqual("blocked", report["status"])
        self.assertIn("personal_path", _finding_checks(report))

    def test_git_range_secret_scan_blocks_without_raw_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            (repo_root / "README.md").write_text("base\n", encoding="utf-8")
            _git(repo_root, "add", "README.md")
            base = _commit(repo_root, "base")

            secret = "sk-" + ("b" * 40)
            (repo_root / "leak.txt").write_text("token=" + secret, encoding="utf-8")
            _git(repo_root, "add", "leak.txt")
            head = _commit(repo_root, "leak")

            report = checker.inspect_git_range_repo_hygiene(
                repo_root,
                f"{base}..{head}",
            )
            rendered = checker.render_text_report(report)

        serialized = json.dumps(report, sort_keys=True) + rendered
        self.assertEqual("blocked", report["status"])
        self.assertEqual("git-range", report["mode"])
        self.assertIn("secret_scan", _finding_checks(report))
        self.assertNotIn(secret, serialized)
        self.assertIn("sha256:", serialized)

    def test_git_range_large_file_blocks_by_blob_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            (repo_root / "README.md").write_text("base\n", encoding="utf-8")
            _git(repo_root, "add", "README.md")
            base = _commit(repo_root, "base")

            (repo_root / "large.bin").write_bytes(b"x" * 17)
            _git(repo_root, "add", "large.bin")
            head = _commit(repo_root, "large")

            report = checker.inspect_git_range_repo_hygiene(
                repo_root,
                f"{base}..{head}",
                max_bytes=16,
            )

        self.assertEqual("blocked", report["status"])
        self.assertIn("large_file", _finding_checks(report))

    def test_git_range_plan_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            (repo_root / "README.md").write_text("base\n", encoding="utf-8")
            _git(repo_root, "add", "README.md")
            base = _commit(repo_root, "base")

            path = repo_root / "NEXT_CONTOUR_CANON_PLAN.md"
            path.write_text("future work", encoding="utf-8")
            _git(repo_root, "add", path.name)
            head = _commit(repo_root, "plan")

            report = checker.inspect_git_range_repo_hygiene(repo_root, f"{base}..{head}")

        self.assertEqual("blocked", report["status"])
        self.assertIn("repo_plan_file", _finding_checks(report))

    def test_git_range_ignores_deletions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            path = repo_root / "deleted.txt"
            path.write_text("remove me\n", encoding="utf-8")
            _git(repo_root, "add", path.name)
            base = _commit(repo_root, "base")

            path.unlink()
            _git(repo_root, "add", path.name)
            head = _commit(repo_root, "delete")

            report = checker.inspect_git_range_repo_hygiene(repo_root, f"{base}..{head}")

        self.assertEqual("ok", report["status"])
        self.assertEqual([], report["checked_files"])

    def test_git_range_blocks_personal_path_in_production_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            (repo_root / "README.md").write_text("base\n", encoding="utf-8")
            _git(repo_root, "add", "README.md")
            base = _commit(repo_root, "base")

            package_path = repo_root / "wild_boar_proxy" / "personal_path.py"
            package_path.parent.mkdir()
            package_path.write_text(
                'OWNER_HOME = "/Users/kirillponomarev/project"\n',
                encoding="utf-8",
            )
            _git(repo_root, "add", "wild_boar_proxy/personal_path.py")
            head = _commit(repo_root, "personal path")

            report = checker.inspect_git_range_repo_hygiene(repo_root, f"{base}..{head}")

        self.assertEqual("blocked", report["status"])
        self.assertIn("personal_path", _finding_checks(report))

    def test_git_range_ignores_unchanged_historical_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            historical = repo_root / "audit_results" / "historical.log"
            historical.parent.mkdir()
            historical.write_text(
                "api_key=" + ("c" * 40),
                encoding="utf-8",
            )
            _git(repo_root, "add", "audit_results/historical.log")
            base = _commit(repo_root, "base historical")

            (repo_root / "README.md").write_text("clean change\n", encoding="utf-8")
            _git(repo_root, "add", "README.md")
            head = _commit(repo_root, "clean change")

            report = checker.inspect_git_range_repo_hygiene(repo_root, f"{base}..{head}")

        self.assertEqual("ok", report["status"])
        self.assertEqual(
            [{"path": "README.md", "size": 13, "revision": head}],
            report["checked_files"],
        )


if __name__ == "__main__":
    unittest.main()

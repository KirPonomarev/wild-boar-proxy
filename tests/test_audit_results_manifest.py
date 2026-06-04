import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "tools" / "build_audit_results_manifest.py"


spec = importlib.util.spec_from_file_location("build_audit_results_manifest", BUILDER_PATH)
assert spec is not None
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


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


def _entry_by_path(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    entries = manifest["entries"]
    assert isinstance(entries, list)
    return {
        str(entry["path"]): entry
        for entry in entries
        if isinstance(entry, dict)
    }


class AuditResultsManifestTests(unittest.TestCase):
    def test_manifest_flags_secret_and_personal_path_without_raw_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results" / "sample"
            audit_dir.mkdir(parents=True)
            secret = "sk-" + ("d" * 40)
            personal_path = "/Users/kirillponomarev/private/auth.json"
            source = audit_dir / "packet.json"
            source.write_text(
                json.dumps(
                    {
                        "api_key": secret,
                        "external_path": personal_path,
                    }
                ),
                encoding="utf-8",
            )
            _git(repo_root, "add", "audit_results/sample/packet.json")
            _commit(repo_root, "base")

            manifest = builder.build_manifest(repo_root, repo_root / "audit_results")
            serialized = builder.manifest_json_bytes(manifest).decode("utf-8")
            entry = _entry_by_path(manifest)["audit_results/sample/packet.json"]

        self.assertTrue(entry["contains_secret_like_pattern"])
        self.assertTrue(entry["contains_personal_path_pattern"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn(personal_path, serialized)
        self.assertEqual([], builder.validate_manifest_redaction(manifest))

    def test_validate_manifest_redaction_blocks_raw_values(self) -> None:
        manifest = {
            "entries": [
                {
                    "path": "audit_results/sk-" + ("e" * 40) + ".txt",
                    "note": "/Users/kirillponomarev/private/auth.json",
                }
            ]
        }

        errors = builder.validate_manifest_redaction(manifest)

        self.assertTrue(errors)
        self.assertTrue(any("secret" in error for error in errors), errors)
        self.assertTrue(any("personal path" in error for error in errors), errors)

    def test_evidence_classification_is_stable(self) -> None:
        cases = {
            "closeout.md": "closeout",
            "command_packet.json": "packet",
            "probe.stdout.log": "log",
            "screen.png": "image",
            "inventory_manifest.json": "manifest",
            "spec.md": "spec",
            "notes.txt": "other",
        }

        actual = {
            name: builder.evidence_class_for_path(Path(name))
            for name in sorted(cases)
        }

        self.assertEqual(cases, actual)

    def test_manifest_tracks_clean_modified_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            tracked = audit_dir / "tracked_packet.json"
            tracked.write_text('{"packet": true}\n', encoding="utf-8")
            _git(repo_root, "add", "audit_results/tracked_packet.json")
            _commit(repo_root, "base")

            tracked.write_text('{"packet": false}\n', encoding="utf-8")
            untracked = audit_dir / "new.log"
            untracked.write_text("new evidence\n", encoding="utf-8")

            manifest = builder.build_manifest(repo_root, audit_dir)
            entries = _entry_by_path(manifest)

        self.assertTrue(entries["audit_results/tracked_packet.json"]["tracked"])
        self.assertEqual(
            "modified",
            entries["audit_results/tracked_packet.json"]["dirty_state"],
        )
        self.assertFalse(entries["audit_results/new.log"]["tracked"])
        self.assertEqual("untracked", entries["audit_results/new.log"]["dirty_state"])

    def test_manifest_surfaces_deleted_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            tracked = audit_dir / "deleted_packet.json"
            tracked.write_text('{"packet": true}\n', encoding="utf-8")
            _git(repo_root, "add", "audit_results/deleted_packet.json")
            _commit(repo_root, "base")

            tracked.unlink()
            manifest = builder.build_manifest(repo_root, audit_dir)
            entries = _entry_by_path(manifest)

        self.assertIn("audit_results/deleted_packet.json", entries)
        self.assertTrue(entries["audit_results/deleted_packet.json"]["tracked"])
        self.assertEqual(
            "deleted",
            entries["audit_results/deleted_packet.json"]["dirty_state"],
        )
        self.assertIsNone(entries["audit_results/deleted_packet.json"]["sha256"])

    def test_manifest_entries_are_sorted_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            (audit_dir / "z.log").write_text("z\n", encoding="utf-8")
            (audit_dir / "a.log").write_text("a\n", encoding="utf-8")

            manifest = builder.build_manifest(repo_root, audit_dir)
            paths = [entry["path"] for entry in manifest["entries"]]
            first = builder.manifest_json_bytes(manifest)
            second = builder.manifest_json_bytes(manifest)

        self.assertEqual(sorted(paths), paths)
        self.assertEqual(first, second)

    def test_cli_check_redaction_writes_metadata_only_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            secret = "sk-" + ("f" * 40)
            (audit_dir / "leaky.log").write_text(
                f"token={secret}\npath=/Users/kirillponomarev/private\n",
                encoding="utf-8",
            )
            output = Path(temp_dir) / "manifest.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_PATH),
                    "--root",
                    str(repo_root),
                    "--output",
                    str(output),
                    "--check-redaction",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = output.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(secret, payload)
        self.assertNotIn("/Users/kirillponomarev", payload)

    def test_cli_refuses_to_write_manifest_under_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            output = repo_root / "manifest.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_PATH),
                    "--root",
                    str(repo_root),
                    "--output",
                    str(output),
                    "--check-redaction",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output_exists = output.exists()

        self.assertEqual(1, result.returncode)
        self.assertIn("refusing to write manifest under repository root", result.stderr)
        self.assertFalse(output_exists)

    def test_cli_refuses_to_write_manifest_under_audit_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _git(repo_root, "init")
            audit_dir = repo_root / "audit_results"
            audit_dir.mkdir()
            output = audit_dir / "manifest.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_PATH),
                    "--root",
                    str(repo_root),
                    "--output",
                    str(output),
                    "--check-redaction",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output_exists = output.exists()

        self.assertEqual(1, result.returncode)
        self.assertIn("refusing to write manifest under audit_results", result.stderr)
        self.assertFalse(output_exists)


if __name__ == "__main__":
    unittest.main()

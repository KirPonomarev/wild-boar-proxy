import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRUNE_PATH = ROOT / "tools" / "prune_audit_results_retention.py"
EXPORTER_PATH = ROOT / "tools" / "export_audit_results_archive.py"


spec = importlib.util.spec_from_file_location("prune_audit_results_retention", PRUNE_PATH)
assert spec is not None
prune = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = prune
spec.loader.exec_module(prune)

exporter_spec = importlib.util.spec_from_file_location(
    "export_audit_results_archive_for_prune_tests",
    EXPORTER_PATH,
)
assert exporter_spec is not None
exporter = importlib.util.module_from_spec(exporter_spec)
assert exporter_spec.loader is not None
sys.modules[exporter_spec.name] = exporter
exporter_spec.loader.exec_module(exporter)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo_root: Path, message: str) -> None:
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


def _seed_repo(repo_root: Path) -> None:
    _git(repo_root, "init")
    audit_dir = repo_root / "audit_results"
    (audit_dir / "nested").mkdir(parents=True)
    (audit_dir / "packet.json").write_text('{"status":"ok"}\n', encoding="utf-8")
    (audit_dir / "nested" / "evidence.log").write_text("bounded evidence\n", encoding="utf-8")
    _git(repo_root, "add", "audit_results")
    _commit(repo_root, "base")


def _archive(repo_root: Path, external_root: Path) -> Path:
    packet = exporter.run_export(
        repo_root=repo_root,
        audit_root=Path("audit_results"),
        external_root=external_root,
        mode="archive",
        include_raw=True,
        acknowledgement=exporter.RAW_ACKNOWLEDGEMENT,
    )
    packet_path = external_root / "archive_packet.json"
    packet_path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return packet_path


class AuditResultsRetentionPruneTests(unittest.TestCase):
    def test_dry_run_reports_delete_surface_without_mutating_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            _seed_repo(repo_root)
            external_root = Path(temp_dir) / "external"
            packet_path = _archive(repo_root, external_root)
            before = sorted(path.relative_to(repo_root).as_posix() for path in repo_root.rglob("*"))

            packet = prune.run_prune(
                repo_root=repo_root,
                audit_root=Path("audit_results"),
                external_root=external_root,
                archive_packet_path=packet_path,
                mode="dry_run",
            )
            after = sorted(path.relative_to(repo_root).as_posix() for path in repo_root.rglob("*"))

        self.assertEqual("ok", packet["status"])
        self.assertEqual("dry_run", packet["mode"])
        self.assertEqual([], packet["mutations"])
        self.assertEqual("audit_results_only", packet["planned_mutation_surface"])
        self.assertEqual(2, packet["delete_plan"]["files_to_delete"])
        self.assertEqual(before, after)

    def test_apply_leaves_only_retained_manifest_under_audit_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            _seed_repo(repo_root)
            external_root = Path(temp_dir) / "external"
            packet_path = _archive(repo_root, external_root)

            packet = prune.run_prune(
                repo_root=repo_root,
                audit_root=Path("audit_results"),
                external_root=external_root,
                archive_packet_path=packet_path,
                mode="apply",
            )
            retained_path = repo_root / packet["retained_manifest_path"]
            remaining = sorted(
                path.relative_to(repo_root).as_posix()
                for path in (repo_root / "audit_results").rglob("*")
            )
            retained = json.loads(retained_path.read_text(encoding="utf-8"))

        self.assertEqual("ok", packet["status"])
        self.assertEqual("apply", packet["mode"])
        self.assertEqual(["audit_results/audit_results_redacted_manifest.json"], remaining)
        self.assertEqual(prune.RETAINED_ARTIFACT_TYPE, retained["artifact_type"])
        self.assertEqual(2, retained["summary"]["files_total"])
        self.assertEqual([], prune.manifest_builder.validate_manifest_redaction(retained))

    def test_apply_blocks_when_current_audit_results_drifted_after_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            _seed_repo(repo_root)
            external_root = Path(temp_dir) / "external"
            packet_path = _archive(repo_root, external_root)
            (repo_root / "audit_results" / "packet.json").write_text(
                '{"status":"changed"}\n',
                encoding="utf-8",
            )

            with self.assertRaises(prune.RetentionPruneError) as raised:
                prune.run_prune(
                    repo_root=repo_root,
                    audit_root=Path("audit_results"),
                    external_root=external_root,
                    archive_packet_path=packet_path,
                    mode="apply",
                )

        self.assertEqual("current_audit_results_archive_drift", raised.exception.code)

    def test_external_root_inside_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            _seed_repo(repo_root)
            external_root = Path(temp_dir) / "external"
            packet_path = _archive(repo_root, external_root)

            inside_repo_external_root = repo_root / "external"
            inside_repo_external_root.mkdir()

            with self.assertRaises(prune.RetentionPruneError) as raised:
                prune.run_prune(
                    repo_root=repo_root,
                    audit_root=Path("audit_results"),
                    external_root=inside_repo_external_root,
                    archive_packet_path=packet_path,
                    mode="dry_run",
                )

        self.assertEqual("external_root_inside_repo", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

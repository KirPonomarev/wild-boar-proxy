import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = ROOT / "tools" / "export_audit_results_archive.py"


spec = importlib.util.spec_from_file_location("export_audit_results_archive", EXPORTER_PATH)
assert spec is not None
exporter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = exporter
spec.loader.exec_module(exporter)


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


def _init_repo_with_audit_file(temp_dir: str) -> tuple[Path, Path]:
    repo_root = Path(temp_dir) / "repo"
    repo_root.mkdir()
    _git(repo_root, "init")
    audit_dir = repo_root / "audit_results"
    audit_dir.mkdir()
    evidence = audit_dir / "packet.json"
    evidence.write_text('{"packet": true}\n', encoding="utf-8")
    _git(repo_root, "add", "audit_results/packet.json")
    _commit(repo_root, "base")
    return repo_root, audit_dir


def _run_exporter(
    repo_root: Path,
    external_root: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(EXPORTER_PATH),
            "--root",
            str(repo_root),
            "--external-root",
            str(external_root),
            "--json",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _packet(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def _manifest_for(repo_root: Path) -> dict[str, object]:
    return exporter.manifest_builder.build_manifest(repo_root, repo_root / "audit_results")


def _write_manifest(external_root: Path, manifest: dict[str, object]) -> Path:
    manifest_path = external_root / exporter.MANIFEST_FILENAME
    manifest_path.write_bytes(exporter.manifest_builder.manifest_json_bytes(manifest))
    return manifest_path


class AuditResultsExternalizationTests(unittest.TestCase):
    def test_dry_run_packet_has_counts_and_does_not_write_external_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external" / "archive"
            before = _git(repo_root, "status", "--porcelain", "--", "audit_results").stdout

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)
            after = _git(repo_root, "status", "--porcelain", "--", "audit_results").stdout
            external_root_exists = external_root.exists()
            audit_dir_exists = audit_dir.exists()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(external_root_exists)
        self.assertEqual(before, after)
        self.assertEqual("ok", packet["status"])
        self.assertEqual("dry_run", packet["mode"])
        self.assertEqual("audit_results", packet["audit_root"])
        self.assertEqual(1, packet["files_total"])
        self.assertEqual([], packet["mutations"])
        self.assertIsNone(packet["archive_sha256"])
        self.assertIsInstance(packet["manifest_sha256"], str)
        self.assertTrue(audit_dir_exists)

    def test_external_root_inside_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = repo_root / "external_archive"

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("external_root_inside_repo", packet["error_code"])

    def test_external_root_inside_audit_results_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = audit_dir / "archive"

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("external_root_inside_audit_results", packet["error_code"])

    def test_archive_mode_requires_raw_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"

            result = _run_exporter(repo_root, external_root, "--archive")
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("archive_mode_requires_include_raw", packet["error_code"])

    def test_archive_mode_writes_only_external_root_with_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"

            result = _run_exporter(
                repo_root,
                external_root,
                "--archive",
                "--include-raw",
                "--acknowledge-raw-archive",
                exporter.RAW_ACKNOWLEDGEMENT,
            )
            packet = _packet(result)
            repo_status = _git(repo_root, "status", "--porcelain").stdout
            manifest_written = (external_root / exporter.MANIFEST_FILENAME).is_file()
            archive_written = (external_root / exporter.ARCHIVE_FILENAME).is_file()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", repo_status)
        self.assertEqual("ok", packet["status"])
        self.assertEqual("archive", packet["mode"])
        self.assertTrue(manifest_written)
        self.assertTrue(archive_written)
        self.assertEqual(
            [exporter.MANIFEST_FILENAME, exporter.ARCHIVE_FILENAME],
            packet["written_files"],
        )
        self.assertEqual(2, len(packet["mutations"]))
        self.assertIsInstance(packet["verification"], dict)
        verification = packet["verification"]
        self.assertEqual("passed", verification["status"])
        self.assertEqual(1, verification["archive_entries_total"])
        self.assertTrue(verification["archive_paths_safe"])
        self.assertTrue(verification["archive_regular_files_only"])
        self.assertTrue(verification["archive_member_sha256_matches"])
        self.assertTrue(verification["archive_sha256_matches"])
        self.assertTrue(verification["manifest_sha256_matches"])

    def test_packet_redacts_secret_and_personal_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, audit_dir = _init_repo_with_audit_file(temp_dir)
            secret = "sk-" + ("a" * 40)
            personal_path = "/Users/" + "kirillponomarev" + "/private/auth.json"
            (audit_dir / "leaky_packet.json").write_text(
                json.dumps({"api_key": secret, "path": personal_path}),
                encoding="utf-8",
            )
            external_root = Path(temp_dir) / "external_archive"

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(personal_path, result.stdout)
        self.assertEqual("ok", packet["status"])
        self.assertEqual(1, packet["secret_like_entries"])
        self.assertEqual(1, packet["personal_path_entries"])

    def test_archive_tar_digest_is_stable_for_stable_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root_a = Path(temp_dir) / "external_a"
            external_root_b = Path(temp_dir) / "external_b"
            common_args = (
                "--archive",
                "--include-raw",
                "--acknowledge-raw-archive",
                exporter.RAW_ACKNOWLEDGEMENT,
            )

            result_a = _run_exporter(repo_root, external_root_a, *common_args)
            result_b = _run_exporter(repo_root, external_root_b, *common_args)
            packet_a = _packet(result_a)
            packet_b = _packet(result_b)

        self.assertEqual(0, result_a.returncode, result_a.stderr)
        self.assertEqual(0, result_b.returncode, result_b.stderr)
        self.assertEqual(packet_a["archive_sha256"], packet_b["archive_sha256"])
        self.assertEqual(packet_a["verification"], packet_b["verification"])

    def test_dry_run_reflects_deleted_tracked_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, audit_dir = _init_repo_with_audit_file(temp_dir)
            (audit_dir / "packet.json").unlink()
            external_root = Path(temp_dir) / "external_archive"

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)
            archive_plan = packet["archive_plan"]

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, packet["dirty_total"])
        self.assertIsInstance(archive_plan, dict)
        self.assertEqual(1, archive_plan["deleted_tracked_entries"])
        self.assertEqual(0, archive_plan["files_to_archive"])

    def test_verify_archive_rejects_absolute_tar_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            external_root.mkdir()
            manifest = _manifest_for(repo_root)
            manifest_path = _write_manifest(external_root, manifest)
            archive_path = external_root / exporter.ARCHIVE_FILENAME
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("/audit_results/packet.json")
                info.size = 0
                archive.addfile(info)

            with self.assertRaises(exporter.ExternalizationError) as raised:
                exporter.verify_archive_readback(
                    archive_path=archive_path,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    archive_sha256=exporter._sha256_file(archive_path),
                    manifest_sha256=exporter._sha256_file(manifest_path),
                )

        self.assertEqual("archive_member_path_unsafe", raised.exception.code)

    def test_verify_archive_rejects_dotdot_tar_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            external_root.mkdir()
            manifest = _manifest_for(repo_root)
            manifest_path = _write_manifest(external_root, manifest)
            archive_path = external_root / exporter.ARCHIVE_FILENAME
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("audit_results/../packet.json")
                info.size = 0
                archive.addfile(info)

            with self.assertRaises(exporter.ExternalizationError) as raised:
                exporter.verify_archive_readback(
                    archive_path=archive_path,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    archive_sha256=exporter._sha256_file(archive_path),
                    manifest_sha256=exporter._sha256_file(manifest_path),
                )

        self.assertEqual("archive_member_path_unsafe", raised.exception.code)

    def test_verify_archive_rejects_symlink_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            external_root.mkdir()
            manifest = _manifest_for(repo_root)
            manifest_path = _write_manifest(external_root, manifest)
            archive_path = external_root / exporter.ARCHIVE_FILENAME
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("audit_results/packet.json")
                info.type = tarfile.SYMTYPE
                info.linkname = "/tmp/target"
                archive.addfile(info)

            with self.assertRaises(exporter.ExternalizationError) as raised:
                exporter.verify_archive_readback(
                    archive_path=archive_path,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    archive_sha256=exporter._sha256_file(archive_path),
                    manifest_sha256=exporter._sha256_file(manifest_path),
                )

        self.assertEqual("archive_member_not_regular_file", raised.exception.code)

    def test_verify_archive_rejects_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            external_root.mkdir()
            manifest = _manifest_for(repo_root)
            manifest_path = _write_manifest(external_root, manifest)
            archive_path = external_root / exporter.ARCHIVE_FILENAME
            with tarfile.open(archive_path, "w"):
                pass

            with self.assertRaises(exporter.ExternalizationError) as raised:
                exporter.verify_archive_readback(
                    archive_path=archive_path,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    archive_sha256=exporter._sha256_file(archive_path),
                    manifest_sha256=exporter._sha256_file(manifest_path),
                )

        self.assertEqual("archive_entry_count_mismatch", raised.exception.code)

    def test_verify_archive_rejects_member_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            external_root.mkdir()
            manifest = _manifest_for(repo_root)
            manifest_path = _write_manifest(external_root, manifest)
            archive_path = external_root / exporter.ARCHIVE_FILENAME
            payload = b'{"packet":false}\n'
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("audit_results/packet.json")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))

            with self.assertRaises(exporter.ExternalizationError) as raised:
                exporter.verify_archive_readback(
                    archive_path=archive_path,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    archive_sha256=exporter._sha256_file(archive_path),
                    manifest_sha256=exporter._sha256_file(manifest_path),
                )

        self.assertEqual("archive_member_digest_mismatch", raised.exception.code)

    def test_export_blocks_symlinked_audit_entry_structurally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            outside = Path(temp_dir) / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (audit_dir / "linked.txt").symlink_to(outside)

            result = _run_exporter(repo_root, external_root, "--dry-run")
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("audit_results_symlink_blocked", packet["error_code"])

    def test_export_blocks_symlinked_audit_root_ancestor_structurally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            outside = Path(temp_dir) / "outside"
            outside.mkdir()
            (outside / "audit_results").mkdir()
            (repo_root / "alias").symlink_to(outside, target_is_directory=True)

            result = _run_exporter(
                repo_root,
                external_root,
                "--audit-root",
                "alias/audit_results",
                "--dry-run",
            )
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("audit_root_symlink_blocked", packet["error_code"])

    def test_export_blocks_absolute_audit_root_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root, _audit_dir = _init_repo_with_audit_file(temp_dir)
            external_root = Path(temp_dir) / "external_archive"
            outside = Path(temp_dir) / "outside_audit_results"
            outside.mkdir()

            result = _run_exporter(
                repo_root,
                external_root,
                "--audit-root",
                str(outside),
                "--dry-run",
            )
            packet = _packet(result)

        self.assertEqual(1, result.returncode)
        self.assertFalse(external_root.exists())
        self.assertEqual("blocked", packet["status"])
        self.assertEqual("audit_root_outside_repo", packet["error_code"])


if __name__ == "__main__":
    unittest.main()

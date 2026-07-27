#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_audit_results_manifest as manifest_builder


ARTIFACT_TYPE = "audit_results_externalization_dry_run"
RAW_ACKNOWLEDGEMENT = "I_UNDERSTAND_RAW_AUDIT_RESULTS_LEAVE_REPO"
MANIFEST_FILENAME = "audit_results_manifest.json"
ARCHIVE_FILENAME = "audit_results_raw.tar"


class ExternalizationError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        mutations: list[dict[str, str]] | None = None,
        written_files: list[str] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.mutations = mutations or []
        self.written_files = written_files or []


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _repo_relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packet_json_bytes(packet: dict[str, Any]) -> bytes:
    return json.dumps(
        packet,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ).encode("utf-8")


def validate_packet_redaction(packet: dict[str, Any]) -> list[str]:
    payload = packet_json_bytes(packet)
    errors: list[str] = []
    if manifest_builder._matches_any(manifest_builder.SECRET_PATTERNS, payload):
        errors.append("packet contains raw secret-like value")
    if manifest_builder._matches_any(manifest_builder.PERSONAL_PATH_PATTERNS, payload):
        errors.append("packet contains raw personal path value")
    return errors


def resolve_audit_root(repo_root: Path, audit_root: Path) -> Path:
    raw_audit_root = audit_root if audit_root.is_absolute() else repo_root / audit_root
    raw_audit_root = raw_audit_root.absolute()
    if not _is_relative_to(raw_audit_root, repo_root):
        raise ExternalizationError("audit_root_outside_repo")

    ancestors = [raw_audit_root, *raw_audit_root.parents]
    for ancestor in reversed(ancestors):
        if ancestor.is_symlink():
            raise ExternalizationError("audit_root_symlink_blocked")

    resolved = raw_audit_root.resolve()
    if not _is_relative_to(resolved, repo_root):
        raise ExternalizationError("audit_root_outside_repo")
    return resolved

def reject_audit_root_symlinks(audit_root: Path) -> None:
    if audit_root.is_symlink():
        raise ExternalizationError("audit_results_symlink_blocked")
    if not audit_root.exists():
        return
    for path in audit_root.rglob("*"):
        if path.is_symlink():
            raise ExternalizationError("audit_results_symlink_blocked")


def validate_external_root(
    *,
    repo_root: Path,
    audit_root: Path,
    external_root: Path,
) -> None:
    if _is_relative_to(external_root, audit_root):
        raise ExternalizationError("external_root_inside_audit_results")
    if _is_relative_to(external_root, repo_root):
        raise ExternalizationError("external_root_inside_repo")


def validate_archive_mode(*, include_raw: bool, acknowledgement: str | None) -> None:
    if not include_raw:
        raise ExternalizationError("archive_mode_requires_include_raw")
    if acknowledgement != RAW_ACKNOWLEDGEMENT:
        raise ExternalizationError("archive_mode_requires_raw_acknowledgement")


def archive_plan_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest["entries"]
    if not isinstance(entries, list):
        raise ExternalizationError("manifest_entries_malformed")

    files_to_archive = 0
    bytes_to_archive = 0
    deleted_tracked_entries = 0
    skipped_entries = 0

    for entry in entries:
        if not isinstance(entry, dict):
            raise ExternalizationError("manifest_entry_malformed")
        if entry.get("kind") != "file":
            continue
        if entry.get("dirty_state") == "deleted":
            deleted_tracked_entries += 1
            skipped_entries += 1
            continue
        files_to_archive += 1
        bytes_to_archive += int(entry.get("size_bytes", 0))

    return {
        "files_to_archive": files_to_archive,
        "bytes_to_archive": bytes_to_archive,
        "deleted_tracked_entries": deleted_tracked_entries,
        "skipped_entries": skipped_entries,
    }


def build_packet(
    *,
    mode: str,
    manifest: dict[str, Any],
    manifest_sha256: str,
    archive_sha256: str | None,
    mutations: list[dict[str, str]],
    written_files: list[str],
    verification: dict[str, Any],
) -> dict[str, Any]:
    summary = manifest["summary"]
    if not isinstance(summary, dict):
        raise ExternalizationError("manifest_summary_malformed")

    packet: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "status": "ok",
        "mode": mode,
        "repo_root": "<redacted>",
        "audit_root": manifest["source_root"],
        "external_root": "<redacted>",
        "external_root_policy": "outside_repo_required",
        "entries_total": summary["entries_total"],
        "files_total": summary["files_total"],
        "dirs_total": summary["dirs_total"],
        "dirty_total": summary["dirty_total"],
        "secret_like_entries": summary["secret_like_entries"],
        "personal_path_entries": summary["personal_path_entries"],
        "archive_plan": archive_plan_from_manifest(manifest),
        "manifest_sha256": manifest_sha256,
        "archive_sha256": archive_sha256,
        "verification": verification,
        "written_files": written_files,
        "mutations": mutations,
    }
    errors = validate_packet_redaction(packet)
    if errors:
        raise ExternalizationError("packet_redaction_failed")
    return packet


def blocked_packet(
    *,
    mode: str,
    code: str,
    mutations: list[dict[str, str]] | None = None,
    written_files: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "status": "blocked",
        "mode": mode,
        "repo_root": "<redacted>",
        "audit_root": "audit_results",
        "external_root": "<redacted>",
        "external_root_policy": "outside_repo_required",
        "error_code": code,
        "errors": [code],
        "written_files": written_files or [],
        "mutations": mutations or [],
    }


def write_manifest(external_root: Path, manifest_payload: bytes) -> Path:
    manifest_path = external_root / MANIFEST_FILENAME
    if manifest_path.exists():
        raise ExternalizationError("external_manifest_already_exists")
    manifest_path.write_bytes(manifest_payload)
    return manifest_path


def _tar_path_is_safe(name: str, *, audit_source_root: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    if ".." in path.parts:
        return False
    return name == audit_source_root or name.startswith(f"{audit_source_root}/")


def write_raw_archive(
    *,
    repo_root: Path,
    external_root: Path,
    manifest: dict[str, Any],
) -> Path:
    archive_path = external_root / ARCHIVE_FILENAME
    if archive_path.exists():
        raise ExternalizationError("external_archive_already_exists")

    entries = manifest["entries"]
    if not isinstance(entries, list):
        raise ExternalizationError("manifest_entries_malformed")

    with tarfile.open(archive_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for entry in entries:
            if not isinstance(entry, dict):
                raise ExternalizationError("manifest_entry_malformed")
            if entry.get("kind") != "file" or entry.get("dirty_state") == "deleted":
                continue

            repo_path = str(entry["path"])
            raw_source = repo_root / repo_path
            if raw_source.is_symlink():
                raise ExternalizationError("archive_source_symlink_blocked")
            source = raw_source.resolve()
            if not _is_relative_to(source, repo_root):
                raise ExternalizationError("archive_source_outside_repo")
            if not source.is_file():
                raise ExternalizationError("archive_source_missing")

            info = tarfile.TarInfo(repo_path)
            info.size = source.stat().st_size
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with source.open("rb") as handle:
                archive.addfile(info, handle)
    return archive_path


def verify_archive_readback(
    *,
    archive_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    archive_sha256: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ExternalizationError("external_manifest_missing")
    if not archive_path.is_file():
        raise ExternalizationError("external_archive_missing")
    if _sha256_file(manifest_path) != manifest_sha256:
        raise ExternalizationError("external_manifest_digest_mismatch")
    if _sha256_file(archive_path) != archive_sha256:
        raise ExternalizationError("external_archive_digest_mismatch")

    manifest_from_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_builder.validate_manifest_redaction(manifest_from_disk):
        raise ExternalizationError("external_manifest_redaction_failed")
    if manifest_from_disk.get("summary") != manifest.get("summary"):
        raise ExternalizationError("external_manifest_summary_mismatch")

    archive_plan = archive_plan_from_manifest(manifest)
    audit_source_root = str(manifest["source_root"])
    expected_sha_by_path = {
        str(entry["path"]): str(entry["sha256"])
        for entry in manifest["entries"]
        if isinstance(entry, dict)
        and entry.get("kind") == "file"
        and entry.get("dirty_state") != "deleted"
    }
    seen_paths: set[str] = set()
    total_size = 0
    entries_total = 0
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        for member in members:
            entries_total += 1
            total_size += member.size
            if not member.isfile():
                raise ExternalizationError("archive_member_not_regular_file")
            if member.issym() or member.islnk():
                raise ExternalizationError("archive_member_link_blocked")
            if not _tar_path_is_safe(member.name, audit_source_root=audit_source_root):
                raise ExternalizationError("archive_member_path_unsafe")
            if member.name not in expected_sha_by_path:
                raise ExternalizationError("archive_member_not_in_manifest")
            handle = archive.extractfile(member)
            if handle is None:
                raise ExternalizationError("archive_member_payload_missing")
            digest = hashlib.sha256(handle.read()).hexdigest()
            if digest != expected_sha_by_path[member.name]:
                raise ExternalizationError("archive_member_digest_mismatch")
            seen_paths.add(member.name)

    if entries_total != archive_plan["files_to_archive"]:
        raise ExternalizationError("archive_entry_count_mismatch")
    if seen_paths != set(expected_sha_by_path):
        raise ExternalizationError("archive_manifest_member_set_mismatch")
    if total_size != archive_plan["bytes_to_archive"]:
        raise ExternalizationError("archive_size_mismatch")

    return {
        "status": "passed",
        "archive_entries_total": entries_total,
        "archive_bytes_total": total_size,
        "archive_entry_count_matches_plan": True,
        "archive_size_matches_plan": True,
        "archive_paths_safe": True,
        "archive_regular_files_only": True,
        "archive_member_sha256_matches": True,
        "archive_sha256_matches": True,
        "manifest_sha256_matches": True,
        "manifest_summary_matches": True,
        "manifest_redaction_passed": True,
    }


def run_export(
    *,
    repo_root: Path,
    audit_root: Path,
    external_root: Path,
    mode: str,
    include_raw: bool,
    acknowledgement: str | None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    audit_root = resolve_audit_root(repo_root, audit_root)
    external_root = external_root.resolve()
    validate_external_root(
        repo_root=repo_root,
        audit_root=audit_root,
        external_root=external_root,
    )
    reject_audit_root_symlinks(audit_root)
    if mode == "archive":
        validate_archive_mode(include_raw=include_raw, acknowledgement=acknowledgement)

    manifest = manifest_builder.build_manifest(repo_root, audit_root)
    manifest_errors = manifest_builder.validate_manifest_redaction(manifest)
    if manifest_errors:
        raise ExternalizationError("manifest_redaction_failed")
    manifest_payload = manifest_builder.manifest_json_bytes(manifest)
    manifest_sha256 = _sha256_bytes(manifest_payload)

    if mode == "dry_run":
        return build_packet(
            mode=mode,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            archive_sha256=None,
            mutations=[],
            written_files=[],
            verification={"status": "not_applicable", "reason": "dry_run"},
        )

    external_root.mkdir(parents=True, exist_ok=True)
    mutations: list[dict[str, str]] = []
    written_files: list[str] = []
    manifest_path = write_manifest(external_root, manifest_payload)
    written_files.append(manifest_path.name)
    mutations.append(
        {"surface": "external_root", "kind": "write_file", "file": manifest_path.name}
    )
    archive_path = write_raw_archive(
        repo_root=repo_root,
        external_root=external_root,
        manifest=manifest,
    )
    written_files.append(archive_path.name)
    mutations.append(
        {"surface": "external_root", "kind": "write_file", "file": archive_path.name}
    )
    archive_sha256 = _sha256_file(archive_path)
    try:
        verification = verify_archive_readback(
            archive_path=archive_path,
            manifest_path=manifest_path,
            manifest=manifest,
            archive_sha256=archive_sha256,
            manifest_sha256=manifest_sha256,
        )
    except ExternalizationError as error:
        raise ExternalizationError(
            error.code,
            mutations=mutations,
            written_files=written_files,
        ) from error
    return build_packet(
        mode=mode,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        archive_sha256=archive_sha256,
        written_files=written_files,
        mutations=mutations,
        verification=verification,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a no-repo-mutation externalization packet for audit_results."
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Repository root. Defaults to git rev-parse --show-toplevel.",
    )
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=Path("audit_results"),
        help="Audit results directory, absolute or relative to --root.",
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        required=True,
        help="External archive root. Must resolve outside the repository.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="mode",
        action="store_const",
        const="dry_run",
        help="Emit the externalization packet without writing archive files.",
    )
    mode.add_argument(
        "--archive",
        dest="mode",
        action="store_const",
        const="archive",
        help="Write a raw archive and redacted manifest to --external-root.",
    )
    parser.set_defaults(mode="dry_run")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Required with --archive because raw audit evidence leaves the repo.",
    )
    parser.add_argument(
        "--acknowledge-raw-archive",
        help=f"Required with --archive. Exact value: {RAW_ACKNOWLEDGEMENT}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for command-surface clarity. Output is always JSON.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = (args.root or manifest_builder.discover_repo_root()).resolve()
        packet = run_export(
            repo_root=repo_root,
            audit_root=args.audit_root,
            external_root=_resolve_path(args.external_root),
            mode=args.mode,
            include_raw=args.include_raw,
            acknowledgement=args.acknowledge_raw_archive,
        )
        sys.stdout.buffer.write(packet_json_bytes(packet) + b"\n")
        return 0
    except ExternalizationError as error:
        sys.stdout.buffer.write(
            packet_json_bytes(
                blocked_packet(
                    mode=args.mode,
                    code=error.code,
                    mutations=error.mutations,
                    written_files=error.written_files,
                )
            )
            + b"\n"
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            packet_json_bytes(blocked_packet(mode=args.mode, code="unexpected_failure"))
            + b"\n"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

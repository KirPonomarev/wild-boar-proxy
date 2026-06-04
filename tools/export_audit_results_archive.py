#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
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
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
    if audit_root.is_absolute():
        return audit_root.resolve()
    return (repo_root / audit_root).resolve()


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
        "written_files": written_files,
        "mutations": mutations,
    }
    errors = validate_packet_redaction(packet)
    if errors:
        raise ExternalizationError("packet_redaction_failed")
    return packet


def blocked_packet(*, mode: str, code: str) -> dict[str, Any]:
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
        "mutations": [],
    }


def write_manifest(external_root: Path, manifest_payload: bytes) -> Path:
    manifest_path = external_root / MANIFEST_FILENAME
    if manifest_path.exists():
        raise ExternalizationError("external_manifest_already_exists")
    manifest_path.write_bytes(manifest_payload + b"\n")
    return manifest_path


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
            source = (repo_root / repo_path).resolve()
            if not _is_relative_to(source, repo_root):
                raise ExternalizationError("archive_source_outside_repo")
            if source.is_symlink():
                raise ExternalizationError("archive_source_symlink_blocked")
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
        )

    external_root.mkdir(parents=True, exist_ok=True)
    manifest_path = write_manifest(external_root, manifest_payload)
    archive_path = write_raw_archive(
        repo_root=repo_root,
        external_root=external_root,
        manifest=manifest,
    )
    return build_packet(
        mode=mode,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        archive_sha256=_sha256_file(archive_path),
        written_files=[manifest_path.name, archive_path.name],
        mutations=[
            {"surface": "external_root", "kind": "write_file", "file": manifest_path.name},
            {"surface": "external_root", "kind": "write_file", "file": archive_path.name},
        ],
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
            packet_json_bytes(blocked_packet(mode=args.mode, code=error.code)) + b"\n"
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

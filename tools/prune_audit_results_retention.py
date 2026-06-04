#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_audit_results_manifest as manifest_builder
import export_audit_results_archive as archive_exporter


ARTIFACT_TYPE = "audit_results_retention_prune"
RETAINED_ARTIFACT_TYPE = "audit_results_retained_redacted_manifest"
RETAINED_MANIFEST_FILENAME = "audit_results_redacted_manifest.json"


class RetentionPruneError(RuntimeError):
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


def _packet_bytes(packet: dict[str, Any]) -> bytes:
    return json.dumps(
        packet,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ).encode("utf-8")


def _validate_packet_redaction(packet: dict[str, Any]) -> None:
    errors = archive_exporter.validate_packet_redaction(packet)
    if errors:
        raise RetentionPruneError("packet_redaction_failed")


def _load_archive_packet(packet_path: Path) -> dict[str, Any]:
    if not packet_path.is_file():
        raise RetentionPruneError("archive_packet_missing")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("status") != "ok":
        raise RetentionPruneError("archive_packet_not_ok")
    if packet.get("mode") != "archive":
        raise RetentionPruneError("archive_packet_not_archive_mode")
    verification = packet.get("verification")
    if not isinstance(verification, dict) or verification.get("status") != "passed":
        raise RetentionPruneError("archive_packet_not_verified")
    if not packet.get("archive_sha256") or not packet.get("manifest_sha256"):
        raise RetentionPruneError("archive_packet_missing_digest")
    return packet


def _load_external_manifest(external_root: Path) -> dict[str, Any]:
    manifest_path = external_root / archive_exporter.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RetentionPruneError("external_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = manifest_builder.validate_manifest_redaction(manifest)
    if errors:
        raise RetentionPruneError("external_manifest_redaction_failed")
    return manifest


def _validate_external_root(repo_root: Path, audit_root: Path, external_root: Path) -> None:
    if not external_root.exists():
        raise RetentionPruneError("external_root_missing")
    if not external_root.is_dir():
        raise RetentionPruneError("external_root_not_directory")
    if external_root.is_symlink():
        raise RetentionPruneError("external_root_symlink_blocked")
    try:
        archive_exporter.validate_external_root(
            repo_root=repo_root,
            audit_root=audit_root,
            external_root=external_root,
        )
    except archive_exporter.ExternalizationError as error:
        raise RetentionPruneError(error.code) from error


def _verify_archive_binding(
    *,
    external_root: Path,
    archive_packet: dict[str, Any],
    external_manifest: dict[str, Any],
) -> dict[str, Any]:
    manifest_path = external_root / archive_exporter.MANIFEST_FILENAME
    archive_path = external_root / archive_exporter.ARCHIVE_FILENAME
    try:
        verification = archive_exporter.verify_archive_readback(
            archive_path=archive_path,
            manifest_path=manifest_path,
            manifest=external_manifest,
            archive_sha256=str(archive_packet["archive_sha256"]),
            manifest_sha256=str(archive_packet["manifest_sha256"]),
        )
    except archive_exporter.ExternalizationError as error:
        raise RetentionPruneError(error.code) from error
    return verification


def _build_retained_manifest(
    *,
    external_manifest: dict[str, Any],
    archive_packet: dict[str, Any],
    archive_verification: dict[str, Any],
) -> dict[str, Any]:
    retained = {
        "schema_version": 1,
        "artifact_type": RETAINED_ARTIFACT_TYPE,
        "source_root": external_manifest["source_root"],
        "archive_binding": {
            "external_root": "<redacted>",
            "external_root_policy": "outside_repo_required",
            "archive_filename": archive_exporter.ARCHIVE_FILENAME,
            "manifest_filename": archive_exporter.MANIFEST_FILENAME,
            "archive_sha256": archive_packet["archive_sha256"],
            "manifest_sha256": archive_packet["manifest_sha256"],
            "archive_verification_status": archive_verification["status"],
        },
        "summary": external_manifest["summary"],
        "entries": external_manifest["entries"],
    }
    errors = manifest_builder.validate_manifest_redaction(retained)
    if errors:
        raise RetentionPruneError("retained_manifest_redaction_failed")
    return retained


def _compare_current_to_archive(
    *,
    repo_root: Path,
    audit_root: Path,
    external_manifest: dict[str, Any],
) -> dict[str, Any]:
    fresh_manifest = manifest_builder.build_manifest(repo_root, audit_root)
    fresh_payload = manifest_builder.manifest_json_bytes(fresh_manifest)
    external_payload = manifest_builder.manifest_json_bytes(external_manifest)
    if manifest_builder.validate_manifest_redaction(fresh_manifest):
        raise RetentionPruneError("fresh_manifest_redaction_failed")
    if fresh_payload != external_payload:
        raise RetentionPruneError("current_audit_results_archive_drift")
    return {
        "status": "passed",
        "exact_manifest_bytes_match": True,
        "fresh_manifest_sha256": archive_exporter._sha256_bytes(fresh_payload),
        "external_manifest_sha256": archive_exporter._sha256_bytes(external_payload),
        "entries_total": fresh_manifest["summary"]["entries_total"],
        "files_total": fresh_manifest["summary"]["files_total"],
        "dirs_total": fresh_manifest["summary"]["dirs_total"],
        "dirty_total": fresh_manifest["summary"]["dirty_total"],
    }


def _delete_plan(external_manifest: dict[str, Any]) -> dict[str, Any]:
    entries = external_manifest["entries"]
    if not isinstance(entries, list):
        raise RetentionPruneError("manifest_entries_malformed")
    files_to_delete = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("kind") == "file"
        and entry.get("dirty_state") != "deleted"
    ]
    dirs_to_delete = [
        entry for entry in entries if isinstance(entry, dict) and entry.get("kind") == "dir"
    ]
    return {
        "files_to_delete": len(files_to_delete),
        "dirs_to_delete": len(dirs_to_delete),
        "bytes_to_delete": sum(int(entry.get("size_bytes", 0)) for entry in files_to_delete),
        "tracked_files_to_delete": sum(1 for entry in files_to_delete if entry.get("tracked")),
        "untracked_files_to_delete": sum(
            1 for entry in files_to_delete if not entry.get("tracked")
        ),
    }


def _remove_audit_root_contents(audit_root: Path, retained_manifest_path: Path) -> None:
    if not audit_root.exists():
        audit_root.mkdir(parents=True)
        return
    for child in audit_root.iterdir():
        if child.resolve(strict=False) == retained_manifest_path.resolve(strict=False):
            continue
        if child.is_symlink():
            raise RetentionPruneError("audit_results_symlink_blocked")
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _build_packet(
    *,
    mode: str,
    repo_root: Path,
    audit_root: Path,
    external_manifest: dict[str, Any],
    archive_packet: dict[str, Any],
    archive_verification: dict[str, Any],
    equality: dict[str, Any],
    retained_manifest_path: Path,
    retained_manifest_sha256: str,
    delete_plan: dict[str, Any],
    mutations: list[dict[str, str]],
) -> dict[str, Any]:
    packet = {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "status": "ok",
        "mode": mode,
        "repo_root": "<redacted>",
        "audit_root": _repo_relative(repo_root, audit_root),
        "external_root": "<redacted>",
        "external_root_policy": "outside_repo_required",
        "retained_manifest_path": _repo_relative(repo_root, retained_manifest_path),
        "retained_manifest_sha256": retained_manifest_sha256,
        "archive_sha256": archive_packet["archive_sha256"],
        "external_manifest_sha256": archive_packet["manifest_sha256"],
        "archive_verification": archive_verification,
        "equality": equality,
        "delete_plan": delete_plan,
        "planned_mutation_surface": "audit_results_only",
        "planned_mutations": [
            {"surface": "audit_results", "kind": "delete_raw_corpus"},
            {"surface": "audit_results", "kind": "write_retained_redacted_manifest"},
        ],
        "mutations": mutations,
        "retained_manifest_summary": external_manifest["summary"],
    }
    _validate_packet_redaction(packet)
    return packet


def blocked_packet(*, mode: str, code: str) -> dict[str, Any]:
    packet = {
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
    _validate_packet_redaction(packet)
    return packet


def run_prune(
    *,
    repo_root: Path,
    audit_root: Path,
    external_root: Path,
    archive_packet_path: Path,
    mode: str,
    retained_manifest_name: str = RETAINED_MANIFEST_FILENAME,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    audit_root = archive_exporter.resolve_audit_root(repo_root, audit_root)
    external_root = external_root.resolve()
    archive_packet_path = archive_packet_path.resolve()
    retained_manifest_path = audit_root / retained_manifest_name

    if not _is_relative_to(retained_manifest_path.resolve(strict=False), audit_root):
        raise RetentionPruneError("retained_manifest_outside_audit_root")
    _validate_external_root(repo_root, audit_root, external_root)
    archive_exporter.reject_audit_root_symlinks(audit_root)

    archive_packet = _load_archive_packet(archive_packet_path)
    external_manifest = _load_external_manifest(external_root)
    archive_verification = _verify_archive_binding(
        external_root=external_root,
        archive_packet=archive_packet,
        external_manifest=external_manifest,
    )
    equality = _compare_current_to_archive(
        repo_root=repo_root,
        audit_root=audit_root,
        external_manifest=external_manifest,
    )
    retained_manifest = _build_retained_manifest(
        external_manifest=external_manifest,
        archive_packet=archive_packet,
        archive_verification=archive_verification,
    )
    retained_payload = _packet_bytes(retained_manifest) + b"\n"
    retained_manifest_sha256 = archive_exporter._sha256_bytes(retained_payload)
    plan = _delete_plan(external_manifest)

    mutations: list[dict[str, str]] = []
    if mode == "apply":
        _remove_audit_root_contents(audit_root, retained_manifest_path)
        audit_root.mkdir(parents=True, exist_ok=True)
        retained_manifest_path.write_bytes(retained_payload)
        mutations = [
            {"surface": "audit_results", "kind": "delete_raw_corpus"},
            {
                "surface": "audit_results",
                "kind": "write_file",
                "file": _repo_relative(repo_root, retained_manifest_path),
            },
        ]

    return _build_packet(
        mode=mode,
        repo_root=repo_root,
        audit_root=audit_root,
        external_manifest=external_manifest,
        archive_packet=archive_packet,
        archive_verification=archive_verification,
        equality=equality,
        retained_manifest_path=retained_manifest_path,
        retained_manifest_sha256=retained_manifest_sha256,
        delete_plan=plan,
        mutations=mutations,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prune raw audit_results after a verified external archive."
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
        help="Verified external archive root.",
    )
    parser.add_argument(
        "--archive-packet",
        type=Path,
        required=True,
        help="Verified K4B archive packet JSON.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="mode", action="store_const", const="dry_run")
    mode.add_argument("--apply", dest="mode", action="store_const", const="apply")
    parser.set_defaults(mode="dry_run")
    parser.add_argument(
        "--retained-manifest-name",
        default=RETAINED_MANIFEST_FILENAME,
        help="Filename to keep under audit_results after pruning.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for command-surface clarity. Output is always JSON.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = (args.root or manifest_builder.discover_repo_root()).resolve()
        packet = run_prune(
            repo_root=repo_root,
            audit_root=args.audit_root,
            external_root=_resolve_path(args.external_root),
            archive_packet_path=_resolve_path(args.archive_packet),
            mode=args.mode,
            retained_manifest_name=args.retained_manifest_name,
        )
        sys.stdout.buffer.write(_packet_bytes(packet) + b"\n")
        return 0
    except RetentionPruneError as error:
        sys.stdout.buffer.write(_packet_bytes(blocked_packet(mode=args.mode, code=error.code)) + b"\n")
        return 1
    except Exception:
        sys.stdout.buffer.write(
            _packet_bytes(blocked_packet(mode=args.mode, code="unexpected_failure")) + b"\n"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

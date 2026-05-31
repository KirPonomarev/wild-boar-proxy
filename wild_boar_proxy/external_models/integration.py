"""Installer/package integration helpers for external-models managed artifacts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from . import contracts
from .paths import ExternalModelsPaths
from .routes import load_routes_file, write_routes_file
from .state import atomic_write_json, load_state_file, write_state_file


LEGACY_EXTERNAL_MODELS_DIRNAME = "external-models"


def installer_managed_paths(paths: ExternalModelsPaths) -> list[Path]:
    return [
        paths.root_dir,
        paths.routes_file,
        paths.state_file,
        paths.secrets_file,
        paths.evidence_dir,
        paths.routes_lock,
        paths.state_lock,
    ]


def _write_secrets_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)
    os.chmod(path, 0o600)


def ensure_installed_layout(paths: ExternalModelsPaths) -> None:
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.evidence_dir.mkdir(parents=True, exist_ok=True)
    if not paths.routes_file.exists():
        atomic_write_json(paths.routes_file, contracts.default_routes_payload())
    if not paths.state_file.exists():
        atomic_write_json(paths.state_file, contracts.default_state_payload())
    if not paths.secrets_file.exists():
        _write_secrets_file(paths.secrets_file, "")
    else:
        os.chmod(paths.secrets_file, 0o600)


def import_legacy_layout(
    source_dir: Path, destination_paths: ExternalModelsPaths
) -> dict[str, Any]:
    source_root = source_dir / LEGACY_EXTERNAL_MODELS_DIRNAME
    if not source_root.exists() or not source_root.is_dir():
        return {
            "status": "not_applicable",
            "final_outcome": "external_models_source_missing",
            "imported_files": [],
        }

    source_paths = ExternalModelsPaths.from_root(source_root)
    imported_files: list[str] = []
    destination_paths.root_dir.mkdir(parents=True, exist_ok=True)
    destination_paths.evidence_dir.mkdir(parents=True, exist_ok=True)

    if source_paths.routes_file.exists():
        write_routes_file(
            destination_paths.routes_file,
            load_routes_file(source_paths.routes_file),
        )
        imported_files.append(str(destination_paths.routes_file))

    if source_paths.state_file.exists():
        write_state_file(
            destination_paths.state_file,
            load_state_file(source_paths.state_file),
        )
        imported_files.append(str(destination_paths.state_file))

    if source_paths.secrets_file.exists():
        _write_secrets_file(
            destination_paths.secrets_file,
            source_paths.secrets_file.read_text(encoding="utf-8"),
        )
        imported_files.append(str(destination_paths.secrets_file))

    if not imported_files:
        return {
            "status": "not_applicable",
            "final_outcome": "external_models_source_incompatible_or_empty",
            "imported_files": [],
        }

    return {
        "status": "imported",
        "final_outcome": "external_models_import_completed",
        "imported_files": imported_files,
    }


def clear_managed_state(
    paths: ExternalModelsPaths, *, preserve_secrets: bool = True
) -> None:
    for candidate in (
        paths.routes_file,
        paths.state_file,
        paths.routes_lock,
        paths.state_lock,
    ):
        if candidate.exists():
            candidate.unlink()
    if paths.evidence_dir.exists() and paths.evidence_dir.is_dir():
        shutil.rmtree(paths.evidence_dir)
    if not preserve_secrets and paths.secrets_file.exists():
        paths.secrets_file.unlink()
    if paths.root_dir.exists() and paths.root_dir.is_dir():
        try:
            next(paths.root_dir.iterdir())
        except StopIteration:
            paths.root_dir.rmdir()

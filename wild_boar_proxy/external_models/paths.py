"""Filesystem paths for the external-models C1 foundation slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _resolve_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


def _default_root_dir() -> Path:
    explicit_root = os.environ.get("WBP_EXTERNAL_MODELS_DIR")
    if explicit_root:
        return _resolve_path(explicit_root)
    managed_dir = os.environ.get("WBP_MANAGED_DIR")
    if managed_dir:
        return _resolve_path(str(Path(managed_dir) / "external-models"))
    return _resolve_path("~/.wild-boar-proxy/external-models")


@dataclass(frozen=True)
class ExternalModelsPaths:
    root_dir: Path
    routes_file: Path
    state_file: Path
    secrets_file: Path
    evidence_dir: Path
    routes_lock: Path
    state_lock: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "ExternalModelsPaths":
        resolved_root = _resolve_path(str(root_dir))
        return cls(
            root_dir=resolved_root,
            routes_file=_resolve_path(str(resolved_root / "routes.json")),
            state_file=_resolve_path(str(resolved_root / "state.json")),
            secrets_file=_resolve_path(str(resolved_root / "secrets.env")),
            evidence_dir=_resolve_path(str(resolved_root / "evidence")),
            routes_lock=_resolve_path(str(resolved_root / "routes.lock")),
            state_lock=_resolve_path(str(resolved_root / "state.lock")),
        )

    @classmethod
    def from_env(cls) -> "ExternalModelsPaths":
        root_dir = _default_root_dir()
        return cls(
            root_dir=root_dir,
            routes_file=_resolve_path(
                os.environ.get(
                    "WBP_EXTERNAL_MODELS_ROUTES", str(root_dir / "routes.json")
                )
            ),
            state_file=_resolve_path(
                os.environ.get("WBP_EXTERNAL_MODELS_STATE", str(root_dir / "state.json"))
            ),
            secrets_file=_resolve_path(
                os.environ.get(
                    "WBP_EXTERNAL_MODELS_SECRETS", str(root_dir / "secrets.env")
                )
            ),
            evidence_dir=_resolve_path(
                os.environ.get(
                    "WBP_EXTERNAL_MODELS_EVIDENCE", str(root_dir / "evidence")
                )
            ),
            routes_lock=_resolve_path(
                os.environ.get(
                    "WBP_EXTERNAL_MODELS_ROUTES_LOCK", str(root_dir / "routes.lock")
                )
            ),
            state_lock=_resolve_path(
                os.environ.get(
                    "WBP_EXTERNAL_MODELS_STATE_LOCK", str(root_dir / "state.lock")
                )
            ),
        )

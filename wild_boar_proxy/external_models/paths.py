"""Filesystem paths for the external-models C1 foundation slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _resolve_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


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
    def from_env(cls) -> "ExternalModelsPaths":
        root_dir = _resolve_path(
            os.environ.get(
                "WBP_EXTERNAL_MODELS_DIR", "~/.wild-boar-proxy/external-models"
            )
        )
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

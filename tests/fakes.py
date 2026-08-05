# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test-owned fakes for the one-shot CLI runtime (R5 separation).

The fake executable/manifest implementation lives ONLY under tests/.
Production code never imports this module, never reads environment hooks,
and never receives a test runtime through a global. Tests construct
explicit `OneShotRuntime` instances here and pass them by parameter.
"""

from __future__ import annotations

import json
from pathlib import Path

from wild_boar_proxy.one_shot_cli_runtime import (
    OneShotRuntime,
    OneShotToolManifestEntry,
)


def load_manifest_entries(path) -> tuple[OneShotToolManifestEntry, ...]:
    """Load fake manifest entries from a JSON file (server_owned=False)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = []
    for item in data.get("tools", []):
        entries.append(
            OneShotToolManifestEntry(
                tool_id=str(item["tool_id"]),
                binary_name=str(item["binary_name"]),
                display_name=str(item.get("display_name", item["tool_id"])),
                version_args=tuple(str(a) for a in item.get("version_args", ("--version",))),
                output_profiles=tuple(str(p) for p in item.get("output_profiles", ("text",))),
                server_owned=False,
            )
        )
    return tuple(entries)


def write_fake_cli(root: Path, name: str, body: str) -> Path:
    """Write an executable fake CLI script under the test-owned root."""
    script = Path(root) / name
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def write_manifest(root: Path, tools: list[dict]) -> Path:
    """Write a fake manifest JSON file under the test-owned root."""
    manifest = Path(root) / "fake-manifest.json"
    manifest.write_text(json.dumps({"tools": tools}), encoding="utf-8")
    return manifest


def make_test_runtime(
    homes_root: Path,
    entries: tuple[OneShotToolManifestEntry, ...],
) -> OneShotRuntime:
    """The test runtime: an explicitly constructed engine instance.

    This is the only sanctioned way tests exercise spawn/probe paths; the
    production facade is never involved and stays fail-closed.
    """
    return OneShotRuntime(homes_root=Path(homes_root), manifest=entries)

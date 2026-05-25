# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--sleep-seconds", type=float, default=3.0)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from wild_boar_proxy.native_filesystem_probe import (
        json_write,
        run_idle_baseline_window,
        summarize_idle_baseline_windows,
        utc_now,
    )

    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    window_1 = run_idle_baseline_window(sleep_seconds=args.sleep_seconds)
    window_2 = run_idle_baseline_window(sleep_seconds=args.sleep_seconds)
    summary = summarize_idle_baseline_windows([window_1, window_2])
    comparison = {
        "captured_at_utc": utc_now(),
        "window_count": 2,
        "window_1_changed_surfaces": summary.get("window_changed_surfaces", [None, None])[0],
        "window_2_changed_surfaces": summary.get("window_changed_surfaces", [None, None])[1],
        "repeated_surface_drift": summary.get("repeated_surface_drift"),
        "repeated_path_drift": summary.get("repeated_path_drift"),
        "drift_repeatability": summary.get("drift_repeatability"),
    }

    json_write(evidence_dir / "current_codex_idle_window_1_packet.json", window_1)
    json_write(evidence_dir / "current_codex_idle_window_2_packet.json", window_2)
    json_write(evidence_dir / "idle_protected_surface_window_comparison.json", comparison)
    json_write(evidence_dir / "current_codex_baseline_stability_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

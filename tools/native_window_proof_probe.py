#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run the bounded native window proof runner surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_window_probe import run_native_window_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-window-proof-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--owner-authorization-phrase", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    packet = run_native_window_probe(
        repo_root=Path(args.repo_root).resolve(),
        evidence_dir=Path(args.evidence_dir).resolve(),
        endpoint=args.endpoint,
        model=args.model,
        owner_authorization_phrase=args.owner_authorization_phrase,
    )
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

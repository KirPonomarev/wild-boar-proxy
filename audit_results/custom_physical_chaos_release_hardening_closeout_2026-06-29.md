<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Physical Chaos Release Hardening Closeout

## Goal

Harden the real Custom Codex release gate against false green launch,
visible-output, repo-bridge, provider, and scratch-code cleanup results found
by physical chaos runs.

## Result

- status: implemented and verified
- final verdict: Custom physical chaos checks exposed false-green surfaces; the
  launcher dispatch packet, visible-output observer, repo-bridge scratch
  mutation parser, mixed create/delete cleanup path, and targeted regression
  coverage now fail closed or require fresh evidence
- closure state: CLOSED

## Contour Capsule

- goal: Custom physical chaos release hardening
- branch: `codex/stabilize-runtime-core`
- head: `3664250a` before contour commit
- touched files: `wild_boar_proxy/runtime.py`, `wild_boar_proxy/wbp_dip_tool.py`, `wild_boar_proxy/custom_codex_physical_observer.py`, `tests/test_cli.py`, `tests/test_wbp_dip_tool.py`, `tests/test_custom_codex_physical_observer.py`, `audit_results/custom_physical_chaos_release_hardening_closeout_2026-06-29.md`
- tests run: `python3 -m pytest tests/test_wbp_dip_tool.py tests/test_custom_codex_physical_observer.py -q`; `python3 -m pytest tests/test_cli.py -q`; `make test-core`; `python3 -m compileall wild_boar_proxy tests`; `python3 -m wild_boar_proxy healthcheck --json`; `python3 -m pytest -q`
- blocked risks: repo-managed launcher exit-code false green, stale visible expected-token proof, Russian file-write text overcapture, scratch-code delete not treated as full-flow mutation, mixed create/readback/delete cleanup exact-answer false green, provider auth/malformed response fail-open risk
- closure state: CLOSED

## Verification

- tests:
  - `python3 -m pytest tests/test_wbp_dip_tool.py tests/test_custom_codex_physical_observer.py -q` -> `142 passed, 2 subtests passed in 5.49s`
  - `python3 -m pytest tests/test_cli.py -q` -> `509 passed, 1 skipped, 123 subtests passed in 275.72s (0:04:35)`
  - `make test-core` -> `456 passed, 125 subtests passed in 58.92s`
  - `python3 -m pytest -q` -> `4329 passed, 1 skipped, 971 subtests passed in 1392.78s (0:23:12)`
- build:
  - `python3 -m compileall wild_boar_proxy tests` -> green
- manual:
  - `git diff --check -- wild_boar_proxy/runtime.py wild_boar_proxy/wbp_dip_tool.py wild_boar_proxy/custom_codex_physical_observer.py tests/test_cli.py tests/test_wbp_dip_tool.py tests/test_custom_codex_physical_observer.py` -> clean
  - `python3 -m wild_boar_proxy launch client --client-path ... --json` -> `dispatch_method=wbp_desktop_launcher`, `dispatch_observed=true`, `process_observed_running=false`, `real_codex_app_launched=false`, `launch_claim_scope=os_dispatch_only`
  - independent disk check after physical scratch mixed cleanup -> `tmp/wbp-scratch-code` absent
- live verification:
  - physical Custom alias/natural-language matrix passed from `/tmp/wbp-chaos-evidence/physical-alias-natural-language-matrix-20260629T1441/summary.json`
  - physical Custom scratch-code create proof passed from `/tmp/wbp-chaos-evidence/physical-ultrahard-scratch-code-20260629T144605/packet.json`
  - physical Custom scratch tree cleanup after fix passed from `/tmp/wbp-chaos-evidence/physical-ultrahard-scratch-tree-cleanup-after-fix-20260629T145149/packet.json`
  - physical Custom mixed scratch create/readback/delete cleanup after fix passed from `/tmp/wbp-chaos-evidence/physical-scratch-delete-fullflow-after-mixed-fix-20260629T150903/packet.json`
  - provider failure/recovery no-write chaos passed from `/tmp/wbp-chaos-evidence/provider-failure-recovery-20260629T1439/summary.json`
  - DeepSeek live-format route levels passed from `/tmp/wbp-chaos-evidence/deepseek-levels-live-format-20260629T1440/summary.json`

## Artifacts

- spec:
  - no separate spec artifact was created for this bounded release hardening contour
- packet:
  - `/tmp/wbp-chaos-evidence/physical-scratch-delete-fullflow-after-mixed-fix-20260629T150903/packet.json`
  - `/tmp/wbp-chaos-evidence/provider-failure-recovery-20260629T1439/summary.json`
  - `/tmp/wbp-chaos-evidence/deepseek-levels-live-format-20260629T1440/summary.json`
- report:
  - independent code inspector reported two release blockers; both were fixed and covered by regression tests
  - independent evidence inspector found one stale-token historical packet; it is superseded by fresh packets with `observed_count_delta=2`

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- live-path mutation performed: yes, bounded to Custom UI prompts and `tmp/wbp-scratch-code`, with cleanup verified
- product safety weakened: no
- provider secrets exposed: no

## Notes

- blockers encountered: physical chaos exposed stale visible-token proof,
  repo-managed launcher process-observation overclaim, scratch cleanup prompt
  echo-only, and mixed create/delete exact-answer false green; each blocker has
  a regression test and a passing physical or packet evidence artifact
- resume from here: CLOSED

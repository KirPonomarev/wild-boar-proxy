<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B00 Baseline Admission Repair Closeout

## Goal

Close the reproduced B00 baseline false-green findings at base head
`b4a9de07fe0d92b12f200a3f78a884c3b7377999` so the multi-actor plan is admitted
on a verified baseline: empty required-step sets must never be accepted,
one SHA must never stand for multiple independent milestones, tests must not
touch protected ports, and the acceptance gate must have negative coverage
for fully missing required packets.

## Result

- status: implemented and verified
- final verdict: all three reproduced findings (F1 empty-step acceptance,
  F2 milestone SHA collision, F3 protected-port test usage) are repaired with
  regression tests; remaining candidate findings classified
  `NOT_REPRODUCED_ALREADY_CONTAINED` with evidence; full local and CI baseline
  gates green
- closure state: CLOSED

## Contour Capsule

- goal: B00 baseline admission repair (empty-step false-green, milestone SHA
  distinctness, protected-port test cleanup, missing-packet negative coverage)
- branch: `codex/b00-baseline-repair`
- head: `b4a9de07fe0d92b12f200a3f78a884c3b7377999` (base before contour commit)
- touched files: `wild_boar_proxy/release_e2e_contract.py`,
  `wild_boar_proxy/desktop_pilot_contract.py`,
  `tests/test_release_e2e_contract.py`, `tests/test_desktop_pilot_contract.py`,
  `tests/test_cli.py`, `tests/test_web_ui.py`,
  `tests/test_web_design_live_server.py`, `tests/test_runtime_atomic_write.py`,
  `tests/test_invariant_false_green.py`, `tests/test_ui_shell.py`,
  `tests/test_healthcheck_probe_repair_contract.py`,
  `tests/test_app_server_bridge_research_classification_r1_probe.py`,
  `tests/test_gpt_api_dip_acceptance_gate.py`,
  `audit_results/B00_BASELINE_ADMISSION_SPEC_2026-08-03.md`,
  `audit_results/B00_baseline_admission_repair_closeout_2026-08-03.md`
- tests run: repro tests failed before fix and passed after; focused files;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make package-web-smoke`; `make test-full`
- blocked risks: `all([])` false-green in release E2E and desktop pilot
  receipts, milestone identity collision, protected-port probe/bind risk in
  tests, missing-packet acceptance-gate gap
- closure state: CLOSED

## Verification

- tests:
  - reproduction: 3 new repro tests failed on base head
    (`RELEASE_E2E_EMPTY_STEP_SET`, `DESKTOP_PILOT_EMPTY_STEP_SET`,
    `FINAL_ASSURANCE_SHA_COLLISION` cases), then passed after the fix
  - focused: `tests/test_release_e2e_contract.py` +
    `tests/test_desktop_pilot_contract.py` -> `19 passed`
  - proxy/reprobe slice `tests/test_cli.py -k "proxy or reprobe"` -> `30 passed`
  - full `tests/test_cli.py` -> `521 passed, 125 subtests passed`
  - port-affected files (`test_web_ui`, `test_ui_shell`,
    `test_runtime_atomic_write`, `test_invariant_false_green`,
    `test_healthcheck_probe_repair_contract`,
    `test_app_server_bridge_research_classification_r1_probe`) -> `190 passed`
  - `tests/test_gpt_api_dip_acceptance_gate.py` -> `11 passed`
  - `make check` -> green; `make test-core` -> green; `make test-custom-stability`
    -> green; `make test-web-e2e` -> green; `make package-web-smoke` -> green
  - `make test-full` -> full local baseline green
- build:
  - `make check` (compileall + collect) green
- manual:
  - `git diff --check` clean; protected-port scan of `tests/` clean (only four
    assertion lines document the production
    `LEGACY_PROXY_REPROBE_DEFAULT_CANDIDATES` list as product data; no test
    binds, probes, or uses `10808`/`12334` as resources)
- live verification:
  - no live mutation performed; synthetic contract level only

## Artifacts

- spec: `audit_results/B00_BASELINE_ADMISSION_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: B00 candidate-finding audit (empty-step, milestone identity,
  fixed-resource ports, synthetic/live separation, web action-phase, updater
  safety, provider catalog) recorded in this closeout

## Git

- branch: `codex/b00-baseline-repair`
- commit: contour commit contains code, tests, spec, and this closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no secrets touched; state tooling is
  external-only)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: three baseline findings reproduced and repaired;
  two candidate findings classified `NOT_REPRODUCED_ALREADY_CONTAINED` with
  evidence: (1) evidence-level taxonomy naming (plan `LIVE_PROVEN` /
  `PHYSICAL_VISIBLE_PROVEN` vs code `PHYSICAL_PROVEN`/`INCOMPLETE`) — synthetic
  and live statuses are already kept separate with no false-green; taxonomy
  normalization is owned by B03 (normalized transport and evidence state
  machine); (2) provider catalog staging — Qwen is intentionally excluded in
  `provider_capability_schema_v2.py` until B08 adds the Qwen API actor;
  OpenRouter is a compatibility/admission surface; documentation alignment is
  carried into the B07 contract contour. Production legacy local-proxy
  candidate discovery (`LEGACY_PROXY_REPROBE_DEFAULT_CANDIDATES`) remains
  unchanged as a product surface.
- resume from here: CLOSED

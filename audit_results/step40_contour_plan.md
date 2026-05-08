<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step40 Contour Plan

```text
CONTOUR:
Goal:
Execute exactly one canonically authorized `sync --json` write step and then
measure, on owner surfaces only, whether the runtime-truth lane actually
reclears. If truth does not reclear after that one sync, close `NO_GO`
immediately.

Size: M
Risk level: high
Decision owner: operator + maintainer, with disputed decisions resolved strictly
through canon order
Mode: live-proof

Execution identity:
- this remains `step40`
- `step40_precondition_gate.md` recorded a prior stop at phase 1 only
- that prior stop did not consume the write lane
- after explicit owner authorization appears, `step40` reopens under the same
  contour identity rather than creating a new contour id

Canon order:
1. CANON.md
2. MASTER_PLAN.md
3. RUNTIME_CONTRACT.md
4. STATE_SCHEMA.md
5. COMMAND_API.md
6. DELIVERY_RULES.md
7. README.md

Precondition:
- the active thread must contain explicit owner authorization for this live
  write contour
- accepted owner markers:
  - project-scoped standing approval phrase from CANON.md
  - or an explicit one-off owner authorization for
    `python3 -m wild_boar_proxy sync --json`
- without that authorization this contour does not open
- if precondition fails again, close the reopen attempt as the same `step40`
  contour family rather than inventing a new contour id

In scope:
- owner-authorization check
- live operation declaration
- exactly one `python3 -m wild_boar_proxy sync --json`
- exactly one rerun of canonical owner surfaces after sync:
  - `status --json`
  - `healthcheck --json`
  - `accounts list --json`
  - `rollout rotation inspect --json`
- factual go/no-go decision for posture-normalization readiness

Out of scope:
- a second `sync --json`
- `launch smoke --json` by default
- accounts promote/demote/hold/release/retire
- policy stage set
- rollout stage advance 20
- repo repair
- engine-layer work
- manual state or registry edits
- UI work

Assumptions:
- step39 is canonical and closed `NO_GO`
- step39 proved both:
  - stale rotation evidence does not reclear on read-only surfaces
  - `sync --json` is required if stale rotation evidence is to be refreshed
- step39 also proved `sync --json` was not authorized in the previous active
  thread state
- the purpose of step40 is not to "fix everything", but to run one bounded
  refresh probe and measure truth afterward

Inputs:
- docs:
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
  - NEXT_CONTOUR_CANON_PLAN.md
  - audit_results/step39_operation_declaration.md
  - audit_results/step39_owner_surface_capture.json
  - audit_results/step39_decision_packet.json
- code:
  - wild_boar_proxy/runtime.py
  - tests/test_cli.py
- runtime evidence:
  - fresh `git status --short --branch`
  - fresh `sync --json`
  - fresh `status --json`
  - fresh `healthcheck --json`
  - fresh `accounts list --json`
  - fresh `rollout rotation inspect --json`

Live operation declaration:
- exact command:
  - `python3 -m wild_boar_proxy sync --json`
- exact real read paths:
  - `/Users/kirillponomarev/.codex-custom-cli/managed/`
  - `/Users/kirillponomarev/.cli-proxy-api/`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- exact real write paths that may be touched by `sync --json` under current
  command contract:
  - `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`
- rollback expectation:
  - no manual file rollback in this contour
  - if sync fails, or truth remains blocked after the one allowed sync, close
    `NO_GO` immediately
  - if the sync packet reports `changed_files` outside the declared write set,
    close `NO_GO` and escalate as contract drift

Allowed execution shape:
phase 1 = verify owner authorization is present in the active thread
phase 2 = record live operation declaration
phase 3 = run exactly one `sync --json`
phase 4 = run exactly one rerun of canonical read surfaces
phase 5 = close with factual verdict

No second sync is allowed in this contour.
No launch smoke is allowed by default in this contour.
No posture normalization is allowed in this contour.

Commands / files:
- git status --short --branch
- python3 -m wild_boar_proxy sync --json
- python3 -m wild_boar_proxy status --json
- python3 -m wild_boar_proxy healthcheck --json
- python3 -m wild_boar_proxy accounts list --json
- python3 -m wild_boar_proxy rollout rotation inspect --json

Truth ownership rules:
- claim_gate owner truth = status --json
- policy_drift owner truth = status --json
- runtime attestation and launch_readiness owner truth = healthcheck --json
- rotation freshness and participation owner truth = rollout rotation inspect --json
- changed-files truth for the write step = sync --json packet
- narrative summaries, memory, and stale prior packets do not override current
  owner surfaces

Acceptance criteria:
- owner authorization is explicit in the active thread before sync executes
- `sync --json` returns strict JSON
- no more than one sync write step is executed
- `rollout rotation inspect --json` no longer returns
  `ROTATION_EVIDENCE_STALE`
- `status --json` no longer reports `claim_gate.status=blocked`
- `status --json` no longer reports `policy_drift.status=detected`
- `healthcheck --json` remains `launch_readiness.status=ready`
- the contour closes with a factual packet and explicit next action

Verification:
- tests:
  - none required for the default live reclear path
  - if contour scope unexpectedly touches repo code, STOP_AND_DIAGNOSE and open a
    separate repo contour
- build:
  - not applicable by default
- manual:
  - compare pre-step39 owner-surface blockers with post-sync owner surfaces
- live packet:
  - sync --json
  - status --json
  - healthcheck --json
  - accounts list --json
  - rollout rotation inspect --json

Artifacts:
- spec:
  - audit_results/step40_contour_plan.md
- packet:
  - audit_results/step40_operation_declaration.md
  - audit_results/step40_sync_packet.json
  - audit_results/step40_owner_surface_capture.json
  - audit_results/step40_decision_packet.json
- closeout note:
  - audit_results/step40_closeout_report.md

Stop conditions:
- owner authorization not explicit in the active thread
- any invalid JSON packet
- `sync --json` fails
- `sync --json` reports `changed_files` outside the declared write set
- rotation evidence remains stale after the one allowed sync
- claim_gate remains blocked after the one allowed sync
- policy_drift remains detected after the one allowed sync
- healthcheck --json stops being green enough
- any need for a second sync
- any need for manual file edits
- any signal that repo repair is required to complete reclear

Closeout:
- verification complete:
  - owner authorization confirmed
  - live operation declaration recorded
  - one sync packet captured
  - one rerun of owner surfaces captured
- commit:
  - docs/artifact-only if repo files changed
- push:
  - required for any closed write contour
- next contour:
  - GO_POSTURE_NORMALIZATION if truth lane is green again
  - NO_GO_RUNTIME_RECLEAR_FAILED if truth lane remains blocked
  - ENGINE_BLOCKER_ESCALATION_REQUIRED if owner surfaces cannot restore truthful
    state after the one allowed sync
```

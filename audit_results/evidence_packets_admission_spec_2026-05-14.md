<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Evidence Packets Admission Spec

## Contour

`EVIDENCE_PACKETS_ADMISSION`

## Goal

Decide whether a dedicated Evidence Packets surface may be admitted into the
web design UI, and define the narrowest truthful product contract.

## Final verdict

`EVIDENCE_PACKETS_DEFERRED_PENDING_STRICTER_PACKET`

## Why this verdict

The repo already contains evidence-adjacent surfaces, but they do not add up to
a canon-safe dedicated Evidence Packets screen yet.

What already exists today:

- route-level local support artifact capture via `api_route_evidence_capture`
- diagnostics bundle export metadata via `diagnostics export --json`
- canonical rollout evidence owner packet via
  `rollout evidence capture 16 --json`

What does not exist yet:

- a bounded packet-owned evidence index
- a unified readonly evidence-screen contract across evidence families
- a server-owned browser-safe selector for evidence packets
- full elimination of path-shaped evidence metadata from current web design
  live-server shaping

So the contour does not end in “no evidence metadata may appear anywhere”.
It ends in a narrower conclusion:

- existing support metadata snippets remain allowed where already admitted
- a dedicated Evidence Packets screen remains deferred pending a stricter
  packet/index contract

## Canon anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI / strict JSON command packets remain truth owners.
- UI is not an evidence-file reader.
- UI is not a log parser.
- UI is not a proof engine.
- browser payload remains `ui_action` plus bounded structured payload only.
- evidence packet metadata may appear only as packet-owned support detail.
- evidence packet metadata must not become route truth, runtime truth, rollout
  proof, or policy proof unless an owner packet explicitly says so.
- diagnostics export remains a redacted support artifact, not runtime health
  truth.
- live evidence capture is not exposed as a normal first-pass UI action.
- different evidence families must not be silently merged into one browser-owned
  proof model.

## Repo facts

### 1. Route evidence support metadata exists today

`web_design_command_adapter.py` already allowlists
`external_models_evidence_capture` as a support command with only `route_id`
allowed from the browser.

`web_design_live_server.py` already exposes `api_route_evidence_capture` as:

- `mutation_class=api_route_support_artifact`
- `mutates_runtime=false`
- `affects_primary_truth=false`
- `action_claim_scope=только локальный support artifact; это не runtime proof и
  не чтение evidence file из UI`

This is a real admitted support metadata surface.
But it is not yet a dedicated evidence-screen contract.

### 2. Diagnostics bundle metadata exists today

`export_diagnostics` is already admitted as a support artifact surface.
The live-server result shaping rewrites `bundle_path` to a basename for browser
display, and UI tests verify basename-only rendering.

This is support artifact metadata only.
It is not a proof/evidence screen contract.

### 3. Canonical rollout evidence owner packet exists today

`COMMAND_API.md` and `runtime.py` already define
`rollout evidence capture 16 --json` as the owner surface for the 16-account
field evidence packet lane.

But `UI_READINESS_SPEC.md` explicitly says:

- the first UI implementation must not expose it as a normal button
- live evidence capture belongs to a separate live evidence lane
- a future advanced/operator mode may reference it only after a separate
  approved contour

So canonical rollout evidence exists, but it is not currently web-admitted for a
general Evidence Packets screen.

### 4. Evidence families are not unified today

The repo currently exposes at least three distinct evidence-adjacent families:

1. route support evidence packet metadata
2. diagnostics/support bundle metadata
3. rollout field evidence packet truth

They have different owners, risk profiles, and truth semantics.
No current bounded packet unifies them into one readonly browser-safe evidence
index.

### 5. Current route evidence shaping still leaks path-shaped metadata

`tests/test_web_design_live_server.py` still expects the route evidence action
result to include a raw `/tmp/wbp-evidence/...` path in `result.data.evidence_path`.

`tests/test_web_design_ui.py` proves the browser renderer trims that down to
basename-only display via `artifactReference(...)`.

That is better than raw path display, but it is still not the same thing as a
server-owned evidence reference contract.

## Evidence-family classification

### Family A. Route support evidence packet metadata

Owner surface:

- `external-models evidence capture --route ... --json`
- web UI action `api_route_evidence_capture`

Current admitted scope:

- support artifact command result metadata
- no runtime proof claim
- no direct evidence file reading
- browser payload bounded to `route_id`

Not yet admitted:

- dedicated evidence screen built on this family
- file-content view
- file-path view
- artifact browsing or selection by browser-derived identity

### Family B. Diagnostics/support bundle metadata

Owner surface:

- `diagnostics export --json`

Current admitted scope:

- basename-only support artifact metadata
- redacted support snapshot semantics
- no runtime health truth

Not yet admitted:

- evidence screen ownership
- bundle browsing
- direct bundle reads
- proof synthesis from export success

### Family C. Rollout/runtime evidence packet truth

Owner surface:

- `rollout evidence capture 16 --json`

Current admitted scope:

- CLI/runtime owner packet only
- explicit packet status / claim scope / gate semantics

Not yet admitted:

- normal web UI action
- generic browser screen for packet selection/view
- evidence screen that mixes live capture with support metadata

## Why the dedicated screen is deferred

The design-package screen `29_evidence_packets` is larger than any one of the
already admitted metadata snippets.

The repo itself already records this dependency:

- `ui_final_screen_passports_2026-05-14.json` says the screen needs a bounded
  evidence index/packet contract
- `ui_final_next_contour_queue_2026-05-14.json` lists
  `EVIDENCE_PACKETS_ADMISSION` with dependency
  `bounded evidence packet/index contract`
- `ui_final_render_package_completeness_matrix_2026-05-14.json` marks the
  screen admission-required and forbids direct evidence/log/state file reads

That dependency is still real.
Current repo truth does not yet provide:

- a packet-owned evidence index
- family-safe packet selection semantics
- path-free route evidence shaping at the server boundary
- a unifying owner packet for the Evidence Packets screen

## Browser payload boundary

Allowed today:

- `ui_action`
- bounded `route_id` for route support evidence capture

Potentially allowed only after a future stricter contract:

- bounded evidence packet selector from a packet-owned evidence index

Forbidden:

- `command_id`
- `argv`
- `shell`
- path
- token
- secret
- raw evidence body
- raw file location
- basename or inferred file handle used as browser identity

## Copy policy

UI may say:

- evidence packet metadata
- support artifact metadata
- local capture result
- diagnostics export metadata
- stale
- historical
- operator review

UI must not say:

- proved
- verified
- runtime healthy
- rollout ready
- route ready
- failover confirmed
- evidence accepted as truth

## Admitted now vs deferred

Admitted now:

- route evidence support metadata where already implemented
- diagnostics support artifact metadata where already implemented
- rollout evidence packet truth in its owner CLI/runtime lane

Deferred:

- dedicated Evidence Packets screen
- unified evidence index
- cross-family evidence packet browser
- direct artifact reading
- proof synthesis across evidence families

## Identity preservation check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.

## Implementation gate

This contour admits no implementation.

The canon-safe result in current repo truth is:

- existing support metadata snippets stay where they already are
- the dedicated Evidence Packets screen remains deferred
- the next enabling dependency is a bounded evidence packet/index contract with
  server-owned identity and no path/file truth leakage

<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Diagnostics History Bounded Packet Admission Spec

## Contour

DIAGNOSTICS_HISTORY_BOUNDED_PACKET_ADMISSION

## Goal

Decide whether the web design UI may admit richer diagnostics detail such as
history, event feed, chart summary, signal-chain status, and account diagnostic
detail without violating the runtime/control-layer boundary.

## Mode

admission / spec-only

## Final Verdict

DIAGNOSTICS_HISTORY_DEFERRED_PENDING_NEW_BOUNDED_PACKET

The current repo truth supports diagnostics export result metadata and a
readonly current-state detail pane assembled from existing bounded JSON
surfaces.
Richer diagnostics history is a valid future product need, but live history,
event-feed, and chart surfaces cannot be truthfully admitted from current
command surfaces alone.

## Canon Anchors

- Wild Boar Proxy UI remains the control-layer renderer.
- `CLIProxyAPI` and strict JSON commands remain owner surfaces.
- The UI is not a log viewer, bundle browser, or file explorer.
- Browser payloads remain `ui_action` plus bounded structured data only.
- No direct reads of logs, bundles, runtime state files, or evidence files.
- `healthcheck --json` owns live runtime attestation truth.
- `status --json` may expose delegated summary truth but does not replace live
  attestation.
- `diagnostics export --json` is a support-artifact surface, not a runtime
  truth owner.

## Existing Repo Facts

Current relevant owner surfaces:

- `diagnostics export --json`
- `status --json`
- `healthcheck --json`
- `accounts list --json`
- `rollout rotation inspect --json`

Current UI diagnostics implementation already reflects the boundary:

- diagnostics export is shown as support-artifact metadata only
- fixture chart and fixture records are demo-only
- live history remains explicitly deferred
- live records remain explicitly deferred
- raw diagnostics text is unavailable
- artifact viewing is deferred

Key evidence:

- `COMMAND_API.md` lists `diagnostics export --json` as the diagnostics command
  surface and preserves runtime-health ownership under `healthcheck --json`
- `RUNTIME_CONTRACT.md` preserves live attestation ownership under
  `healthcheck --json` and limits `status --json` to delegated summary
- `tests/test_web_design_ui.py` asserts:
  - diagnostics is support-artifact only
  - live history requires a future bounded redacted JSON surface
  - live records do not come from log tail
  - full local paths must not leak into DOM

## Why Current Surfaces Are Insufficient

Current surfaces do not truthfully provide a bounded live packet for:

- recent event feed
- trend/chart points
- per-step signal-chain diagnostics
- live historical drilldown

`diagnostics export --json` only proves export outcome and redacted artifact
metadata. It must not be stretched into a pseudo-history surface.

`status --json`, `healthcheck --json`, and `rollout rotation inspect --json`
provide runtime and rotation truth, but not a bounded diagnostics-history model
for the target screen.

## Admitted Product Position

Admitted today:

- diagnostics export result metadata
- basename-only artifact reference
- changed-files count
- machine error code
- next-action copy
- readonly current-state diagnostics detail assembled from bounded runtime and
  evidence surfaces
- fixture/demo diagnostics visuals clearly labeled as non-live

Not admitted today:

- live chart from current command surfaces
- live event feed from current command surfaces
- log-tail rendering
- raw diagnostics bundle browsing
- raw file-path disclosure
- raw diagnostics text in browser UI
- direct runtime/state/evidence file reads

Readonly current-state detail is already admitted in principle when grounded in:

- `status --json`
- optional operator-triggered `healthcheck --json`
- bounded evidence readouts such as `rollout rotation inspect --json`

Implementation of that detail remains out of scope for this contour.

## Future Packet Admission Requirements

A future diagnostics-history packet may be admitted only through a separate
server-owned readonly JSON command surface.

Minimum contract requirements:

- readonly only
- strict JSON packet
- bounded time-window presets only
- bounded entity scope only
- explicit stale/unknown/error states
- redacted event summaries only
- no raw file paths
- no auth refs
- no secrets
- no raw stack dumps as primary UI payload
- no mutation side effects
- no replacement of `healthcheck --json` or `status --json` truth ownership

Minimum packet fields for future consideration:

- `schema_version`
- `packet_status`
- `observed_at_utc`
- `subject_scope`
- `time_window`
- `history_mode`
- `staleness`
- `chart_series_summary`
- `event_entries`
- `signal_chain_summary`
- `subject_status_summary`
- `support_guidance`
- `machine_error_code`
- `blocked_reasons`

Allowed packet semantics:

- bounded readonly diagnostic summary
- bounded historical summary points
- bounded redacted event entries
- bounded signal-chain step states if command-owned

Forbidden packet semantics:

- runtime healthy claim by implication
- stage-proof claim
- route-primary/failover claim
- provider-availability claim from history alone
- raw log replay
- arbitrary query over local logs
- arbitrary file browsing

## Browser Payload Policy For Any Future UI

Allowed:

- `ui_action`
- bounded time-window preset
- bounded subject identifier if already canonically safe
- bounded view mode preset

Forbidden:

- command id
- argv
- shell
- file path
- bundle path
- raw log text
- regex/query expression
- token or credential
- raw JSON injection

## Copy Policy

UI may say:

- recent diagnostic summary
- bounded event history
- support export result
- stale / unavailable / unknown
- waiting for a bounded live packet

UI must not say:

- runtime healthy because history looks green
- route active/primary/failover-ready from diagnostics history
- provider healthy because no recent errors are visible
- proof complete from chart alone
- recovery successful unless a command packet owns that truth

## Identity Preservation Check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.

## Implementation Gate

This contour admits no implementation.

If richer diagnostics detail is reprioritized later, the next required contour
is a dedicated bounded packet contract contour. Until then, the existing UI
must remain:

- export-result aware
- fixture/demo for history visuals
- deferred for live history and live records

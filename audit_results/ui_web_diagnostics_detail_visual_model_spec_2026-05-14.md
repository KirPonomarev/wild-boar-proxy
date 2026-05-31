<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Diagnostics Detail Visual Model And Data Gate

Contour: `UI_WEB_DIAGNOSTICS_DETAIL_VISUAL_MODEL_AND_DATA_GATE`

Date: `2026-05-14`

Mode: exploration / admission / spec-only.

## Objective

Admit a diagnostics detail visual/data model for a later implementation contour
without allowing diagnostics export, charts, latest records, or support
artifacts to become runtime truth.

## Canon Basis

- `CANON.md`: one active truth surface per topic; no false-green or stale-green.
- `MASTER_PLAN.md`: diagnostics is a control-layer support and recovery surface.
- `RUNTIME_CONTRACT.md`: final live runtime truth is owned by status and
  healthcheck command packets.
- `STATE_SCHEMA.md`: cached snapshots and history inputs do not override live
  runtime checks.
- `COMMAND_API.md`: UI and automation must consume strict JSON command packets
  and must not fall back to plain-text or log parsing.
- `DELIVERY_RULES.md`: diagnostics and evidence close contours, not narrative
  memory.

## Current Implementation Facts

- The web design diagnostics screen exists at `diagnosticsScreen`.
- `export_diagnostics` maps to the diagnostics export command surface through
  the server allowlist.
- The existing diagnostics UI renders support-artifact metadata only:
  `status`, `exit_code`, `human_message`, `machine_error_code`, `next_action`,
  changed-file count, and bundle basename metadata.
- Existing tests pin the support-artifact boundary and reject raw artifact
  reading, file inputs, direct window opening, and plain command text in the UI.
- The existing screen already includes a signal list, command-result block,
  support-chain block, packet fields, and artifact metadata block.

## Visual Baseline

- Primary baseline: the original diagnostics render package screen.
- Supplemental baseline: owner-provided high-resolution diagnostics detail
  image.
- The supplemental image is admitted as content/layout supplement only.
- The supplemental image shell is not admitted; implementation must keep the
  locked Wild Boar left-sidebar shell, current identity, operator copy, and
  spacing discipline.

## In Scope

- Region admission for:
  - signal list
  - selected object detail
  - signal status
  - command/support check chain
  - history chart slot
  - runtime summary card
  - latest records
  - recommended bounded actions
- Data-source classification for each region.
- Live vs fixture-only vs deferred distinctions.
- Next implementation contour limits.

## Out Of Scope

- Production UI implementation.
- Live chart rendering.
- New backend command surfaces.
- Direct reads of logs, state, config, evidence, or diagnostics bundle files.
- Opening diagnostics artifacts from UI.
- `runtime.py` changes.
- Live server or command adapter semantic changes.
- Desktop transfer.

## Admission Decision

`DIAGNOSTICS_DETAIL_MODEL_ADMITTED_WITH_DEFERRED_LIVE_HISTORY`

The layout/content model is admitted for later implementation, but live history,
live charts, and latest records remain deferred until a bounded redacted JSON
command surface exists.

## Data Rules

- Diagnostics export result may populate support-artifact metadata only.
- Runtime summary may be shown only as a separately labeled block sourced from
  canonical status/healthcheck command packets.
- Runtime summary must not be presented as diagnostics export output.
- Fixture chart and fixture latest-record rows are allowed in fixture/demo mode
  only.
- Live chart and live latest-record rows are deferred.
- No live data may be synthesized from raw logs, direct state/config reads,
  evidence files, diagnostics bundle contents, or stale cached snapshots.

## Recommended Actions Policy

- Recommended actions may reference only already admitted allowlisted
  `ui_action` values.
- No hidden repair is admitted.
- No new recovery, runtime mutation, arbitrary command, shell, file-path, token,
  or raw argument path is admitted in this contour.
- Risky actions require their own later contour and confirmation policy.

## Acceptance Criteria

- Every diagnostics detail region has an admission verdict.
- Live, fixture-only, deferred, and forbidden data are explicit.
- Diagnostics export remains support-artifact metadata only.
- Runtime truth remains status/healthcheck-owned.
- Runtime summary, if implemented later, is separately labeled and sourced.
- History/chart live rendering is blocked without a bounded redacted JSON
  command surface.
- Latest-records live rendering is blocked without a bounded redacted JSON
  command surface.
- No direct file/log/state/config/evidence read is admitted.
- No UI implementation occurs in this contour.
- Independent audit returns PASS or blocks the next contour.

## Verification

- `python3 -m json.tool audit_results/ui_web_diagnostics_detail_region_matrix_2026-05-14.json`
- `python3 -m json.tool audit_results/ui_web_diagnostics_detail_data_contract_2026-05-14.json`
- Scoped trace scans for forbidden reference-service strings.
- Scoped private-path scans for new artifacts.
- Scoped overclaim scans for forbidden readiness or false-health wording.
- `git diff --check`
- `python3 tools/check_closeout_resilience.py`

## Resume From Here

Create independent audit and closeout, then run final scans, commit, and push.

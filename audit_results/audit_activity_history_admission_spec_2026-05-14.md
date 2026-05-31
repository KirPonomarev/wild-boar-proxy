<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Audit Activity History Admission Spec

## Contour

`AUDIT_ACTIVITY_HISTORY_ADMISSION`

## Goal

Decide whether a dedicated Audit / Activity History surface may be admitted
into the web design UI, and define the narrowest truthful product contract.

## Final verdict

`AUDIT_ACTIVITY_HISTORY_CURRENT_SESSION_SUMMARY_ONLY_ADMITTED`

for ephemeral current-session command packet summaries.

`AUDIT_ACTIVITY_HISTORY_DEFERRED_PENDING_BOUNDED_ACTIVITY_PACKET`

for the dedicated durable Audit / Activity History screen from the final design
package.

## Why this verdict

The repo already contains a current UI-session action ledger. It is bounded,
non-persistent, derived from existing action packet results, and explicitly
labels rows as command packet outcome only.

The repo does not yet contain a durable server-owned activity JSON packet/index.
So the full Audit / Activity History screen remains deferred.

## Canon anchors

- UI consumes strict JSON command packets only.
- UI must not infer runtime truth from local files, logs, cached UI state, exit
  code alone, or narrative operator memory.
- UI must not parse logs as an API.
- `stdout` must contain exactly one JSON object.
- `stderr` may be shown as support detail but must not be parsed as truth.
- `changed_files` may be shown as audit/support signal, not as UI success
  source.
- current-session history and durable audit ledger are separate contracts.
- browser storage must not become the source of activity truth.
- durable history requires a server-owned bounded activity JSON packet/index.

## Repo facts

### 1. Current-session action summary already exists

The current web design UI has an action panel and a bounded action ledger.

`overview.js` records action result summaries from existing UI action packets:

- `ui_action`
- `action_role`
- target id if present
- packet status
- display state
- machine error code
- human message
- next action
- changed files count
- refresh status
- truth note

Rows render as `command packet outcome only`.
The empty state also says the ledger is for actions in this UI session.

### 2. Stale refresh is handled as stale, not as green truth

When a post-action refresh fails, `actionDisplayState(...)` downgrades the row
to `stale`.

The truth note explicitly warns that stale UI state must not be treated as green
runtime truth.

### 3. changed_files is count-only in the current design ledger

The current design ledger stores only `changedFilesCount`.
Tests verify that raw changed-file path identity does not appear in the ledger.

This is safe enough for current-session operator feedback.
It is not a durable audit contract.

### 4. Raw logs and plain text parsing remain forbidden

`UI_READINESS_SPEC.md` and `COMMAND_API.md` both forbid log/plain-text fallback
as machine truth.

This blocks any Activity History implementation that would reconstruct events
from raw logs, stdout/stderr text, local files, or diagnostics bundles.

### 5. Durable screen remains admission-required

The final screen matrix still marks `30_audit_activity_history` as
`admission-required`.

It records:

- no current web surfaces
- no repo surfaces
- no truth sources
- no allowed UI actions
- implementation note: activity history needs bounded JSON activity packet; raw
  logs are forbidden

That means the final design screen cannot be treated as already implemented by
the existing current-session ledger.

## Admitted now

Current-session summary only:

- action result summaries from existing UI action packets
- bounded in-memory UI-session rows
- command packet status and machine error code
- human message and next action from the packet
- refresh required / refresh failed labels
- changed files count only
- support metadata that is already admitted by the action result surface

Rules:

- rows are historical operator feedback
- rows are not durable truth
- rows do not survive as truth through browser storage
- rows do not prove current runtime/account/route/rollout state

## Deferred

Dedicated durable Audit / Activity History screen:

- cross-session history
- server-owned activity index
- paging/filtering over past activity
- durable actor/source labels
- durable activity ids
- any reconstructed event stream

This requires a future bounded activity JSON packet/index.

## Not admitted

- raw logs
- raw stdout/stderr activity parsing
- raw argv
- browser-visible command id as executable identity
- raw changed file paths
- local file/state/registry/evidence/diagnostics reads
- localStorage/sessionStorage/IndexedDB as activity truth
- browser-owned durable ledger
- proof/current-truth synthesis from historical action rows

## Browser payload boundary

Allowed now:

- `ui_action`
- already admitted bounded action args such as `account_id` or `route_id`

Allowed only after future durable packet admission:

- bounded readonly activity page/view selector

Forbidden:

- command id
- argv
- shell
- path
- log query
- regex
- raw packet fragment
- token
- secret

## Future durable packet requirements

A future durable activity packet/index must provide:

- server-owned activity id
- server-owned timestamp
- bounded activity family
- packet-owned status summary
- machine error code
- next action
- stale/historical marker
- no raw argv
- no raw stdout/stderr/log body
- no raw file paths
- no current-truth synthesis

## Copy policy

UI may say:

- command packet summary
- historical action result
- current-session activity
- operator action history
- stale
- unavailable
- refresh required
- support/audit signal

UI must not say:

- verified
- proven
- runtime healthy
- route ready
- rollout ready
- recovered
- active now
- current truth confirmed

## Identity preservation check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.

## Implementation gate

This contour admits no implementation.

The canon-safe result in current repo truth is:

- current-session command packet summaries are admitted
- durable Audit / Activity History remains deferred pending a bounded activity
  JSON packet/index

<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Human Open Support Actions Admission Spec

## Contour

HUMAN_OPEN_SUPPORT_ACTIONS_ADMISSION

## Goal

Decide whether the web design UI may admit human-open support actions for
operator inspection, and define the narrowest safe product contract.

## Mode

admission / spec-only

## Final Verdict

HUMAN_OPEN_SUPPORT_ACTIONS_DEFERRED_PENDING_REFERENCE_CONTRACT

The repo canon acknowledges support/open-file concepts and an older support-only
precedent exists in `web_ui.py`.
The current web design UI does not yet have a safe server-owned reference
contract for open actions.

Lower-risk artifact-reference opening may become admissible later through a
dedicated bounded reference contract.
Higher-risk internal files remain not admitted in this contour.

## Canon Anchors

- Wild Boar Proxy remains the managing/control layer.
- UI consumes strict JSON command surfaces only.
- Browser must not send command id, argv, shell, arbitrary path, token, file
  path, directory path, glob, or search expression.
- Open-support actions are operator support helpers only.
- Open-support actions are never primary truth surfaces.
- UI may help a human inspect artifacts, but it must not parse those files into
  runtime/account/route/rollout truth.
- No direct file read is admitted as primary truth.
- Any future open target must be resolved from a server-owned bounded reference
  already produced by an admitted command packet or allowlisted support locator.
- UI-visible labels and basenames must not be treated as resolvable paths.
- Internal files likely to be reused as de facto truth sources require a
  stronger contract than artifact-reference opening.

## Existing Repo Facts

Canonically acknowledged support-open concepts already exist:

- Open Logs
- Open State
- Open Registry
- Open Data Folder
- Open Diagnostics Bundle

Repo and canon already frame them as:

- operator support actions only
- shell/app open actions, not command API truth bindings
- not primary truth sources
- not allowed to be parsed as runtime truth

Older support-only precedent exists in `wild_boar_proxy/web_ui.py`:

- server-owned fixed targets for root dir, routes file, state file, evidence dir
- optional latest-evidence file from the last external action result
- OS-level open performed server-side
- actions rendered in a dedicated support section
- independent audit already recorded that those actions do not parse files and
  are not used as truth inputs

Current web design UI constraints are narrower:

- no `window.open` or browser-side file opening behavior
- diagnostics artifact reference is rendered as basename only
- diagnostics bundle path is sanitized to basename in web-design live-server
  result shaping
- route evidence path is still present as a raw path in current live-server
  action results, which is not yet a safe open-reference contract
- unsupported payloads like `bundle_path` or `log_path` sent from browser are
  rejected as `UI_ACTION_NOT_ALLOWED`

## Risk Split

Lower-risk candidates:

- latest diagnostics bundle reference
- latest local evidence artifact reference

Higher-risk internal files:

- state file
- registry file
- logs directory
- latest log file
- managed data folder

Forbidden in this contour:

- arbitrary path from browser
- free-form open-any-file behavior
- direct bundle member selection
- auth file locations
- secret-bearing files
- recursive directory browsing

## Why Verdict Is Deferred

The repo shows that human-open support actions are conceptually valid.
What is still missing in the web design UI is the specific bounded reference
contract that would make them safe:

- server-owned reference ids or support target ids
- path resolution fully on the server
- allowlisted target classes
- refusal on unsafe or missing targets
- no raw path disclosure back into browser UI

Without that contract, even lower-risk artifact opening should not be admitted
yet in the web design UI.

## Future Admittable Shape

If a future contour admits artifact-reference opening, the contract must be:

- reference-only
- server-owned
- allowlisted
- no browser path payload
- no raw file contents returned to the browser
- basename or label display only
- explicit support-only copy

Potential future low-risk scope:

- latest diagnostics bundle reference
- latest evidence artifact reference

Not part of that future low-risk scope by default:

- state file
- registry file
- logs
- managed data folder

## Higher-Risk Internal Files

State, registry, logs, and data-folder targets remain not admitted in this
contour because they are much more likely to be repurposed as de facto truth
inputs or to disclose private local paths.

Any later admission would require a stronger dedicated contract and likely a
different contour than artifact-reference opening.

## Browser Payload Policy For Any Future Open Action

Allowed:

- `ui_action`
- bounded support target id or server-owned reference id

Forbidden:

- command id
- argv
- shell
- absolute path
- relative path
- glob
- regex
- arbitrary filename
- bundle member path
- token
- secret

## Copy Policy

UI may say:

- open for inspection
- support artifact
- operator review
- local reference
- not used as runtime truth

UI must not say:

- verified
- proven
- runtime healthy
- route healthy
- selected route confirmed
- failover confirmed
- evidence accepted

## Privacy Boundary

Allowed only if admitted later:

- server-owned bounded references
- basename-level or label-level display
- explicit warning that opened material is for human inspection only

Forbidden:

- exposing raw private filesystem paths in browser UI
- opening auth/token-bearing files
- inferring truth from opened content
- browser-selected local path submission
- treating UI labels as resolvable filesystem locations

## Identity Preservation Check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.

## Implementation Gate

This contour admits no implementation.

The canon-safe result in current repo truth is:

- artifact-reference opening remains deferred pending a dedicated bounded
  reference contract
- higher-risk internal files remain not admitted in web phase

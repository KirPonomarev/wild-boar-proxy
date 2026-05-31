<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Route Detail Readonly Admission Spec

## Contour

API_ROUTE_DETAIL_READONLY_ADMISSION

## Goal

Decide whether a richer readonly API route detail surface may be admitted into
the web design UI, and define the narrowest truthful product contract.

## Mode

admission / spec-only

## Final Verdict

API_ROUTE_DETAIL_DEFERRED_PENDING_NEW_BOUNDED_PACKET

Current repo truth already supports safe route summary in the existing
API-connections table and separately bounded support packet actions.
It does not yet admit a dedicated readonly route-detail screen or pane, because
that surface still needs an explicit bounded packet boundary before
implementation.

## Canon Anchors

- Wild Boar Proxy remains the managing/control layer.
- `CLIProxyAPI` and the external-models adapter remain engine owners.
- UI consumes strict JSON command surfaces only.
- Browser must not send command id, argv, shell, path, token, raw route JSON,
  raw provider config, base URL mutation, endpoint mutation, or secret values.
- UI is not a route editor.
- UI is not a provider debugger.
- UI is not a source of selected-route, active-route, primary-route, or
  failover truth.
- Route detail truth must come only from route registry/readowner surfaces.
- Support profile/evidence packets may appear only as auxiliary support
  metadata.
- Support packet outcomes must not redefine route state, route readiness,
  runtime selection, provider health, or traffic ownership.
- Secret-related detail is deferred unless already exposed as a safe bounded
  field by an admitted readonly packet.

## Existing Repo Facts

Current route/readowner truth already present:

- API connections readonly list is grounded in `external-models routes list --json`
- existing table fields include route id, display name, provider, enabled state,
  status label, visual state, role label, note, and summary counts

Existing support actions already present:

- `api_route_profile`
- `api_route_evidence_capture`

Their existing guarantees are already bounded:

- both are `affects_primary_truth=false`
- both are `mutates_runtime=false`
- profile packet is not Codex config mutation and not runtime readiness
- evidence capture is local support-artifact metadata only
- UI does not read evidence file contents and shows artifact basename only

Existing route mutation/support boundaries already deferred elsewhere:

- active / selected / primary route truth is deferred
- automatic failover is deferred
- route create/update builder and secret contract are deferred

## Existing Summary Already Present

Safe readonly route summary already exists in the current API-connections table
from the existing route/readowner surface for fields that are already
packet-owned and bounded.

Admitted summary field classes:

- `route_id`
- bounded display label such as `display_name`
- provider family if already packet-owned
- bounded upstream model label if already packet-owned
- enabled/disabled registry state
- bounded registry-facing status label
- bounded note/copy already carried by the route packet

These fields are already admitted as registry/readowner summary only.
They are not runtime-selected-route truth.

## Support Metadata Already Present As Secondary Context Only

Support packet outputs may appear only as a separate secondary support block.
They do not by themselves admit a new route-detail screen.

Allowed secondary support metadata:

- profile packet availability
- profile packet bounded boolean/result fields such as:
  - `writes_external_config=false`
  - `listener_proven=false`
  - `runtime_claim_blocked=true`
  - `profile_ready=false`
- evidence packet availability
- evidence packet artifact basename metadata
- support packet machine error code / next action, scoped to the packet result

Rule:

Support packet metadata must never become the owner of route detail truth.

## Not Admitted In This Contour

The following remain not admitted or deferred:

- raw route JSON
- raw provider config
- raw transform details
- raw base URL or endpoint summary synthesized outside the existing readonly packet
- raw secret reference
- secret value/key/token material
- selected route / active route / primary route truth
- failover role or failover readiness
- traffic ownership or serving-path claims
- provider health claims inferred from support packet success
- runtime health claims inferred from route packet or support packet success
- direct file, log, or evidence reads from UI

## Verdict Detail

What already exists safely today:

- minimal readonly route summary in the current API-connections table
- secondary support packet metadata through explicit support actions

What is not admitted by this contour:

- a new dedicated route-detail pane or drawer built only by stitching together
  current surfaces
- any richer route detail that needs new packet-owned fields
- any detail surface that would broaden support packets into route/runtime truth

## Future Packet Requirement

If product later requires a richer route detail pane, a separate bounded
route-detail packet admission contour is required.

That future packet would need:

- readonly only
- strict JSON
- packet-owned fields only
- no raw secrets
- no raw file paths
- no route-editing semantics
- no selected-route or failover truth unless separately admitted

## Browser Payload Policy For Any Future Readonly Detail

Allowed:

- `ui_action`
- `route_id`
- optional bounded presentation mode such as `summary` or `support`

Forbidden:

- command id
- argv
- shell
- file path
- raw route object
- raw provider config
- secret reference
- secret value
- token/credential
- mutation payloads

## Copy Policy

UI may say:

- route registered
- route enabled / disabled
- readonly summary
- support profile packet
- local support artifact
- packet unavailable / stale / deferred
- last validate/check packet result, if clearly historical or scoped

UI must not say:

- primary route
- active route
- route currently serving traffic
- failover ready
- provider healthy because profile packet succeeded
- runtime healthy because route packet looks clean
- configuration complete
- selection confirmed
- traffic switched

## Validate/Check Rule

Validate/check results may appear only as bounded command-result context.

They must not be elevated into durable route truth.
If rendered, they must be labeled as packet-scoped, historical, or stale when
freshness is not proven.

## Secret Boundary Policy

Allowed only if already packet-owned and safe:

- redacted presence summary
- explicit non-display wording such as `configured / not shown`

Forbidden:

- raw secret reference disclosure that broadens infra detail
- revealing auth storage locations
- inferring secret health from unrelated packet success
- secret editing or selection

## Identity Preservation Check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.

## Implementation Gate

This contour admits no implementation.

The only canon-safe outcome in current repo truth is to keep the existing table
summary plus secondary support actions, and defer a separate route-detail screen
until a bounded route-detail packet admission contour exists.

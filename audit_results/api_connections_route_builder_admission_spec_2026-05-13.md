<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Route Builder Admission Spec

## Contour

API_CONNECTIONS_ROUTE_CONFIG_BUILDER_ADMISSION

## Goal

Decide whether API route create/update can be admitted into the web UI as a
bounded server-side builder, and define the contract required before any future
implementation.

## Mode

exploration / admission / spec-only

## Final Verdict

ROUTE_BUILDER_UI_NOT_ADMITTED

Route create/update remain CLI/support-only for the current web UI. A future
builder contour may be reopened only if a blocked managed operator workflow is
identified and a separate non-leaking secret reference contract is admitted.

## Why Not Admitted

- No currently blocked managed operator workflow requires route create/update
  from the web UI.
- Backend create/update require a complete route object from `--file` or
  `--stdin`.
- Authenticated routes require `auth.secret_ref` in the route object.
- Route object fields include provider, endpoint, model, compatibility, auth,
  cost class, lane role, fallback policy, and enabled registry state.
- Admitting those fields to browser-owned editing would turn the UI into a
  generic route config editor.
- A server-side builder is not enough by itself unless the secret reference
  selector and server-owned template contract are separately admitted.

## Canon Anchors

- Wild Boar Proxy remains the control layer.
- CLIProxyAPI and the external adapter own engine and route behavior.
- The UI is not a universal CLIProxy GUI.
- The UI is not a generic OAuth/config/log shell.
- Every generic UI feature must be required for managed operations.
- UI and automation consume strict JSON command packets.
- Browser payloads must remain bounded and semantic.
- Command packets are execution evidence; file paths and changed files are not
  UI truth.

## Backend Facts

Existing commands:

- `external-models routes add --json --file/--stdin`
- `external-models routes update --json --route <route_id> --file/--stdin`

Backend behavior:

- add/update require exactly one input source: `--file` or `--stdin`
- route input must parse as a JSON object
- route schema rejects missing or unexpected fields
- required fields include route identity, provider, endpoint, model,
  compatibility, auth, cost class, lane role, fallback policy, and enabled state
- `route_id` must start with `wbp-`
- update payload `route_id` must match `--route`
- remote route URLs must use the allowed secure scheme policy
- `auth` must be an object
- authenticated routes require `auth.secret_ref`
- transform and response profiles are fixed allowlist values
- successful add/update returns `changed_files` for the registry write only

## Admission Matrix Summary

- create: not admitted
- update: not admitted
- draft-only builder: not admitted
- bounded create-only builder: not admitted
- bounded create/update builder: not admitted

## Reopen Conditions

All conditions below are required before reopening builder admission:

- A concrete managed operator workflow is blocked without UI create/update.
- The workflow cannot be served by CLI/support lane, route remove, allow/disable,
  validate/check, profile packet, evidence packet, or documentation.
- A separate secret reference contract exists and is admitted.
- Browser-visible fields are bounded semantic selectors, not route object fields.
- Route templates are server-owned and versioned.
- Provider/model/endpoint/compatibility/cost/lane role options are server-owned.
- Initial enabled registry value is defined without broader system claims.
- The browser never submits raw route JSON, file contents, path, token, free-text
  secret reference, auth object, or arbitrary provider config.
- Server-side schema validation happens before execution.

## Future Builder Contract If Reopened

Allowed future browser fields may only be semantic and bounded:

- `ui_action`
- `route_template_id`
- `display_name`
- `provider_template_id`
- `model_template_id`
- `secret_ref_selector_id`, only after separate admission
- `initial_registry_enabled_flag`

Forbidden future browser fields:

- raw route JSON
- file path
- stdin payload
- free-text base URL
- free-text endpoint path
- free-text compatibility
- auth object
- token or key
- free-text secret reference
- secret value
- transform code
- arbitrary transform profile
- arbitrary provider config

## Draft-Only Decision

Draft-only is not admitted in this contour.

Reason:

- A browser-visible draft can become a bypass for a complete route object.
- A draft returned to the server as executable config would recreate the same
  boundary problem as `--stdin`.
- A safe draft design still needs server-owned templates and the secret
  reference contract, which are not admitted here.

## Secret Reference Policy

This contour does not admit any secret reference selector.

Forbidden:

- browser token input
- browser free-text secret reference
- secret inventory exposure
- secret value display
- secret file writes from UI
- bundling key setup into route create/update
- treating missing secret as a route builder UI failure

## Explicit Non-Scope

- production code changes
- route create/update implementation
- route editor form
- adapter specs for create/update
- credential entry
- secret manager
- direct route/state/secret/evidence file reads from UI
- Codex config mutation
- runtime changes
- desktop implementation

## Identity Preservation Check

No external visual pattern or generic config-editor pattern is admitted here.
The Wild Boar UI remains a managed operator control surface.

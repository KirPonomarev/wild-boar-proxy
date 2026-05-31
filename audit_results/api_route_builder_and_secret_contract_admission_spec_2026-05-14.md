<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Route Builder And Secret Contract Admission Spec

## Contour

```text
CONTOUR:
Goal:
Decide whether the web UI may admit API route create/update, route draft,
preflight preview, or secret reference selection as product functionality.

Size: S
Risk level: high
Decision owner: owner/canon
Mode: admission / spec-only

In scope:
- route add/update command shape
- current web UI action allowlist
- current route config and route builder admission history
- secret reference safety boundary
- visual draft vs product admission boundary
- next admissible contract requirements

Out of scope:
- code implementation
- visual polish
- new server route-builder implementation
- secret storage or secret manager behavior
- live provider mutation
- desktop transfer

Assumptions:
- CLI command packets remain the primary truth source.
- UI surfaces must not outrun admitted server packets.
- Existing rendered drafts are design inventory only.
- Route remove remains admitted only for disabled routes under the previous
  route-config admission contour.

Inputs:
- docs:
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
  - audit_results/api_connections_route_config_admission_spec_2026-05-13.md
  - audit_results/api_connections_route_builder_admission_spec_2026-05-13.md
  - audit_results/ui_final_forbidden_or_admission_required_screens_2026-05-14.json
- code:
  - wild_boar_proxy/cli.py
  - wild_boar_proxy/external_models/__init__.py
  - wild_boar_proxy/external_models/contracts.py
  - wild_boar_proxy/external_models/routes.py
  - wild_boar_proxy/external_models/state.py
  - wild_boar_proxy/external_models/validate.py
  - wild_boar_proxy/web_design_command_adapter.py
  - wild_boar_proxy/web_design_live_server.py
- runtime evidence:
  - not applicable; no runtime mutation in this contour

Commands / files:
- create admission spec
- create admission matrix JSON
- create independent audit JSON
- create closeout note

Acceptance criteria:
- route create/update/draft admission is decided from repo facts, not visual
  draft presence
- secret reference selector admission is decided from repo facts, not visual
  draft presence
- no browser-owned raw route JSON, provider config, command id, argv, paths, or
  secrets are admitted
- next contour requirements are concrete and bounded
- no implementation changes are made

Verification:
- tests:
  - python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json
  - python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json
  - python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_cli_external_models
- build:
  - not applicable, spec-only contour
- manual:
  - inspect parser, route helpers, web allowlist, secret boundary, prior admission artifacts
- live packet:
  - not applicable

Artifacts:
- spec: audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md
- packet: audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json
- report: audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json
- closeout note: audit_results/api_route_builder_and_secret_contract_admission_closeout_2026-05-14.md

Stop conditions:
- any evidence that web UI already admits route create/update/draft
- any evidence that browser can pass raw command ids, argv, route JSON, paths,
  provider config, or secrets
- any contradiction between previous admission artifacts and current repo facts
- any failing JSON validation, closeout resilience check, or relevant tests

Closeout:
- verification complete: required
- commit: required
- push: required
- next contour: owner-selected after admission result
```

## Evidence Summary

The backend route mutation commands are file/stdin shaped, not browser-payload
shaped. `external-models routes add` requires `--json` and exactly one of
`--file` or `--stdin`; `external-models routes update` requires `--route`,
`--json`, and exactly one of `--file` or `--stdin`
(`wild_boar_proxy/cli.py:234-248`).

The route command runner loads add/update payloads through `load_route_input`
and writes registry changes through `add_route` or `update_route`
(`wild_boar_proxy/external_models/__init__.py:145-166`). The loader requires a
JSON object (`wild_boar_proxy/external_models/routes.py:46-60`).

The canonical route schema requires a complete route object:
`schema_version`, `route_id`, `display_name`, `provider`, `base_url`,
`endpoint_path`, `upstream_model`, `compatibility`, `auth`, `cost_class`,
`lane_role`, `fallback_eligible`, and `enabled`
(`wild_boar_proxy/external_models/contracts.py:14-50`). The validator also
requires route ids prefixed with `wbp-`, remote HTTPS or local loopback HTTP
base URLs, and `auth.secret_ref` for authenticated routes
(`wild_boar_proxy/external_models/routes.py:100-164`). Update additionally
requires the payload route id to match the route id argument
(`wild_boar_proxy/external_models/routes.py:211-218`).

The current web design command adapter allowlist admits route validate, enable,
disable, remove, check, profile, and local evidence capture actions only
(`wild_boar_proxy/web_design_command_adapter.py:167-222`). The live server
route-id UI action set has the same shape and does not include create, update,
or draft (`wild_boar_proxy/web_design_live_server.py:66-75`).

The live server blocks command-id payloads and explicitly treats
`api_route_create`, `api_route_update`, and `api_route_draft` as forbidden UI
actions in tests (`tests/test_web_design_live_server.py:1634-1643`). The
readonly API connections snapshot calls only status, models, and routes list
packets, and tests assert secret references and private paths are not serialized
(`tests/test_web_design_live_server.py:402-427`).

The secret boundary is file-owned and permission-gated. `secrets.env` must have
mode `0600`, otherwise `unsafe_secret_permissions` is emitted
(`wild_boar_proxy/external_models/state.py:134-143`). Provider validation may
detect missing or invalid secret references, but the secret value is only used
server-side to build an outbound Authorization header
(`wild_boar_proxy/external_models/validate.py:39-71`).

Previous route config admission admitted only remove for disabled routes and
deferred route create/update until a bounded route builder and secret reference
contract exists
(`audit_results/api_connections_route_config_admission_spec_2026-05-13.md:21-26`,
`:126-147`). The previous builder admission explicitly concluded
`ROUTE_BUILDER_UI_NOT_ADMITTED`
(`audit_results/api_connections_route_builder_admission_spec_2026-05-13.md:20-27`).
The final screen inventory marks the route builder draft and secret selector as
admission-required, not product-admitted screens
(`audit_results/ui_final_forbidden_or_admission_required_screens_2026-05-14.json:92-166`).

## Admission Decision

Final verdict:

```text
API_ROUTE_BUILDER_AND_SECRET_CONTRACT_NOT_ADMITTED
```

The route builder draft is not admitted as product UI. The current backend has
route add/update commands, but their shape is not safe for direct browser
admission because they accept complete route objects through file/stdin. A
browser UI must not become a generic route JSON editor or provider config
editor.

Route create/update are not admitted, including preflight-only variants. Even a
preview/preflight screen would still need a bounded server-owned route template
packet, option allowlists, validation semantics, and a privacy-safe secret
reference contract before the UI can collect inputs.

The secret reference selector is not admitted. The current repo supports
server-side secret reference validation and secret-file permission checks, but
there is no admitted browser-safe packet for listing, selecting, or displaying
secret references. Secret values, token entry, secret file paths, and secret
manager behavior remain forbidden.

Existing route remove admission is unchanged: remove remains allowed only under
the already-admitted disabled-route cleanup contract.

## Required Future Contract

Reopen route create/update only after a new server packet exists with these
minimum properties:

- browser sends only `ui_action` plus bounded scalar template inputs
- server owns route object construction
- server owns route id generation or validates a narrow id label
- server owns provider/model/compatibility/cost/lane option allowlists
- server owns base URL and endpoint path policies
- browser never sends raw route JSON, raw provider config, raw auth object,
  command id, argv, shell, paths, file contents, or transform code
- response returns a sanitized draft summary, validation status, and next action
  only

Reopen secret reference selection only after a safe reference packet exists with
these minimum properties:

- browser never sees secret values
- browser never sees secret file paths
- browser never writes or edits secret files
- browser never accepts token/API-key input
- server returns opaque reference handles or status-only descriptors
- missing/invalid/unsafe secret states are represented as status, not as leaked
  raw identifiers unless explicitly admitted by a later contract

Until those packets exist and are admitted, route builder and secret selector
screens may remain design inventory/passport entries only.

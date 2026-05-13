<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Route Config Admission Spec

## Contour

API_CONNECTIONS_ROUTE_CONFIG_ADMISSION

## Goal

Decide whether API route create, update, and remove may be admitted into the web
design UI, and define the safest product contract for any future UI work.

## Mode

exploration / admission / spec-only

## Final Verdict

ROUTE_CONFIG_UI_REMOVE_ONLY_ADMITTED

Route remove is admitted only as a future narrow UI action for an already
disabled route. Route create and route update remain deferred until a separate
bounded route builder and secret reference contract exists.

## Canon Anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI and the external adapter own route behavior.
- The UI is not a generic config editor.
- The browser may consume and submit only strict JSON command surfaces.
- The browser must not send command ids, argv, shell, file paths, raw route
  objects, raw provider config, transform code, credentials, or secret values.
- Route registry mutation must serve managed operations, not UI convenience.
- Command packets are the only acceptable execution evidence for UI actions.

## Backend Facts

Existing route mutation commands:

- `external-models routes add --json --file/--stdin`
- `external-models routes update --json --route <route_id> --file/--stdin`
- `external-models routes remove --json --route <route_id>`

Observed backend behavior:

- add and update load a full route object from `--file` or `--stdin`
- add and update validate route schema before writing registry data
- route ids must use the `wbp-` prefix
- remote route URLs must use `https://`
- authenticated routes require `auth.secret_ref`
- remove requires the route to exist
- remove requires `route.enabled=false`
- remove writes registry data and may also remove observed route state
- remove returns a canonical command packet with `changed_files`

Code references:

- `wild_boar_proxy/cli.py`
- `wild_boar_proxy/external_models/__init__.py`
- `wild_boar_proxy/external_models/routes.py`

## Admitted Future Remove Contract

Future UI action name:

- `api_route_remove`

Browser payload:

- `ui_action`
- `route_id`

Forbidden browser payload:

- command id
- argv
- shell
- file path
- raw route object
- provider config
- base URL
- endpoint path
- compatibility profile
- transform profile
- credential
- secret reference
- secret value

Server preflight:

- validate `route_id` shape
- fetch route list through `external-models routes list --json`
- require route exists
- require route is disabled
- reject if route state cannot be proven from command packet data
- do not read route, state, secret, or evidence files directly from UI code

Command:

```text
external-models routes remove --json --route <route_id>
```

Confirmation:

- strong confirmation required
- confirmation must show route id
- confirmation must state that this removes a disabled registry entry
- duplicate submission must be guarded by the existing action execution policy

Allowed UI copy:

- `Удалить отключённый маршрут`
- `Удаляет запись отключённого маршрута из registry после server preflight`

Forbidden UI copy:

- any claim that a serving path changed
- any claim that provider health changed
- any claim that system state changed
- any claim that route selection changed
- any wording that suggests secret cleanup

## Deferred Create/Update Contract

Route create and route update are not admitted in this contour.

Required before future admission:

- server-side bounded route builder
- bounded provider option set
- bounded compatibility option set
- bounded cost class option set
- bounded lane role option set
- explicit base URL policy
- secret reference selector policy
- no credential entry from browser UI
- no raw provider blob
- no transform code
- no arbitrary transform profile
- schema validation before execution
- command packet `changed_files` used only as evidence, not browser truth

The browser must never pass `--file`, `--stdin`, file contents, or file paths for
route create/update.

## Secret Reference Policy

Allowed in this contour:

- classify secret reference handling
- require future create/update to use a bounded selector or server-owned policy

Not allowed:

- browser credential entry
- writing secret files from UI
- displaying secret values
- bundling key setup into route create/update
- treating missing secret as proof that route config is invalid

## Identity Preservation Check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, logo treatment, and product
identity must stay aligned with the original Wild Boar design baseline.

## Implementation Gate

This contour admits no implementation.

The next implementation contour may implement only `api_route_remove` if it
keeps the contract above intact. Any create/update work requires a new contour
for the bounded builder and secret reference contract.

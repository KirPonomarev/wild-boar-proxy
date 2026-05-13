<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Route Remove Action Gate Spec

## Contour

API_CONNECTIONS_ROUTE_REMOVE_ACTION_GATE

## Goal

Implement `api_route_remove` as a bounded web UI action for removing an already
disabled API route registry entry.

## Admission Basis

`API_CONNECTIONS_ROUTE_CONFIG_ADMISSION` closed with
`ROUTE_CONFIG_UI_REMOVE_ONLY_ADMITTED`.

## Product Meaning

`api_route_remove` is a destructive registry cleanup action. It removes only an
already disabled route entry through the existing external-models command
surface. It is not a route editor and does not admit route create/update.

## Browser Contract

Allowed browser payload:

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
- token
- secret reference
- secret value

## Server Flow

1. Validate `route_id` shape.
2. Preflight through `external-models routes list --json`.
3. Require route exists.
4. Require `enabled is False`.
5. Reject missing or non-boolean route enabled state before execution.
6. Execute `external-models routes remove --route <route_id> --json`.
7. Return the strict UI action packet.
8. Require post-action refresh through existing API Connections command surfaces.

## Implementation

- `wild_boar_proxy/web_design_command_adapter.py`
  - added `external_models_routes_remove`
  - exact argv: `external-models routes remove --route {route_id} --json`
  - structured args: `route_id` only
- `wild_boar_proxy/web_design_live_server.py`
  - added `api_route_remove` metadata and allowlist binding
  - reused route list preflight
  - added remove-specific ineligible and unproven-state blocks
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - added critical confirmation policy
  - added remove button with disabled-route gating
  - added copy limited to registry cleanup
- `wild_boar_proxy/web_design_ui/styles/overview.css`
  - visually separated destructive route action

## Explicit Non-Scope

- route create
- route update
- route editor form
- credential entry
- secret reference selection
- secret file writes
- direct route/state/secret/evidence file reads from web UI
- adapter lifecycle controls
- desktop implementation
- `runtime.py` changes

## Identity Preservation Check

The action is integrated into the existing API Connections table and confirmation
system. It adds only a restrained destructive affordance and preserves the
current Wild Boar operator UI language.

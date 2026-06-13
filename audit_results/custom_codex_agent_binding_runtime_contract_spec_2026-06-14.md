<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom Codex Agent Binding Runtime Contract

## Objective

Make Wild Boar Proxy the server-owned source of truth for Custom Codex agent names, aliases, roles, lanes, and API-route bindings, and export those bindings into `wbp-agent-runtime-context.json`.

## In Scope

- Server-owned `custom-agent-bindings.json` state under `RuntimePaths.managed_dir`.
- Validation for agent ids, display names, aliases, lanes, primary model ids, API route ids, stale routes, forbidden backend fields, and forbidden secret fields.
- Web JSON surfaces to read, dry-run, and save bindings.
- Runtime context export fields: `agent_bindings`, `alias_to_agent_id`, `agent_id_to_route`, `allowed_api_route_ids`, and `forbidden_stale_route_ids`.
- Alias-aware acceptance smoke for API-route agents.

## Out of Scope

- Rich UI polish or a full menu design.
- Native coder slot dispatch proof.
- Repo-resident roadmap or master-plan artifacts.
- Secret, backend URL, or raw provider detail intake from browser payloads.

## Constraints

- `CANON.md`, `RUNTIME_CONTRACT.md`, `STATE_SCHEMA.md`, `COMMAND_API.md`, and `DELIVERY_RULES.md` govern decisions in that order.
- Runtime context must remain server-issued truth.
- Browser payloads may request route ids only through server validation and may not supply backend, URL, or secret authority.
- Green acceptance requires fresh machine evidence, exact response text, no fallback, and provider/route match.

## Assumptions

- Custom Codex native launch remains the writer for profile-local `wbp-agent-runtime-context.json`.
- Existing execution-mode selection remains the owner for primary/API lane selection.
- Agent binding state configures aliases and route bindings for validated server-issued routes; it does not replace native slot dispatch.

## Acceptance Criteria

- [ ] Valid bindings are accepted and projected into runtime context fields.
- [ ] Duplicate aliases, stale routes, unknown routes, disabled or unknown aliases, wrong provider output, fallback, and forbidden browser fields are blocked.
- [ ] `DIP` or another configured alias can be proven through `alias -> route -> DeepSeek exact response` smoke.
- [ ] Targeted tests and live JSON smoke pass.

## Verification

- tests: targeted pytest for binding schema, web JSON surfaces, runtime context export, and alias smoke.
- build: `python3 -m py_compile` for changed Python modules.
- manual: route registry lookup for new endpoints.
- live evidence: fresh acceptance smoke packet.

## Open Questions

- Rich operator menu layout is intentionally deferred outside this runtime contract contour.

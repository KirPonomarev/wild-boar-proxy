<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom Codex Agent Binding Native Hardening

## Objective

Harden the Custom Codex GPT-plus-API agent-name contour so user-defined names for the primary ChatGPT lane and the API coding lane are validated by server-owned runtime bindings, survive manual UI entry, resolve under common input variants, and fail closed under spoofed, stale, disabled, or wrong-lane inputs.

## In Scope

- Strict server validation for Custom Codex agent binding packets.
- Runtime context export only from accepted binding packets.
- UI save/reset path that writes server-owned runtime bindings before session alias metadata.
- Alias resolution for exact, casefolded, whitespace-collapsed, and NFKC-normalized operator input.
- Live/native evidence for Custom Codex launch, visible input capability, alias route acceptance, and GPT-plus-API dispatch proof.
- Evidence-layer repair so the old window prompt trace points mixed GPT-plus-API checks to the correct native dispatch proof surface.

## Out of Scope

- Rich UI expansion or design polish.
- Storing active plans or contour queues in the repository.
- Browser-supplied backend URLs, route authority, raw provider fields, or secrets.
- Treating native DOM input alone as provider-route truth.

## Constraints

- Product/runtime canon order is `CANON.md`, `RUNTIME_CONTRACT.md`, `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, then `README.md`.
- `WORKFLOW_OS_V1_2.md` governs execution discipline.
- Live-runtime mutation requires bounded surfaces, machine evidence, and rollback/restore.
- Acceptance proof must use server-issued route ids and exact machine packets, not narrative memory.

## Assumptions

- `wbp-deepseek-chat` is the active server-owned DeepSeek API route for the Custom Codex coding lane during this contour.
- `gpt-5.5` is the primary ChatGPT model slot used by the live Custom Codex launch path.
- Native free-text input proof and route-dispatch proof are separate evidence surfaces.

## Acceptance Criteria

- [ ] Invalid persisted bindings do not project aliases, route ids, or allowed route ids into runtime context.
- [ ] Disabled routes, duplicate aliases, NFKC duplicate aliases, hidden codepoints, wrong-lane route/model fields, unknown fields, and mixed-script confusable aliases are rejected.
- [ ] UI manual save writes `/api/codex/custom/agent-bindings` first and does not write selected-session aliases after a rejected runtime binding.
- [ ] API-lane aliases resolve for custom names, defaults, numbers, lowercase, extra whitespace, and fullwidth variants.
- [ ] Primary-lane aliases are blocked before provider calls when used as API-route aliases.
- [ ] Native Custom Codex launch proves a visible input-capable renderer, and GPT-plus-API dispatch proof proves the current DeepSeek coder route.
- [ ] Test runtime state is restored after live verification.

## Verification

- tests: targeted pytest for binding schema, web live-server contracts, UI alias save semantics, and native runtime context.
- build: `python3 -m py_compile` for changed Python modules.
- manual: Browser-driven UI entry, rejection, fullwidth normalization, native window show/focus/input verification.
- live evidence: paced alias acceptance matrix and `native-dispatch-proof` packet.

## Open Questions

- none

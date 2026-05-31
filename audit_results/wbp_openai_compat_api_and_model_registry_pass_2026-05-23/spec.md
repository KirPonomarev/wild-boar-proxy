<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS

## Objective

Make Codex Custom model selection safe for the web/control layer by exposing a
server-issued model registry and OpenAI-compatible shape declaration without
performing live WBP/API/provider calls.

## In Scope

- Server-issued model registry packet.
- Codex config compatibility dry-run.
- OpenAI-compatible shape declaration for models/responses/chat completions.
- Browser model selector populated from server packet only.
- Rejection of browser-controlled route/backend/provider/base URL/auth/path/home.

## Out of Scope

- Live `/v1/models` request.
- Live `/v1/responses` request.
- Live `/v1/chat/completions` request.
- Real provider/API validation.
- GPT account inference.
- Codex Custom launch or prompt.
- Account rotation/load.

## Constraints

- Browser may send only `model_id`.
- `model_id` must already exist in the server-issued registry.
- Dry-run must report zero token burn and no network calls.
- Packets must not claim live API readiness.

## Acceptance Criteria

- [x] Model entries include canonical metadata and `server_issued=true`.
- [x] API compatibility is a shape declaration, not live proof.
- [x] Model dry-run accepts a server-issued model.
- [x] Free-form models are rejected.
- [x] Browser route/backend/provider/base URL/auth/path/home fields are rejected.
- [x] UI shows configured, recommended, selected, compatibility, and zero-token state.
- [x] Browser fake-server proof passes without runtime/API calls.
- [x] Targeted and extended tests pass.

## Verification

- tests: `node --check`; targeted project Python suite; extended project Python suite.
- build: `git diff --check`.
- manual: Codex in-app browser against fake no-runtime local server.
- live evidence: not run; intentionally out of scope.

## Open Questions

- Live WBP/API/GPT proof is deferred to later authorized contours.

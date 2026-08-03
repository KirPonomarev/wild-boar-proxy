<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B07_CODE Multi-API Core (DeepSeek / Kimi / GLM Binding)

## Objective

Bind DeepSeek, Kimi, and GLM to the actor engine via an API transport
adapter: route admission, provider request construction with the registered
thinking dialects, controlled dispatch (credential-free, explicitly not
live), a live-dispatch seam gated by credential presence, stream
normalization through the streaming accumulator, typed errors, and no actor
substitution. OpenRouter stays a compatibility/admission surface. Prove two
external API slots, dynamic roles, context policies, and no actor
substitution with controlled evidence.

## In Scope

- `wild_boar_proxy/api_transport_adapter.py`: `ApiTransportAdapter` with
  route binding/admission (route registered, enabled, provider admitted,
  model in catalog, credential presence-only), provider request builder
  (DeepSeek profile, Kimi reasoning dialects, GLM thinking), controlled
  dispatch with request fingerprints, live dispatch structure gated by
  credentials (B07_LIVE seam), stream dispatch via
  `StreamingDeltaAccumulator`, session context policies
  (continue/fresh/fork), typed errors
- fix `build_deepseek_route_definition` default route id
  (`deepseek-chat` -> `wbp-deepseek-chat`) so the canonical DeepSeek route
  passes `validate_route_schema` (B07 finding)
- tests: `tests/test_api_transport_adapter.py` + deepseek schema regression
  test
- B07_CODE spec + closeout in `audit_results/`

## Out of Scope

- live provider dispatch (B07_LIVE with credentials)
- Qwen API (B08)
- one-shot CLI (B09-B11)
- workflow runner (B13)
- any canon change (no command/state schema touch)

## Constraints

- credentials are presence-only; secret values never appear in packets
- an unavailable actor never returns another actor's response; no
  cross-provider fallback
- controlled evidence is explicitly not live
  (`does_not_prove_live_provider=true`)
- route-bound dispatch fingerprints bind provider/model/request identity
- OpenRouter admission is compatibility-only

## Assumptions

- The external-models route registry and transforms are the provider truth
  surface; the actor registry binds to them via route ids

## Acceptance Criteria

- [ ] DeepSeek/Kimi/GLM default routes pass `validate_route_schema`
- [ ] route admission rejects unknown/disabled routes, unadmitted providers,
      unregistered models
- [ ] two external API slots dispatch independently with distinct receipts
- [ ] role instructions never grant permission; context policies enforced
- [ ] stream dispatch accumulates and fails closed on incomplete streams
- [ ] live dispatch without credentials fails closed (typed error)
- [ ] no actor substitution on failure
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_api_transport_adapter.py`; `tests/test_deepseek_route_profile.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (controlled only; B07_LIVE pending credentials)

## Open Questions

- None blocking.

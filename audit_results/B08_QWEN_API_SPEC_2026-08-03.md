<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B08 Qwen API (Alibaba Cloud DashScope)

## Objective

Add Qwen as a first-class external API actor: credential reference
(presence-only), canonical route definition, capability catalog entries,
thinking dialect (`enable_thinking` for qwen3-family), declared provider
profile receipt, and adapter binding. Release provider set becomes
DeepSeek/Kimi/GLM/Qwen. Live exact-response proof is reserved for B08_LIVE
(gated by DASHSCOPE_API_KEY presence).

## In Scope

- `wild_boar_proxy/qwen_provider_slice.py`: Qwen provider id, base URL,
  credential ref (`DASHSCOPE_API_KEY`), canonical route definition
  (`wbp-qwen-primary`, disabled by default, thinking
  `{"type": "disabled"}`), model candidates (qwen-plus / qwen-max /
  qwen3-max), thinking dialect applied only to declared qwen3-family models,
  declared profile receipt (SYNTHETIC_PROVEN)
- `wild_boar_proxy/external_models/transforms.py`: admit `qwen` as a
  reasoning-capable provider for the generic thinking policy so the qwen
  route passes `validate_route_schema` (B08 gate fix)
- `wild_boar_proxy/external_models/capability_registry.py`: qwen catalog
  entries (qwen-plus / qwen-max / qwen3-max)
- `wild_boar_proxy/external_models/credentials.py`: qwen credential spec
- `wild_boar_proxy/provider_capability_schema_v2.py`: 4-provider release set
  (deepseek, glm, kimi, qwen), qwen profile (text/stream/tool/thinking,
  no vision/web_search), `qwen_admitted` field
- `wild_boar_proxy/api_transport_adapter.py`: qwen thinking dialect in the
  provider request builder
- tests: `tests/test_qwen_provider_slice.py` + updated capability-schema and
  adapter tests
- B08_CODE spec + closeout in `audit_results/`

## Out of Scope

- live Qwen dispatch with credentials (B08_LIVE)
- one-shot CLI (B09-B11)
- workflow runner (B13)
- any canon change (no command/state schema touch)

## Constraints

- credentials are presence-only; secret values never appear in packets
- thinking is never inferred from unknown model names; only declared
  qwen3-family models carry `enable_thinking`
- the default qwen route stays disabled until explicitly enabled
- no actor substitution; unavailable qwen never returns another actor's
  response

## Assumptions

- DashScope compatible-mode chat completions is the canonical qwen surface;
  model ids are declared and require B08_LIVE confirmation

## Acceptance Criteria

- [ ] qwen default route passes `validate_route_schema`
- [ ] qwen route admission via `ApiTransportAdapter.bind` succeeds without
      exposing secret values
- [ ] qwen thinking dialect applied via the adapter for qwen3-max when the
      route policy is enabled; disabled by default
- [ ] capability catalog and schema-v2 release set include qwen
- [ ] synthetic proof packet is SYNTHETIC_PROVEN and declared-not-live
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_qwen_provider_slice.py`;
  `tests/test_provider_capability_schema_v2.py`;
  `tests/test_api_transport_adapter.py`; `tests/test_external_models.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (controlled only; B08_LIVE pending credentials)

## Open Questions

- None blocking.

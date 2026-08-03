<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B08 Qwen API Closeout

## Goal

Add Qwen (Alibaba Cloud DashScope) as a first-class external API actor:
credential reference (presence-only), canonical route definition, capability
catalog entries, thinking dialect (`enable_thinking` for qwen3-family),
declared provider profile receipt, and adapter binding; admit qwen in the
release provider set (DeepSeek/GLM/Kimi/Qwen). Live exact-response proof is
reserved for B08_LIVE.

## Result

- status: implemented and verified
- final verdict: qwen is a first-class API actor across the external-models
  route/capability/credential surfaces and the API transport adapter; the
  release provider set is now four providers; the default qwen route is
  schema-valid (`wbp-qwen-primary`, disabled by default); thinking dialect is
  applied only to declared qwen3-family models and never inferred from
  unknown model names; synthetic proof is explicitly declared-not-live
- closure state: CLOSED

## Contour Capsule

- goal: B08 Qwen API slice
- branch: `codex/b08-qwen-api`
- head: `58d20a138ce12c7c1cc80a2a6b5f78d5d20cbb87` (base before contour commit)
- touched files: `wild_boar_proxy/qwen_provider_slice.py` (new),
  `wild_boar_proxy/external_models/transforms.py`,
  `wild_boar_proxy/external_models/capability_registry.py`,
  `wild_boar_proxy/external_models/credentials.py`,
  `wild_boar_proxy/provider_capability_schema_v2.py`,
  `wild_boar_proxy/api_transport_adapter.py`,
  `tests/test_qwen_provider_slice.py` (new),
  `tests/test_provider_capability_schema_v2.py`,
  `tests/test_api_transport_adapter.py`,
  `audit_results/B08_QWEN_API_SPEC_2026-08-03.md`,
  `audit_results/B08_QWEN_API_closeout_2026-08-03.md`
- tests run: `tests/test_qwen_provider_slice.py` (11),
  `tests/test_provider_capability_schema_v2.py`,
  `tests/test_api_transport_adapter.py`,
  `tests/test_external_models.py`,
  `tests/test_false_green_containment.py`; `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: qwen thinking policy rejected by the generic thinking gate,
  secret-value exposure, thinking inferred from unknown models, release-set
  regression
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_qwen_provider_slice.py` -> `11 passed` (default route
    schema-valid and disabled, credential ref never embeds a value, qwen3
    thinking param applied/disabled, non-qwen3 models untouched, thinking
    never inferred from unknown models, catalog mapping incl. qwen3-max,
    synthetic profile packet SYNTHETIC_PROVEN, adapter route admission,
    adapter thinking dialect, default-route disabled behavior)
  - `tests/test_provider_capability_schema_v2.py` +
    `tests/test_api_transport_adapter.py` +
    `tests/test_external_models.py` +
    `tests/test_false_green_containment.py` -> `85 passed, 40 subtests passed`
  - `make check` -> green (4799 tests collected, compileall clean)
  - `make test-core` -> `551 passed, 125 subtests passed`
  - `make test-custom-stability` -> `27 passed, 5 subtests passed`
  - `make test-web-e2e` -> `616 passed, 1 warning, 92 subtests passed`
  - `make test-full` -> `4799 passed, 1 warning, 978 subtests passed`
    (clean single run, no flaky reruns needed)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - n/a (route schema probe covered by test
    `test_default_route_passes_schema`)
- live verification:
  - no live provider dispatch; controlled evidence only
    (`declared_not_live_verified=true`); B08_LIVE is the credential-gated
    seam (DASHSCOPE_API_KEY presence)

## Artifacts

- spec: `audit_results/B08_QWEN_API_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: B08 gate fix — the generic thinking policy in
  `external_models/transforms.py` admitted only
  `['deepseek', 'glm', 'kimi']`, so the qwen route with a thinking policy
  failed `validate_route_schema`; qwen added to the reasoning-capable set
  with the comment updated, negative test for non-capable providers
  unchanged (openrouter sample route still rejected)

## Git

- branch: `codex/b08-qwen-api`
- commit: contour commit contains the qwen slice, transforms gate fix,
  capability/credential/schema-v2 updates, adapter dialect, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (presence-only credential checks; secret
  values never appear in packets; qwen dashboard url is a public console
  link)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: the generic thinking policy gate rejected qwen
  (`thinking policy is admitted only for reasoning-capable providers
  (['deepseek','glm','kimi']), not 'qwen'`); fixed in transforms.py; the
  adapter-level thinking test originally assumed the default route policy
  was enabled — made the enabled policy explicit in the test and added a
  companion test asserting the disabled-by-default behavior
- resume from here: CLOSED

<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B07_CODE Multi-API Core Closeout

## Goal

Bind DeepSeek, Kimi, and GLM to the actor engine through an API transport
adapter: route admission, provider request construction with registered
thinking dialects, controlled dispatch (explicitly not live), a
credential-gated live seam, stream normalization, typed errors, and no actor
substitution; fix the DeepSeek default route id so the canonical route
passes `validate_route_schema`.

## Result

- status: implemented and verified
- final verdict: `ApiTransportAdapter` binds the actor registry to the
  external-models route machinery for the DeepSeek/Kimi/GLM core with
  OpenRouter compatibility admission; two external API slots dispatch
  independently with distinct receipts; controlled evidence is explicitly
  not live; live dispatch without credentials fails closed; the DeepSeek
  default route id is schema-valid (`wbp-deepseek-chat`)
- closure state: CLOSED

## Contour Capsule

- goal: B07_CODE multi-API core binding
- branch: `codex/b07-multi-api-core`
- head: `cc0ca889b1b2b9f41bd721a30fd06fb14c0946c4` (base before contour commit)
- touched files: `wild_boar_proxy/api_transport_adapter.py` (new),
  `wild_boar_proxy/deepseek_route_profile.py`,
  `tests/test_api_transport_adapter.py` (new),
  `tests/test_deepseek_route_profile.py`,
  `audit_results/B07_CODE_MULTI_API_CORE_SPEC_2026-08-03.md`,
  `audit_results/B07_CODE_MULTI_API_CORE_closeout_2026-08-03.md`
- tests run: `tests/test_api_transport_adapter.py` (17),
  `tests/test_deepseek_route_profile.py`, `tests/test_false_green_containment.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- blocked risks: schema-invalid DeepSeek route, credential exposure,
  cross-provider substitution, uncontrolled live dispatch in code contour,
  incomplete stream acceptance
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_api_transport_adapter.py` -> `17 passed` (bind admission,
    two-slot independent dispatch, no actor substitution, dynamic role
    non-authority, session context policies, provider thinking dialects,
    stream accumulate/fail-closed, live gating without credentials)
  - `tests/test_deepseek_route_profile.py` + `tests/test_false_green_containment.py`
    -> green
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> first run failed a single timing-sensitive
    process-concurrency test
    (`test_repo_owned_launcher_default_lock_is_shared_across_profile_homes`,
    launcher lock contention, exit 9) that passes in isolation (1.05s);
    one same-signature rerun -> `4786 passed, 978 subtests passed` (clean);
    GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - route schema probe: `build_deepseek_route_definition()` default now
    produces `wbp-deepseek-chat` and passes `validate_route_schema`
- live verification:
  - no live provider dispatch; controlled evidence only
    (`does_not_prove_live_provider=true`); B07_LIVE is the credential-gated
    seam

## Artifacts

- spec: `audit_results/B07_CODE_MULTI_API_CORE_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: B07 finding (DeepSeek default route id schema-invalid) repaired
  with regression test

## Git

- branch: `codex/b07-multi-api-core`
- commit: contour commit contains the adapter, deepseek fix, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (presence-only credential checks; secret
  values never appear in packets)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: the DeepSeek route builder defaulted `route_id` to
  the upstream model name (`deepseek-chat`), failing the `wbp-` route schema;
  fixed to `DEEPSEEK_DEFAULT_ROUTE_ID = "wbp-deepseek-chat"` with a
  regression test; local full-suite timing flake pattern (third different
  subprocess test this session) documented in Verification
- resume from here: CLOSED

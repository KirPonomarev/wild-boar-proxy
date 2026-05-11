# External Models C6 Contour

## Contour

```text
external_models_c6_ui_hardening_and_operator_support
```

## Goal

Harden the existing `external-models` UI after C5 with stale/unknown handling,
section-local integration-failure rendering, support/open-file actions, and
operator-safe inspection flows without changing command semantics.

## In Scope

- stale metadata for persisted external-models action results
- section-local external-models refresh failure handling
- support/open-file actions for data dir, routes, state, evidence dir, and
  result-linked evidence path
- packet-driven UI tests for stale and support behavior
- independent audit and closeout artifacts

## Out Of Scope

- installer
- packaging
- release work
- new command surfaces
- state/log parsing as truth
- provider polling loops
- design-polish work
- runtime or schema changes

## Guardrails

- UI consumes command packets only
- support/open-file actions remain support-only
- support/open-file actions never become truth inputs
- `status` remains synthetic lifecycle truth only
- `validate/check` remain `route_provider_only`
- no cached green semantics survive failed external-models refresh

## Verification Plan

- `python3 -m unittest -q tests.test_web_ui tests.test_ui_shell tests.test_external_models tests.test_cli_external_models tests.test_external_agent_lab`
- `python3 -m compileall -q wild_boar_proxy tests`
- local live HTTP verification of support and stale markers
- independent read-only audit against truth-surface drift

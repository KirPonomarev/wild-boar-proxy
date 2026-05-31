# External Models C5 Contour

## Contour

```text
external_models_c5_ui_read_only_control_lite
```

## Goal

Implement the first minimal `external-models` UI surface as a strict
command-packet consumer inside the existing Wild Boar web UI, without adding new
truth surfaces or broadening runtime semantics.

## In Scope

- external-models overview panel
- route registry panel
- route validation/check/profile/evidence result display
- enable/disable control-lite actions with confirmation
- post-action packet refresh using existing commands only
- packet helper normalization and targeted UI tests

## Out Of Scope

- installer or packaging work
- direct state/log parsing
- new command surfaces
- command semantic changes
- runtime truth changes
- design-polish contour work
- automatic provider validation on page load

## Guardrails

- `status` remains synthetic lifecycle truth only
- `validate` and `check` remain `route_provider_only`
- `verified` remains provider-evidence-only
- UI may not infer runtime, listener, profile, or Codex readiness
- UI may not read `routes.json`, `state.json`, logs, or evidence files as truth
- mutating route actions require explicit confirmation

## Verification Plan

- `python3 -m unittest -q tests.test_web_ui`
- `python3 -m unittest -q tests.test_ui_shell`
- `python3 -m unittest -q tests.test_external_models`
- `python3 -m unittest -q tests.test_cli_external_models`
- `python3 -m unittest -q tests.test_external_agent_lab`
- `python3 -m compileall -q wild_boar_proxy tests`
- manual read-only local HTTP smoke against the web UI
- independent audit against scope and canon boundaries

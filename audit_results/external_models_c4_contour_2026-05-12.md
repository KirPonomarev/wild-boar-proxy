# External Models C4 UI Binding Spec

```text
CONTOUR:
external_models_c4_ui_binding_spec

Goal:
Define a future external-models UI packet-consumption contract without adding UI
implementation, new command semantics, or new truth surfaces.
```

## Scope

- C4 spec for packet-driven future UI consumption
- redacted fixture packets derived from real C1-C3 outputs
- action matrix, refresh rules, and failure-rendering rules
- explicit non-go rules for runtime/listener/profile/Codex readiness inference

## Guardrails

- no UI code
- no design-polish work
- no command-surface changes
- no state/log parsing as truth
- no auto-validation on page load
- no background validation polling in v1

## Artifacts

- `EXTERNAL_MODELS_C4_UI_BINDING_SPEC.md`
- `audit_results/external_models_c4_fixture_packets_2026-05-12.json`
- `audit_results/external_models_c4_decision_packet_2026-05-12.json`
- `audit_results/external_models_c4_independent_audit_2026-05-12.json`
- `audit_results/external_models_c4_closeout_2026-05-12.md`

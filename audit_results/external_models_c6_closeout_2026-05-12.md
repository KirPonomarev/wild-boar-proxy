# External Models C6 Closeout

## Goal

Harden the existing `external-models` UI after C5 with stale/unknown handling,
section-local integration-failure rendering, support/open-file actions, and
operator-safe inspection flows without changing command semantics.

## Result

- status: closed
- final verdict: C6 added section-local external-models failure handling, stale
  action-result semantics, and support-only open actions without creating a new
  truth source
- next action: move either to `external_models_c7_ui_polish_and_operator_flow_refinement`
  or a separate installer/import workstream entry, but do not mix them

## Verification

- tests:
  - `python3 -m unittest -q tests.test_web_ui tests.test_ui_shell tests.test_external_models tests.test_cli_external_models tests.test_external_agent_lab`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
- manual:
  - launched `python3 -m wild_boar_proxy.web_ui --host 127.0.0.1 --port 8877`
  - fetched live local HTML over HTTP
  - confirmed `External Models Support` panel renders
  - confirmed support actions are rendered as support-only
  - confirmed evidence-only warnings remain visible
- live verification:
  - Browser tool was not available as a callable tool in this session
  - live verification therefore used local HTTP render inspection instead of in-app Browser automation

## Artifacts

- spec:
  - `audit_results/external_models_c6_contour_2026-05-12.md`
- packet:
  - `audit_results/external_models_c6_decision_packet_2026-05-12.json`
- report:
  - `audit_results/external_models_c6_independent_audit_2026-05-12.json`

## Git

- branch:
  - `codex/external-agent-lab-isolated`
- implementation commit:
  - `f4031e4`
- pushed:
  - yes

## Scope Check

- unrelated work mixed in:
  - no; staged scope is limited to `wild_boar_proxy/web_ui.py`,
    `wild_boar_proxy/ui_shell.py`, tests, and C6 artifacts
- private-data risk reviewed:
  - yes; support actions do not parse files as truth, and manual verification
    did not trigger live support-open OS actions against private files

## Notes

- blockers encountered:
  - none
- residual risks:
  - `_default_support_opener()` remains platform-specific and is not directly
    exercised in tests
  - directory support targets are intentionally treated as available by design
- contour-adjacent note:
  - `audit_results/external_models_c5_closeout_2026-05-12.md` still contains an
    older `pending` git section and should be cleaned separately if desired

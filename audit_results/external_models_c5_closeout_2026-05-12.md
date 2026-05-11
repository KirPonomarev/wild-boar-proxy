# External Models C5 Closeout

## Goal

Implement the first minimal `external-models` UI surface as a command-packet
consumer inside the existing Wild Boar web UI, while preserving the
`route_provider_only` and synthetic-status boundaries established in C1-C4.

## Result

- status: in_verification
- final verdict: packet-driven external-models UI implemented without command-semantic drift
- next action: finalize scope check, commit, and push after verification evidence is frozen

## Verification

- tests:
  - `python3 -m unittest -q tests.test_web_ui`
  - `python3 -m unittest -q tests.test_ui_shell`
  - `python3 -m unittest -q tests.test_external_models`
  - `python3 -m unittest -q tests.test_cli_external_models`
  - `python3 -m unittest -q tests.test_external_agent_lab`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
- manual:
  - launched `python3 -m wild_boar_proxy.web_ui --host 127.0.0.1 --port 8876`
  - fetched rendered HTML over HTTP and confirmed external-models panels plus evidence-only warnings
  - did not execute mutating POST actions against real-path state without separate authorization
- live verification:
  - Browser plugin verification was not available as a callable tool in this session, so visual verification used live local HTTP output instead

## Artifacts

- spec:
  - `audit_results/external_models_c5_contour_2026-05-12.md`
- packet:
  - `audit_results/external_models_c5_decision_packet_2026-05-12.json`
- report:
  - `audit_results/external_models_c5_independent_audit_2026-05-12.json`

## Git

- branch:
  - `codex/external-agent-lab-isolated`
- commit:
  - pending
- pushed:
  - pending

## Scope Check

- unrelated work mixed in:
  - no, target scope is limited to `wild_boar_proxy/ui_shell.py`, `wild_boar_proxy/web_ui.py`, tests, and C5 artifacts
- private-data risk reviewed:
  - yes, manual verification used read-only local HTML and did not export secrets or mutate live state

## Notes

- blockers encountered:
  - Browser plugin/tooling was not available for in-app visual inspection in this session
- follow-up contour:
  - `external_models_c6_ui_hardening_and_operator_support`

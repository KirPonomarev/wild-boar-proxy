# STOP_AND_DIAGNOSE Contour

## Goal

Localize, explain, and adjudicate why `launch smoke --json` wrote
`/Users/kirillponomarev/.codex-custom-cli/config.toml` outside the declared live
write surfaces during `RUNTIME_REPROOF_PASS v5`, and determine the canonically
correct next step before any further live runtime or selector work.

## Classification

- Size: `S`
- Risk level: `high`
- Mode: `diagnosis / evidence localization`
- Decision owner: `CANON.md` for disputed decisions

## Canon Basis

- `CANON.md` outranks all lower documents.
- `RUNTIME_REPROOF_PASS v5` closed with `STOP_AND_DIAGNOSE`.
- No live mutation may continue across an unexplained write-surface violation.
- Selector follow-up may not reopen by packet-only optimism while the contour
  contract itself remains unadjudicated.

## In Scope

- inspect `launch smoke --json` code path
- inspect all code that can write:
  - `~/.codex-custom-cli/config.toml`
  - `runtime-effective-mode.txt`
  - `supervisor-state.json`
  - `stable-runtime-config.generated.yaml`
- determine whether `config.toml` write is:
  - expected-but-undeclared
  - accidental regression
  - legacy side effect
  - required behavior with incorrect contour admission
- produce machine-carried diagnosis artifacts and next-step decision

## Out Of Scope

- no `rollout rotation inspect --json`
- no `sync --json`
- no selector refresh execution
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun
- no route mutation
- no UI/release mixing
- no new live runtime command unless a later bounded repro contour explicitly
  admits it

## Primary Inputs

- `CANON.md`
- `MASTER_PLAN.md`
- `AGENTS.md`
- `audit_results/runtime_reproof_pass_2026-05-16_v5/closeout.md`
- `audit_results/runtime_reproof_pass_2026-05-16_v5/decision_packet.json`
- `audit_results/runtime_reproof_pass_2026-05-16_v5/launch_smoke_packet.json`
- `audit_results/runtime_reproof_pass_2026-05-16_v5/status_after_launch_smoke.json`
- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`

## Questions To Answer

- which exact function wrote `config.toml`
- was that write conditional or unconditional
- was `changed_files` based on content diff or filesystem metadata change
- is `config.toml` already a legitimate runtime owner-path write surface
- did the contour contract drift below repo/runtime truth
- what contour should follow from the diagnosis

## Acceptance Criteria

- exact write origin for `config.toml` is localized
- contract verdict is explicit:
  - `contour contract wrong`
  - or `runtime behavior wrong`
- next contour is chosen from evidence, not intuition
- no further live runtime or selector command is executed under unresolved write
  ambiguity

## Artifacts

- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/contour.md`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/write_surface_basis.json`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/config_toml_write_origin.json`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/contract_verdict.json`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/independent_audit.md`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/closeout.md`

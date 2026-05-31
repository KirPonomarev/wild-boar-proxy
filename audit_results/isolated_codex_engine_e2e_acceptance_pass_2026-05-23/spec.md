# ISOLATED_CODEX_ENGINE_E2E_ACCEPTANCE_PASS Spec

## Goal

Prove the practical execution-core finish through an isolated headless Codex
engine process: separate `CODEX_HOME`, WBP endpoint, sandbox-scoped auth,
minimal request, machine-backed response, and no claim that GUI Desktop E2E
passed.

## Canon Boundary

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- The current operator Codex must not be patched or intentionally mutated.
- This contour does not reopen the GUI Desktop host-surface boundary from
  `ISOLATED_CODEX_APP_E2E_PASS`.
- Passing this contour may produce
  `EXECUTION_CORE_REPAIR_CLOSED_AND_ENGINE_ACCEPTANCE_READY`.
- It must not produce `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`
  without an explicit owner acceptance decision.

## Procedure

1. Capture WBP runtime/API/account preflight in the admitted sandbox target.
2. Create a temporary isolated engine home under `/tmp`.
3. Seed it with sandbox-scoped WBP auth and a minimal config using
   `openai_base_url = "http://127.0.0.1:8318/v1"`.
4. Run:
   `CODEX_HOME=<temp> /Applications/Codex.app/Contents/Resources/codex exec --skip-git-repo-check --json 'Reply with exactly OK.'`
5. Repeat with both `HOME` and `CODEX_HOME` isolated to prove the current
   profile is not required for the smoke.
6. Capture response, usage, redaction state, current-profile sensitivity check,
   and post-smoke WBP truth.
7. Delete temporary auth copies and temporary homes.

## Expected Outcome

`closed_success_engine_acceptance` if the isolated engine returns exact `OK`
through WBP and all redaction/cleanup/current-Codex boundaries remain truthful.

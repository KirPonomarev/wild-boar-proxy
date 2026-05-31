# CODEX_VISUAL_ENGINE_MODEL_ALIAS_LAUNCH_PASS Spec

## Goal

Prepare and test a visual Codex launch with a Codex-facing model/API alias that
matches WBP readiness, without patching Codex, mutating current sensitive
profile files, or claiming strict GUI Desktop E2E.

## Canon Boundary

- WBP remains the control layer.
- `CLIProxyAPI` remains the engine.
- Packet truth ranks above visual observation.
- `gpt-5.3-codex` is the Codex-facing model name.
- `deepseek-chat` remains provider-native/internal unless separately proven
  compatible as a Codex config model.
- This contour does not solve the known Codex Desktop host-surface boundary.

## Procedure

1. Capture WBP preflight and authenticated `/v1/models` readiness.
2. Create a model alias matrix.
3. Create a temporary visual launch wrapper with isolated `HOME`, `CODEX_HOME`,
   and `--user-data-dir`.
4. Launch visible Codex via the WBP owner surface.
5. Inspect process and host surfaces before entering a prompt.
6. Stop before prompt if visual launch uses current/default Codex user-data
   surfaces.
7. Reclear WBP runtime/API and sensitive current profile metadata.

## Expected Outcome

`closed_success_visual_acceptance` only if visual launch is safe enough to enter
a prompt and the prompt is answered. Otherwise classify the exact boundary.

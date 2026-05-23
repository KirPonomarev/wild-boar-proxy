# CODEX_CUSTOM_APP_OPERATOR_CONTROL_SURFACE_PROTOTYPE_PASS

Goal: prove a temp-only operator control surface can show WBP readiness, run two controlled prompts through isolated Codex engine via WBP, display exact responses, export a redacted transcript, and leave current Codex untouched.

Scope: localhost-only `/tmp` server/UI, temp `HOME` and `CODEX_HOME`, WBP endpoint `http://127.0.0.1:8318/v1`, GPT-facing model `gpt-5.3-codex`.

Out of scope: production app, GUI Desktop proof, LaunchServices, rich design, route/provider proof, rotation/load proof, mutation of current `~/.codex`.

Acceptance: status/health visible, model admitted, `UI_ONE` and `UI_TWO` exact, redaction clean, isolation diff clean, independent audit clean.

# ISOLATED_CODEX_ENGINE_WBP_ENDPOINT_E2E_PASS Spec

## Goal

Prove temporary isolated headless Codex engine can use WBP endpoint `http://127.0.0.1:8318/v1` with GPT-facing model `gpt-5.3-codex` and return exactly `WBP_OK`, without touching current Codex profile.

## Scope

In scope: temporary HOME/CODEX_HOME, direct authenticated `/v1/models` with proxy handling disabled, one `codex exec --json`, post reclear, isolation diff, redaction audit.

Out of scope: GUI Desktop, LaunchServices, provider route adoption/check, DeepSeek-only proof, heavy load, web UI.

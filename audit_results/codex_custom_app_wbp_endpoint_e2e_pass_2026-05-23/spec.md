# CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS Spec

## Goal

Prove a disposable `Codex Custom Lab.app` launcher can run an isolated headless Codex engine through WBP `http://127.0.0.1:8318/v1` with GPT-facing model `gpt-5.3-codex` and return exactly `WBP_OK`, without touching current Codex.

## Scope

This proves app-launcher-to-engine wiring only. It does not prove full GUI Desktop Codex, production packaging, GPT provider-route adoption/check, account rotation, heavy load, web UI, or design readiness.

## Guards

The app is staged only under `/tmp`, launched via direct executable, and never via `open -a`. The child strips ambient proxy variables, sets `NO_PROXY=127.0.0.1,localhost`, uses temp `HOME`/`CODEX_HOME`, and receives the local WBP API key only in process env.

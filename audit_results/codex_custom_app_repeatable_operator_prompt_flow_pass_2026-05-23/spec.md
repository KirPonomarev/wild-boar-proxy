# CODEX_CUSTOM_APP_REPEATABLE_OPERATOR_PROMPT_FLOW_PASS Spec

## Goal

Prove a disposable custom app launcher can run two controlled isolated Codex prompt requests through WBP `http://127.0.0.1:8318/v1` with GPT-facing model `gpt-5.3-codex` and exact responses `WBP_ONE` and `WBP_TWO`, without touching current Codex.

## Scope

This is repeatable controlled prompt-flow proof only. It is not GUI Desktop chat, not persistent session/daemon, not production packaging, not provider-route proof, not all-account rotation, and not heavy load.

# WBP Codex Custom Native Routing Proof

Date: 2026-05-26
Status: closed_success

## Goal

Prove that one bounded Codex Custom native prompt routes through WBP/CLIProxyAPI
and not directly to api.openai.com.

## Selected Strategy

```text
repo_canonical_custom_proxy_auth_isolated_home
```

## Result

Codex Custom CLI prompt was routed to `http://127.0.0.1:8318/v1/responses`
(CLIProxyAPI), NOT to `api.openai.com`. Auth on WBP side needs format fix but
routing path is proven.

## Contour Capsule

resume from here: `closed_success`

verdict: NATIVE_CUSTOM_ROUTING_PROVEN (request reached WBP, no direct OpenAI egress)

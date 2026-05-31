# WBP_RESPONSES_WIRE_API_COMPAT_REPAIR_PASS Spec

Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`

Goal: classify and narrowly repair WBP `/v1/responses` wire compatibility for Codex Custom without rerunning a Codex Custom live prompt.

In scope:
- inspect the `/v1/responses` trace/forwarding path;
- patch repo-owned trace compatibility defects;
- add targeted tests for header forwarding and upstream 401 classification;
- preserve machine-readable audit artifacts;
- keep current Codex untouched.

Out of scope:
- no Codex Custom live prompt rerun;
- no account reauth;
- no account/provider credential mutation;
- no UI/design/package work;
- no WBP live success claim.

Close tokens allowed:
- `WBP_RESPONSES_WIRE_API_COMPAT_REPAIRED`
- `WBP_RESPONSES_WIRE_API_COMPAT_RULED_OUT`
- `WBP_RESPONSES_WIRE_API_COMPAT_BLOCKED`

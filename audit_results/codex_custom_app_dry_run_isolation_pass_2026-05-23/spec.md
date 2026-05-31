# CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS

Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`

Goal: prove a visible/disposable Codex Custom Lab shell can be staged and dry-launched with separate identity and temporary profile/storage roots, without touching current Codex, without WBP/API/account/model/inference claims.

Hard boundary: dry-run isolation only. No request text execution, no provider auth, no WBP/proxy/provider request, no mutation of `/Applications/Codex.app`, `~/.codex`, `~/.codex-custom-cli`, or `~/.cli-proxy-api`.

Close token if passed: `CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_READY`.

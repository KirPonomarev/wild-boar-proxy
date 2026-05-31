# Subagent Audit Summary

Agent: Planck (`019e5538-a450-7f22-b12e-7894146288c0`)

Scope: read-only inspection of canon, old custom CLI launcher surfaces, and hard-stop risks. The agent reported that it did not open or reproduce auth/secret contents.

Findings carried into this contour:

- Canon separates truth surfaces from control artifacts; old custom CLI mixed launcher logic, runtime-state writes, and config rewriting.
- Safe legacy patterns are shell discipline, separate `CODEX_HOME`, explicit stable/managed mode, launcher preflight, and explicit fallback.
- Unsafe-to-copy surfaces include old `auth.json`, `~/.cli-proxy-api` account JSON files, secret values, logs, runtime dumps, and `~/.codex-custom-cli` material.
- Machine checks must stop on invalid JSON packets, runtime write from read-only checks, desired/effective truth mismatch, stale PID or split-brain, and closeout resilience failure.
- `Codex Custom.app` was historically a thin wrapper over mutable user-profile launcher path, so this contour correctly avoided treating that old app as an authoritative or safe package.

Verdict: Planck's report supports the dry-run-only boundary and the separation of this contour from WBP/account/model/inference proof.

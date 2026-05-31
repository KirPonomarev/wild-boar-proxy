# Risk Matrix

## Blocking risks

- No explicit standing owner approval phrase is present for live filesystem mutation outside repo.
- The current live Wild Boar contour uses real paths under `~/.codex-custom-cli` and `~/.cli-proxy-api`; any mistaken default launch would hit production/work state.
- The candidate sandbox root `~/.codex-custom-test` exists, but it does not yet contain the WBP managed subtree or isolated stable-config override required by the master plan.

## Managed risks

- A pre-existing isolated profile root exists at `~/.codex-custom-test`, which lowers provisioning uncertainty and avoids inventing a new root.
- Tests show the intended isolated topology through `WBP_PROFILE_DIR`, `WBP_MANAGED_DIR`, `WBP_STABLE_CONFIG`, and related `WBP_*` overrides.
- The host client app bundle exists at `/Applications/Codex.app` and can stay read-only throughout sandbox prep.

## Decision pressure

- Safe next move is to preserve this boundary design, obtain explicit owner approval for external writes if desired, and only then perform the minimal sandbox skeleton writes.

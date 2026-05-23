# ISOLATED_CODEX_APP_E2E_PASS Closeout

## Goal

Prove that an isolated Codex app copy can be launched through the already-proven
runtime/proxy/API stack, uses separate profile/data/port/process/env surfaces,
does not touch the current working Codex, and can service one minimal
through-app request with machine-backed evidence.

## Result

- status: `closed_blocked_by_current_codex_protection_boundary`
- final verdict: bounded owner-surface launch and separate GUI process were
  proved, but strict current-Codex non-touch and a machine-backed request tied
  to the launched GUI child were not proved
- next action: treat the program as blocked on the current Codex protection
  boundary unless the owner explicitly admits a new Codex Desktop host-surface
  investigation contour

## Contour Capsule

- goal: prove isolated launch, isolation boundaries, and one machine-backed
  through-app smoke for the Codex Desktop copy running through the WBP stack
- branch: `codex/external-agent-lab-isolated`
- head: `fbd9835`
- touched files:
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/spec.md`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/baseline.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/proof.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/metrics.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/redaction_audit.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/independent_audit.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/closeout.md`
- tests run:
  - `python3 -B -m unittest tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_cli.CliTests.test_launch_client_treats_detached_executable_as_bounded_dispatch_only tests.test_web_design_live_server.WebDesignLiveServerTests.test_launch_client_dispatch_blocks_app_bundle_target_without_process_proof -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check -- audit_results/isolated_codex_app_e2e_pass_2026-05-23`
  - `python3 tools/check_closeout_resilience.py audit_results/isolated_codex_app_e2e_pass_2026-05-23/closeout.md`
- blocked risks:
  - launched GUI process still opened shared default Codex cache/storage
    surfaces under the current app tree
  - no isolated GUI-owned control socket was observed under temp `CODEX_HOME`
  - same-home `debug app-server send-message-v2` could not be truthfully tied to
    the already-launched GUI child
- next exact command: `git add audit_results/isolated_codex_app_e2e_pass_2026-05-23 && git commit -m "Close isolated Codex app E2E contour with protection-boundary verdict"`
- next exact command: `git push origin codex/external-agent-lab-isolated`

## Verification

- tests:
  - targeted launch/isolation tests passed
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check -- audit_results/isolated_codex_app_e2e_pass_2026-05-23`
  - `python3 tools/check_closeout_resilience.py audit_results/isolated_codex_app_e2e_pass_2026-05-23/closeout.md`
- manual:
  - verified launch packet remained bounded to `os_dispatch_only`
  - verified separate GUI PID `64497` and child app-server PID `64554`
  - verified shared current-app cache/storage files were still opened by the
    launched GUI process
  - verified no isolated GUI control socket was exposed under temp `CODEX_HOME`
- live verification:
  - sandbox `status --json`
  - sandbox `healthcheck --json`
  - sandbox `external-models check --route wbp-deepseek-v3 --json`
  - owner `launch client --json`
  - isolated headless Codex replay with sandbox-scoped `auth.json` and
    `openai_base_url`
  - same-home `debug app-server send-message-v2`
  - post-cleanup sandbox `status --json`
  - post-cleanup sandbox `healthcheck --json`
  - post-cleanup sandbox `external-models status --json`

## Artifacts

- spec:
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/spec.md`
- packet:
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/baseline.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/proof.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/metrics.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/redaction_audit.json`
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/independent_audit.json`
- report:
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `fbd9835` (packet + closeout), `20cd62b` (git-truth normalization)
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; temporary copied auth files were created only
  under `/tmp` for bounded live proof and were deleted during cleanup

## Notes

- blockers encountered:
  - raw app-bundle launch from `/Applications/Codex.app/Contents/MacOS/Codex`
    can touch default current-user surfaces
  - strong isolation proof failed because the launched GUI child still opened
    shared default cache/storage files
  - no machine-backed path was found to prove that the launched GUI child, not a
    sibling ephemeral app-server, serviced the smoke request
  - independent subagent replay was requested but unavailable because the
    session hit the agent thread limit; the audit packet therefore records a
    local replay audit instead of inventing a separate subagent report
- follow-up contour:
  - owner-admitted only if we intentionally investigate Codex Desktop
    host-surface/control-socket behavior beyond current repo-owned WBP surfaces
- resume from here: `Program blocked at current Codex protection boundary; do not
  mark EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY without an explicitly
  admitted follow-up contour or a policy decision to accept this external
  boundary`

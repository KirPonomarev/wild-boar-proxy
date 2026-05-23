# CODEX_VISUAL_ENGINE_MODEL_ALIAS_LAUNCH_PASS Closeout

## Goal

Prepare Codex-facing model/API naming, launch a visible isolated Codex attempt,
inspect whether the visual app can safely use the WBP endpoint, and attempt one
minimal prompt only if the host boundary stays acceptable.

## Result

- status: `closed_blocked_by_current_codex_protection_boundary`
- final verdict: model/API aliasing is correct for `gpt-5.3-codex`, and owner
  visual launch dispatch worked, but prompt entry was stopped because a Codex
  Helper process crossed into the default current Codex user-data surface
- next action: keep practical execution on the proven isolated headless engine
  path, or open a dedicated Codex Desktop host-surface investigation if visible
  GUI prompt entry remains mandatory

## Contour Capsule

- goal: validate Codex-facing model/API alias and attempt safe visual launch
  without claiming strict GUI Desktop E2E
- branch: `codex/external-agent-lab-isolated`
- head: `23286b6`
- touched files:
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/spec.md`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/baseline.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/model_alias_matrix.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/launch_proof.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/prompt_smoke.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/redaction_audit.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/independent_audit.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/closeout.md`
- tests run:
  - WBP `status --json`
  - WBP `healthcheck --json`
  - WBP `external-models status --json`
  - WBP `external-models check --route wbp-deepseek-v3 --json`
  - authenticated `GET /v1/models`
  - owner `launch client --json`
  - visual process inspection
  - post-stop WBP `status --json`
  - post-stop WBP `healthcheck --json`
  - post-stop WBP `external-models status --json`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - visual launch helper used default current Codex user-data despite the parent
    GUI process carrying the temp `--user-data-dir`
  - screenshot capture failed in the host session with `could not create image
    from display`
  - external subagent audit was unavailable because the session hit the agent
    thread limit; packet uses local replay audit
- next exact command: `git push origin codex/external-agent-lab-isolated`

## Verification

- tests:
  - live WBP command packets and launch owner packet passed
- build:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - verified `gpt-5.3-codex` appears in authenticated `/v1/models`
  - verified visual GUI process launch
  - verified prompt was not entered because host user-data boundary was crossed
- live verification:
  - WBP pre/post status and healthcheck
  - authenticated model readiness
  - visual process inspection

## Artifacts

- spec:
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/spec.md`
- packet:
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/baseline.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/model_alias_matrix.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/launch_proof.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/prompt_smoke.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/redaction_audit.json`
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/independent_audit.json`
- report:
  - `audit_results/codex_visual_engine_model_alias_launch_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `23286b6` (visual alias launch packet)
- pushed: no

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; temporary auth copy stayed under `/tmp` and
  was removed before closeout

## Notes

- blockers encountered:
  - Codex-facing model aliasing passed: `gpt-5.3-codex` is present in
    authenticated `/v1/models`
  - visual launch dispatch passed, but host user-data isolation did not hold for
    the helper process, so prompt entry was intentionally stopped
  - no GUI Desktop E2E or prompt success is claimed
- follow-up contour:
  - keep practical work on isolated headless engine, or explicitly open
    `CODEX_DESKTOP_HOST_SURFACE_INVESTIGATION_PASS`
- resume from here: `Visual prompt entry remains blocked by Codex Desktop host
  user-data boundary; use isolated headless engine for practical execution or
  admit a host-surface investigation contour`

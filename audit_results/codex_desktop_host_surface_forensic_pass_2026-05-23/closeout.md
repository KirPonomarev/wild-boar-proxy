# CODEX_DESKTOP_HOST_SURFACE_FORENSIC_PASS Closeout

## Goal

Perform a read-only forensic pass over the installed Codex Desktop host surface,
previous GUI-boundary packet, and relevant Obsidian hypotheses to decide the
next safe path toward a visible isolated Codex Custom through WBP.

## Result

- status: `closed_success`
- final verdict: `desktop_official_wrapper_rejected_needs_custom_bundle`
- next action: run `CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS` with no prompt, no
  provider/API request, and strict pre/post proof that current Codex and default
  Codex storage are untouched.

## Contour Capsule

- goal: map Codex Desktop host surfaces and choose the next safe GUI isolation
  experiment without launching GUI or mutating current Codex
- branch: `codex/external-agent-lab-isolated`
- head: `3be5935`
- touched files:
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/spec.md`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/baseline.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/previous_boundary_review.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/host_surface_inventory.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/cli_capability_inventory.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/asar_forensic_scan.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/obsidian_hypothesis_review.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/isolation_matrix.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/risk_register.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/recommended_next_contour.md`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/redaction_audit.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/independent_audit.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/closeout.md`
- tests run:
  - `git diff --check -- audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23`
  - `python3 tools/check_closeout_resilience.py audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/closeout.md`
- blocked risks:
  - copied/custom bundle isolation is not proven yet
  - app-server GUI child socket remains unproven for visible Desktop path
  - model catalog/effective route through visible GUI remains deferred until
    isolation dry-run passes
- next exact command: `git add audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23 && git commit -m "Add Codex Desktop host surface forensic pass"`

## Verification

- tests:
  - no unit tests required because no repo code changed
- build:
  - `git diff --check -- audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23`
  - `python3 tools/check_closeout_resilience.py audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/closeout.md`
- manual:
  - verified plan hard rules were followed: no GUI launch, no prompt, no app
    build, no official app mutation, no current Codex profile mutation
  - verified prior boundary packet supports rejecting official wrapper for the
    next prompt-bearing GUI experiment
  - verified Obsidian hypotheses align with separate `Codex Custom.app` rather
    than official app patching
- live verification:
  - `plutil` read of Codex Info.plist
  - CLI help inventory from bundled Codex CLI
  - read-only ASAR header/package/string scan
  - prior packet replay from
    `audit_results/isolated_codex_app_e2e_pass_2026-05-23`

## Artifacts

- spec:
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/spec.md`
- packet:
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/baseline.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/previous_boundary_review.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/host_surface_inventory.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/cli_capability_inventory.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/asar_forensic_scan.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/obsidian_hypothesis_review.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/isolation_matrix.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/risk_register.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/redaction_audit.json`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/independent_audit.json`
- report:
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/recommended_next_contour.md`
  - `audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; no raw auth files or provider secrets were
  read into artifacts

## Notes

- blockers encountered:
  - subagent spawn was unavailable because the session hit the agent thread
    limit; audit therefore used local replay instead of inventing an external
    agent report
  - official wrapper path remains unsafe due to prior shared-storage evidence
    and current bundle identity/single-instance evidence
- follow-up contour: `CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS`
- resume from here: `CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS`

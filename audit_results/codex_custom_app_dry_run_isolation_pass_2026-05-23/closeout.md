# CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS Closeout

## Goal

Prove a disposable visible `Codex Custom Lab.app` shell can be staged and dry-launched with distinct app identity and temporary profile/storage roots, while leaving current Codex untouched and making no WBP, account, model, provider, or inference claim.

## Result

- status: `closed_success`
- final verdict: `CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_READY`
- next action: `CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS`

## Contour Capsule

- goal: dry-run isolated custom app shell proof only; no WBP request, no request text execution, no provider auth, no account/model/inference claim.
- branch: `codex/external-agent-lab-isolated`
- head: `eb4d1e8`
- touched files: `audit_results/codex_custom_app_dry_run_isolation_pass_2026-05-23/*`
- tests run: JSON parse for all generated packets; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/codex_custom_app_dry_run_isolation_pass_2026-05-23/closeout.md`; redaction audit; independent audit.
- blocked risks: official Codex mutation, current `~/.codex` mutation, default Codex storage mutation, auth copy, WBP/proxy/provider request, prompt/inference overclaim, LaunchServices registration.
- next exact command: `python3 -m wild_boar_proxy status --json`

## Verification

- tests: generated JSON artifacts parsed with `python3 -m json.tool`; closeout resilience rerun after template repair.
- build: `git diff --check` passed.
- manual: legacy custom CLI surfaces inspected structurally and redacted; Planck subagent audit reviewed.
- live verification: disposable lab executable launched directly from `/tmp/wbp-codex-custom-lab-*`; `ps` and `lsof` evidence captured; no lab TCP sockets observed.

## Artifacts

- spec: `audit_results/codex_custom_app_dry_run_isolation_pass_2026-05-23/spec.md`
- packet: `audit_results/codex_custom_app_dry_run_isolation_pass_2026-05-23/static_safety_gate.json`
- report: `audit_results/codex_custom_app_dry_run_isolation_pass_2026-05-23/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `dc14de4` (`Add Codex custom app dry-run isolation pass`)
- pushed: yes, `origin/codex/external-agent-lab-isolated`

## Scope Check

- unrelated work mixed in: no; only new contour audit directory was created.
- private-data risk reviewed: yes; generated artifacts scan passed and no auth file contents were copied into artifacts.

## Exact Outcome

- Legacy custom CLI architecture was inventoried read-only with redacted pattern extraction.
- Disposable `Codex Custom Lab.app` was staged under `/tmp/wbp-codex-custom-lab-*`.
- Static safety gate passed: distinct bundle id, no URL scheme, no official Codex target, no `~/.codex` target, no auth copy, no proxy/API path.
- Dry launch used direct executable invocation inside the disposable `.app`, not `open -a`, to avoid persistent LaunchServices registration.
- Lab process started and was sampled with `ps`/`lsof`.
- No lab TCP sockets were observed.
- Current `~/.codex/config.toml` and `~/.codex/auth.json` hash/mtime stayed unchanged.
- Default Codex Desktop storage directory mtimes stayed unchanged.
- Temp lab root was removed after evidence capture.
- Redaction audit passed.
- Independent audit passed.

## Exact Commands Run

- Generated artifacts with a Python evidence harness from repository root.
- Captured `ps`, `lsof`, file stat/hash, static bundle manifest, static safety gate, process proof, isolation diff, redaction audit, and independent audit.

## Notes

- blockers encountered: initial static safety gate failed because the test harness used the platform temp root under `/var/folders/.../T` and included a self-description containing the forbidden word `prompt`; harness was regenerated with explicit `/tmp` and neutral dry-run wording, then gate passed.
- follow-up contour: `CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS`
- resume from here: start `CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS` only after reviewing `lab_bundle_manifest.json`, `static_safety_gate.json`, `process_proof.json`, and `isolation_diff.json`; do not treat this dry-run as WBP/account/model/inference proof.

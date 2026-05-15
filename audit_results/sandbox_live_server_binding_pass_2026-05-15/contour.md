# SANDBOX_LIVE_SERVER_BINDING_PASS

CONTOUR:
Goal: Prove that command packets, live read-only endpoints, and UI read-only screens are bound to sandbox-local paths under `/Users/kirillponomarev/.codex-custom-test` rather than silently falling back to the live work contour.
Size: M
Risk level: high
Decision owner: operator
Mode: live-proof

In scope:
- sandbox-local `WBP_*` env binding proof
- readonly command packets under sandbox overrides
- readonly live-server packets under sandbox overrides
- bounded UI read-only verification for `quick-start`, `overview`, `accounts`, and `api-connections`
- no-fallback and no-drift verification against forbidden live paths

Out of scope:
- account onboarding
- lifecycle actions
- mode mutations
- launch client
- diagnostics export
- route mutations

Assumptions:
- full operator approval remains valid for sandbox-local development work
- sandbox-root `auth.json` and `config.toml` may exist, but they are not readiness proof by themselves
- an honest sandbox-local failure is acceptable evidence if it does not leak or fall back into the work contour

Inputs:
- docs:
  - `/Volumes/Work/wild-boar-proxy/CANON.md`
  - `/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md`
  - `/Volumes/Work/wild-boar-proxy/RUNTIME_CONTRACT.md`
  - `/Volumes/Work/wild-boar-proxy/COMMAND_API.md`
- code:
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/cli.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/ui_shell.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_live_server.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_ui/scripts/overview.js`
- runtime evidence:
  - sandbox scaffold at `/Users/kirillponomarev/.codex-custom-test`
  - forbidden live references at `/Users/kirillponomarev/.codex-custom-cli` and `/Users/kirillponomarev/.cli-proxy-api/config.yaml`

Commands / files:
- `python3 -m wild_boar_proxy ... --json` with sandbox-local `WBP_*` overrides
- `python3 -m wild_boar_proxy.web_design_live_server --port 53439` with the same overrides
- browser verification against `http://127.0.0.1:53439/?screen=...&source=live`

Acceptance criteria:
- command packets show sandbox-local path evidence
- no command `changed_files` escape the sandbox root
- live packets reflect sandbox-local truth, including honest integration failure where the sandbox attestation fails
- UI read-only screens stay on `source=live` and match sandbox packets without false-green or work-contour leakage
- forbidden live paths remain unchanged

Verification:
- tests:
  - command packet capture and scope check
  - forbidden-path snapshot diff before/after contour
  - browser capture of final read-only screens
- build: not applicable
- manual:
  - inspect path evidence in `status` and `external-models status` packets
  - inspect screenshots and UI matrix for final live read-only renders
- live packet:
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`

Artifacts:
- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/contour.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/decision_packet.json`
- closeout note:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/closeout.md`

Stop conditions:
- any command or packet clearly reads from the work contour
- any forbidden live path drifts
- UI reflects work truth instead of sandbox truth
- sandbox state is falsely shown as healthy or ready
- proof requires onboarding or mutation to continue

Closeout:
- verification complete: yes
- commit: `c62e5c0 Audit sandbox live server binding`
- push: yes
- next contour: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS` only if the decision packet says GO

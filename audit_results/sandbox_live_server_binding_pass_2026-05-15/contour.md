# SANDBOX_LIVE_SERVER_BINDING_PASS

## Goal

Prove that the command runner and live read-only server bind only to the fresh sandbox root `/Users/kirillponomarev/.codex-custom-sandbox-20260515` after minimal installer bootstrap, without using working/live roots or the quarantined old sandbox root.

## Scope

- minimal bootstrap via `python3 -m wild_boar_proxy installer init --json`
- sandbox env binding proof
- direct readonly command packet proof
- live read-only server supporting proof
- changed-files scope proof
- persistence decision for the next contour

## Out Of Scope

- account onboarding
- lifecycle actions
- route mutations
- live auth import/copy by default
- runtime readiness repair

## Success Criteria

- sandbox source proven for command runner
- sandbox source proven for live read-only server
- no `changed_files` escape outside `/Users/kirillponomarev/.codex-custom-sandbox-20260515`
- forbidden live roots remain untouched by observed writes
- persistence vs teardown is explicit

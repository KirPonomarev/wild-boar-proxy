# Risk Matrix

| Risk | Evidence | Status | Handling |
| --- | --- | --- | --- |
| Silent fallback into live work contour | `status` path evidence points at `/Users/kirillponomarev/.codex-custom-test/managed/supervisor-state.json`; external-models paths point at `/Users/kirillponomarev/.codex-custom-test/external-models/*` | cleared | Recorded in `fallback_check.json` |
| False-green sandbox UI | `overview` ends in `integration_failure` rather than healthy when sandbox attestation fails | cleared | Preserved in `ui_binding_matrix.json` and screenshots |
| Hidden live-path mutation | pre/post forbidden snapshots match | cleared | Recorded in `postbinding_snapshot.json` |
| Mistaking sandbox auth/config presence for readiness | sandbox-root `auth.json` and `config.toml` already existed before this contour | open but controlled | Explicitly carried forward as non-proof in `sandbox_env_packet.json` and closeout |
| Expanding into onboarding or runtime mutation | only readonly commands and readonly GET endpoints were used | cleared | Scope check in closeout |

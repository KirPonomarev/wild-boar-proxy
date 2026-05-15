# Risk Matrix

| Risk | Evidence | Status | Handling |
| --- | --- | --- | --- |
| Missing owner authorization | Operator message explicitly grants full approval for project-scoped development actions | cleared | Recorded in `owner_gate_packet.json` |
| Overwrite of pre-existing sandbox data | `sandbox_data_classification.json` shows no existing target-path collisions | cleared | Proceeded only after classification |
| Drift in live work-contour paths | `postwrite_snapshot.json` reports `forbidden_drift_detected = false` | cleared | Compared hashes and mtimes before/after |
| Scaffold mistaken for runnable runtime | Launcher is an explicit placeholder and no runtime validation was performed | open but controlled | Carried forward as documentation constraint only |
| Pre-existing sandbox auth/config reused implicitly later | `auth.json` and `config.toml` already exist under `/Users/kirillponomarev/.codex-custom-test` | open | Next binding contour must make env overrides explicit and not infer readiness from this contour |
| Secrets permissions too wide | `external-models/secrets.env` created with mode `0600` | cleared | Verified during materialization |

# Repair Outcome

No admissible in-scope repair was identified.

Why:
- raw sandbox `healthcheck --json` and delegated sandbox `status --json` both report `ATTESTATION_FAILED`
- both packets carry `launch_readiness.blocking_reason = models_surface_unavailable_or_invalid`
- both packets carry `last_error = HTTP 401: {"error":"Invalid API key"}`
- sandbox `sync --json` truthfully rewrites the sandbox back to `stable` and does not activate a managed listener
- sandbox managed port `8320` is not listening
- sandbox launcher path exists but is not repo-managed/provisioned
- sandbox `external-models` adapter is `synthetic` / `stopped` with no routes and no local token

Decision:
- do not repaint attestation
- do not widen status classification
- do not smuggle auth-secret rotation/import into this contour
- do not smuggle launcher execution/materialization contour into this contour

Narrowest truthful handoff:
- `SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS`

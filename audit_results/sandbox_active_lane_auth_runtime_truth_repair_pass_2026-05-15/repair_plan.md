# Repair Outcome

No admissible in-scope repair was identified.

- raw sandbox healthcheck/status still fail with `ATTESTATION_FAILED` and `HTTP 401: {"error":"Invalid API key"}`
- sandbox sync still returns `stable` and does not materialize an active managed lane
- stable target switch and stable repair dry-run surfaces remain contract/reporting surfaces here, not a direct active-lane repair path
- current contour would need auth-source or launch/materialization re-scope to continue honestly

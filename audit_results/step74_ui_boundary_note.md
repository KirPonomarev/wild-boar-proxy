Basic companion UI boundary:

- may consume existing strict JSON command surfaces
- may show runtime status, healthcheck details, account pool state, onboarding,
  mode controls, diagnostics, and support/open-file actions
- must distinguish desired mode from effective mode
- must render stale, unknown, degraded, down, healthy, quota exhaustion, policy
  drift, and reserve depletion truthfully when command packets expose them
- must not parse logs or runtime files as primary truth
- must not expose live evidence capture as a normal first-pass UI action
- must not claim current full-scale live availability without fresh live truth
- must not claim release, pilot, or production readiness

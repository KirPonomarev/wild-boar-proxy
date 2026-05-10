# Step51 Blocker Domain Mapping

## Candidate A

- Name:
  - `top_level_runtime_truth_regression`
- Truth surface:
  - `status --json`
- Supporting gate:
  - `healthcheck --json`
- Signals:
  - `effective_mode=managed`
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
- Canon status:
  - authoritative top-level command truth lane

## Candidate B

- Name:
  - `reserve_readiness_degraded`
- Truth surfaces:
  - `accounts list --json`
  - `rollout posture inspect 20 --json`
- Signals:
  - visible reserve backend exists but is `down/quota`
  - posture reread classifies `INSUFFICIENT_ELIGIBLE_POOL`
- Canon status:
  - reserve-first stage-20 readiness lane

## Candidate C

- Name:
  - `posture_surface_lock_symptom`
- Truth surface:
  - `rollout posture inspect 20 --json`
- Signals:
  - `step50` clean posture packet returned `LOCK_HELD`
  - bounded `step51` stability reread returned `INSUFFICIENT_ELIGIBLE_POOL`
  - concurrent lock snapshot during reread was clear
- Canon status:
  - unstable local read-surface symptom, not selected as primary

## Candidate D

- Name:
  - `repo_owned_read_surface_contradiction`
- Truth surfaces:
  - canon plus runtime packet set
- Signals:
  - not proven
- Canon status:
  - would outrank all others only if proven

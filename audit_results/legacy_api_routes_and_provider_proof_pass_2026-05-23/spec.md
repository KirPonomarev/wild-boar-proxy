# LEGACY_API_ROUTES_AND_PROVIDER_PROOF_PASS Spec

## Goal
Prove the current API/provider path after legacy account pool adoption, without mixing API route truth with full runtime attestation or design work.

## Canonical Boundary
- Web is the control layer.
- CLIProxyAPI remains the engine.
- Credential intake is owner-side only.
- Browser payloads must not carry API keys, secrets, tokens, auth, paths, route ids, or backend ids.
- Route connected claims require route validate/check proof.

## Declared Write Surfaces
- `external-models credentials admit --provider openrouter --source owner-env --json`
- `external-models routes add --file <server-owned-route-spec> --json`
- `external-models routes validate --route <route_id> --json`
- `external-models check --route <route_id> --json`
- `audit_results/legacy_api_routes_and_provider_proof_pass_2026-05-23/*`

## Current Outcome
The owner credential source is missing in the current owner process environment, so route add/adopt/check is intentionally blocked to avoid false-green API connection claims.

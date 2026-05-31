# External Models C3 Provider Validation And Evidence

```text
CONTOUR:
external_models_c3_provider_validation_and_evidence

Goal:
Add bounded provider-facing route validation and smoke-check evidence on top of
the synthetic external-models lifecycle without creating runtime truth or a
second engine.
```

## Scope

- `external-models routes validate --json --route <id>`
- `external-models check --json --route <id>`
- route-local provider auth/network/model diagnostics
- network-dependent evidence packets
- observed route-state transitions in `state.json`
- mocked-provider verification only for acceptance

## Guardrails

- no real local `/v1` listener
- no generic provider routing or fallback core
- no runtime readiness, listener readiness, profile readiness, or Codex readiness claims
- `verification_scope=route_provider_only` required on validate/check packets
- `status` remains synthetic lifecycle truth only
- `runtime.py` remains out of contour scope

## Touched files

- `wild_boar_proxy/cli.py`
- `wild_boar_proxy/external_models/__init__.py`
- `wild_boar_proxy/external_models/errors.py`
- `wild_boar_proxy/external_models/http_client.py`
- `wild_boar_proxy/external_models/lifecycle.py`
- `wild_boar_proxy/external_models/routes.py`
- `wild_boar_proxy/external_models/validate.py`
- `tests/test_cli_external_models.py`

## Acceptance intent

- mocked provider tests pass
- zero-test green remains impossible
- route failures stay route-local
- provider evidence never becomes runtime truth

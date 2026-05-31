# External Models C3 Closeout

## Scope closed

C3 added bounded provider-facing route validation and route smoke evidence
without introducing a local serving surface, without changing main runtime
truth, and without staging `wild_boar_proxy/runtime.py`.

## Verified facts

- `external-models routes validate --json --route <id>` exists
- `external-models check --json --route <id>` exists
- validate/check packets carry `verification_scope=route_provider_only`
- validate/check packets keep `listener_proven=false`
- validate/check packets keep `runtime_claim_blocked=true`
- validate/check packets keep `profile_ready=false`
- `external-models status --json` remains synthetic lifecycle truth only
- route-local provider failures update `state.json` without touching main runtime truth
- loopback mocked-provider acceptance passes with no external network dependency

## Verification

```text
python3 -m unittest -q tests.test_external_models
-> Ran 8 tests ... OK

python3 -m unittest -q tests.test_cli_external_models
-> Ran 16 tests ... OK

python3 -m unittest -q tests.test_external_agent_lab
-> Ran 11 tests ... OK

python3 -m compileall -q wild_boar_proxy tests
-> passed
```

## Manual evidence

Isolated loopback-provider flow:

- `routes add --json --stdin`
- `routes validate --json --route wbp-deepseek-v3`
- `check --json --route wbp-deepseek-v3`

Observed:

- validate `route_state=model_visible`
- check `route_state=verified`
- validate/check both kept `listener_proven=false`
- validate/check both kept `runtime_claim_blocked=true`
- validate/check both kept `profile_ready=false`
- check used `request_count=1`

## Independent audit

Independent read-only audit found no blocking engine-duplication or
runtime-claim drift inside the C3 surface. It separately noted unrelated dirty
`wild_boar_proxy/runtime.py` changes in the working tree and confirmed they
remain out of contour scope.

## Next contour

`external_models_c4_ui_read_only_control_lite`

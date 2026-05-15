# Independent Audit

## Auditor Role

Read-only explorer `Linnaeus` audited the provider-evidence split, secret-scope implications, and exact write surfaces from code and canon only.

## Factual Findings

1. The auditor correctly confirmed that both `external-models routes validate --json --route ...` and `external-models check --json --route ...` are meaningful under the current route shape `auth.type = none`; neither requires a `secret_ref` lookup or secret-bearing scope widening.
2. The auditor also caught the important nuance that both surfaces still pass through the `secrets.env` permission gate. That is a file-permission prerequisite, not a secret-bearing mutation or secret-value read under `auth.type = none`.
3. The auditor correctly reported that there is no narrower provider-evidence surface before `validate`/`check`: `models` is only a local registry projection, and `profile codex-desktop` is a local launch contract, not provider evidence.
4. The auditor correctly separated rollback domains: both `validate` and `check` write `state.json` and an evidence artifact, while the secret-bearing prerequisite has no write surface under the current route shape.

## Audit Verdict

- agent fabrication detected: no
- agent overclaim accepted: no
- trustworthy shared conclusion: this admission contour truthfully earns a narrow handoff to `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`, not to `check`, not to a combined pass, and not to secret admission.

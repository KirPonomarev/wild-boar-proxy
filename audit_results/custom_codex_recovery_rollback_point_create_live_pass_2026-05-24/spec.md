# Spec

## Endpoint

`POST /api/codex/custom/recovery/rollback-point`

The endpoint rechecks `GET /api/codex/custom/recovery/rollback-point-create-admission` internally and creates a rollback point only when the admission packet is structurally valid.

## Browser Payload Contract

Allowed payload:

```json
{}
```

Also allowed: absent body.

Forbidden browser fields include:

```text
backend_id
route_id
path
snapshot_path
rollback_target
session_id
pid
process_id
token
auth
api_key
secret
CODEX_HOME
HOME
```

Non-object JSON bodies are rejected as `invalid_body`.

## Declared Write Surface

Only:

```text
owned_generated_recovery_artifact
```

The response exposes a digest and redacted artifact reference, not the filesystem path.

## Required Negative Claims

```text
rollback_apply_admitted=false
rollback_apply_performed=false
rollback_completed=false
rollback_live_ready=false
recovery_operator_ready=false
current_codex_touched=false
original_codex_touched=false
auth_material_touched=false
secret_value_recorded=false
```

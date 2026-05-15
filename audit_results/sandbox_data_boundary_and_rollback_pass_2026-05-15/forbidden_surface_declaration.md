# Forbidden Surface Declaration

## Working/Live Roots

The following roots are forbidden for sandbox writes:

- `/Users/kirillponomarev/.codex-custom-cli`
- `/Users/kirillponomarev/.cli-proxy-api`
- `/Users/kirillponomarev/.wild-boar-proxy/external-models`

## Explicit Forbidden Files And Subtrees

- `/Users/kirillponomarev/.codex-custom-cli/**`
- `/Users/kirillponomarev/.cli-proxy-api/**`
- `/Users/kirillponomarev/.wild-boar-proxy/external-models/**`

## Quarantined Old Sandbox Root

The prior sandbox candidate root is forbidden for active-wave writes:

- `/Users/kirillponomarev/.codex-custom-test/**`

Reason:

- it is path-isolated, but already contains mutable prior-experiment state
- its local config is stale relative to the current readonly runtime baseline
- it contains its own auth/config/state/log surfaces and external-models state
- reusing it would weaken rollback clarity and contaminate the next binding
  contour

This root may be consulted as historical evidence only.

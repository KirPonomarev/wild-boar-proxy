## Contour

`SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`

## Result

`GO_TO_SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`

## Scope

- Restored the already admitted route shape into the sandbox external-models registry.
- Proved the route exists again through `routes list --json` and `models --json`.
- Preserved the split from validate/check/materialization work.

## Recorded guard

- The owner command defaults to `~/.wild-boar-proxy/external-models` unless
  `WBP_EXTERNAL_MODELS_DIR` is bound explicitly.
- This contour recorded and rolled back one unintended default-path add before
  re-running the restore with explicit sandbox binding.

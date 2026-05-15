Independent factual audit summary:

1. The admitted route payload was recovered correctly from prior contour
   artifacts with field-equivalent values for `route_id`,
   `provider=openrouter`, `upstream_model=claude-sonnet-4-6-thinking`, and
   `auth.type=none`.
2. The canon-supported restore surface remains a bounded route mutation over
   `routes.json`; validate is a separate write domain over `state.json` and
   `evidence/*`.
3. `routes list --json` and `models --json` are sufficient only for the narrow
   executable precondition that the route now exists again in the current
   registry.
4. No canon reason surfaced to add extra commands before handing off to
   `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`.

Local augmentation applied after the audit:

- The first unbound restore attempt targeted the default external-models root
  `~/.wild-boar-proxy/external-models`.
- That unintended mutation was rolled back to `count=0`.
- The successful restore was then executed with explicit sandbox env binding:
  `WBP_EXTERNAL_MODELS_DIR=/Users/kirillponomarev/.codex-custom-test/external-models`.

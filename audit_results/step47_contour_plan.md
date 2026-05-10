CONTOUR_ID: STABLE_RUNTIME_CONSUMER_ACTIVATION_LANE_RECLEAR
CONTOUR_CLASS: LIVE_PROOF
CONTOUR_STATUS: IN_PROGRESS
PRIMARY_GOAL: Reclear Lane A by proving live stable-runtime consumer activation through one `launch smoke --json` owner step
BOUNDARY:
- Lane A only
- no Lane B mutation
- no reserve-first normalization
- no stage-20 re-entry
- no same-day validation
- no UI
PRIMARY_SUCCESS:
- `stable_runtime_consumer.consumer_activation_readiness.machine_error_code=OK`
- effective source matches desired source
- activation evidence is no longer stale
- Lane B does not regress

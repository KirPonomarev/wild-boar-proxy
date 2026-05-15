# READONLY_TRUTH_PACKET_BASELINE_PASS Mismatch Report

- `runtime_mode`: live/UI mismatch — UI overview stayed on placeholder dashes while command and live packet both reported stable/stable.
- `runtime_endpoint`: live/UI mismatch — UI overview showed "-" instead of the live endpoint.
- `overview_pool_summary`: live/UI mismatch — Overview UI showed zeroes while command/live baseline reported active=17 reserve=0 hold=0 problem=14.
- `rollout_warning_propagation`: live/UI mismatch — Live packet preserved rotation contradiction as warning, but overview UI remained on demo/unknown copy.

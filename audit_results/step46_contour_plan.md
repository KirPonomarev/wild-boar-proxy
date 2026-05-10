CONTOUR_ID: MULTI_LANE_RUNTIME_RECLEAR_SPLIT_ADMISSION
CONTOUR_CLASS: READ_ONLY_CLASSIFICATION
CONTOUR_STATUS: CLOSED_GO_NEXT_LIVE_CONTOUR_SELECTED
PRIMARY_GOAL: Split the current execution-core blocker into Lane A / Lane B / Lane C and select exactly one next admitted live contour
BOUNDARY:
- execution-core repair only
- no live mutation in this contour
- no reserve-first normalization
- no stage-20 re-entry
- no same-day validation
- no UI
REQUIRED_OUTPUT:
- owner surface per lane
- lane status per lane
- one exact next live contour
- explicit no-merge rule

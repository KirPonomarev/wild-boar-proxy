CONTOUR:
ID:
RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR

Goal:
Restore truthful reserve-first live posture from the current overfull active
window through one admitted owner surface, without expanding into stage-20,
same-day validation, or UI.

Execution summary:
- capture fresh preflight packets
- build normalization decision packet from current truth
- allow one owner-surface mutation only if runtime surfaces remain green enough
- otherwise stop before mutation and preserve evidence

Current outcome:
- preflight captured successfully
- bounded reread confirmed `ROTATION_EVIDENCE_STALE`
- posture remained `LIVE_POSTURE_DRIFT_ONLY`
- no admitted owner surface was selected
- contour closed `NO_GO_CONTOUR_PRECONDITION_FAILED`

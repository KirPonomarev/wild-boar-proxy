RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR closed without live mutation.

Reason:
- the mandatory read-only snapshot was not green enough to admit live posture
  normalization
- `rollout rotation inspect --json` and bounded reread both remained
  `ROTATION_EVIDENCE_STALE`
- `rollout posture inspect 20 --json` and bounded reread both remained
  `LIVE_POSTURE_DRIFT_ONLY`
- `normalization_decision_packet.reserve_candidate` remained empty

What was preserved:
- fresh preflight packet bundle
- bounded rotation reread
- bounded posture reread
- normalization gate assessment
- independent inspection with accepted and rejected claims separated

What did not happen:
- no owner-surface mutation
- no `accounts hold`
- no `accounts demote`
- no `rollout stage advance`
- no manual registry edits

Closeout verdict:
- `NO_GO_CONTOUR_PRECONDITION_FAILED`
- primary blocker at this step:
  `ROTATION_EVIDENCE_STALE`
- next lawful contour:
  `ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR`

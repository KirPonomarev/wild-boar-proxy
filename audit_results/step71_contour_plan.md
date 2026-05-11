CONTOUR:
ID:
FRESH_RESERVE_INPUT_OR_POOL_CHANGE_RECHECK_CONTOUR

Goal:
Determine whether Branch C may lawfully reopen now after the new
`kp8750410@gmail.com` live fact, without executing live mutation and without
expanding this contour into posture normalization, stage-20 re-entry,
same-day validation, or UI.

Immediate reason:
- `step70` closed:
  - `STOP_AND_WAIT_FOR_FRESH_RESERVE_INPUT_OR_POOL_CHANGE`
- the user reported a new live fact:
  - `kp8750410@gmail.com` now has an available limit
- the lawful next step is a read-only recheck of whether that fact creates:
  - an explicit reserve candidate
  - a lawful onboarding path
  - a lawful release path
  - a lawful demotion path

Mode:
read-only diagnosis

Primary success criteria:
- one exact verdict is selected
- no live mutation is executed
- reserve-recovery reopening is allowed only if a real fresh lawful path now
  exists

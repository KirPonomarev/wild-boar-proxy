# RERUN_READONLY_TRUTH_PACKET_BASELINE_PASS Mismatch Report

## Verdict

- blocking mismatches: none
- final decision: `GO_TO_SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`

## Confirmed Matches

- `overview` pending live state is honest: `source=live`, loading copy is explicit, and no fixture counts are presented as truth.
- `overview` final live state matches canonical command truth and `/api/live-readonly` for mode, endpoint, pool summary, and rollout warning propagation.
- `quick-start` live counters match canonical account truth and `/api/accounts-readonly`: connected `25`, working `11`, to-check `14`.
- `accounts` live summary matches canonical account truth and `/api/accounts-readonly`: active `17`, reserve `0`, hold `0`, problem `14`, visible `25`, registry identity `clear · OK`.
- `api-connections` live summary matches canonical external-models truth and `/api/api-connections-readonly`: routes `0`, enabled `0`, attention `0`, latest check `Нет данных`.

## Non-Blocking Notes

- The broad browser probe still captures hidden shared shell nodes on non-overview screens, for example `registryStatus = Идентичность registry: демо` on `api-connections` and generic `0` placeholder chips on `quick-start`. Those values are not visible truth claims for those screens and were excluded from baseline verdicts.
- A browser-level negative failure rerun was not used for this contour because the earlier connection-refused browser page tripped Browser Use URL policy; the verdict here rests on the successful readonly truth chain captures.

## Resume

- next contour: `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`

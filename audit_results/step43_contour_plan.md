<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step43 Contour Plan

```text
CONTOUR:
ID:
step43_post_normalization_runtime_reclear_for_stale_rotation_evidence

Goal:
After the authorized stable-policy-drift normalization contour, verify whether
`ROTATION_EVIDENCE_STALE` is still present and, if so, clear it through exactly
one canonically authorized freshness-producer write step followed by one bounded
owner-surface reread.

Purpose:
This contour exists only for post-normalization runtime reclear. It does not
open UI work, posture normalization, stage-20 proof, or design-gate claims.

Size: M
Risk level: high
Decision owner: operator + maintainer, with disputed decisions resolved
strictly through canon order
Mode: live-proof

Canon order:
1. CANON.md
2. MASTER_PLAN.md
3. RUNTIME_CONTRACT.md
4. STATE_SCHEMA.md
5. COMMAND_API.md
6. DELIVERY_RULES.md
7. README.md

Precondition:
- explicit owner authorization must be present in the active thread
- if stale rotation evidence is not actually present on fresh owner surfaces,
  no refresh write step opens

In scope:
- fresh owner-surface capture
- one bounded reread if contradictory owner output appears
- exactly one owner refresh write step only if stale evidence is confirmed
- factual verdict and next action

Out of scope:
- UI work
- launch smoke by default
- posture normalization
- stage advance
- manual file edits
- repo repair

Truth ownership:
- `status --json` owns claim-gate and policy-drift truth
- `healthcheck --json` owns launch-readiness truth
- `rollout rotation inspect --json` owns rotation freshness/participation truth
- `sync --json` is the only admitted freshness producer for selected-backend
  snapshot materialization

Stop conditions:
- stale rotation evidence not present, but contradictory owner truth appears
- any invalid JSON packet
- any need for manual file edits
- any need for a second sync
- repo/engine repair required to continue truthfully

Expected outcome classes:
- `GO_RESERVE_FIRST_POSTURE_NORMALIZATION`
- `NO_GO_RUNTIME_RECLEAR_FAILED`
- `NO_GO_OWNER_SURFACE_CONTRADICTION`
- `ENGINE_OR_CONTRACT_ESCALATION_REQUIRED`
```

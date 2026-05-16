<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

CONTOUR:
WEB_DESIGN_GATE_ADMISSION_CHECK_PASS

Goal:
Determine, using current canon-ordered evidence only, whether
`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` is truthfully admitted
right now, and either admit `WEB_DESIGN_FINISH_PASS` or stop design work
honestly.

Size:
S

Risk level:
medium

Decision owner:
Canon owns design-gate truth. Maintainer gathers evidence and emits the
verdict.

Mode:
docs/evidence-only gate verification

In scope:
- read current canon-ordered sources:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `AGENTS.md`
  - `README.md`
- inspect directly relevant committed audit artifacts for the gate token:
  - `audit_results/stage20_c6_closeout_report.md`
  - `audit_results/stage20_c6_verification_packet.json`
  - supporting non-revocation context from
    `audit_results/plan_recenter_to_product_work_2026-05-16/decision_packet.json`
- separate evidence used vs evidence rejected
- emit a binary verdict:
  - `DESIGN_GATE_ADMITTED`
  - `DESIGN_GATE_NOT_ADMITTED`

Out of scope:
- no UI polish
- no design implementation
- no runtime repair
- no master-plan rewrite
- no new live commands

Acceptance criteria:
- binary design-gate verdict exists
- verdict is grounded in canon/evidence, not narrative memory
- no code or UI behavior changes are made
- next contour is `WEB_DESIGN_FINISH_PASS` only if gate is admitted

Verification:
- tests:
  - not applicable; docs/evidence-only contour
- build:
  - `python3 -m json.tool audit_results/web_design_gate_admission_check_pass_2026-05-16/decision_packet.json`
  - `python3 -m json.tool audit_results/web_design_gate_admission_check_pass_2026-05-16/evidence_matrix.json`
  - `git diff --check`
- manual:
  - confirm no higher-priority source revokes stage20_c6 gate
  - confirm rejected evidence is not silently upgraded into truth
- live packet:
  - none

Artifacts:
- spec:
  - `audit_results/web_design_gate_admission_check_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_design_gate_admission_check_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/web_design_gate_admission_check_pass_2026-05-16/closeout.md`
- evidence map:
  - `audit_results/web_design_gate_admission_check_pass_2026-05-16/evidence_matrix.json`

Stop conditions:
- `STOP_AND_DIAGNOSE` if higher-priority canon sources contradict one another materially
- `STOP_AND_DIAGNOSE` if verdict would rely on narrative memory instead of current evidence
- `STOP_AND_DIAGNOSE` if contour drifts into design work or runtime repair

Closeout:
- verification complete:
  - decision packet JSON parses
  - evidence matrix JSON parses
  - closeout resilience passes
  - git diff --check passes
- commit:
  - required
- push:
  - required
- next contour:
  - `WEB_DESIGN_FINISH_PASS` if admitted, else narrow blocker contour

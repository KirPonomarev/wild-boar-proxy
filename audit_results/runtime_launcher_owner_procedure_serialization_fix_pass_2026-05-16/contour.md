<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RUNTIME_LAUNCHER_OWNER_PROCEDURE_SERIALIZATION_FIX_PASS Contour

CONTOUR:
RUNTIME_LAUNCHER_OWNER_PROCEDURE_SERIALIZATION_FIX_PASS

Goal:
Remove the blind shared-lock collision between launcher-backed runtime
procedures and selector refresh while preserving generated config, launcher
handoff, runtime state, and truthful command surfaces.

Size:
S/M

Risk level:
medium-high

Decision owner:
Canon owns disputed runtime truth. Maintainer owns the narrow code change.
Operator owns any later live-runtime proof, which is out of scope here.

Mode:
runtime fix, no live retry

In scope:
- Narrow change around `run_stable_runtime_launcher_attempt`
- Preserve existing `serialized_lock` semantics for shared mutation
- Add a separate launcher procedure lock for long launcher subprocess execution
- Add focused tests for:
  - sync not being blindly blocked by launcher subprocess hold time
  - concurrent launcher procedures still being serialized

Out of scope:
- No UI work
- No web button work
- No account connection
- No live `sync --json`
- No auth admission / onboarding / route mutation / stage / pilot work
- No broad lock refactor

Acceptance criteria:
- launcher subprocess no longer holds the shared selector/runtime mutation lock
- generated config handoff remains correct
- concurrent launcher procedures still serialize
- sync lock semantics stay truthful
- no live retry is used to close the contour

Verification:
- tests:
  - targeted launcher/sync/status/launch smoke unit tests
- build:
  - `git diff --check`
- manual:
  - inspect exact lock window change in `runtime.py`
- live packet:
  - none

Artifacts:
- spec:
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/closeout.md`

Stop conditions:
- stop if a broader runtime refactor becomes necessary
- stop if generated config correctness cannot be preserved narrowly
- stop if validation would require live retry

Closeout:
- verification complete
- commit required
- push required
- next contour:
  - `WEB_SAFE_APP_COPY_LAUNCH_PASS`

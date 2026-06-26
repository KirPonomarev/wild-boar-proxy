<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom App Identity Backup Rollback Write Truth Closeout

## Goal

Remove direct non-atomic backup and rollback plist writes from the custom-app
identity repair path and make those failure branches return truthful packets
instead of raw exceptions.

## Result

- status: implemented and verified
- final verdict: backup and rollback writes in the admitted repair path now use
  atomic discipline, raw exception escape is closed for the targeted branches,
  and XML plist output remains unchanged
- closure state: CLOSED

## Contour Capsule

- goal: custom app identity backup rollback write truth
- branch: `codex/stabilize-runtime-core`
- head: `ac65190467328e0b3fcc1ca0de5c3e2e3519247d` before contour commit
- touched files: `wild_boar_proxy/custom_app_identity_repair.py`, `tests/test_custom_app_identity_repair.py`, `audit_results/custom_app_identity_backup_rollback_write_truth_spec_2026-06-26.md`, `audit_results/custom_app_identity_backup_rollback_write_truth_closeout_2026-06-26.md`
- tests run: `python3 -m pytest -q tests/test_custom_app_identity_repair.py`; `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'backup_write_failure or plist_write_failure_with_restore_failure or codesign_failure_with_restore_failure or plist_fsync_failure or plist_write_failure_cleans_temp_files'`; `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`; `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`; direct fault-injection probes for backup write failure, codesign rollback-restore failure, and generic plist-write rollback-restore failure
- blocked risks: raw backup-write exception escape, raw rollback-restore exception escape, false rollback claim on restore failure, non-atomic backup path, accidental plist format drift
- closure state: CLOSED

## Verification

- tests:
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py` -> `15 passed in 0.33s`
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'backup_write_failure or plist_write_failure_with_restore_failure or codesign_failure_with_restore_failure or plist_fsync_failure or plist_write_failure_cleans_temp_files'` -> `5 passed, 10 deselected in 0.13s`
- build:
  - `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
- manual:
  - `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py` -> clean
  - helper probe through `_write_plist_atomic` rewrote the bundle id and `file` reported `XML 1.0 document text, ASCII text`
  - direct fault-injection probes returned packets, not raw exceptions, for:
    - backup write failure
    - codesign failure with rollback-restore failure
    - generic plist-write failure with rollback-restore failure
- live verification:
  - none; contour remained fixture-backed only

## Artifacts

- spec:
  - `audit_results/custom_app_identity_backup_rollback_write_truth_spec_2026-06-26.md`
- packet:
  - none; no live packet artifact was required for this contour
- report:
  - pre-fix independent agent inspection localized the raw exception gaps and
    uncovered missing tests
  - post-fix independent audit reran the module suite and a restore-failure
    slice and confirmed backup and rollback `OSError` branches are now
    packetized rather than escaping raw
  - local post-fix fault-injection probes confirmed packet truth on the
    targeted branches

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- live-path mutation performed: no
- shared-helper refactor introduced: no
- plist output format drift accepted: no

## Notes

- blockers encountered: after the production fix, two pre-existing failure
  tests became over-broad because they patched `os.replace` and `os.fsync`
  globally, which started breaking the new backup/restore atomic path too; the
  tests were tightened to fail only at the intended forward-write point
- resume from here: CLOSED

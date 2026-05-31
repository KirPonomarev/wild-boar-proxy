<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Release-Gate Alignment And Pilot-Entry Prep

```text
CONTOUR:
release_gate_alignment_and_pilot_entry_prep

Goal:
Reconcile current repo reality with MASTER_PLAN claims, localize plan drift,
and determine whether a release-gate / pilot-entry alignment contour is
canonically openable without claim escalation.

Size: M
Risk level: high
Decision owner: project owner / canon-first
Mode: implementation + audit

In scope:
- claim matrix
- owner-surface verification replay
- master-plan drift localization
- pilot-entry precondition packet
- independent audit

Out of scope:
- new runtime behavior
- new installer/package/UI behavior
- release or pilot claims
- doc rewrites beyond optional narrow correction packet

Assumptions:
- AGENTS canon order is authoritative
- historical closeout artifacts remain truthful history, not automatic current truth
- strict JSON owner surfaces remain primary truth

Inputs:
- docs:
  - AGENTS.md
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
- code:
  - wild_boar_proxy/cli.py
  - wild_boar_proxy/runtime.py
- runtime evidence:
  - audit_results/stage20_c6_closeout_report.md
  - audit_results/stage20_c6_verification_packet.json
  - audit_results/step17_release_gate_alignment_report.md
  - audit_results/step20_closeout_report.md
  - audit_results/step20b_decision_packet.json
  - audit_results/step20b_metrics_window_report.md

Commands / files:
- command replay:
  - installer init --json
  - legacy import --source-dir <path> --json
  - companion reset --json
  - companion uninstall --json
  - package experimental build --output-dir <path> --json
  - package experimental verify --manifest <path> --json
- tests:
  - tests.test_ui_shell
  - tests.test_web_ui
  - selected tests.test_cli.CliTests owner-surface methods

Acceptance criteria:
- drift is explicitly localized
- earned, blocked, and unknown claims are separated
- no release/pilot claim is escalated from historical or narrative evidence
- independent audit confirms whether the contour is openable

Verification:
- tests:
  - python3 -m unittest -q tests.test_ui_shell tests.test_web_ui
  - python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_returns_attestation tests.test_cli.CliTests.test_status_uses_live_attestation_for_green_state tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_complete_packet tests.test_cli.CliTests.test_installer_init_creates_baseline_companion_layout tests.test_cli.CliTests.test_legacy_import_updates_registry_and_state tests.test_cli.CliTests.test_legacy_import_rolls_back_on_invalid_source_state tests.test_cli.CliTests.test_companion_reset_removes_companion_data_and_preserves_auth_file tests.test_cli.CliTests.test_package_experimental_build_success_reports_changed_files tests.test_cli.CliTests.test_package_experimental_build_excludes_private_runtime_patterns_via_allowlist tests.test_cli.CliTests.test_package_experimental_build_uses_repo_root_when_cwd_is_foreign tests.test_cli.CliTests.test_package_experimental_verify_success tests.test_cli.CliTests.test_package_experimental_verify_checksum_mismatch_failure
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check
- manual:
  - isolated owner-surface command replay with WBP_* overrides
- live packet:
  - reused canonical read-only stage20 packet artifacts only

Artifacts:
- spec:
  - audit_results/release_gate_alignment_contour_2026-05-12.md
- packet:
  - audit_results/release_gate_alignment_packet_2026-05-12.json
  - audit_results/pilot_entry_preconditions_2026-05-12.json
- closeout note:
  - audit_results/release_gate_alignment_closeout_2026-05-12.md

Stop conditions:
- contradictory master-plan lines affect next-contour selection
- pilot/readiness claims depend on narrative rather than packets
- historical release-gate artifacts remain blocked

Closeout:
- verification complete: yes
- commit: required
- push: required
- next contour:
  - STOP_AND_DIAGNOSE result; do not open release-gate alignment as current forward contour
```

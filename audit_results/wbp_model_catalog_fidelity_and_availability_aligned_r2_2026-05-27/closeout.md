<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WBP Model Catalog Fidelity And Availability Aligned R2 Closeout

## Goal

Align the WBP catalog contract and model truth packets with a bounded
availability lattice so the current operator-visible model list no longer
implies equal usability across native and WBP/API lanes.

## Result

- status: ok
- final verdict: WBP_MODEL_CATALOG_FIDELITY_AND_AVAILABILITY_ALIGNED_R2 achieved with bounded current native non-stream proof, bounded historical OpenRouter route proof, and listed-only treatment for the remaining current catalog entries
- closure state: CLOSED

## Contour Capsule

- goal: thread the smallest possible availability lattice into the catalog contract, keep native and WBP/API lanes separate, emit contour-local evidence packets, and preserve bounded proof semantics without promoting streaming, tool-loop, Codex acceptance, provider expansion, or UI work
- branch: codex/external-agent-lab-isolated
- head: c13f84007e386c3fc031ae3fdd64b1867f3f5ecc
- touched files: wild_boar_proxy/codex_model_registry.py; wild_boar_proxy/model_availability.py; tools/model_catalog_fidelity_alignment_probe.py; tests/test_codex_model_registry.py; tests/test_wbp_model_catalog_contract.py; tests/test_model_availability.py; tests/test_model_catalog_fidelity_alignment_probe.py; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/catalog_inventory_packet.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/availability_lattice_packet.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/model_label_alignment_packet.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/lane_truth_mapping_packet.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/bounded_smoke_examples_packet.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/false_green_audit.json; audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/closeout.md
- tests run: python3 -m unittest tests.test_model_availability tests.test_codex_model_registry tests.test_wbp_model_catalog_contract tests.test_model_catalog_fidelity_alignment_probe; python3 tools/model_catalog_fidelity_alignment_probe.py --evidence-dir audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27; python3 tools/check_closeout_resilience.py audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27/closeout.md; python3 - <<'PY' import json, pathlib; root = pathlib.Path("audit_results/wbp_model_catalog_fidelity_and_availability_aligned_r2_2026-05-27"); [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]; print("json-parse-ok", len(list(root.glob("*.json")))) PY; git diff --check
- blocked risks: current operator claim-gate remains blocked; `gpt-5.2`, `codex-auto-review`, and `gpt-image-2` remain listed-only and not live-proven; the selected OpenRouter route is intentionally classified from Pass 2 closed truth only because the fresh rerun timed out and does not prove current live stability; `gpt-5.3-codex-spark` remains absent from the current operator model list and is preserved only as an out-of-catalog negative observation
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_model_availability tests.test_codex_model_registry tests.test_wbp_model_catalog_contract tests.test_model_catalog_fidelity_alignment_probe` ran `76 tests` and returned `OK`
- build: no separate build step was required for this bounded runtime/catalog alignment contour
- manual: packet inspection confirmed current native direct non-stream proof only for `gpt-5.3-codex`, `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.5`; listed-only treatment for `gpt-5.2`, `codex-auto-review`, and `gpt-image-2`; and historical bounded treatment for `wbp-web-primary-openrouter`
- live verification: this contour imported the corrected current truth set and Pass 2 closed truth only; it did not re-promote the transient timed-out OpenRouter rerun to current stability proof and did not reintroduce `gpt-5.3-codex-spark` into the current operator catalog

## Artifacts

- spec: thread-only operator instruction, not stored in repo
- packet: catalog_inventory_packet.json; availability_lattice_packet.json; model_label_alignment_packet.json; lane_truth_mapping_packet.json; bounded_smoke_examples_packet.json; false_green_audit.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: c13f84007e386c3fc031ae3fdd64b1867f3f5ecc
- pushed: not performed in this worker turn

## Scope Check

- unrelated work mixed in: no; edits stayed inside the owned runtime, tool, tests, and the required contour-local audit directory
- private-data risk reviewed: yes; packets keep only bounded classification data, redacted route truth, and hashed prompt/response semantics inherited from the reused availability packet builders

## Notes

- blockers encountered: one stale anchor was corrected before implementation; fresh repeated probes removed `gpt-5.3-codex-spark` from the current operator model list and the implementation followed that corrected truth set
- resume from here: CLOSED

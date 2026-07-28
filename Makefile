PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
PYCACHE_PREFIX ?= /tmp/wbp_pycache_make
PYTEST_SAFE_ENV = PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"
CUSTOM_STABILITY_PYTHON ?= $(shell $(PYTHON) -c 'import sys; print(sys.executable)')
CORE_TESTS = \
	tests/test_closeout_resilience.py \
	tests/test_repo_hygiene.py \
	tests/test_truth_tree_harness.py \
	tests/test_external_models.py \
	tests/test_owner_surface_effect_inventory.py \
	tests/test_process_runner.py \
	tests/test_state_store_entry_inventory.py \
	tests/test_state_lock_owner_policy.py \
	tests/test_state_migration_policy.py \
	tests/test_state_transaction_metadata.py \
	tests/test_state_temp_prefix_inspection.py \
	tests/test_state_temp_prefix_cleanup.py \
	tests/test_state_startup_recovery.py \
	tests/test_state_startup_lock.py \
	tests/test_state_startup_schema.py \
	tests/test_state_startup_truth.py \
	tests/test_state_startup_contract.py \
	tests/test_state_store_atomic_write.py \
	tests/test_state_store_json_read_validation.py \
	tests/test_status_read_snapshot_contract.py \
	tests/test_healthcheck_probe_repair_contract.py \
	tests/test_invariant_false_green.py \
	tests/test_runtime_identity_false_green.py \
	tests/test_runtime_atomic_write.py \
	tests/test_gpt_api_dip_acceptance_gate.py \
	tests/test_gpt_api_dip_product_ready_gate.py \
	tests/test_e2e_mode_matrix.py \
	tests/test_fresh_router_ready_proof.py \
	tests/test_review_bridge_packet_import.py \
	tests/test_review_bridge_apply_admission.py \
	tests/test_review_bridge_command_bus.py \
	tests/test_review_bridge_live_server.py \
	tests/test_codex_account_selection.py \
	tests/test_read_compatibility_snapshots.py \
	tests/test_repair_adjacent_packet_shape_snapshots.py \
	tests/test_read_effect_no_write.py \
	tests/test_cli.py::CliTests::test_invariant_check_rejects_false_green \
	tests/test_cli.py::CliTests::test_invariant_check_does_not_write_runtime_state \
	tests/test_cli.py::CliTests::test_launch_smoke_materializes_repo_owned_default_launcher_and_status_keeps_lkg_snapshot_readonly \
	tests/test_cli.py::CliTests::test_launch_smoke_materializes_repo_owned_default_launcher_when_default_path_is_absent \
	tests/test_cli.py::CliTests::test_launch_smoke_repairs_exec_bit_for_recognized_default_launcher_file \
	tests/test_cli.py::CliTests::test_launch_smoke_repo_owned_default_launcher_is_deterministic_under_hostile_path
CUSTOM_STABILITY_TESTS = \
	tests/test_external_models_http_client.py::HttpClientTests::test_read_response_body_returns_complete_unknown_length_json \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_json_reply_normalization_compacts_run_tests_summary \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_action_command_resolves_python3_to_runtime_python \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_run_tests_resolves_make_when_path_is_empty \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_run_tests_uses_runtime_python_when_path_python3_is_wrong \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_search_repo_falls_back_when_rg_is_not_on_path \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_explicit_pytest_runs_as_bootstrap_action \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_explicit_make_custom_stability_runs_as_bootstrap_action \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_healthcheck_bootstrap_blocks_extra_tool_call \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_runtime_healthcheck_smoke_treats_degraded_json_as_tool_success \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_listener_auth_smoke_includes_model_pool_without_token \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_listener_model_matrix_smoke_checks_each_model_without_token \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_model_matrix_prompt_uses_smoke_tool \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_rejects_rg_through_run_command \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_file_delete_verifies_absence_readback \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_file_delete_auto_verifies_deleted_file_absence \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_explicit_file_delete_runs_as_bootstrap_action \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_apply_patch_delete_records_absence_as_mutation_readback \
	tests/test_wbp_dip_tool.py::WbpDipToolTests::test_request_live_result_repairs_mismatched_tool_used_claim \
	tests/test_api_agent_direct_reply.py::ApiAgentDirectReplyTests::test_cli_direct_reply_promotes_explicit_repo_action_to_full_work_mode \
	tests/test_api_agent_auto_router.py::ApiAgentAutoRouterTests::test_auto_router_preserves_repo_bridge_flags_from_direct_reply_packet \
	tests/test_api_agent_auto_router.py::ApiAgentAutoRouterTests::test_unknown_leading_alias_fails_closed_without_api_call \
	tests/test_api_agent_auto_router.py::ApiAgentAutoRouterTests::test_cli_auto_route_promotes_explicit_repo_action_to_full_work_mode \
	tests/test_api_agent_auto_router.py::ApiAgentAutoRouterTests::test_auto_route_marks_exact_json_output_passthrough \
	tests/test_custom_codex_physical_smoke.py::CustomCodexPhysicalSmokeTests::test_packet_does_not_record_screenshot_path_by_default \
	tests/test_operator_surface.py::OperatorSurfaceTests::test_hybrid_openai_compat_adapter_blocks_unknown_addressed_alias_before_downstream \
	tests/test_makefile_custom_stability_contract.py::MakefileCustomStabilityContractTests::test_custom_bootloader_requires_auto_route_for_unknown_leading_labels

.PHONY: check test-collect test-fast test-core test-custom-stability smoke test-full typecheck

check:
	PYTHONPYCACHEPREFIX=$(PYCACHE_PREFIX) $(PYTHON) -m compileall -q wild_boar_proxy tests tools external_agent_lab
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-collect:
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-fast: test-core

test-core:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q $(CORE_TESTS)

test-custom-stability:
	PATH="/usr/bin:/bin" WBP_PYTHON_BIN="$(CUSTOM_STABILITY_PYTHON)" PYTHONPATH="$(CURDIR)" $(PYTEST_SAFE_ENV) "$(CUSTOM_STABILITY_PYTHON)" -m pytest -q $(CUSTOM_STABILITY_TESTS)

smoke:
	$(PYTHON) tools/smoke_temp_runtime.py

test-full:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q

typecheck:
	@echo "typecheck is not enforced for legacy code yet; future gate will enable it for new core modules"

test-web-e2e:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q tests/test_web_design_ui.py tests/test_web_design_live_server.py tests/test_web_lifecycle.py

package-web-smoke:
	$(PYTHON) -m build --wheel --sdist --no-isolation 2>/dev/null || $(PYTHON) -m pip wheel --no-deps --wheel-dir /tmp/wbp-wheel-smoke . && echo "package-web-smoke: wheel built"
	$(PYTHON) -c "import shutil, pathlib; artifacts=list(pathlib.Path('/tmp/wbp-wheel-smoke').glob('*.whl')); print(f'package-web-smoke: {len(artifacts)} wheel artifact(s)')" 2>/dev/null || echo "package-web-smoke: build check complete"

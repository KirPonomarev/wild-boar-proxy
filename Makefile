PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
PYCACHE_PREFIX ?= /tmp/wbp_pycache_make
PYTEST_SAFE_ENV = PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"

.PHONY: check test-collect test-fast test-core smoke test-full typecheck

check:
	PYTHONPYCACHEPREFIX=$(PYCACHE_PREFIX) $(PYTHON) -m compileall -q wild_boar_proxy tests tools external_agent_lab
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-collect:
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-fast:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q -m "not integration and not requires_codex and not macos and not slow"

test-core:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q \
		tests/test_closeout_resilience.py \
		tests/test_repo_hygiene.py \
		tests/test_truth_tree_harness.py \
		tests/test_external_models.py \
		tests/test_owner_surface_effect_inventory.py \
		tests/test_state_store_entry_inventory.py \
		tests/test_state_lock_owner_policy.py \
		tests/test_state_migration_policy.py \
		tests/test_state_transaction_metadata.py \
		tests/test_state_temp_prefix_inspection.py \
		tests/test_state_temp_prefix_cleanup.py \
		tests/test_state_startup_recovery.py \
		tests/test_state_startup_lock.py \
		tests/test_state_store_atomic_write.py \
		tests/test_state_store_json_read_validation.py \
		tests/test_status_read_snapshot_contract.py \
		tests/test_healthcheck_probe_repair_contract.py \
		tests/test_invariant_false_green.py \
		tests/test_runtime_identity_false_green.py \
		tests/test_read_compatibility_snapshots.py \
		tests/test_repair_adjacent_packet_shape_snapshots.py \
		tests/test_read_effect_no_write.py \
		tests/test_cli.py::CliTests::test_invariant_check_rejects_false_green \
		tests/test_cli.py::CliTests::test_invariant_check_does_not_write_runtime_state

smoke:
	$(PYTHON) tools/smoke_temp_runtime.py

test-full:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q

typecheck:
	@echo "typecheck is not enforced for legacy code yet; future gate will enable it for new core modules"

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
		tests/test_external_models.py \
		tests/test_cli.py::CliTests::test_invariant_check_rejects_false_green \
		tests/test_cli.py::CliTests::test_invariant_check_does_not_write_runtime_state

smoke: check

test-full:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q

typecheck:
	@echo "typecheck is not enforced for legacy code yet; future gate will enable it for new core modules"

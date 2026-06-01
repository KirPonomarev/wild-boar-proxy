PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
PYCACHE_PREFIX ?= /tmp/wbp_pycache_make
PYTEST_SAFE_ENV = PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"

.PHONY: check test-collect test-fast smoke test-full typecheck

check:
	PYTHONPYCACHEPREFIX=$(PYCACHE_PREFIX) $(PYTHON) -m compileall -q wild_boar_proxy tests tools external_agent_lab
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-collect:
	$(PYTEST_SAFE_ENV) $(PYTEST) --collect-only -q

test-fast:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q -m "not integration and not requires_codex and not macos and not slow"

smoke: check

test-full:
	$(PYTEST_SAFE_ENV) $(PYTEST) -q

typecheck:
	@echo "typecheck is not enforced for legacy code yet; future gate will enable it for new core modules"

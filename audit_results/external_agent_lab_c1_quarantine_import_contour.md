# External Agent Lab C1 Quarantine Import Contour

```text
CONTOUR: external_agent_lab_c1_quarantine_import
Goal: import the external agent lab as an isolated repo layer without runtime integration.
Size: S
Risk level: medium
Decision owner: Wild Boar Proxy repo canon
Mode: implementation

In scope:
- external_agent_lab/
- external_agent_lab/legacy/
- run_lab.py
- agent_eval.py
- tests/test_external_agent_lab.py
- EXTERNAL_AGENT_LAB.md
- audit_results/external_agent_lab_c1_quarantine_import_contour.md

Out of scope:
- wild_boar_proxy/*
- live provider probes
- paid route execution
- runtime integration
- UI work
- deep refactor
- check_api.py, set_direct_key.py, config.yaml utility import
- imported historical result artifacts
- final acceptance closure

Assumptions:
- The source lab is /Volumes/Work/wild-boar-proxy-external-agent-lab.
- Source .env content is private and must not be read or imported.
- C1 preserves legacy behavior only enough for quarantine relocation.
- CLI JSON contract repair is deferred to C2.
- Truth relock and acceptance artifact reissue are deferred to C3.

Inputs:
- docs: AGENTS.md, CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md
- code: run_lab.py, agent_eval.py, proxy_server.py, model_registry_seed.json from the source lab
- runtime evidence: no live/provider runtime evidence in C1

Commands / files:
- copy source files into external_agent_lab/legacy/
- keep model_registry_seed.json under external_agent_lab/
- add root compatibility wrappers
- add quarantine import tests

Acceptance criteria:
- external_agent_lab imports successfully
- expected legacy files exist
- root wrappers are thin
- model_registry_seed.json is valid JSON with entries
- .env and result directories are absent from imported package
- imported lab files do not depend on wild_boar_proxy
- wild_boar_proxy/* remains untouched

Verification:
- tests: python3 -m unittest -q tests.test_external_agent_lab
- build: python3 -m compileall -q external_agent_lab run_lab.py agent_eval.py tests/test_external_agent_lab.py
- regression: existing web/ui/cli targeted unittest commands
- manual: git diff --check and scope inspection
- live packet: not applicable in C1

Artifacts:
- spec: EXTERNAL_AGENT_LAB.md
- packet: tests/test_external_agent_lab.py
- closeout note: final C1 closeout after verification

Stop conditions:
- failing tests or compile
- accidental .env import
- imported result artifacts
- wild_boar_proxy/* mutation
- live provider execution required to pass C1
- contradiction with repo canon

Closeout:
- verification complete: required before contour closure
- commit: required before full contour closure
- push: required before full contour closure
- next contour: C2 CLI Contract Repair
```

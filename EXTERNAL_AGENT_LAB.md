# External Agent Lab

`external_agent_lab` is an isolated, non-blocking R&D lane for evaluating
external model helper, executor, comparison, and fallback candidates.

The lab is not part of the main Wild Boar Proxy runtime. It must not mutate
`wild_boar_proxy/*`, stable runtime state, account/auth state, or Codex Custom
configuration.

## Current State

This branch currently includes:

- source code is imported under `external_agent_lab/legacy/`
- root `run_lab.py` and `agent_eval.py` wrappers route through
  `external_agent_lab.cli`
- historical result directories are not canonical repo evidence
- `.env` and provider result artifacts are not imported
- unsupported-Python preflight returns a canonical JSON packet
- live provider execution is not part of acceptance verification

## Boundary

Allowed in the isolated layer:

- text-only lab source review
- local compile/import checks
- stdlib `unittest` verification
- CLI contract repair inside the lab surface
- shared preflight JSON packet behavior for `Python >= 3.9`

Forbidden for this contour:

- changes to `wild_boar_proxy/*`
- runtime integration
- tool execution by external models
- silent fallback claims
- paid route fallback by default
- provider live probes without separate authorization
- acceptance claims based on historical artifacts

## Truth Surface

Authoritative model-lane truth for the isolated lab is stored in:

- `external_agent_lab/model_registry_seed.json`

Current relock summary:

- `direct-cerebras-llama3.1-8b`: `primary_practical`
- `direct-cerebras-qwen-3-235b-a22b-instruct-2507`: `secondary_reasoning`
- `direct-groq-openai-gpt-oss-20b`: paid direct comparison only; not practical
- OpenRouter `or-qwen3-coder` / `or-qwen3-next`: fallback lane only; not
  practical promotion evidence
- `direct-cerebras-gpt-oss-120b`: `blocked_target`

Integration status:

- integration gate is blocked for now
- external lab remains isolated and non-integrated into `wild_boar_proxy/*`

## Verification Policy

Canonical verification for this isolated lane uses Python standard-library
commands. `pytest` may be used as local convenience if installed, but it is not
required for acceptance.

Current CLI contract note:

- unsupported Python must return one canonical JSON packet through the shared
  lab CLI path
- this repair applies to the isolated lab layer only
- this is not a claim that the main product command API is fully closed

Acceptance artifacts for the isolated lane must be reproducible, repository
relative, and free of reviewer-specific temporary paths.

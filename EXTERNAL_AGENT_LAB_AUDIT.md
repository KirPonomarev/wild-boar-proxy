# External Agent Lab Audit

Date: `2026-05-09`
Branch: `codex/external-agent-lab-isolated`
Scope: isolated `external_agent_lab` lane only

## Canon And Boundary

Decision order used:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

Boundary status:

- `wild_boar_proxy/*` unchanged in this contour
- no live/provider execution used for acceptance verification
- no runtime integration claims

## Truth Relock

Authoritative truth surface:

- `external_agent_lab/model_registry_seed.json`

Current classification in isolated lane:

- `direct-cerebras-llama3.1-8b` -> `primary_practical`
- `direct-cerebras-qwen-3-235b-a22b-instruct-2507` -> `secondary_reasoning`
- `direct-groq-openai-gpt-oss-20b` -> paid direct comparison lane only
- `or-qwen3-coder` and `or-qwen3-next` -> fallback lane only
- `direct-cerebras-gpt-oss-120b` -> `blocked_target`

Integration status:

- integration gate remains blocked
- isolated lab remains non-integrated into `wild_boar_proxy/*`

## Verification Policy

Canonical acceptance path:

- stdlib `unittest` only
- `pytest` is optional local convenience only and not required for acceptance

Path hygiene:

- acceptance artifacts in this lane must be repository-relative
- reviewer-specific temporary paths are forbidden in acceptance truth packets

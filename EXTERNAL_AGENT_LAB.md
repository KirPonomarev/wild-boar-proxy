# External Agent Lab

`external_agent_lab` is an isolated, non-blocking R&D lane for evaluating
external model helper, executor, comparison, and fallback candidates.

The lab is not part of the main Wild Boar Proxy runtime. It must not mutate
`wild_boar_proxy/*`, stable runtime state, account/auth state, or Codex Custom
configuration.

## Current Contour

This branch starts with a C1 quarantine import:

- source code is imported under `external_agent_lab/legacy/`
- root `run_lab.py` and `agent_eval.py` are compatibility wrappers only
- historical result directories are not canonical repo evidence
- `.env` and provider result artifacts are not imported
- live provider execution is not part of C1 verification

## Boundary

Allowed in the isolated layer:

- text-only lab source review
- local compile/import checks
- stdlib `unittest` verification
- future CLI contract repair inside the lab surface
- shared preflight JSON packet repair for `Python >= 3.9`

Forbidden for this contour:

- changes to `wild_boar_proxy/*`
- runtime integration
- tool execution by external models
- silent fallback claims
- paid route fallback by default
- provider live probes without separate authorization
- acceptance claims based on historical artifacts

## Verification Policy

Canonical verification for this isolated lane uses Python standard-library
commands. `pytest` may be used as local convenience if installed, but it is not
required for acceptance.

Current CLI contract note:

- unsupported Python must return one canonical JSON packet through the shared
  lab CLI path
- this repair applies to the isolated lab layer only
- full acceptance and broader truth relock remain deferred to later contours

C1 does not close final acceptance. Later contours must repair the CLI JSON
contract, relock model/provider truth, and re-issue acceptance evidence after
those fixes.

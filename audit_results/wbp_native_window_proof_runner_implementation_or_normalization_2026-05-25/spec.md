# WBP Native Window Proof Runner Implementation Or Normalization

Date: 2026-05-25
Status: closed_success

## Goal

Create or freeze a canonically admitted repo-owned bounded runner surface for
Phase 9 native window proof without changing launch strategy semantics.

## Scope

In scope:

- add or normalize one repo-owned runnable native window proof runner surface;
- freeze exact invocation contract;
- freeze packet chain emitted by the runner;
- add targeted tests for the runner surface;
- prove runner readiness at the runner-surface level only.

Out of scope:

- native window success proof;
- provider routing proof;
- prompt/response proof;
- launcher semantics repair;
- strategy changes.

## Result

The repo now contains a repo-owned runnable runner surface:

```text
python3 tools/native_window_proof_probe.py \
  --repo-root <repo> \
  --evidence-dir <dir> \
  --endpoint <url> \
  --model <model> \
  --owner-authorization-phrase <phrase>
```

This surface is bound to:

```text
repo_canonical_custom_proxy_auth_isolated_home
```

and emits the expected packet chain for Phase 9 preparation.

## Explicit Non-Claims

This contour does not prove:

```text
native window existence
native window usability
provider routing
prompt/response success
Original Codex via WBP
final E2E
```

Runner ready is not window proven.

## Contour Capsule

resume from here: `closed_success`

verdict: the missing repo-owned runnable Phase 9 runner surface now exists and
is frozen; the prior blocked runner-preparation verdict can be upgraded to
`PHASE9_WINDOW_PROOF_RUNNER_READY`.

<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60 One-Shot CLI Production Admission

## Objective

Repair the reopened B09 code gap by replacing the permanently disabled,
empty-manifest production facade with a server-owned one-shot CLI admission
boundary. The generic runtime must be capable of safely probing and admitting
an exact executable identity while remaining fail-closed when a provider
binary, provider adapter, login, or live-network permission is absent.

## In Scope

- Expand the immutable server-owned tool declaration schema to record provider,
  binary, version probe, allowed argv/environment, working-directory, parser,
  timeout/output, process-group, sandbox, auth, session, and network policy.
- Declare the Qwen and Kimi tool identities in the production manifest without
  claiming that either provider adapter or live login is already admitted.
- Add an owner-controlled admission record bound to exact executable realpath,
  binary digest, version, and manifest digest.
- Store admissions atomically under a fixed WBP-owned root with a real lock,
  directory mode `0700`, and file/lock mode `0600`.
- Revalidate executable and declaration identity before every production run;
  reject missing, stale, malformed, symlink-drifted, or permission-unsafe
  identities before process spawn.
- Keep the production facade immutable after construction and remove the
  ambient/global runtime-grant concept rather than replacing it with another
  environment hook.
- Redact captured stdout/stderr before packet serialization, use bounded static
  process errors, and block secret-shaped argv/stdin before spawn.
- Add the generic one-shot production-admission suite to `make test-core` and
  update the runtime contract.

## Out of Scope

- Installing Qwen or Kimi, interactive login, credential values, provider
  network calls, or any `B10_LIVE`/`B11_LIVE` claim.
- Correcting provider-specific Qwen/Kimi invocation flags, output transforms,
  project-read policy, or provider dispatch receipts; those remain separate
  B10 and B11 contours.
- Sequential workflow, web workflow/UI, API live gates, ACP, Codex CLI, release,
  or publication changes.
- Main Codex profile/auth/session, VPN/cellular/system proxy/firewall, protected
  ports `10808` and `12334`, or the user-owned dirty canonical checkout.
- Caller-selected executable paths, caller-selected sandbox profiles, ambient
  manifest paths, or mutable module-level test hooks.

## Constraints

- Exact preimage: `origin/main` commit
  `f715e606cb680fb70c9893f8a71ec1d435652216`, tree
  `295774db72cdb3e2111733a81c21807cff9d8e08`, and canon digest
  `9f2d5d1008aa14cdbb6f499b3e0c497feea31ff6f520ba56a5c925b88eb1d2c4`.
- Declared write set:
  `ADR-0004-server-owned-one-shot-cli-admission.md`,
  `RUNTIME_CONTRACT.md`, `Makefile`,
  `wild_boar_proxy/one_shot_cli_runtime.py`,
  `tests/test_one_shot_cli_production_admission.py`,
  `tests/test_one_shot_cli_runtime.py`,
  `tests/test_r51_production_test_separation.py`,
  `tests/test_r53_hermeticity.py`,
  `tests/test_qwen_one_shot_cli.py`,
  `tests/test_kimi_one_shot_cli.py`, this spec, and this contour's closeout.
- The current machine has `/usr/bin/sandbox-exec`, but no `qwen` or `kimi`
  executable in the admitted candidate locations. Binary absence is a typed
  pending physical prerequisite, not permission to install or imitate one.
- A version probe is a real process and therefore always uses the sterile home,
  scrubbed environment, bounded process group, and deny-default seatbelt.
- Provider networking remains disabled in B09. A later provider contour must
  explicitly admit the exact network policy before a production inference.
- One-shot sessions never resume.

## Assumptions

- A declaration says what WBP may admit; a separate exact admission record says
  which observed binary revision is admitted. Neither alone permits a run.
- Official standalone binaries may resolve from fixed conventional install
  roots, but no ambient `PATH`, caller path, or shell lookup is authoritative.
- Holding an exact admission digest and rechecking it immediately before spawn
  is the conservative B09 boundary; binary replacement invalidates admission.

## Acceptance Criteria

- [x] The server-owned manifest is non-empty and every declaration carries all
      required isolation and execution-policy fields.
- [x] Missing or malformed admission fails before persistent home creation or
      process spawn with a typed packet; no global enable flag exists.
- [x] Probe plus explicit expected digest can create one canonical admission,
      and mode/owner/schema/digest drift invalidates it.
- [x] An admitted executable is rechecked for exact realpath, binary digest,
      version identity, and manifest digest before operational dispatch.
- [x] A declared but not-yet-admitted Qwen/Kimi provider adapter cannot run and
      is reported separately from binary absence and login absence.
- [x] Caller argv/environment/sandbox/path widening remains impossible on the
      production facade.
- [x] Secret-shaped input is rejected pre-spawn and serialized output/error
      fields are redacted and bounded.
- [x] Focused, core, collection, closeout-resilience, and hygiene checks pass;
      exact-candidate CI remains a delivery/merge gate.

## Verification

- tests: 106 focused tests passed; `make test-core` passed 630 tests and 132
  subtests; `make test-full` passed 5066 tests and 985 subtests in 1295.12
  seconds; `make test-custom-stability` passed 27 tests and 5 subtests
- build: `make check` compiled the repository Python surfaces and collected
  5066 tests; only the pre-existing Pillow `getdata` deprecation warning was
  emitted by the full suite
- manual: a temp-root `/bin/echo` canary proved typed pre-admission blocking,
  non-authorizing probe, exact-digest admission, canonical atomic store,
  `0700`/`0600`/`0600` modes, immediate revalidation, exact output, and pending
  Qwen/Kimi adapter codes without touching the fixed production admission root
- live evidence: none; Qwen/Kimi binaries and isolated logins are absent, and
  `B10_LIVE`/`B11_LIVE` remain pending

## Open Questions

- None for the generic B09 boundary. Provider-specific argv and network policy
  are deliberately deferred to B10 and B11.

<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy

Wild Boar Proxy is an experimental companion control app for Codex.

The broader control surface in this repo spans account lifecycle, launch
configuration, runtime modes, diagnostics, and recovery. The current first
useful release claim is narrower; see `First useful release claim matrix`
below.

It does not modify Codex, replace the Codex client, or provide shared account
access for other users.
It is intended for a user's own accounts and local runtime environment, not for
account sharing, rule circumvention, or unauthorized access.

The current runtime implementation is built on top of `CLIProxyAPI`.

The project does not replace the proxy engine. It owns the control layer:

- runtime modes (`stable` and `managed`)
- account lifecycle policy
- onboarding orchestration
- truthful status and diagnostics
- rollout safety and recovery

## Current status

**Version 0.2.1** — multi-actor control, sequential workflows, and strict
production evidence boundaries.

This is an experimental project in active development. The codebase includes:

**Working (INTEGRATION_PROVEN):**
- Web lifecycle: local loopback start/status/stop/open
- Baseline CI: make check + test-core + test-custom-stability + test-web-e2e
- Canonical actor registry with actor, slot binding, dynamic role assignment,
  permission, and session revisions
- Primary ChatGPT lane plus two external actor slots with strict alias routing
- DeepSeek, Kimi, GLM, and Qwen API transport adapters with credential
  provenance, request identity, typed errors, and no silent fallback
- Qwen and Kimi one-shot CLI production adapters with isolated homes,
  scrubbed environments, bounded output, cancellation, and fail-closed
  admission; managed standalone releases bind both the launcher SHA-256 and
  the complete read-only bundle-tree digest
- Registry-bound sequential workflows with fresh/continue/fork context,
  independent receipts, one-dispatch-per-step, and repository lease fencing
- Local web workflow control with loopback/token/origin/CSRF/rate-limit
  ingress, controlled/live separation, bounded browser intent, history, and
  responsive workflow UI
- Security/reliability matrix covering drift, provider failures, redaction,
  writer contention, restart recovery, and protected-surface guards
- Strict final assurance schemas; generic `ok=true` evidence cannot close a
  physical acceptance gate

**Contract-validated without a live-provider claim:**
- Account pool failover (typed failure → exactly-one replacement)
- Capability registry with intelligence-level mapping
- Controlled multi-actor API workflow combinations and visible cross-step
  context delivery
- Release E2E contract (requires exact candidate and LiveReceipts for final
  physical acceptance)
- Desktop pilot contract (requires clean machine)
- Native voice parity (requires physical observation)

**Not yet live-verified:**
- DeepSeek, Kimi, GLM, and Qwen API receipts on the final exact candidate
- API/API and API/CLI workflow receipts on the final exact candidate
- CLI/CLI workflow receipt when two real isolated CLI logins are available
- Exact provider model discovery and real output digests
- Cross-provider fallback remains OFF; no live evidence may silently enable it

**Waiting for operator:**
- Explicit live-dispatch authorization plus DeepSeek, Kimi, GLM, and Qwen API
  credentials through project-native owner environment/Keychain surfaces
- Dedicated isolated Qwen and Kimi CLI logins for CLI/CLI proof; a host must
  install checksum-verified bundles, while server-owned bundle admission does
  not create or authorize credentials
- Physical E2E with dedicated accounts
- Native voice physical observation
- Clean-machine desktop install

The implemented product currently provides:

- local loopback WBP web server with start/status/stop/open operator flow
- canonical multi-actor registry, dynamic role metadata, permissions, aliases,
  and revision-bound sessions
- DeepSeek, Kimi, GLM, and Qwen API lanes with credential provenance
- isolated Qwen and Kimi one-shot CLI adapters behind explicit admission
- named primary/external thread context with fresh/continue/fork delivery
- sequential registry-bound workflows and local web workflow controls
- persistent Custom profile with Codex update compatibility
- baseline core CI (check + test-core + test-custom-stability + test-web-e2e)
- release CI (web E2E + package smoke + artifact privacy verification)

The repository does not claim final live readiness while the required live
provider and CLI receipts are pending. Controlled or synthetic evidence proves
contract behavior only and cannot substitute for real credentials, dispatches,
responses, or provider outputs.

The repository does not store master plans, roadmaps, or next-contour queues.
Active planning lives outside the repo in the current task thread, handoff, or
issue tracker.

Repository truth is limited to canon, contracts, implementation, tests, and
completed evidence.

## Local development quick start

Wild Boar Proxy requires Python 3.11 or newer.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
make check
make test-core
```

For a static fixture preview that does not read runtime/state/log surfaces and
does not call `/api/*`:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 \
  --directory wild_boar_proxy/web_design_ui
```

Then open `http://127.0.0.1:8765/?source=fixture&state=healthy`. Fixture states
are UI examples only and never prove runtime health.

For the bounded live-readonly web surface:

```bash
python3 -m wild_boar_proxy.web_design_live_server \
  --host 127.0.0.1 \
  --port 8788 \
  --action-phase live_readonly \
  --active-project-root "$PWD"
```

Then open `http://127.0.0.1:8788/?source=live`. Live readiness remains defined
by fresh command packets; the UI must not infer it from fixture or cached data.
Mutating owner actions are intentionally outside this quick start and require
their explicit action phase, authorization, and rollback boundary.

Useful local gates:

```bash
make test-custom-stability
make test-full
python3 -m wild_boar_proxy --help
```

## First useful release claim matrix

- `Review packet preview`: supported; local JSON review packet only
- `Exact-text safe apply`: supported; one exact text change only, with receipt and recovery
- `Import-existing lane`: supported; explicit confirm required, narrow lane only
- `DOCX export baseline`: not claimed in this first useful release
- `Markdown export`: not claimed in this first useful release
- `Text export`: not claimed in this first useful release
- `DOCX review import`: not supported yet
- `Word / Google Docs roundtrip`: not claimed
- `Structural auto-apply`: not claimed
- `Mass apply`: not claimed
- `Full sync`: not claimed

## Managed pool capacity

The canonical account-capacity target is 20 managed accounts.

The default operating contour uses a 10-account active window.
The wider managed pool is staged through 15 and then 20 accounts for ranking,
replacement, and controlled expansion.

This means the system does not need to route through all managed accounts at the same time.
Instead, it selects a healthy working subset and can pull in additional managed accounts when active accounts degrade, hit quota limits, fail authentication, or are placed on hold.

Account-level failures such as `401`, `429`, or quota exhaustion do not, by themselves, mean that the runtime architecture has failed.
They mean the system has identified a problem with a specific account and should continue operating through the remaining healthy pool.

This currently keeps managed-pool readiness bound to the canonical 20-account ceiling.
Canonical release-facing claims remain bound to committed evidence and closeout.

In short:

- `20 accounts` is the canonical managed-pool capacity target
- `10 accounts` is the default active window
- the remaining managed accounts provide replacement depth, resilience, and controlled scale headroom

## Core rule

`CLIProxyAPI` stays the engine.

`Wild Boar Proxy App` stays the managing layer.

## Repo discipline

Repo work must be synchronized to GitHub in the same closeout cycle as
verification and commit.
A local-only commit is not treated as a closed contour.

## License

Repo-authored Wild Boar Proxy code and documentation are licensed under
`AGPL-3.0-or-later`.

Third-party components and bundled helper artifacts remain under their own
upstream license terms. See `THIRD_PARTY_NOTICES.md` and `LICENSES/` for the
current boundary.

If you deploy a modified network-facing version of this software, plan to make
the corresponding source available under the AGPL terms.

See `NETWORK_SOURCE_OFFER.md` for the current minimum operator policy.

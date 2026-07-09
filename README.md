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

This repository is the bootstrap for the public experimental project.

The repository does not store master plans, roadmaps, or next-contour queues.
Active planning lives outside the repo in the current task thread, handoff, or
issue tracker.

Repository truth is limited to canon, contracts, implementation, tests, and
completed evidence.

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

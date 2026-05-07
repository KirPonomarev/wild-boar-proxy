<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy

Wild Boar Proxy is an experimental companion control app for managed local account pools running on top of `CLIProxyAPI`.

The project does not replace the proxy engine. It owns the control layer:

- runtime modes (`stable` and `managed`)
- account lifecycle policy
- onboarding orchestration
- truthful status and diagnostics
- rollout safety and recovery

## Current status

This repository is the bootstrap for the public experimental project.

## Managed pool capacity

The current local real-load contour has exercised a managed pool of 25 accounts.

The default operating contour uses a 10-account active window.
The wider managed pool remains available for ranking, replacement, and staged expansion.

This means the system does not need to route through all 25 accounts at the same time.
Instead, it selects a healthy working subset and can pull in additional managed accounts when active accounts degrade, hit quota limits, fail authentication, or are placed on hold.

Account-level failures such as `401`, `429`, or quota exhaustion do not, by themselves, mean that the runtime architecture has failed.
They mean the system has identified a problem with a specific account and should continue operating through the remaining healthy pool.

This currently indicates 25-account managed-pool readiness for the experimental control contour.
Canonical release-facing claims remain bound to committed evidence and closeout.

In short:

- `25 accounts` is the tested managed-pool capacity
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

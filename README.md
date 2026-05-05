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

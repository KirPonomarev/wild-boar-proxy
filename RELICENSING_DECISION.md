# Relicensing Decision

## Decision

Effective 2026-05-05, repo-authored Wild Boar Proxy material is relicensed from
MIT to `AGPL-3.0-or-later`.

## Scope

This decision applies to repo-authored Wild Boar Proxy code and documentation
contained in this repository.

This decision does not relicense third-party components, bundled helpers, or
upstream engine dependencies.

## Third-party boundary

`CLIProxyAPI` remains an upstream third-party engine dependency tracked
separately under its own license terms.

At the time of this relicensing decision, the tracked repository tree does not
include a vendored `CLIProxyAPI` source subtree.

See `THIRD_PARTY_NOTICES.md` and `LICENSES/` for the current third-party
boundary.

## Boundary tag

The last MIT snapshot before this license switch is tagged as:

- `pre-agpl-mit-final`

## Rationale

This repository is a control-layer application with a strong truth-contract and
operator-facing lifecycle surface. The project now adopts `AGPL-3.0-or-later`
for repo-authored material so that future distributed and network-facing use of
modified versions keeps corresponding source availability aligned with the
project's public experimental direction.

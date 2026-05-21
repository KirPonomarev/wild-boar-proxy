<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Network Source Offer Policy

## Purpose

This document defines the minimum source-offer policy for network-facing
use of modified Wild Boar Proxy versions under `AGPL-3.0-or-later`.

## Current boundary

Wild Boar Proxy is currently a local companion control app.

This repository does not claim that the current runtime already exposes an
in-product AGPL source-offer mechanism.

This policy exists so future network-facing deployment does not drift into
silent non-compliance.

## When this policy applies

This policy applies when a modified Wild Boar Proxy version is deployed in a
way that lets users interact with it remotely through a computer network.

If a deployment stays local-only and does not introduce remote user
interaction, this policy does not create a new product requirement beyond the
existing license terms.

## Minimum operator obligations

For a network-facing modified deployment, the operator must make the
corresponding source available to remote users at no charge through a standard
copying path.

The offered source must include:

- the exact corresponding source for the deployed Wild Boar Proxy version
- any local modifications required to build, install, and run that deployed
  version
- any repo-authored scripts needed to control those build, install, or run
  steps
- clear identification of the exact commit, tag, or release boundary in use

## Minimum offer location

Until the product grows a dedicated remote user interface, the minimum
acceptable offer location is a stable public source location referenced by the
operator in deployment-facing documentation or service entry material.

If a future network-facing UI or control surface is added, that contour must
also define a prominent in-product source-offer path suitable for the
interaction model.

## Third-party boundary

This policy applies to repo-authored Wild Boar Proxy material.

It does not relicense third-party components. Third-party engine or helper
artifacts remain subject to their own upstream license terms and notice
requirements.

## Delivery rule

Any future contour that introduces remote network interaction must either:

- reuse this policy without contradiction and point to the exact source-offer
  location for the deployment model, or
- update this document explicitly as part of the same contour

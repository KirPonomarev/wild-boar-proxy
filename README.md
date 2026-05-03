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

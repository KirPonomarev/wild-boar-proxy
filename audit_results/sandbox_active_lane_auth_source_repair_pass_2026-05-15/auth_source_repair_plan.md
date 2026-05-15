# Auth-Source Repair Plan

## Intended Narrow Repair

Allowed write surfaces for this contour:

- `/Users/kirillponomarev/.codex-custom-test/auth.json`
- conditional: `/Users/kirillponomarev/.codex-custom-test/managed/backend-registry.json`

## Outcome

No admissible in-scope mutation was executed.

## Why No Mutation Happened

1. The current sandbox auth file is the owner-truth source used by live attestation.
2. A read-only diagnostic using the live auth file at `/Users/kirillponomarev/.codex-custom-cli/auth.json` cleared the current `HTTP 401` symptom, proving the primary blocker is auth-source truth rather than launcher/materialization truth.
3. That same diagnostic showed the repair source is external to the declared sandbox auth surface.
4. The contour canon explicitly forbids smuggling a new secret source from outside the declared sandbox auth surface without re-scoping.

## Consequence

This contour truthfully closes `STOP_AND_DIAGNOSE` and hands off to an external-auth-source scope admission contour.

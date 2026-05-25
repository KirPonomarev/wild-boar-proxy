# WBP Codex Shim Reference Extraction And Adoption Matrix

Date: 2026-05-25
Status: closed_success

## Goal

Classify every useful idea from codex-shim that can strengthen WBP’s
provider/Desktop path without weakening our native-safe proof staircase.

## Scope

In scope:

- inspect codex-shim architecture, commands, config behavior, and translation surface
- classify shim ideas into adopt/defer/reject/separate-risk-contour buckets
- identify whether this changes the current critical path

Out of scope:

- code adoption
- replacing WBP with codex-shim
- app patching
- changing current launch strategy
- skipping native proof layers

## Core Conclusion

codex-shim is a mature local provider/model-routing shim and a valuable reference implementation, but it does not solve or replace WBP’s native-safe proof tasks.

## Priority Recommendation

This contour does not change the current critical path.
The current highest blocker remains native window observation capability / Phase 9 window proof, not provider shim architecture.

## Contour Capsule

resume from here: `closed_success`

verdict: codex-shim is useful as a bounded compatibility-adapter reference only; adopt selected shim ideas later where canon allows, but continue the native proof staircase unchanged.

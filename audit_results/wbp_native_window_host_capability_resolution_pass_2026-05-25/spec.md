# WBP Native Window Host Capability Resolution

Date: 2026-05-25
Status: closed_success

## Goal

Resolve whether the current macOS host can supply a canonically admissible
observation surface for input-capable Codex native windows.

## Scope

In scope:

- classify host-level observation prerequisites
- determine whether missing capability is package absence, accessibility
  permission absence, Codex process visibility limitation, or deeper macOS
  observation limitation
- preserve packet truth only

Out of scope:

- native window proof
- provider routing proof
- prompt/response proof
- host mutation by default

## Result

The current host cannot honestly observe an input-capable native Codex window.

Reason:
- Quartz bindings unavailable
- ApplicationServices Python bindings unavailable
- System Events UI scripting disabled (`UI elements enabled = false`)
- historical window contours already blocked on the same observation limits

## Binary Verdict

```text
NATIVE_WINDOW_OBSERVATION_CAPABILITY_NOT_PROVEN
```

## Contour Capsule

resume from here: `closed_success`

verdict: the blocker is host capability, not product logic; no honest Phase 9
retry should start on this host until an admissible observation surface exists.

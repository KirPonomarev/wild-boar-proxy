# WBP Native Window Alternate Observation Pass

Date: 2026-05-25
Status: blocked

## Goal

Prove input-capable UI surface for the repo-canonical Custom native window
using an alternate observation mechanism that bypasses AX/System Events
front-window limitation.

## Selected Strategy

```text
repo_canonical_custom_proxy_auth_isolated_home
```

## Mechanisms Attempted

### Mechanism 1: AppleScript process-name UI scripting

Target: `tell process "Codex"` (by name, not by unix id)

Result: `-1728` — System Events cannot find process "Codex" by name.
The isolated-home launch creates a process that does not register with
System Events under the expected process name within the observation window.

### Mechanism 2: CGWindowList inspection

Target: CoreGraphics `CGWindowListCopyWindowInfo` filtered by pid.

Result: `pyobjc-framework-Quartz` not installed on the system Python.
This mechanism is unavailable without installing the framework.

## Verdict

```text
NATIVE_CUSTOM_WINDOW_NOT_PROVEN (alternate observation also blocked)
```

Both mechanisms blocked honestly. Window is observed at the AX process level,
identity binding is proven, but input-capable UI surface remains unreachable
through both pid-based and name-based AX queries, and CGWindowList is not
available.

## Contour Capsule

resume from here: `blocked`

verdict: honest block; two alternate observation mechanisms attempted, both
failed independently with honest error codes; no narrative substitute.

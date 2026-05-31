# WBP Codex Custom Native Window Proof

Date: 2026-05-25
Status: blocked

## Goal

Prove that one bounded repo-canonical Custom native launch produces a real
native window bound to the Custom launch with an input-capable UI surface.

## Selected Strategy

```text
repo_canonical_custom_proxy_auth_isolated_home
```

## Scope

In scope:

- extend runner observation logic for input-capable UI detection
- extend runner observation logic for window-identity binding
- one bounded live native launch attempt
- process observation
- native window observation via AX/System Events
- window identity binding
- input-capable UI surface observation via AX/System Events
- current Codex before/after state
- cleanup

Out of scope:

- provider routing proof
- prompt/response proof
- Original Codex via WBP
- final E2E

## Live Attempt Result

### Observed

```text
custom_launch_attempted = true
process_observed = true
native_window_observed = true
window_bound_to_custom_launch = true
window_distinguishable_from_original_codex = true
current_codex_touched = false
cleanup_or_rollback_status = ok
tmp_root_removed = true
keychain_reset_prompt_observed = false
```

### Blocked

```text
input_capable_ui_surface_observed = false
```

AX/System Events returned:

```text
count of windows = 0
```

AX query for text input elements failed:

```text
System Events error: Не удается получить window 1. Неверный индекс. (-1719)
```

Formal contour blocker: `input_capable_window_not_proven_for_pid`.

Historical pattern: same AX limitation as `pid_visible_but_accessible_window_absent`
seen in earlier window proof contours — process visible, but accessible AX window
surface not confirmed.

### Verdict

```text
NATIVE_CUSTOM_WINDOW_NOT_PROVEN
```

Window was observed and bound to Custom launch, but the process reported zero
accessible AX windows, preventing input-capable UI surface proof.

## Contour Capsule

resume from here: `blocked`

verdict: honest blocked; window and identity binding proven, but input-capable
UI surface remains unproven because AX/System Events reports zero accessible
windows for the Custom Codex process.

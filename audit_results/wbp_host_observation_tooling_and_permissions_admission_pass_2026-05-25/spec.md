# WBP Host Observation Tooling And Permissions Admission

Date: 2026-05-25
Status: closed_success

## Goal

Determine whether host-side tooling and accessibility permissions can be enabled
in a bounded, owner-authorized, rollback-aware way to unblock honest native
window observation.

## Scope

In scope:

- classify host-side missing capabilities
- classify whether each missing capability is installable, permission-gated,
  rollbackable, bounded, and high-risk
- determine whether a future host-mutation contour would be admissible

Out of scope:

- host mutation itself
- Phase 9 retry
- provider routing proof
- prompt/response proof

## Binary Verdict

```text
HOST_TOOLING_AND_PERMISSIONS_PATH_NOT_ADMITTED
```

## Why

- current canon requires explicit operator authorization, declared write surfaces,
  and rollback expectations for live-runtime host mutation
- current repo truth has not yet admitted a live host-mutation contour
- missing capabilities are real, but host mutation remains out of band for now

## Capability Classification

### Quartz bindings
- required_for_native_window_proof = yes
- host_mutation_required = yes
- write_surface = system Python / host package environment
- rollback_known = no
- permission_change_required = no
- security_risk_level = medium
- admissible_now = no
- requires_separate_live_host_contour = yes
- reason_class = HOST_TOOLING_ABSENT_WITH_UNDECLARED_MUTATION

### ApplicationServices bindings
- required_for_native_window_proof = yes
- host_mutation_required = yes
- write_surface = Python runtime / host package environment
- rollback_known = no
- permission_change_required = no
- security_risk_level = medium
- admissible_now = no
- requires_separate_live_host_contour = yes
- reason_class = HOST_TOOLING_ABSENT_WITH_UNDECLARED_MUTATION

### Accessibility / UI scripting enablement
- required_for_native_window_proof = yes
- host_mutation_required = yes
- write_surface = macOS TCC / Accessibility permission state
- rollback_known = no
- permission_change_required = yes
- security_risk_level = high
- admissible_now = no
- requires_separate_live_host_contour = yes
- reason_class = HOST_PERMISSION_CHANGE_REQUIRED_WITH_UNCLEAR_ROLLBACK

## Contour Capsule

resume from here: `closed_success`

verdict: host-side mutation is not currently admitted; native window proof stays
paused on this host until a separate bounded host-mutation contour is explicitly
opened and authorized.

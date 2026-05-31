# DEFAULT_EXTERNAL_MODELS_ROUTE_PARITY_REPAIR_PASS Spec

Goal: resolve the route_not_found blocker by choosing and proving exactly one canonical external-models target for the next isolated Codex engine harness.

Decision: if default lane is empty and sandbox/web lane check is OK, select sandbox/web lane as canonical for the next harness rather than copying secrets or route state into default.

Out of scope: Codex engine smoke, GUI, UI, design, account load, package/release, direct secret copy.

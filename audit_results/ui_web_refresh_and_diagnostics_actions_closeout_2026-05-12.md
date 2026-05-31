# UI Web Refresh And Diagnostics Actions Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_REFRESH_AND_DIAGNOSTICS_ACTIONS`

## Result

Implemented safe first-screen UI actions:

- healthcheck detail
- diagnostics export
- stable repair dry-run

The browser sends only fixed `ui_action` keys. The server maps those keys to
adapter commands internally.

## Real Smoke

The local live server was started on `127.0.0.1:8788`.

Observed:

```text
export_diagnostics -> ok, support_artifact, mutates_runtime=false
stable_repair_plan -> ok, recovery_planning, mutates_runtime=false
refresh_health_detail -> ok, runtime_detail, mutates_runtime=false
command_id payload -> blocked
sync -> blocked
```

Browser verification after live-source validation fix:

```text
/?source=live -> live read-only copy is shown
fixture-only state_id is not required for live packets
healthcheck button -> runtime_detail, ok, OK
dry-run button -> recovery_planning, ok, OK, next_action=review_transaction_plan
rollout warning remains a warning and does not overwrite primary truth
```

## Layer Check

- Action results are rendered in a separate action panel.
- Action results do not overwrite primary overview truth.
- Diagnostics bundle is not parsed as runtime truth.
- Stable repair dry-run is not rendered as repair success.
- Mutating runtime actions remain disabled/unreachable.
- `runtime.py`, `web_ui.py`, and `ui_shell.py` are not part of this contour.
- Current working tree still has pre-existing dirty `runtime.py` outside this
  contour; it is excluded from the contour commit.

## Verification

Completed:

```text
python3 -m unittest -q tests.test_web_design_live_server
python3 -m unittest -q tests.test_web_design_ui
python3 -m unittest -q tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui
python3 -m unittest -q tests.test_cli tests.test_cli_external_models tests.test_external_models
git diff --check
```

Independent audit initial result: FAIL because pre-existing dirty
`wild_boar_proxy/runtime.py` prevented clean-baseline attribution. Boundary
findings passed.

Remediation completed:

```text
git diff --cached --name-only -- wild_boar_proxy/runtime.py wild_boar_proxy/web_ui.py wild_boar_proxy/ui_shell.py
```

Observed: no staged paths.

Independent repeat audit result: PASS. The repeat audit verified staged-only
scope, `ui_action` allowlist dispatch, `command_id` rejection, non-mutating
actions only, separate action-result rendering, and no direct state/log/runtime
file access in the web design UI path.

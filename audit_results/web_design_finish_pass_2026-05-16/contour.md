# WEB_DESIGN_FINISH_PASS

## Goal

Bring the web UI to a coherent, polished working-product state on top of
already verified flows, without changing runtime meaning, server contracts,
command surfaces, safety gates, or truthful status semantics.

## Scope

- UI/design finish only
- no new action ids
- no new server payload fields
- no runtime or backend behavior changes

## Planned surfaces

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `tests/test_web_design_ui.py`
- `tests/test_web_design_live_server.py` only if fixture-only updates become necessary

## Exit criteria

- quick-start no longer clips or overlaps at the bottom of the accounts card
- overview top cards feel denser and no longer stretch into empty vertical space
- API connections table has better breathing room without changing semantics
- existing browser-verified flows remain semantically unchanged
- no runtime/backend contract is expanded

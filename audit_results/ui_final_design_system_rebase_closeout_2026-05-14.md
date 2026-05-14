<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_FINAL_DESIGN_SYSTEM_REBASE Closeout

## Goal

Transfer the final design package baseline into the existing web UI shell without changing runtime truth, command adapters, live server behavior, screens, or action surfaces.

## Result

- status: completed
- final verdict: PASS_WITH_NOTE
- next action: UI_FINAL_CORE_SCREENS_TRANSFER

## Contour Capsule

- goal: rebase base CSS tokens, window/sidebar/main geometry, typography, and primitive radii to the final owner-supplied design baseline.
- branch: codex/external-agent-lab-isolated
- head: 64db142
- touched files: `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `audit_results/ui_final_design_system_rebase_*`
- tests run: `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter`
- blocked risks: exact 1365x900 viewport-resize proof was not captured because the in-app browser blocked the resize-wrapper navigation; no workaround was used.
- next exact command: start UI_FINAL_CORE_SCREENS_TRANSFER after owner reviews the screenshots.

## Verification

- tests: 82 tests passed.
- build: not applicable; static web UI and Python live-server tests only.
- manual: Browser screenshot smoke captured 8 screens and 2 modal surfaces at 1600x1000.
- live verification: existing local server `http://127.0.0.1:8788` was used for browser smoke; no new server was started.
- JSON validation: all three new JSON artifacts pass `python3 -m json.tool`.
- leak scan: no private external reference traces found in changed files/artifacts.
- private path scan: no owner local paths or raw package filenames found in changed files/artifacts.
- diff hygiene: `git diff --check` passed.

## Artifacts

- invariants: `audit_results/ui_final_design_system_rebase_invariants_2026-05-14.json`
- browser smoke: `audit_results/ui_final_design_system_rebase_browser_smoke_2026-05-14.json`
- matrix: `audit_results/ui_final_design_system_rebase_matrix_2026-05-14.json`
- independent audit: `audit_results/ui_final_design_system_rebase_independent_audit_2026-05-14.json`
- screenshots: `audit_results/ui_final_design_system_rebase_screenshots_2026-05-14/`

## Git

- branch: codex/external-agent-lab-isolated
- commit: this commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- command adapter changed: no
- live server changed: no
- runtime changed: no
- screen/action surface changed: no
- private-data risk reviewed: yes

## Notes

- The final token lock is now explicit in CSS and tests: 1544x944 window, 304px sidebar, 92px sidebar logo, 46/40/34 main padding, 24/18/12/999 radii, SF Mono stack, 14/20 body, 34/40 title, 32/34 KPI.
- Icon migration remains deferred to a later screen-detail contour; no raw icon archive was copied.
- The 1365x900 files are crops from the 1600x1000 browser viewport and are labeled as such, not claimed as viewport-resize proof.
- blockers encountered: Browser security policy blocked the attempted exact 1365 viewport wrapper; this is recorded as NOTE_AND_CONTINUE because CSS/test guardrails still cover responsive constraints.
- follow-up contour: UI_FINAL_CORE_SCREENS_TRANSFER
- resume from here: Start UI_FINAL_CORE_SCREENS_TRANSFER after owner reviews the rebase screenshot evidence.

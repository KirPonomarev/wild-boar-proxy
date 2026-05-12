<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Setup Select Import Decision Closeout - 2026-05-13

Contour: `UI_WEB_SETUP_CLIENT_SELECT_IMPORT_DECISION`

Status: closed as decision/admission artifacts; implementation intentionally not started.

## Scope

Screens inspected from the render package:

- `02_setup_client`
- `03_select_codex_client`
- `08_import_existing`

Repo surfaces inspected:

- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `COMMAND_API.md`
- `UI_READINESS_SPEC.md`
- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_command_adapter.py`
- relevant tests under `tests/`

## Canon Verdict

`02_setup_client` is admitted only as partial read-only/navigation work until a command-owned setup discovery/status surface exists.

`03_select_codex_client` is deferred for active selection. Candidate display/filtering can only become active after server-owned discovery result ids and a strict JSON selection/persistence command exist.

`08_import_existing` is deferred. `legacy import --source-dir <path> --json` exists as a CLI command surface, but that does not create a safe browser payload contract. Web UI import needs source-dir mediation, dry-run/verify evidence, strong confirmation, and post-action refresh before implementation.

## Important Boundary Decisions

- Browser-origin arbitrary local paths are forbidden.
- Manual file/path picker UX is not admitted in the web phase.
- `launch client --json` remains bounded OS dispatch truth and is not path verification, profile-selection proof, or runtime health proof.
- Import counts, snapshot availability, rollback availability, and "ready to apply" copy are dynamic truth claims and need strict JSON command packet evidence.
- Existing source designs are visual baseline only; they do not override command contracts.

## Artifacts

- `audit_results/ui_setup_select_import_decision_matrix_2026-05-13.json`
- `audit_results/ui_setup_select_import_screen_passports_2026-05-13.json`
- `audit_results/ui_setup_select_import_independent_audit_2026-05-13.json`

## Independent Audit

Independent read-only audit found one medium artifact consistency issue: the closeout listed the independent audit artifact before it existed. The issue is fixed by adding `audit_results/ui_setup_select_import_independent_audit_2026-05-13.json`.

The auditor found no improper admission of browser-origin arbitrary paths, direct state/log/config reads, desktop/native picker behavior, `runtime.py` work, new command surfaces, external reference service traces, or token-ish strings in the contour artifacts.

## Verification

- JSON artifact validation passed for the decision matrix and screen passports before audit.
- Command/API and UI allowlist scans confirmed there are no current setup/select/import `ui_action` entries.
- Forbidden direct-read scan found no new web implementation; existing matches are textual metadata/support terms in the current web UI path.
- External reference leak scan found no service-specific markers in the new artifacts.
- Staged scope scan remains required immediately before commit.
- Independent read-only audit passed after the artifact consistency fix.

## Scope Exclusions

No UI implementation, no desktop work, no `runtime.py` changes, no new command API, no legacy import execution, and no unrelated dirty-tail staging belong to this contour.

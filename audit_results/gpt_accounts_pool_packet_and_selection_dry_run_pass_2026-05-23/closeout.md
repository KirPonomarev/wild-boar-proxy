# GPT_ACCOUNTS_POOL_PACKET_AND_SELECTION_DRY_RUN_PASS Closeout

## Contour Capsule

- Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`
- Contour: `GPT_ACCOUNTS_POOL_PACKET_AND_SELECTION_DRY_RUN_PASS`
- Status: `closed_success_non_live_dry_run`
- Branch: `codex/external-agent-lab-isolated`
- Head before closeout: `72b8ba6`
- Live WBP/account/API commands: not run
- Token burn: `0`
- goal: prove Codex Custom GPT account packet + server-side selection dry-run in WBP web UI without live account/API claims.
- head: final commit self-hash is recorded in the operator final note; this file records `72b8ba6` as the pre-contour head.
- touched files: `wild_boar_proxy/codex_account_selection.py`, `wild_boar_proxy/codex_custom_sessions.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, related tests, this audit directory.
- tests run: `node --check`, targeted unittest set, browser fake-server click proof, `git diff --check`, closeout resilience, redaction scan, extended unittest set.
- blocked risks: live account/API inference remains blocked until exact live-runtime authorization and next E2E contour; legacy `web_ui.py` raw last_error cleanup deferred.
- next exact command: `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_codex_custom_sessions tests.test_web_design_live_server tests.test_web_design_ui -q`

## What Changed

- Custom account packets now distinguish dry-run selection from live proof:
  - `selection_dry_run_proven=true`
  - `live_selection_proven=false`
- Custom account packets now explicitly deny inference/provider/network work:
  - `inference_proven=false`
  - `responses_called=false`
  - `chat_completions_called=false`
  - `provider_called=false`
  - `network_calls_made=false`
  - `account_mutation_performed=false`
  - `token_burn=0`
- Raw account/backend ids are redacted from Codex Custom account packets.
- Browser dry-run payload remains limited to server-issued `model_id`.
- WBP web UI labels now say `selection dry-run` and `live unchecked` instead of implying live server-side proof.

## Exact Commands Run

```bash
git status -sb
node --check wild_boar_proxy/web_design_ui/scripts/overview.js
/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_codex_account_selection tests.test_codex_custom_sessions tests.test_codex_model_registry tests.test_web_design_live_server tests.test_web_design_ui -q
```

Browser fake-server proof was run against local static `web_design_ui` with stubbed `/api/codex/custom/*` endpoints. Screenshot:

```text
audit_results/gpt_accounts_pool_packet_and_selection_dry_run_pass_2026-05-23/evidence/browser_account_dry_run_panel.png
```

## Verification Result

- `node --check`: passed
- targeted unittest set: `171 tests OK`
- browser fake-server click proof: passed
- current Codex mutation: not performed
- live account/API/proxy calls: not performed
- raw account id leak in custom account dry-run response: not observed

## Independent Audit

Read-only subagent audit completed. Findings addressed in this contour:

- dry-run selection is now explicitly not live selection;
- backend/account ids are redacted into refs;
- browser forbidden field coverage expanded.

Deferred non-blocking finding:

- legacy `wild_boar_proxy/web_ui.py` can still show raw `last_error`; this belongs to a later legacy web UI cleanup contour.

## Resume From Here

resume from here: start `CODEX_CUSTOM_SESSION_MANAGER_PASS`, verify current commit, then extend session create/prompt boundaries while preserving `selection_dry_run_proven=true`, `live_selection_proven=false`, `selected_backend_id_redacted=true`, no browser backend/route/account ids, and no live prompt unless authorized.

Next contour should be:

```text
CODEX_CUSTOM_SESSION_MANAGER_PASS
```

Resume by verifying the committed packets still expose:

```text
selection_dry_run_proven=true
live_selection_proven=false
selected_backend_id_redacted=true
network_calls_made=false
token_burn=0
```

Then wire session create/prompt dry-run/live prompt boundaries without browser-supplied account/backend/route ids.

## Commit And Push

- Commit: pending at closeout file creation time
- Commit hash: recorded in operator final note because a commit cannot truthfully embed its own final hash before hashing.
- Push: pending until remote push completes

CONTOUR: `ISOLATED_CODEX_APP_E2E_PASS`

Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`

Goal:
- prove bounded owner-surface launch of an isolated Codex app copy
- prove separate `CODEX_HOME` and separate `--user-data-dir`
- prove current runtime/API stack still healthy before and after launch
- prove one minimal through-app request through the intended stack, or classify the exact external boundary

Canonical boundary:
- `launch client --json` only proves bounded OS dispatch
- a visible app process is not enough
- a successful headless Codex CLI request is not automatically a GUI through-app proof
- current working Codex must remain untouched in the strong sense required by the program

Read surfaces:
- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `COMMAND_API.md`
- `AGENTS.md`
- `wild_boar_proxy/runtime.py`
- `wild_boar_proxy/web_design_live_server.py`
- live owner packets from the sandbox launch-copy runtime:
  - `status --json`
  - `healthcheck --json`
  - `external-models check --route wbp-deepseek-v3 --json`
- live host process and socket evidence from `ps` and `lsof`

Write surfaces:
- this contour packet under `audit_results/isolated_codex_app_e2e_pass_2026-05-23/*`

Experiment shape:
1. Reuse the previously admitted sandbox launch-copy runtime:
   - profile dir: `/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/profile`
   - managed dir: `/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed`
   - copy port: `9347`
2. Build a temporary executable wrapper that launches:
   - `/Applications/Codex.app/Contents/MacOS/Codex`
   - with `--user-data-dir=/tmp/.../user-data`
   - with separate `CODEX_HOME=/tmp/.../codex-home`
3. Seed isolated `CODEX_HOME` with:
   - sandbox-scoped `auth.json` from the launch-copy profile
   - local-routing config using `openai_base_url = "http://127.0.0.1:8318/v1"`
4. Run `launch client --json` against the wrapper under the sandbox launch-copy runtime.
5. Inspect launched process truth:
   - separate process observed
   - separate `--user-data-dir` observed
   - child `codex app-server --analytics-default-enabled` observed
6. Attempt machine-backed through-app proof.
7. If GUI child cannot expose a control surface while still touching shared current-app surfaces, classify exact external boundary instead of claiming pass.

Acceptance rule used in this packet:
- bounded launch dispatch must be true
- separate process must be true
- separate GUI `--user-data-dir` must be true
- through-app proof counts only if tied to the launched GUI child, not to a separate ephemeral helper lane
- any shared current-app state touch or missing GUI control surface must be surfaced as a blocker

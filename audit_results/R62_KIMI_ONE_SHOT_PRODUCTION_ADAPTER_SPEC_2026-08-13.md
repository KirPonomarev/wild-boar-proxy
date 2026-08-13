<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R62 Kimi One-Shot Production Adapter

## Objective

Replace the fake-only B11 completion claim with a server-owned production Kimi
Code one-shot adapter whose prompt-mode argv, stream-JSON output, isolated data
root, auth-presence boundary, read-only project access, network posture, and
binary identity are explicit and fail closed.

## In Scope

- admit the Kimi provider adapter declaration after R61 admitted Qwen;
- bind current official Kimi Code prompt mode: `--prompt`,
  `--output-format stream-json`, a sealed empty skills directory, and an
  optional read-only `--add-dir` project/snapshot root;
- bound steps, retry attempts, subagent concurrency/time, background work,
  cron, product skills, telemetry, and update checks with fixed server-owned
  environment values;
- add Kimi to the bounded production prompt surface without caller-supplied
  argv, executable, environment, home root, parser, permissions, or sandbox;
- require complete non-truncated JSON Lines with a non-empty final assistant
  message; preserve nonzero provider exits as typed failures without inventing
  undocumented retryability;
- isolate config, credentials, sessions, plans, and logs under a server-owned
  `KIMI_CODE_HOME`, with presence-only checks of safe `config.toml` and
  `credentials/*.json` metadata and no secret reads;
- disable telemetry with a fixed server-owned value;
- keep probes offline and allow provider network only to the exact operational
  Kimi child after binary admission and auth-presence checks;
- expose an optional validated project/snapshot root read-only at both Kimi
  argv and OS sandbox layers while keeping repo writes denied;
- require a unique `R62_KIMI_ONE_SHOT_PRODUCTION_ADAPTER` evidence supplement;
- update runtime contracts, final assurance, and direct regressions.

## Out of Scope

- installing Kimi Code, writing a binary-admission record, login, reading or
  creating credentials, provider requests, or B11 live proof;
- Qwen/B10 changes beyond shared runtime compatibility;
- B13 workflow integration, UI, release, public publishing, or ACP;
- YOLO/AFK/auto flags supplied by WBP, resume/continue/session, writable
  project access, ambient skills, MCP configuration, or caller environment.

## Constraints

- exact base is merged remote main
  `779c3558db04e7f4a1670f1613eedc5234a8cba3`;
- official Kimi Code rejects `--prompt` with `--plan`, `--auto`, or `--yolo`;
  non-interactive mode itself uses auto permission, so safety comes from fixed
  environment bounds, the empty skills root, default-denied extensions, and
  deny-default OS filesystem sandbox rather than a false flag claim;
- Kimi data remains under `KIMI_CODE_HOME`; the facade checks only safe file
  presence/metadata and never reads `config.toml` or credential values;
- home-level `mcp.json`, `AGENTS.md`, `agents/`, and `plugins/` extension
  surfaces are absent before every admitted spawn;
- prompt input is non-empty, bounded, secret-shape screened, and never passed
  through a shell;
- provider network is denied for probes and defaults, and widened only for the
  revalidated operational Kimi child;
- one-shot sessions never resume; output and error packets remain bounded and
  redacted;
- B11_LIVE remains pending until exact binary admission, operator-managed auth,
  and real positive/negative provider evidence exist.

## Assumptions

- current official Kimi Code supports prompt mode, stream-JSON, replacement
  skills directories, `--add-dir`, `KIMI_CODE_HOME`, fixed loop/background
  controls, telemetry disable, cron disable, and update disable;
- Kimi stream-JSON output uses JSONL messages whose successful final response
  has `role=assistant` and non-empty string or text-block content;
- macOS seatbelt enforces read-only project access and provider-home-only writes
  even though Kimi print mode implicitly handles tool approval non-interactively.

## Acceptance Criteria

- [x] Qwen and Kimi are the only server-owned providers with admitted
      production adapters;
- [x] default Kimi session/run fails before home or spawn when binary admission
      is absent;
- [x] an admitted deterministic test binary receives only the exact bounded
      prompt-mode argv, sealed environment, writable Kimi home, empty skills
      root, optional read-only project root, and provider-network profile;
- [x] caller argv plus invalid, empty, oversized, NUL, or secret-shaped prompts
      fail before spawn;
- [x] missing or unsafe auth-config presence fails before operational spawn and
      never reads or exposes credential content;
- [x] stream-JSON is normalized without fabrication; malformed, truncated,
      non-assistant, or empty final output fails;
- [x] sterile probes/default sandbox remain offline and project writes remain
      denied by the OS sandbox;
- [x] the R62 supplement is required exactly once by GateEvidenceBundleV2;
- [x] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
      resilience gates pass on the final candidate.

## Verification

- tests: focused Kimi/runtime/production-admission/sandbox/evidence/final-
  assurance regressions; repository core, custom-stability, and full suites;
- build: `make check`;
- manual: exact manifest/argv diff, no binary admission/home/auth/provider side
  effects, and scoped/full evidence truth;
- live evidence: not performed; B11_LIVE remains pending.

## Open Questions

- none blocking for B11_CODE; installed binary identity, exact configured auth,
  and live provider behavior remain B11_LIVE facts.

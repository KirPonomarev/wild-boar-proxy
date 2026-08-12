<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R61 Qwen One-Shot Production Adapter

## Objective

Replace the fake-only B10 completion claim with a server-owned production
Qwen Code one-shot adapter whose prompt argv, JSON output, isolated home,
read-only project access, network posture, binary identity, and auth-presence
preconditions are explicit and fail closed.

## In Scope

- admit the Qwen provider adapter declaration while leaving Kimi pending;
- bind the current official Qwen Code headless contract: `--prompt`, JSON
  output, safe mode, plan approval, excluded mutation/subagent tools, and
  bounded turns, wall time, and tool calls;
- add a bounded production prompt surface with no caller-supplied argv,
  executable, environment, home root, parser, or sandbox posture;
- parse a whole JSON document honestly in addition to JSON Lines and text, and
  accept production success only for Qwen's complete buffered success envelope;
- keep sterile version probes offline while allowing provider network only to
  an operational Qwen child after exact binary admission and isolated-home
  auth-presence checks;
- expose an active-project root only as an OS-enforced read-only root and keep
  repo writes denied;
- disable Qwen usage statistics and telemetry with fixed server-owned values;
- require a unique `R61_QWEN_ONE_SHOT_PRODUCTION_ADAPTER` evidence supplement
  so the historical fake-only B10 receipt cannot independently re-earn B10;
- update the one-shot runtime contract and direct regressions.

## Out of Scope

- installing Qwen Code, writing a binary-admission record, creating or
  populating a production Qwen home, reading credentials, login, provider
  requests, or B10 live proof;
- Kimi/B11, dispatcher/workflow integration, UI, release, or public publish;
- caller-controlled network widening, writable project access, resume, YOLO,
  auto-edit, shell, write, edit, or subagent authority.

## Constraints

- exact base is merged remote main
  `3ccab9e9391d1a31b87b13ad2009d01f8ce65b33`;
- the safe production probe already returned `TOOL_BINARY_NOT_FOUND` with no
  changed files, admission store, provider-home creation, or authority grant;
- probe and admission remain offline; only the revalidated operational child
  may receive the fixed provider-network sandbox profile;
- prompt input is non-empty, bounded, secret-shape screened, and never
  interpolated into a shell;
- ambient or caller input cannot enable Qwen usage statistics or telemetry;
- Qwen auth is presence-only configuration under the sealed provider home;
  presence is a precondition, never live success evidence;
- one-shot sessions never resume and every packet remains redacted and bounded;
- B10_LIVE remains pending until the exact binary, auth authority, and a real
  positive/negative provider proof exist.

## Assumptions

- current official Qwen Code supports headless `--prompt`,
  `--output-format json`, `--safe-mode`, approval mode, exclusions, and run
  budgets;
- macOS seatbelt can distinguish the default offline profile from an explicit
  operational provider-network profile while preserving read-only project and
  isolated-home boundaries.

## Acceptance Criteria

- [x] Qwen is the only server-owned provider with an admitted production
      adapter; Kimi remains adapter-blocked;
- [x] default Qwen session/run fails before home or spawn when binary
      admission is absent;
- [x] a deterministic admitted test binary receives only the exact bounded
      headless argv, sealed environment, writable provider home, optional
      read-only active project root, and explicit provider-network profile;
- [x] invalid, empty, oversized, NUL, or secret-shaped prompts fail before
      spawn;
- [x] missing/unsafe auth-presence evidence fails before operational spawn and
      never exposes auth content;
- [x] JSON document output is normalized and redacted without fabricating
      JSON Lines; malformed, truncated, error, or result-empty envelopes fail;
- [x] sterile probes remain offline and the default sandbox remains offline;
- [x] the R61 supplement is required exactly once by GateEvidenceBundleV2;
- [ ] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
      resilience gates pass on the final candidate.

## Verification

- tests: focused one-shot runtime, production admission, Qwen adapter,
  sandbox, gate-evidence, and final-assurance regressions; repository core,
  custom-stability, and full suites;
- build: `make check`;
- manual: exact manifest/argv diff, no production admission/home artifacts,
  no process/provider side effects, and exact four-layer gate truth;
- live evidence: not performed; B10_LIVE stays pending and must not be inferred
  from fake binaries, auth presence, or code completion.

## Open Questions

- none blocking for B10_CODE; exact installed binary identity and provider
  output remain B10_LIVE facts.

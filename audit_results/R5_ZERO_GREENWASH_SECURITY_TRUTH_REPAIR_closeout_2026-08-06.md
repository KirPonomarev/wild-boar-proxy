<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R5 Zero-Greenwash Security Truth Repair Closeout

## Goal

Repair the independently proven R4 defects F01 through F16 on exact remote
HEAD: production/test separation for the provider CLI lane, deny-default
sandboxing, hermetic tests, GateEvidenceBundleV2, read-only FinalAssuranceV2,
and real required CI, without greenwash and without touching the main Codex
installation, real provider CLIs, networks, or protected ports.

## Result

- status: repair implementation complete on merged main; independent audit
  is a separate actor stage and is not claimed here
- final verdict: R5_REPAIR_CANDIDATE_AWAITING_INDEPENDENT_AUDIT
- closure state: CLOSED

## Contour Capsule

- goal: eliminate greenwash security truth defects F01-F16 with typed
  fail-closed behavior and receipt-bound evidence
- branch: codex/r5-prf-closeout
- head: 85f080559ce7097cb39e02ee4f20fe4c50cf38d3 (base before contour commit)
- touched files: wild_boar_proxy/one_shot_cli_runtime.py,
  wild_boar_proxy/qwen_one_shot_cli.py, wild_boar_proxy/kimi_one_shot_cli.py,
  wild_boar_proxy/gate_evidence_bundle_v2.py,
  wild_boar_proxy/assurance_evidence_bundle_v2.py,
  wild_boar_proxy/final_candidate_assurance.py, tests/fakes.py,
  tests/test_r51_production_test_separation.py,
  tests/test_r52_sandbox_adversarial.py, tests/test_r53_hermeticity.py,
  tests/test_gate_evidence_bundle_v2.py,
  tests/test_final_candidate_assurance.py, tests/test_r5_ci_receipt.py,
  tools/emit_r5_ci_receipt.py, .github/workflows/r5-assurance-ci.yml,
  plus rewritten one-shot CLI test files
- tests run: 23 final-assurance tests, 19 gate bundle forged regressions,
  15 sandbox adversarial tests, 6 hermeticity tests, 7 production/test
  separation tests, 8 CI receipt tests, R53 mandatory set in both orders,
  make check with 5008 collected, make test-core 551 passed, CI baseline
  legs, r5 unit-isolation, r5 macos-sandbox 22 passed, r5 package with
  checksums, r5 full-suite executed
- blocked risks: full-suite green on a clean CI runner is not earned; 107
  failures on a clean macOS runner are environment-bound legacy probe
  classes, proven environment-bound by control experiment, and are
  pre-existing rather than caused by this repair; provider CLI live lane
  stays disabled pending security admission
- closure state: CLOSED

## Verification

- tests: all R5 regression suites green per PR; CI run URLs recorded in the
  external handoff evidence; full-suite executed honestly and its red
  result on clean runners preserved as per-attempt receipts
- build: wheel and sdist built in r5 package job with sha256 checksums and
  content hygiene checks green
- manual: remote HEAD readback after every merge; external execution-state
  CAS transitions rev 35 through 39 with per-transition receipts
- live verification: macos-sandbox job exercises the real production
  profile builder with adversarial canaries on macOS runners, 22 passed

## Artifacts

- spec: governing packet EXECUTE_WBP_R5_ZERO_GREENWASH_SECURITY_TRUTH_REPAIR
  held outside the repository per plan rule
- packet: merge sequence PR 138 R51, PR 139 R52 plus R53, PR 140 R54,
  PR 141 R55, PR 142 R56, this closeout PR R57
- report: CI receipts emitted per workflow attempt under run artifacts,
  external state-transition receipts rev 35 to 39 in the server control
  root

## Git

- branch: codex/r5-prf-closeout
- commit: contour commit contains this closeout only; merge commit recorded
  in the external execution state after merge readback
- pushed: yes, origin codex/r5-prf-closeout

## Scope Check

- unrelated work mixed in: hermeticizing legacy environment-bound probe
  tests was identified and deliberately left outside this contour as
  cross-subsystem scope; it is documented as an unearned claim, not
  silently absorbed
- private-data risk reviewed: zero main Codex paths read or written, zero
  real provider CLI invocations, zero network or protected-port contact,
  zero VPN or proxy mutations, zero public releases

## Notes

- blockers encountered: sandbox deny-default model required realpath-aware
  seatbelt rules; full-suite revealed environment-bound legacy tests on
  clean runners; both localized and documented with receipts
- resume from here: CLOSED

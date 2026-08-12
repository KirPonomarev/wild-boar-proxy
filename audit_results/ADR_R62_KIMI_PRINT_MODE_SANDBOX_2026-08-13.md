<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Kimi Print-Mode Sandbox

## Status

Accepted

## Date

2026-08-13

## Context

Kimi Code prompt mode is the supported programmatic one-shot interface, but its
current CLI contract rejects combining `--prompt` with `--plan` and treats
print mode as non-interactive. WBP therefore cannot claim safety from an
incompatible plan flag or from interactive approval. Kimi also persists config,
OAuth credentials, sessions, plans, logs, and metadata beneath its data root.

## Decision

Use sealed `--prompt … --output-format stream-json` argv and a server-owned
empty replacement skills directory. Bound loop/background/subagent behavior
through fixed documented environment values; disable built-in product skills,
cron, telemetry, and update checks. Set both `HOME` and `KIMI_CODE_HOME` to the
isolated provider home. Require safe presence metadata for `config.toml` and at
least one top-level `credentials/*.json` file without opening either.

Keep probes and shared defaults offline. Only the exact admitted operational
Kimi child receives outbound network. Home-level MCP, agent, plugin, and
`AGENTS.md` extension surfaces must be absent before spawn. It may write its isolated home and
ephemeral sandbox cwd, may read an explicitly validated project or immutable
snapshot root, and may never write the project. The OS sandbox is the
enforcement boundary for print-mode tool behavior.

## Alternatives Considered

1. Combine `--prompt` with `--plan`, `--auto`, or `--yolo`.
   Rejected because the current official CLI declares these combinations invalid.
2. Use plain text output.
   Rejected because plain text cannot prove assistant-message structure or
   distinguish malformed output.
3. Trust print-mode approval defaults.
   Rejected because non-interactive approval is not a host filesystem boundary.
4. Reuse ambient `~/.kimi-code` or discovered skills.
   Rejected because it would mix credentials, sessions, customization, and
   project state outside WBP's isolated authority boundary.

## Consequences

- Positive: the production path matches current Kimi CLI behavior while repo
  writes remain OS-denied and output stays machine-verifiable.
- Negative: outbound traffic cannot be hostname-scoped by macOS seatbelt, and
  Kimi may write bounded session/log state inside its provider home.
- Negative: auth presence is only a precondition; it is not proof that a model
  or provider request will succeed.
- Follow-up work: B11_LIVE must bind an installed binary and operator-managed
  isolated auth, then prove positive response/read, denied write,
  timeout/cancel, provider errors, redaction, and no protected-host mutation.

## Evidence

- spec: `audit_results/R62_KIMI_ONE_SHOT_PRODUCTION_ADAPTER_SPEC_2026-08-13.md`
- primary docs: `https://moonshotai.github.io/kimi-code/en/reference/kimi-command.html`,
  `https://moonshotai.github.io/kimi-code/en/configuration/env-vars.html`, and
  `https://moonshotai.github.io/kimi-code/en/configuration/data-locations.html`
- tests: focused production admission, Kimi adapter, output normalization,
  environment isolation, and macOS sandbox regressions

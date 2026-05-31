<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RUNTIME_INVARIANT_CHECK_AND_RECOVERY_HINTS_PASS Spec

## Goal

Add a read-only strict JSON runtime command that machine-checks a bounded set of
runtime invariants and returns advisory recovery hints without executing repair.

Canonical command:

```bash
wild-boar-proxy invariant-check --json
```

## Canon

Decision order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Scope

In:

- top-level `invariant-check --json` command
- strict JSON packet with `invariant_result` and `recovery_hints`
- bounded invariant checks:
  - `command_packet_shape`
  - `no_false_green`
  - `listener_truth`
  - `mode_truth`
  - `accounts_pool_integrity`
  - `reserve_first_policy`
  - `active_routing_explicit`
  - `managed_paths_bound`
- advisory recovery hints sorted by `priority_score`
- packet-level tests and read-only proof

Out:

- UI changes
- auto-recovery
- schema expansion
- lifecycle state changes
- broad runtime refactor

## Contract

Any critical invariant failure must return a non-green packet:

- `status=error`
- `machine_error_code=RUNTIME_INVARIANT_FAILED`
- `invariant_result.status=failed`

The command is read-only:

- no recovery execution
- no runtime state writes
- `changed_files=[]`

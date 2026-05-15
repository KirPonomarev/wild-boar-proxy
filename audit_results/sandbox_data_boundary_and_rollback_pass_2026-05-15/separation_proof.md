# Separation Proof

## Observed Isolation Facts

- working/live roots:
  - `/Users/kirillponomarev/.codex-custom-cli`
  - `/Users/kirillponomarev/.cli-proxy-api`
  - `/Users/kirillponomarev/.wild-boar-proxy/external-models`
- chosen active sandbox root:
  - `/Users/kirillponomarev/.codex-custom-sandbox-20260515`
- chosen active sandbox root does not exist yet
- chosen active sandbox root is not equal to, inside, or above any working/live
  root

## Path-Override Proof Surfaces

Runtime and external-models path selection is explicitly overrideable:

- runtime env path surfaces:
  - [runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:159)
  - [runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:187)
  - [runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:312)
- external-models env path surfaces:
  - [paths.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/external_models/paths.py:14)
  - [paths.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/external_models/paths.py:34)

## Practical Bootstrap Proof

Repo tests already prove that an isolated companion layout can be initialized
under env overrides without default live-path reuse:

- [tests/test_external_models.py](/Volumes/Work/wild-boar-proxy/tests/test_external_models.py:76)
- [tests/test_cli.py](/Volumes/Work/wild-boar-proxy/tests/test_cli.py:14361)

## Admissibility Verdict

- `.codex-custom-test`:
  - path-isolated: `yes`
  - active-wave admissible: `no`
  - reason: prior mutable state and stale experiment-specific configuration
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515`:
  - path-isolated: `yes`
  - active-wave admissible: `yes`
  - reason: fresh dedicated root with explicit write surfaces and clear rollback

## Consequence For The Next Contour

`SANDBOX_LIVE_SERVER_BINDING_PASS` may proceed only against the declared fresh
sandbox root, not against working/live roots and not against the quarantined old
sandbox root.

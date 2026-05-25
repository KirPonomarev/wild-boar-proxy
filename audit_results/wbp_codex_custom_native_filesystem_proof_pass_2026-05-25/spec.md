# WBP Codex Custom Native Filesystem Proof

Date: 2026-05-25
Status: closed_success

## Goal

Prove that one bounded repo-canonical isolated-home Custom native Codex launch
attempt does not mutate protected default Codex filesystem surfaces.

## Selected Strategy

```text
repo_canonical_custom_proxy_auth_isolated_home
```

Meaning:

```text
isolated HOME
isolated CODEX_HOME
isolated userData mechanism
repo-owned launcher
```

## Scope

In scope:

- one bounded native launch attempt;
- recursive protected-surface scan before and after launch;
- protected-surface diff classification;
- Custom-owned write inventory;
- user-data-dir respect classification;
- current Codex before/after process state;
- cleanup confined to the Custom-owned temp root.

Out of scope:

- native window usability proof;
- prompt/response proof;
- provider routing proof;
- Original Codex via WBP;
- final E2E;
- any claim about real-HOME A0.

## Protected Surfaces

```text
~/.codex
~/Library/Application Support/Codex
~/Library/Caches/com.openai.codex
~/Library/HTTPStorages/com.openai.codex
```

## Accepted Result

The live filesystem probe packet proves:

- protected default Codex surfaces unchanged;
- current Codex remained closed/untouched before and after the launch attempt;
- writes were confined to the Custom-owned temp profile tree;
- cleanup removed only the Custom-owned temp root and custom-launched process;
- `user_data_dir_respected=true` for the repo-canonical isolated-home lane.

## Explicit Non-Claims

This contour does not claim:

```text
native window usability
prompt/response success
provider routing success
native request reached WBP
Original Codex reversibility as a user flow
global Keychain strategy correctness
```

## Contour Capsule

resume from here: `closed_success`

verdict: one bounded repo-canonical isolated-home Custom native launch attempt
left all protected default Codex filesystem surfaces unchanged and confined all
writes/cleanup to Custom-owned surfaces.

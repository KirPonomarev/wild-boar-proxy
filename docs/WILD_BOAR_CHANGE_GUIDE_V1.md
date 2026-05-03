# WILD_BOAR_CHANGE_GUIDE_V1

This is a working guide for the human and the agent on how to change
`Wild Boar Proxy` without mixing runtime truth, policy truth, engine truth,
UI truth, and docs-only contours.

This guide is not a second canon and does not create binding law by itself.
It exists to help open narrow, safe contours on top of current mainline and
to reduce confusion between different truth surfaces.

## 1. Truth and state snapshot

Always distinguish these three things first:

1. active canon
2. current mainline snapshot
3. current local machine state

Active canon defines the mandatory law.
Current mainline snapshot says what was considered true for a specific base.
Current local machine state may differ because of an unfinished contour, local
generation, a dirty worktree, or an old branch.

```text
TRUTH_ORDER_01: CANON_MD
TRUTH_ORDER_02: MASTER_PLAN_MD
TRUTH_ORDER_03: RUNTIME_CONTRACT_MD
TRUTH_ORDER_04: STATE_SCHEMA_MD
TRUTH_ORDER_05: COMMAND_API_MD
TRUTH_ORDER_06: DELIVERY_RULES_MD
TRUTH_ORDER_07: README_MD
TRUTH_RULE_01: OLD_PLANS_ARE_DONOR_ONLY
TRUTH_RULE_02: NO_SECOND_CANON
```

Any document claiming current-mainline alignment must be tied to a snapshot.

```text
SNAPSHOT_FIELDS_REQUIRED: SELECTED_BASE_SHA BINDING_BASE_SHA VERIFIED_AT_UTC LOCAL_BRANCH LOCAL_WORKTREE_STATE
SNAPSHOT_RULE_01: WITHOUT_THESE_FIELDS_NO_CURRENT_MAINLINE_ALIGNED_CLAIM
SNAPSHOT_RULE_02: LOCAL_MACHINE_STATE_MAY_DIFFER_FROM_MAINLINE_SNAPSHOT
SNAPSHOT_RULE_03: DIRTY_LOCAL_WORKTREE_BLOCKS_NEW_WRITE_CONTOUR_UNLESS_HYGIENE_TASK
```

## 2. What Wild Boar Proxy is right now

`Wild Boar Proxy` is a real managing layer over the engine contour.
It is not the engine itself and it does not own the entire truth of the
traffic layer.

It is responsible for:

- runtime modes
- lifecycle policy
- onboarding orchestration
- truthful status
- diagnostics
- fallback
- staged scaling

It is not responsible for:

- provider protocol translation
- low-level request routing
- OAuth engine behavior
- auth storage format ownership
- upstream execution semantics

```text
SYSTEM_RULE_01: DO_NOT_PRESENT_POLICY_LAYER_AS_ENGINE_LAYER
SYSTEM_RULE_02: DO_NOT_PRESENT_DEFERRED_OR_DORMANT_SLICES_AS_FULLY_LIVE
SYSTEM_RULE_03: MAIN_VALUE_IS_POLICY_AND_RECOVERY_NOT_GENERIC_GUI
```

## 3. Ownership boundaries

If the change touches the right column, it is no longer a pure Wild Boar
Proxy contour.

```text
CAN_CHANGE: MODES LIFECYCLE_POLICY ONBOARDING_ORCHESTRATION TRUTH_LAYER DIAGNOSTICS RECOVERY ROLLOUT_RULES UI_OPERATOR_WORKFLOWS
CANNOT_CHANGE: ENGINE_TRANSPORT AUTH_ENGINE PROVIDER_TRANSLATION LOW_LEVEL_ROUTING UPSTREAM_EXECUTION_SEMANTICS
BOUNDARY_RULE_01: TOUCHING_CANNOT_CHANGE_ESCALATES_OUT_OF_PURE_CONTROL_LAYER
BOUNDARY_RULE_02: UI_MAY_PRESENT_ENGINE_STATE_BUT_MUST_NOT_REDEFINE_ENGINE_BEHAVIOR
```

## 4. Entity classes

Do not mix these classes in one list:

- required surface
- gap
- deferred test
- lane status
- blocked environment

```text
ENTITY_01: REQUIRED_SURFACE
ENTITY_02: GAP
ENTITY_03: DEFERRED_TEST
ENTITY_04: LANE_STATUS
ENTITY_05: BLOCKED_ENV
ENTITY_RULE_01: NEVER_MIX_THESE_IN_ONE_LIST
ENTITY_RULE_02: LANE_STATUS_IS_NOT_SURFACE
ENTITY_RULE_03: DEFERRED_TEST_IS_NOT_ADMITTED_SURFACE
ENTITY_RULE_04: GAP_IS_NOT_SURFACE
ENTITY_RULE_05: BLOCKED_ENV_IS_NOT_LANE_STATUS
```

## 5. Runtime map

This is not an eternal truth.
It is the current runtime map tied to current mainline.

```text
REQUIRED_SURFACES: SURFACE_RUNTIME_TRUTH SURFACE_COMMAND_API SURFACE_ONBOARDING SURFACE_DIAGNOSTICS SURFACE_STAGED_ROLLOUT SURFACE_RECOVERY
CURRENT_GAPS: GAP_UI_NOT_IMPLEMENTED GAP_INSTALLER_NOT_IMPLEMENTED GAP_SCALE_PROOF_NOT_COMPLETE
CURRENT_BLOCKED_ENV: NONE_UNLESS_REBOUND
CURRENT_LANE_STATUSES: RUNTIME_HARDENING_PENDING ONBOARDING_PRODUCTIZATION_PENDING
```

Status claims must point to artifacts, not float freely.

```text
ARTIFACT_RULE_01: STATUS_CLAIMS_MUST_POINT_TO_ARTIFACT_CLASS
ARTIFACT_RULE_02: VERIFIED_AT_UTC_WITHOUT_ARTIFACT_CLASS_IS_NOT_ENOUGH
ARTIFACT_RULE_03: REQUIRED_SURFACE_CLAIMS_AND_LANE_STATUS_CLAIMS_MUST_NOT_SHARE_THE_SAME_SLOT
```

Freshness is checked by rebinding facts before a new contour.

```text
FRESHNESS_RULE_01: BEFORE_EACH_NEW_WRITE_CONTOUR_RERUN_git_status_short_branch
FRESHNESS_RULE_02: BEFORE_EACH_NEW_WRITE_CONTOUR_RERUN_git_rev_parse_HEAD
FRESHNESS_RULE_03: BEFORE_EACH_NEW_WRITE_CONTOUR_RERUN_git_rev_parse_origin_main
FRESHNESS_RULE_04: IF_HEAD_OR_ORIGIN_MAIN_DIFFERS_FROM_BOUND_SHA_REBIND_REQUIRED
FRESHNESS_RULE_05: VERIFIED_AT_UTC_IS_METADATA_NOT_A_REBIND_SUBSTITUTE
```

## 6. Runtime model

This is not just a UI wrapper.
The system has resolver order and commit points.

Resolver order:

base
  |
mode
  |
profile
  |
workspace
  |
runtime_fallback
  |
diagnostics_state

```text
RESOLVER_ORDER: base mode profile workspace runtime_fallback diagnostics_state
COMMIT_POINTS: apply sync_complete rollout_step_end healthcheck_pass mode_switch safe_reset restore_last_stable app_close_debounced
FORBIDDEN_PATCH_ROOTS: ENGINE_TRANSPORT AUTH_ENGINE LOW_LEVEL_ROUTING
```

Context dimensions:

```text
CONTEXT_DIMENSIONS: MODE PROFILE WORKSPACE MACHINE_STATE
ACTIVE_UI_PROFILES: BASELINE OPERATOR SAFE
RUNTIME_MODES: STABLE MANAGED
WORKSPACES: OPERATE REVIEW RECOVERY
```

Managing-layer ports:

```text
PORTS: GET_RUNTIME_STATUS RUN_SYNC RUN_HEALTHCHECK SAFE_RESET RESTORE_LAST_STABLE RUN_ONBOARDING EXPORT_DIAGNOSTICS
PORT_RULE_01: BEHAVIOR_CHANGES_GO_THROUGH_PORTS_OR_COMMAND_API
PORT_RULE_02: ROUTING_LOGIC_CHANGES_DO_NOT_LIVE_IN_UI
```

## 7. How to choose the change group

Pick one problem first.
Then choose exactly one group.

Visual and copy changes:
  Group 01

UI binding to an existing command:
  Group 02

Runtime policy or recovery behavior:
  Group 03

State or storage contract:
  Group 04

Docs and status refresh:
  Group 05

```text
DECISION_01: PURE_VISUAL_CHANGE_TO_GROUP_01
DECISION_02: EXISTING_COMMAND_BINDING_TO_GROUP_02
DECISION_03: POLICY_OR_RECOVERY_CHANGE_TO_GROUP_03
DECISION_04: STATE_OR_STORAGE_CHANGE_TO_GROUP_04
DECISION_05: POST_ACCEPTANCE_DOC_CHANGE_TO_GROUP_05
DECISION_06: IF_MULTIPLE_GROUPS_ARE_TRUE_SPLIT_THE_TASK
```

## 8. Group 01 - visual and copy

These tasks are about markup, styles, spacing, sizes, labels, icons, and
visual composition.
If the task can be solved without changing runtime behavior, it must be solved
without changing runtime behavior.

```text
GROUP_ID: GROUP_01_VISUAL_AND_COPY
WHEN: HTML CSS SPACING SIZING LABELS ICONS VISUAL_COMPOSITION
DEFAULT_DENYLIST: ENGINE_INTEGRATION_FILES RUNTIME_CONTRACT_FILES STATE_SCHEMA_FILES COMMAND_API_FILES
PATCH_SCOPE: UI_ONLY
ESCALATE_IF: NEEDS_RUNTIME_BEHAVIOR OR_STORAGE OR_COMMAND_SEMANTICS_CHANGE
```

## 9. Group 02 - interface binding

These tasks connect an existing button, action, or control to an existing
command id and existing handler path.
Command meaning does not change here.

```text
GROUP_ID: GROUP_02_INTERFACE_BINDING
WHEN: BUTTON_SELECT_MENU_OR_ACTION_TO_EXISTING_COMMAND_ID
PATCH_SCOPE: UI_PLUS_COMMAND_BINDING
ESCALATE_IF: COMMAND_MEANING_CHANGES
```

## 10. Group 03 - runtime policy and recovery

These tasks change safe reset, restore last stable, runtime modes, lifecycle,
truth layer, sync policy, or fallback behavior.

```text
GROUP_ID: GROUP_03_RUNTIME_POLICY_AND_RECOVERY
WHEN: MODES LIFECYCLE TRUTH_LAYER FALLBACK DIAGNOSTICS RECOVERY
PATCH_SCOPE: CONTROL_LAYER_RUNTIME
ESCALATE_IF: ENGINE_BEHAVIOR_MUST_BE_REDEFINED
```

## 11. Group 04 - state and storage

These tasks affect schema, atomic writes, diagnostics artifacts, migration, or
state transitions.

```text
GROUP_ID: GROUP_04_STATE_AND_STORAGE
WHEN: STATE_SCHEMA STORAGE CONTRACTS MIGRATIONS DIAGNOSTICS_PERSISTENCE
PATCH_SCOPE: STORAGE_AND_SCHEMA_ONLY
ESCALATE_IF: ENGINE_AUTH_FORMAT_OWNERSHIP_IS_TOUCHED
```

## 12. Group 05 - docs and status

These tasks are docs-only after accepted code work.
They keep current truth aligned.

```text
GROUP_ID: GROUP_05_DOCS_AND_STATUS
WHEN: FACTUAL_DOC_REFRESH STATUS_REBIND MASTER_PLAN_REFRESH
PATCH_SCOPE: DOCS_ONLY
STOP_IF: DOCS_ATTEMPT_TO_OVERRIDE_CANON
```

## 13. Golden rules

```text
RULE_01: ONE_BOUNDED_CONTOUR_ONE_PRIMARY_TRUTH_CHANGE
RULE_02: DO_NOT_OPEN_UI_WORK_BEFORE_RUNTIME_AND_COMMAND_API_ARE_FROZEN
RULE_03: DO_NOT_CLAIM_20_ACCOUNT_READINESS_FROM_SCHEMA_ONLY
RULE_04: DO_NOT_PRESENT_LOG_PARSING_AS_A_FORMAL_API
RULE_05: DO_NOT_HIDE_STALE_OR_UNKNOWN_STATE_UNDER_HEALTHY_LABELS
RULE_06: IF_THE_TASK_STARTS_LOOKING_LIKE_A_GENERIC_CLIPROXY_MANAGER_STOP_AND_RECLASSIFY
```

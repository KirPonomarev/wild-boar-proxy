# UI Web Design Baseline Lock Spec

Contour: `UI_WEB_DESIGN_BASELINE_LOCK`

Date: 2026-05-14

## Goal

Lock the owner-provided source design baseline as a repo-safe technical design
contract for the remaining web UI repair contours before owner review and any
future desktop transfer.

This contour locks the ruler. It does not repair screens.

## Decision Owner

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. Owner-provided source design baseline as visual authority only

## Canon Anchors

- Wild Boar Proxy is the managing/control layer.
- CLIProxyAPI remains the engine.
- The UI is operator UX for managed operations, not a generic CLI or config
  editor.
- UI truth comes from strict JSON command packets.
- The design baseline controls visual geometry, hierarchy, density, tone, and
  identity only.
- The design baseline cannot create runtime truth, command truth, action
  availability, health/readiness claims, or desktop approval.
- Browser UI must not read logs, runtime state, config, or evidence files
  directly.
- `runtime.py` is outside this contour.
- Desktop implementation is outside this contour.

## Design Authority

Primary visual baseline:

- Owner-provided source design package containing screens `00` through `09`.

Secondary visual input:

- Owner-provided high-resolution design package.
- Lost diagnostics-detail high-resolution PNG.

Typography note:

- One owner-provided designer package suggests a `Roboto Mono` light-weight
  direction.
- The source render package itself uses a mono-first `SF Mono` stack.
- This contour keeps the source render package typography as the current
  authority unless the owner explicitly overrides typography later.

## Repo-Safe Privacy Rule

Repo artifacts for this contour must not include:

- absolute private local paths
- external reference service names
- external reference URLs
- tokens
- install prompts
- downloaded external screenshots
- private research notes

Allowed wording:

- owner-provided source design package
- owner-provided high-resolution design package
- private external reference research, only if the concept must be named

## In Scope

- Inventory source design screens.
- Record visual role for each source screen.
- Extract measured baseline tokens from source HTML/CSS and PNG metadata.
- Map every current web screen to a visual reference.
- Classify missing or derived screens.
- Admit the lost diagnostics-detail PNG as a content/layout supplement without
  adopting its mismatched application shell.
- Define diagnostics graph/data admission rules.
- Define no-layer-mixing rules for later visual repair contours.
- Produce repo-safe spec, tokens, matrix, and closeout artifacts.

## Out Of Scope

- CSS layout changes.
- HTML implementation changes.
- JavaScript behavior changes.
- New UI actions.
- New command surfaces.
- Runtime changes.
- Desktop files.
- Live-runtime mutation.
- External reference screenshots or service traces in repo.

## Locked Decisions

### Main App Shell

The canonical shell for the web-rendered UI prototype is the left-sidebar shell
from source screens `00` through `09`.

The shell includes:

- centered desktop frame
- rounded app window
- left product sidebar
- large product mark and wordmark
- main content area to the right of the sidebar
- calm warm technical editorial visual direction

### Lost Diagnostics Detail

The lost diagnostics-detail high-resolution PNG is admitted as a content and
layout supplement for the Diagnostics screen only.

Admitted model:

- signal list
- selected object detail
- signal status
- check chain
- history/graph slot
- current state
- latest records
- recommended bounded actions

Rejected model:

- top tab-bar shell
- alternate application chrome
- any visual implication that diagnostics is runtime truth by itself

### Diagnostics Graphs

Charts are visually allowed.

Live chart data is not admitted unless backed by a bounded JSON command packet.
If no bounded JSON surface exists:

- fixture/demo chart may exist only in fixture mode
- live mode must show unavailable or deferred state
- UI must not build chart data from logs, state files, config files, or evidence
  files

### Header Controls

Source/live/demo controls are implementation utilities. They must not dominate
final product headers in later repair contours.

### Action Density

Row-level actions must not become persistent button clutter. Destructive and
rare actions should move to overflow, details, or confirmation patterns unless
a source reference explicitly admits a persistent action.

### Typography

Use source render package typography as current authority. Do not switch the
whole UI to `Roboto Mono` light-weight typography in this contour.

### External References

External references may inform generic interaction geometry only. They are not
repo evidence and cannot override Wild Boar identity.

## Layer Separation Rules

Design baseline may control:

- visual hierarchy
- density
- layout rhythm
- card/table/modal geometry
- icon/button/chip treatment
- copy tone boundaries
- product identity

Design baseline may not control:

- runtime truth
- command availability
- action success claims
- route/account lifecycle rules
- health/readiness status
- graph data sources
- desktop admission
- engine behavior

## Acceptance Criteria

- Every current web screen has a declared visual reference.
- Every missing or derived screen has a declared source model or owner-review
  note.
- Diagnostics-detail is classified without adopting its mismatched shell.
- Diagnostics charts are fixture-only unless a bounded JSON command surface
  exists.
- Baseline tokens are recorded as measured values.
- Each future repair contour has a clear target.
- Design artifacts do not contain absolute private local paths.
- Design artifacts contain no external reference service traces.
- Baseline is visual authority only and cannot override command/runtime truth.
- No runtime truth or command behavior is changed.
- No CSS/HTML/JS implementation changes are made.
- Closeout includes contour capsule and resume-from-here.

## Verification

Required before closeout:

```text
python3 -m json.tool audit_results/ui_web_design_baseline_tokens_2026-05-14.json
python3 -m json.tool audit_results/ui_web_design_screen_reference_matrix_2026-05-14.json
rg forbidden external-reference traces in new artifacts
rg forbidden private local paths in new artifacts
rg forbidden overclaim wording in new artifacts
git diff --check
git status --short --untracked-files=no
```

## Stop Conditions

- Baseline files cannot be read or measured.
- Source baseline conflicts with canon/runtime truth.
- Any artifact starts treating visual reference as runtime evidence.
- Any token or matrix entry requires direct UI reads from logs, state, config, or
  evidence files.
- Diagnostics graph would require direct log/state/evidence reads.
- The contour starts implying desktop approval.
- External reference service traces would enter repo.
- Absolute private local paths would enter repo artifacts.
- Any implementation drift appears inside this baseline-lock contour.

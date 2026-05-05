<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Delivery Rules

## Core discipline

- one bounded write contour at a time
- no new write contour before the previous one is truly closed
- no dirty tail accepted as normal state
- false-green and stale-green are forbidden

## Git discipline

- each meaningful write contour ends with a commit
- public repo delivery uses branch, push, PR, merge
- new write work does not start from a dirty worktree unless it is an explicit hygiene task
- a contour is not considered closed while its changes exist only as local commits
- each closed contour must be pushed to GitHub on its branch before the next contour begins
- timely sync is mandatory: branch push happens in the same closeout cycle as verification and commit
- PR creation follows push as soon as the contour is ready for reviewable delivery
- merge is allowed only after verification evidence exists for the contour

## Runtime discipline

- runtime truth is more important than narrative summaries
- diagnostics and evidence should close contours, not memory or assumption

## Scaling discipline

- architecture supports 20 accounts immediately
- proof of scale is staged
- every expansion step requires rollback points

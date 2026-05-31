<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Closeout Template

```markdown
# [Contour Name] Closeout

## Goal

[What this contour set out to achieve]

## Result

- status:
- final verdict:
- closure state: CLOSED

## Contour Capsule

- goal:
- branch:
- head:
- touched files:
- tests run:
- blocked risks:
- closure state: CLOSED

## Verification

- tests:
- build:
- manual:
- live verification:

## Artifacts

- spec:
- packet:
- report:

## Git

- branch:
- commit:
- pushed:

## Scope Check

- unrelated work mixed in:
- private-data risk reviewed:

## Notes

- blockers encountered:
- resume from here: CLOSED

> Fill all `Contour Capsule` fields with concrete values before commit.
> Placeholder values are not accepted by resilience checks.
> Future plans, next-contour pointers, and master-plan routes belong outside
> the repository. Closeout artifacts record completed evidence only.
```

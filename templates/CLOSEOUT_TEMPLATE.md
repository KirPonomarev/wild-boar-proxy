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
- next action:

## Contour Capsule

- goal:
- branch:
- head:
- touched files:
- tests run:
- blocked risks:
- next exact command:

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
- follow-up contour:
- resume from here: CLOSED / [exact next contour or command]

> Fill all `Contour Capsule` fields with concrete values before commit.
> Placeholder values are not accepted by resilience checks.
```

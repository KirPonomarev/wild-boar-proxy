<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step44 Contour Plan

```text
CONTOUR:
ID:
STEP44_OWNER_SURFACE_CONTRADICTION_CLASSIFICATION

Goal:
Classify the reproduced status-vs-rotation policy-drift mismatch after step43
without any live writes, repo repair, or UI work.

Purpose:
This contour exists only to determine whether the mismatch is:
- contractually separate truth domains
- repo-owned contradiction
- or an unclassified engine/contract escalation

Size: M
Risk level: medium
Mode: read-only proof

In scope:
- fresh owner-packet capture
- bounded reread
- semantic contract/code/test mapping
- classification packet

Out of scope:
- any write command
- repo edits
- UI work
- normalization work
- repo repair
```

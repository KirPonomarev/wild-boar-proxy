<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Desktop Renderer Admission Approval Gate

## Goal

Record the approval gate before `DESKTOP_RENDERER_ADMISSION` and prevent an
implicit transition from completed web UI work into desktop phase.

## Current State

- current contour: `DESKTOP_RENDERER_ADMISSION_APPROVAL_GATE`
- mode: blocked planning / owner approval gate / no implementation
- desktop approval: not granted
- next admitted contour after explicit approval: `DESKTOP_RENDERER_ADMISSION`

## Canon Evidence

- `audit_results/ui_final_next_contour_queue_2026-05-14.json` sets
  `desktop_approval_granted` to `false`.
- The same queue lists `DESKTOP_RENDERER_ADMISSION` as
  `owner-gated desktop admission` depending on `explicit owner approval`.
- `audit_results/rollout_scale_gate_admission_closeout_2026-05-14.md` says to
  stop for owner approval before `DESKTOP_RENDERER_ADMISSION`.
- `CANON.md` says generic phrases such as `начинай работу` do not themselves
  authorize gated work that requires a more specific owner marker.

## Approval Condition

Desktop phase may start only after explicit owner approval in the active
thread. Acceptable approval must name the desktop phase or renderer admission
intent, for example:

- `одобряю старт desktop phase`
- `начинай DESKTOP_RENDERER_ADMISSION`
- `разрешаю открыть desktop renderer admission`

Generic continuation phrases are insufficient:

- `погнали`
- `начинай работу`
- `продолжай`
- `делай следующий контур`
- approval of this gate plan

## Forbidden Before Approval

- no desktop implementation
- no desktop files touched
- no renderer scaffold
- no static embed smoke
- no command bridge
- no live binding
- no packaging or installer work
- no runtime, web UI, command adapter, or live server changes
- no direct runtime/state/log/evidence reads

## Future Scope After Approval

The future `DESKTOP_RENDERER_ADMISSION` may only evaluate the renderer boundary:

- renderer as presentation shell
- web UI as the starting canonical visual/interaction source
- command truth still through strict JSON packets
- no direct CLI execution from renderer
- no direct runtime/state/log/evidence file reads
- no packaging, bridge, or live binding until later contours

## Result

The gate remains blocked until the owner explicitly approves desktop phase.

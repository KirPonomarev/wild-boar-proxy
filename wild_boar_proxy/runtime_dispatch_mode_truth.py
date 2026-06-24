# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any


DISPATCH_MODE_CHATGPT_ONLY = "chatgpt_only"
DISPATCH_MODE_CHATGPT_API = "chatgpt_plus_api"
DISPATCH_MODE_API_ONLY = "api_only"

ORCHESTRATOR_CHATGPT = "custom_codex_chatgpt"
ORCHESTRATOR_API_ROUTE = "api_route"
EXECUTOR_CHATGPT = "custom_codex_chatgpt"
EXECUTOR_API_ROUTE = "api_route"
EXECUTOR_DIP_API_ROUTE = "dip_api_route"


def _safe_text(value: object, *, limit: int = 120) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def dispatch_mode_truth_fields(
    *,
    execution_mode: str,
    truth_source: str,
    orchestrator: str,
    executor: str,
    mode_proven: bool,
    chatgpt_lane_selected: bool | None = None,
    api_route_selected: bool | None = None,
    chatgpt_lane_called: bool = False,
    api_route_called: bool = False,
    target_repo_required: bool = False,
    target_repo_available: bool = False,
    target_repo_fallback_used: bool = False,
    wrapper_substitution_used: bool = False,
    wrapper_substitution_detected: bool = False,
    wrapper_substitution_allowed: bool = False,
) -> dict[str, Any]:
    mode = _safe_text(execution_mode, limit=80)
    chatgpt_mode_proven = bool(mode_proven and mode == DISPATCH_MODE_CHATGPT_ONLY)
    api_mode_proven = bool(mode_proven and mode == DISPATCH_MODE_API_ONLY)
    gpt_api_mode_proven = bool(mode_proven and mode == DISPATCH_MODE_CHATGPT_API)
    return {
        "execution_mode": mode,
        "selected_mode": mode,
        "dispatch_mode_truth_source": _safe_text(truth_source, limit=120),
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": bool(mode_proven),
        "orchestrator": _safe_text(orchestrator, limit=80),
        "executor": _safe_text(executor, limit=80),
        "orchestrator_lane": _safe_text(orchestrator, limit=80),
        "executor_lane": _safe_text(executor, limit=80),
        "chatgpt_lane_selected": (
            bool(chatgpt_lane_called)
            if chatgpt_lane_selected is None
            else bool(chatgpt_lane_selected)
        ),
        "api_route_selected": (
            bool(api_route_called) if api_route_selected is None else bool(api_route_selected)
        ),
        "chatgpt_lane_called": bool(chatgpt_lane_called),
        "api_route_called": bool(api_route_called),
        "chatgpt_only_mode_proven": chatgpt_mode_proven,
        "gpt_mode_proven": chatgpt_mode_proven,
        "api_only_mode_proven": api_mode_proven,
        "api_mode_proven": api_mode_proven,
        "chatgpt_plus_api_mode_proven": gpt_api_mode_proven,
        "gpt_api_mode_proven": gpt_api_mode_proven,
        "target_repo_required": bool(target_repo_required),
        "target_repo_available": bool(target_repo_available),
        "target_repo_fallback_used": bool(target_repo_fallback_used),
        "wrapper_substitution_used": bool(wrapper_substitution_used),
        "wrapper_substitution_detected": bool(wrapper_substitution_detected),
        "wrapper_substitution_allowed": bool(wrapper_substitution_allowed),
    }

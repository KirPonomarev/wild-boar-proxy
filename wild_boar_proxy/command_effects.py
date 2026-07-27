# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import Final

EFFECT_READ: Final = "read"
EFFECT_PROBE: Final = "probe"
EFFECT_MUTATE: Final = "mutate"
EFFECT_REPAIR: Final = "repair"

EFFECT_VALUES: Final = frozenset(
    {
        EFFECT_READ,
        EFFECT_PROBE,
        EFFECT_MUTATE,
        EFFECT_REPAIR,
    }
)


def validate_effect(effect: str) -> str:
    if effect not in EFFECT_VALUES:
        raise ValueError(f"Unsupported command effect: {effect}")
    return effect

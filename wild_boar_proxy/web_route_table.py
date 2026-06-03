# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Backend web route effect registry helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


EFFECT_READ = "read"
EFFECT_PROBE = "probe"
EFFECT_MUTATE = "mutate"
EFFECT_REPAIR = "repair"
CANONICAL_ROUTE_EFFECTS = frozenset(
    {
        EFFECT_READ,
        EFFECT_PROBE,
        EFFECT_MUTATE,
        EFFECT_REPAIR,
    }
)

BODY_KIND_NONE = "none"
BODY_KIND_JSON = "json"
BODY_KIND_OPTIONAL_JSON = "optional_json"
BODY_KIND_SPECIAL_JSON = "special_json"

BROWSER_FIELD_POLICY_NONE = "none"
BROWSER_FIELD_POLICY_QUERY_VALIDATED = "query_validated_by_handler"
BROWSER_FIELD_POLICY_JSON_VALIDATED = "json_validated_by_handler"
BROWSER_FIELD_POLICY_UI_ACTION_REGISTRY = "ui_action_registry"

EFFECT_SOURCE_ROUTE = "route"
EFFECT_SOURCE_UI_ACTION_REGISTRY = "ui_action_registry"
EFFECT_SOURCE_DYNAMIC_SUBACTION = "dynamic_subaction"


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    effect: str
    auth_required: bool
    body_kind: str
    browser_field_policy: str
    prefix: bool = False
    effect_source: str = EFFECT_SOURCE_ROUTE
    multiplexed_by: str | None = None
    handler_id: str | None = None

    def __post_init__(self) -> None:
        method = self.method.upper()
        path = normalize_request_path(self.path)
        handler_id = None if self.handler_id is None else str(self.handler_id).strip()
        if method not in {"GET", "POST"}:
            raise ValueError("method must be GET or POST")
        if not path.startswith("/"):
            raise ValueError("path must start with /")
        if self.effect not in CANONICAL_ROUTE_EFFECTS:
            raise ValueError(f"unsupported route effect: {self.effect}")
        if not handler_id:
            raise ValueError(f"{method} routes must declare handler_id")
        if self.prefix and not path.endswith("/"):
            raise ValueError("prefix routes must end with /")
        if not self.body_kind:
            raise ValueError("body_kind must be declared")
        if not self.browser_field_policy:
            raise ValueError("browser_field_policy must be declared")
        if handler_id == "":
            raise ValueError("handler_id must be non-empty when declared")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "handler_id", handler_id)

    @property
    def key(self) -> tuple[str, str, bool]:
        return (self.method, self.path, self.prefix)


class WebRouteTable:
    def __init__(self, routes: Iterable[RouteSpec]) -> None:
        self._routes = tuple(routes)
        exact: dict[tuple[str, str], RouteSpec] = {}
        prefix: dict[tuple[str, str], RouteSpec] = {}
        handler_ids_by_method: dict[str, set[str]] = {}
        for route in self._routes:
            bucket = prefix if route.prefix else exact
            key = (route.method, route.path)
            if key in bucket:
                raise ValueError(f"duplicate route spec: {route.method} {route.path}")
            bucket[key] = route
            handler_id = str(route.handler_id or "")
            method_handler_ids = handler_ids_by_method.setdefault(route.method, set())
            if handler_id in method_handler_ids:
                raise ValueError(f"duplicate {route.method} route handler_id: {handler_id}")
            method_handler_ids.add(handler_id)
        self._exact = exact
        self._prefixes = tuple(
            sorted(
                prefix.values(),
                key=lambda route: (route.method, len(route.path), route.path),
                reverse=True,
            )
        )

    @property
    def routes(self) -> tuple[RouteSpec, ...]:
        return self._routes

    def lookup(self, method: str, path: str) -> RouteSpec | None:
        normalized_method = method.upper()
        normalized_path = normalize_request_path(path)
        exact = self._exact.get((normalized_method, normalized_path))
        if exact is not None:
            return exact
        for route in self._prefixes:
            if route.method == normalized_method and normalized_path.startswith(route.path):
                return route
        return None


def normalize_request_path(path: str) -> str:
    value = str(path or "").split("?", 1)[0]
    return value or "/"

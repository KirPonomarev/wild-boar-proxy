# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.web_route_table import (
    BODY_KIND_JSON,
    BODY_KIND_NONE,
    BROWSER_FIELD_POLICY_JSON_VALIDATED,
    BROWSER_FIELD_POLICY_NONE,
    CANONICAL_ROUTE_EFFECTS,
    EFFECT_MUTATE,
    EFFECT_READ,
    RouteSpec,
    WebRouteTable,
)


class WebRouteTableTests(unittest.TestCase):
    def test_lookup_ignores_query_string(self) -> None:
        table = WebRouteTable(
            [
                RouteSpec(
                    method="POST",
                    path="/api/action",
                    effect=EFFECT_MUTATE,
                    auth_required=True,
                    body_kind=BODY_KIND_JSON,
                    browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
                    handler_id="post_api_action",
                )
            ]
        )

        route = table.lookup("POST", "/api/action?attempt=1")

        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(route.path, "/api/action")

    def test_prefix_routes_use_longest_match(self) -> None:
        broad = RouteSpec(
            method="POST",
            path="/api/codex/custom/",
            effect=EFFECT_MUTATE,
            auth_required=True,
            body_kind=BODY_KIND_JSON,
            browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
            handler_id="post_api_codex_custom_prefix",
            prefix=True,
        )
        narrow = RouteSpec(
            method="POST",
            path="/api/codex/custom/sessions/",
            effect=EFFECT_MUTATE,
            auth_required=True,
            body_kind=BODY_KIND_JSON,
            browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
            handler_id="post_api_codex_custom_sessions_prefix",
            prefix=True,
        )
        table = WebRouteTable([broad, narrow])

        route = table.lookup("POST", "/api/codex/custom/sessions/session-1/prompt")

        self.assertEqual(route, narrow)

    def test_duplicate_exact_routes_are_rejected(self) -> None:
        route = RouteSpec(
            method="GET",
            path="/api/status",
            effect=EFFECT_READ,
            auth_required=False,
            body_kind=BODY_KIND_NONE,
            browser_field_policy=BROWSER_FIELD_POLICY_NONE,
        )

        with self.assertRaises(ValueError):
            WebRouteTable([route, route])

    def test_duplicate_post_handler_ids_are_rejected(self) -> None:
        first = RouteSpec(
            method="POST",
            path="/api/first",
            effect=EFFECT_MUTATE,
            auth_required=True,
            body_kind=BODY_KIND_JSON,
            browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
            handler_id="post_duplicate",
        )
        second = RouteSpec(
            method="POST",
            path="/api/second",
            effect=EFFECT_MUTATE,
            auth_required=True,
            body_kind=BODY_KIND_JSON,
            browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
            handler_id="post_duplicate",
        )

        with self.assertRaises(ValueError):
            WebRouteTable([first, second])

    def test_effects_are_canonical(self) -> None:
        self.assertEqual(CANONICAL_ROUTE_EFFECTS, {"read", "probe", "mutate", "repair"})
        with self.assertRaises(ValueError):
            RouteSpec(
                method="GET",
                path="/api/status",
                effect="unknown",
                auth_required=False,
                body_kind=BODY_KIND_NONE,
                browser_field_policy=BROWSER_FIELD_POLICY_NONE,
            )

    def test_post_routes_require_handler_id(self) -> None:
        with self.assertRaises(ValueError):
            RouteSpec(
                method="POST",
                path="/api/status",
                effect=EFFECT_MUTATE,
                auth_required=True,
                body_kind=BODY_KIND_JSON,
                browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
            )


if __name__ == "__main__":
    unittest.main()

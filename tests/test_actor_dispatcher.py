# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B05: dispatcher resolution, permission intersection, repo lease tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import actor_dispatcher as ad
from wild_boar_proxy import actor_registry as ar
from wild_boar_proxy import repo_lease as rl

_V1_BINDINGS = [
    {
        "agent_id": "codex",
        "display_name": "Codex",
        "role": "orchestrator",
        "aliases": ["Codex", "Agent 1", "1"],
        "lane": "primary_chatgpt",
        "model_id": "gpt-5.5",
        "enabled": True,
        "allowed_actions": ["plan", "inspect", "patch", "verify"],
    },
    {
        "agent_id": "dip",
        "display_name": "DIP",
        "role": "coding_agent",
        "aliases": ["DIP", "Agent 2", "2"],
        "lane": "api_route",
        "route_id": "wbp-deepseek-chat",
        "enabled": True,
        "allowed_actions": ["code_review", "implementation_help"],
    },
]


class PermissionIntersectionTests(unittest.TestCase):
    def test_intersection_is_conservative(self) -> None:
        self.assertEqual(
            ad.effective_permission(
                binding_permission_ceiling="repo_write",
                explicit_operator_grant="repo_read",
                adapter_capability="network_read",
                runtime_policy="repo_read",
            ),
            "repo_read",
        )

    def test_assignment_cannot_grant(self) -> None:
        # role/assignment can only reduce: granting is structurally impossible
        self.assertEqual(
            ad.effective_permission(
                binding_permission_ceiling="context_only",
                explicit_operator_grant="repo_write",
                adapter_capability="repo_write",
                runtime_policy="repo_write",
            ),
            "context_only",
        )

    def test_none_wins(self) -> None:
        self.assertEqual(
            ad.effective_permission(
                binding_permission_ceiling="network_read",
                explicit_operator_grant="repo_read",
                adapter_capability="context_only",
                runtime_policy="repo_write",
            ),
            "context_only",
        )


class ResolutionTests(unittest.TestCase):
    def _registry(self) -> dict[str, object]:
        return ar.build_actor_registry_document(_V1_BINDINGS)

    def test_canonical_resolution(self) -> None:
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=self._registry())
        self.assertEqual(plan["machine_error_code"], "DISPATCH_PLAN_READY")
        self.assertFalse(plan["legacy_projection_used"])
        self.assertEqual(plan["binding_id"], "binding-agent_1")
        self.assertEqual(plan["actor_id"], "dip")
        self.assertEqual(plan["route_id"], "wbp-deepseek-chat")
        self.assertTrue(plan["no_fallback"])
        self.assertFalse(plan["cross_provider_fallback"])

    def test_primary_slot_resolution(self) -> None:
        plan = ad.resolve_alias_dispatch(alias="Codex", registry_document=self._registry())
        self.assertEqual(plan["slot_id"], "primary")
        self.assertEqual(plan["transport_adapter_id"], "native_primary")
        self.assertEqual(plan["model_policy"], {"model_id": "gpt-5.5"})

    def test_unknown_alias_fails_closed(self) -> None:
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(alias="Ghost", registry_document=self._registry())
        self.assertEqual(raised.exception.machine_error_code, "ALIAS_UNKNOWN")

    def test_legacy_projection_resolution(self) -> None:
        plan = ad.resolve_alias_dispatch(
            alias="Agent 2",
            registry_document=None,
            legacy_bindings=_V1_BINDINGS,
        )
        self.assertTrue(plan["legacy_projection_used"])
        self.assertEqual(plan["actor_id"], "dip")

    def test_stale_route_rejected_in_legacy(self) -> None:
        bindings = [dict(b) for b in _V1_BINDINGS]
        bindings[1]["route_id"] = "wbp-deepseek-v3"
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(
                alias="DIP", registry_document=None, legacy_bindings=bindings
            )
        self.assertEqual(raised.exception.machine_error_code, "STALE_ROUTE_REJECTED")

    def test_permission_denied_fails_closed(self) -> None:
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(
                alias="DIP",
                registry_document=self._registry(),
                explicit_operator_grant="none",
                adapter_capability="none",
                runtime_policy="none",
                requested_permission="repo_read",
            )
        self.assertEqual(raised.exception.machine_error_code, "PERMISSION_DENIED")

    def test_fork_requires_context_digest(self) -> None:
        registry = self._registry()
        registry["role_assignments"][1]["assignment_context_policy"] = "fork"
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        self.assertEqual(raised.exception.machine_error_code, "FORK_CONTEXT_DIGEST_MISSING")

    def test_fork_with_digest_ok(self) -> None:
        registry = self._registry()
        registry["role_assignments"][1]["assignment_context_policy"] = "fork"
        plan = ad.resolve_alias_dispatch(
            alias="DIP", registry_document=registry, context_digest="ctx-abc"
        )
        self.assertEqual(plan["assignment_context_policy"], "fork")

    def test_invalid_registry_fails_closed(self) -> None:
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(alias="DIP", registry_document={"schema_version": 2})
        self.assertEqual(raised.exception.machine_error_code, "ACTOR_REGISTRY_INVALID")

    def test_missing_registry_fails_closed(self) -> None:
        with self.assertRaises(ad.DispatchResolutionError) as raised:
            ad.resolve_alias_dispatch(alias="DIP", registry_document=None, legacy_bindings=None)
        self.assertEqual(raised.exception.machine_error_code, "ALIAS_UNKNOWN")


class DispatchRequestTests(unittest.TestCase):
    def test_build_request_from_plan(self) -> None:
        registry = ar.build_actor_registry_document(_V1_BINDINGS)
        plan = ad.resolve_alias_dispatch(alias="DIP", registry_document=registry)
        request = ad.build_dispatch_request(
            dispatch_plan=plan,
            dispatch_id="dispatch-1",
            text="review this",
            idempotency_key="idem-1",
            context_digest="ctx-1",
        )
        from wild_boar_proxy.transport_normalization import NormalizedRequest

        self.assertIsInstance(request, NormalizedRequest)
        assert isinstance(request, NormalizedRequest)
        self.assertEqual(request.dispatch_id, "dispatch-1")
        self.assertEqual(request.effective_permission, "context_only")


class RepoLeaseTests(unittest.TestCase):
    def test_acquire_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lease = rl.RepoLease(Path(temp_dir))
            acquired = lease.acquire(holder="actor-1", operation="read", worktree="/work")
            self.assertEqual(acquired["machine_error_code"], "REPO_LEASE_ACQUIRED")
            status = lease.status()
            self.assertTrue(status["lease_held"])

    def test_second_acquirer_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lease = rl.RepoLease(Path(temp_dir))
            lease.acquire(holder="actor-1", operation="read", worktree="/work")
            blocked = lease.acquire(holder="actor-2", operation="write", worktree="/work")
            self.assertEqual(blocked["machine_error_code"], "REPO_LEASE_HELD")

    def test_release_requires_matching_fencing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lease = rl.RepoLease(Path(temp_dir))
            acquired = lease.acquire(holder="actor-1", operation="read", worktree="/work")
            wrong = lease.release(fencing_token="not-the-token")
            self.assertEqual(wrong["machine_error_code"], "REPO_LEASE_FENCING_MISMATCH")
            released = lease.release(fencing_token=acquired["fencing_token"])
            self.assertEqual(released["machine_error_code"], "REPO_LEASE_RELEASED")
            self.assertEqual(lease.status()["machine_error_code"], "REPO_LEASE_FREE")

    def test_stale_lease_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lease = rl.RepoLease(Path(temp_dir))
            lease.acquire(holder="actor-1", operation="read", worktree="/work", ttl_seconds=0)
            acquired = lease.acquire(holder="actor-2", operation="read", worktree="/work")
            self.assertEqual(acquired["machine_error_code"], "REPO_LEASE_ACQUIRED")


if __name__ == "__main__":
    unittest.main()

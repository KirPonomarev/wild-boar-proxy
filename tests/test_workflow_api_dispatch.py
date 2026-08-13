# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wild_boar_proxy import actor_dispatcher
from wild_boar_proxy import actor_registry
from wild_boar_proxy import api_transport_adapter
from wild_boar_proxy import sequential_workflow_runner as workflow
from wild_boar_proxy import workflow_api_dispatch as wad
from wild_boar_proxy.deepseek_route_profile import build_deepseek_route_definition
from wild_boar_proxy.external_models import routes as external_routes
from wild_boar_proxy.kimi_glm_provider_slices import build_kimi_route_definition
from wild_boar_proxy.repo_lease import RepoLease


def _fixtures(root: Path):
    deepseek = build_deepseek_route_definition()
    kimi = build_kimi_route_definition()
    for route in (deepseek, kimi):
        route["auth"] = {"type": "none"}
        route["enabled"] = True
    root.mkdir(parents=True, exist_ok=True)
    external_routes.write_routes_file(
        root / "routes.json",
        {"schema_version": 1, "routes": [deepseek, kimi]},
    )
    registry = actor_registry.build_actor_registry_document(
        [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex"],
                "lane": "primary_chatgpt",
                "model_id": "gpt-5.5",
                "enabled": True,
                "allowed_actions": [],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "researcher",
                "aliases": ["DIP"],
                "lane": "api_route",
                "route_id": deepseek["route_id"],
                "enabled": True,
                "allowed_actions": [],
            },
            {
                "agent_id": "kimi",
                "display_name": "Kimi",
                "role": "reviewer",
                "aliases": ["Kimi"],
                "lane": "api_route",
                "route_id": kimi["route_id"],
                "enabled": True,
                "allowed_actions": [],
            },
        ],
        route_records=[deepseek, kimi],
    )
    adapter = api_transport_adapter.ApiTransportAdapter(
        routes_file=root / "routes.json",
        external_models_dir=root,
        managed_dir=root / "managed",
    )
    return registry, adapter


def _step(
    registry,
    alias: str,
    step_id: str,
    *,
    policy: str = workflow.CONTEXT_POLICY_FRESH,
    fork_from: str = "",
    repo_touching: bool = False,
):
    plan = actor_dispatcher.resolve_alias_dispatch(
        alias=alias,
        registry_document=registry,
    )
    return workflow.WorkflowStep(
        step_request_id=step_id,
        slot_id=plan["slot_id"],
        binding_id=plan["binding_id"],
        binding_revision=plan["binding_revision"],
        assignment_id=plan["assignment_id"],
        assignment_revision=plan["assignment_revision"],
        provider=plan["provider_id"],
        prompt=f"task for {step_id}",
        role_instruction=f"role for {step_id}",
        context_policy=policy,
        fork_from=fork_from,
        repo_touching=repo_touching,
        alias=alias,
    )


class WorkflowApiDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry, self.adapter = _fixtures(self.root / "external-models")
        self.lease_root = self.root / "lease"

    def tearDown(self):
        self.temp.cleanup()

    def run_controlled(self, steps):
        return wad.run_registry_bound_api_workflow(
            steps,
            registry_document=self.registry,
            adapter=self.adapter,
            execution_mode=wad.EXECUTION_MODE_CONTROLLED,
            lease_root=self.lease_root,
            workflow_run_id="workflow-test",
        )

    def test_controlled_path_uses_real_registry_and_adapter_boundary(self):
        steps = [
            _step(self.registry, "DIP", "s1"),
            _step(
                self.registry,
                "Kimi",
                "s2",
                policy=workflow.CONTEXT_POLICY_CONTINUE,
            ),
        ]
        calls = []
        original = self.adapter.dispatch

        def record(request, plan, **kwargs):
            calls.append((request, plan, kwargs))
            return original(request, plan, **kwargs)

        with patch.object(self.adapter, "dispatch", side_effect=record):
            packet = self.run_controlled(steps)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["controlled"])
        self.assertFalse(packet["live_provider_proven"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call[2]["controlled"] for call in calls))
        self.assertIn("VERIFIED PRIOR WORKFLOW CONTEXT", calls[1][0].text)
        self.assertIn(packet["receipts"][0]["output_text"], calls[1][0].text)
        self.assertTrue(packet["receipts"][1]["context_material_delivered"])
        self.assertEqual(
            packet["receipts"][1]["visible_context_source_step"], "s1"
        )

    def test_live_mode_fails_before_credential_probe_without_authorization(self):
        with patch.object(
            self.adapter,
            "_credential_presence",
            side_effect=AssertionError("credential presence must not be probed"),
        ), patch.object(
            self.adapter,
            "dispatch",
            side_effect=AssertionError("dispatch must not be attempted"),
        ):
            packet = wad.run_registry_bound_api_workflow(
                [_step(self.registry, "DIP", "s1")],
                registry_document=self.registry,
                adapter=self.adapter,
                execution_mode=wad.EXECUTION_MODE_LIVE,
                live_dispatch_authorized=False,
                lease_root=self.lease_root,
            )
        self.assertEqual(packet["machine_error_code"], wad.WAD_LIVE_NOT_AUTHORIZED)
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["credential_probe_performed"])

    def test_authorized_live_mode_passes_exact_identity_and_context(self):
        steps = [
            _step(self.registry, "DIP", "s1"),
            _step(
                self.registry,
                "Kimi",
                "s2",
                policy=workflow.CONTEXT_POLICY_CONTINUE,
            ),
        ]
        calls = []

        def live_double(request, plan, **kwargs):
            calls.append((request, plan, kwargs))
            return {
                "status": "ok",
                "machine_error_code": "DISPATCH_COMPLETE",
                "provider_id": plan["provider_id"],
                "response_text": f"live output {kwargs['step_request_id']}",
                "dispatch_proven": True,
                "dispatch_attempted": True,
                "response_observed": True,
                "controlled": False,
                "live_provider_called": True,
                "live_provider_proven": True,
                "result": "ok",
            }

        with patch.object(self.adapter, "dispatch", side_effect=live_double):
            packet = wad.run_registry_bound_api_workflow(
                steps,
                registry_document=self.registry,
                adapter=self.adapter,
                execution_mode=wad.EXECUTION_MODE_LIVE,
                live_dispatch_authorized=True,
                lease_root=self.lease_root,
                workflow_run_id="workflow-live-double",
            )
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["live_provider_proven"])
        self.assertFalse(calls[0][2]["controlled"])
        self.assertEqual(calls[1][2]["slot_id"], steps[1].slot_id)
        self.assertEqual(
            calls[1][2]["assignment_revision"], steps[1].assignment_revision
        )
        self.assertIn("live output s1", calls[1][0].text)
        self.assertNotEqual(calls[0][0].idempotency_key, calls[1][0].idempotency_key)

    def test_authorized_live_mode_missing_credential_stops_before_network(self):
        routes = self.adapter._load_routes()
        route = routes[next(iter(routes))]
        route["auth"] = {"type": "bearer", "secret_ref": "TEST_REF"}
        external_routes.write_routes_file(
            self.adapter.routes_file,
            {"schema_version": 1, "routes": list(routes.values())},
        )
        step = _step(self.registry, "DIP", "s1")
        with patch.object(
            self.adapter, "_credential_presence", return_value=(False, "")
        ), patch.object(
            self.adapter,
            "_live_dispatch",
            side_effect=AssertionError("network seam must not run"),
        ):
            packet = wad.run_registry_bound_api_workflow(
                [step],
                registry_document=self.registry,
                adapter=self.adapter,
                execution_mode=wad.EXECUTION_MODE_LIVE,
                live_dispatch_authorized=True,
                lease_root=self.lease_root,
            )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["receipts"][0]["machine_error_code"], "CREDENTIAL_MISSING")
        self.assertFalse(packet["receipts"][0]["live_provider_called"])

    def test_caller_identity_drift_fails_before_transport(self):
        step = _step(self.registry, "DIP", "s1")
        drifted = workflow.WorkflowStep(
            **{**step.to_dict(), "binding_revision": step.binding_revision + 1}
        )
        with patch.object(
            self.adapter,
            "dispatch",
            side_effect=AssertionError("transport must not run"),
        ):
            packet = self.run_controlled([drifted])
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["receipts"][0]["machine_error_code"], wad.WAD_IDENTITY_DRIFT
        )

    def test_invalid_registry_fails_before_transport(self):
        invalid = dict(self.registry)
        invalid["slot_bindings"] = []
        with patch.object(
            self.adapter,
            "dispatch",
            side_effect=AssertionError("transport must not run"),
        ):
            packet = wad.run_registry_bound_api_workflow(
                [_step(self.registry, "DIP", "s1")],
                registry_document=invalid,
                adapter=self.adapter,
                execution_mode=wad.EXECUTION_MODE_CONTROLLED,
            )
        self.assertEqual(packet["machine_error_code"], wad.WAD_REGISTRY_INVALID)

    def test_unknown_execution_mode_fails_before_transport(self):
        with patch.object(
            self.adapter,
            "dispatch",
            side_effect=AssertionError("transport must not run"),
        ):
            packet = wad.run_registry_bound_api_workflow(
                [_step(self.registry, "DIP", "s1")],
                registry_document=self.registry,
                adapter=self.adapter,
                execution_mode="maybe",
            )
        self.assertEqual(packet["machine_error_code"], wad.WAD_MODE_INVALID)

    def test_missing_context_delivery_proof_stops_before_third_step(self):
        steps = [
            _step(self.registry, "DIP", "s1"),
            _step(
                self.registry,
                "Kimi",
                "s2",
                policy=workflow.CONTEXT_POLICY_CONTINUE,
            ),
            _step(
                self.registry,
                "DIP",
                "s3",
                policy=workflow.CONTEXT_POLICY_CONTINUE,
            ),
        ]
        seen = []

        def incomplete_proof(request, plan, **kwargs):
            seen.append(kwargs["step_request_id"])
            return {
                "status": "ok",
                "machine_error_code": "DISPATCH_COMPLETE",
                "provider_id": plan["provider_id"],
                "response_text": "output",
                "dispatch_proven": kwargs["step_request_id"] != "s2",
                "response_observed": True,
                "controlled": True,
                "live_provider_called": False,
                "live_provider_proven": False,
                "result": "ok",
            }

        with patch.object(self.adapter, "dispatch", side_effect=incomplete_proof):
            packet = self.run_controlled(steps)
        self.assertEqual(packet["machine_error_code"], workflow.WF_CONTEXT_DELIVERY_UNPROVEN)
        self.assertEqual(seen, ["s1", "s2"])
        self.assertFalse(packet["visible_delivery"])

    def test_fork_delivers_named_step_material(self):
        steps = [
            _step(self.registry, "DIP", "s1"),
            _step(self.registry, "Kimi", "s2"),
            _step(
                self.registry,
                "DIP",
                "s3",
                policy=workflow.CONTEXT_POLICY_FORK,
                fork_from="s1",
            ),
        ]
        texts = {}
        original = self.adapter.dispatch

        def record(request, plan, **kwargs):
            texts[kwargs["step_request_id"]] = request.text
            return original(request, plan, **kwargs)

        with patch.object(self.adapter, "dispatch", side_effect=record):
            packet = self.run_controlled(steps)
        self.assertEqual(packet["status"], "ok")
        self.assertIn(packet["receipts"][0]["output_text"], texts["s3"])
        self.assertNotIn(packet["receipts"][1]["output_text"], texts["s3"])
        self.assertEqual(
            packet["receipts"][2]["visible_context_source_step"], "s1"
        )

    def test_unexpected_dispatch_exception_releases_repo_lease(self):
        step = _step(self.registry, "DIP", "s1", repo_touching=True)
        with patch.object(self.adapter, "dispatch", side_effect=RuntimeError("boom")):
            packet = self.run_controlled([step])
        self.assertEqual(packet["machine_error_code"], workflow.WF_DISPATCH_EXCEPTION)
        self.assertEqual(
            RepoLease(self.lease_root).status()["machine_error_code"],
            "REPO_LEASE_FREE",
        )

    def test_late_unknown_fork_releases_already_owned_repo_lease(self):
        steps = [
            _step(self.registry, "DIP", "s1", repo_touching=True),
            _step(
                self.registry,
                "Kimi",
                "s2",
                policy=workflow.CONTEXT_POLICY_FORK,
                fork_from="missing",
            ),
        ]
        packet = self.run_controlled(steps)
        self.assertEqual(packet["machine_error_code"], workflow.WF_FORK_TARGET_UNKNOWN)
        self.assertEqual(
            RepoLease(self.lease_root).status()["machine_error_code"],
            "REPO_LEASE_FREE",
        )


if __name__ == "__main__":
    unittest.main()

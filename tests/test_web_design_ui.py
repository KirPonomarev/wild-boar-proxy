# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import unittest
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
FIXTURES = WEB_DESIGN_UI / "fixtures"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class WebDesignUiTests(unittest.TestCase):
    def test_first_screen_design_assets_exist(self) -> None:
        self.assertTrue((WEB_DESIGN_UI / "index.html").is_file())
        self.assertTrue((WEB_DESIGN_UI / "styles" / "overview.css").is_file())
        self.assertTrue((WEB_DESIGN_UI / "scripts" / "overview.js").is_file())
        self.assertTrue((WEB_DESIGN_UI / "assets" / "boar_mark.png").is_file())

    def test_referenced_phosphor_png_assets_exist_and_tokens_are_declared(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        icon_refs = set(re.findall(r'assets/icons/phosphor/([^"\']+\.png)', html + css))
        self.assertIn("folder.png", icon_refs)
        for icon_ref in icon_refs:
            self.assertTrue((WEB_DESIGN_UI / "assets" / "icons" / "phosphor" / icon_ref).is_file(), icon_ref)
        self.assertNotIn("var(--mono)", css)

    def test_fixture_states_are_present_and_distinct(self) -> None:
        expected = {
            "healthy",
            "degraded",
            "down",
            "stale",
            "unknown",
            "integration_failure",
        }
        actual = {path.stem for path in FIXTURES.glob("*.json")}
        self.assertLessEqual(expected, actual)

        visual_states = {}
        for state in expected:
            payload = json.loads((FIXTURES / f"{state}.json").read_text())
            self.assertEqual(payload["state_id"], state)
            visual_states[state] = payload["runtime"]["visual_state"]

        self.assertEqual(visual_states["healthy"], "healthy")
        self.assertEqual(visual_states["down"], "down")
        self.assertEqual(visual_states["unknown"], "unknown")
        self.assertEqual(visual_states["integration_failure"], "integration_failure")
        self.assertNotEqual(visual_states["healthy"], visual_states["stale"])

    def test_fixtures_have_required_runtime_shape(self) -> None:
        required_top = {
            "schema_version",
            "state_id",
            "fixture_notice",
            "runtime",
            "pool_summary",
            "events",
        }
        required_runtime = {
            "visual_state",
            "status_label",
            "desired_mode",
            "effective_mode",
            "endpoint",
            "machine_error_code",
            "human_message",
            "last_error",
            "observed_at_utc",
        }
        required_pool = {
            "active",
            "reserve",
            "hold",
            "problem",
            "active_note",
            "reserve_note",
            "hold_note",
            "problem_note",
        }

        for path in FIXTURES.glob("*.json"):
            payload = json.loads(path.read_text())
            self.assertLessEqual(required_top, set(payload), path)
            self.assertLessEqual(required_runtime, set(payload["runtime"]), path)
            self.assertLessEqual(required_pool, set(payload["pool_summary"]), path)
            self.assertIsInstance(payload["events"], list, path)
            self.assertTrue(
                "not runtime truth" in payload["fixture_notice"].lower()
                or "не является runtime truth" in payload["fixture_notice"].lower()
                or "не является runtime evidence" in payload["fixture_notice"].lower()
                or payload["state_id"] != "healthy",
                path,
            )

    def test_static_design_ui_does_not_execute_live_commands_or_read_runtime_files(
        self,
    ) -> None:
        combined = "\n".join(
            [
                (WEB_DESIGN_UI / "index.html").read_text(),
                (WEB_DESIGN_UI / "scripts" / "overview.js").read_text(),
            ]
        )
        forbidden_fragments = [
            "subprocess",
            "child_process",
            "exec(",
            "spawn(",
            "status --json",
            "healthcheck --json",
            "accounts list --json",
            "rollout rotation inspect --json",
            "state.json",
            "routes.json",
            "secrets.env",
            "supervisor-state",
            ".codex-custom-cli",
            ".cli-proxy-api",
        ]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, combined)

    def test_static_preview_serves_index_and_fixture_payloads(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        process = subprocess.Popen(
            [
                "python3",
                "-m",
                "http.server",
                str(port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(WEB_DESIGN_UI),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            index = self._fetch_with_retry(f"{base_url}/?state=healthy")
            self.assertIn("Wild Boar Proxy - предпросмотр операторского интерфейса", index)
            self.assertIn("sourcePicker", index)
            self.assertIn("statePicker", index)
            self.assertIn("fixtureBanner", index)

            for state in [
                "healthy",
                "degraded",
                "down",
                "stale",
                "unknown",
                "integration_failure",
            ]:
                body = self._fetch_with_retry(f"{base_url}/fixtures/{state}.json")
                payload = json.loads(body)
                self.assertEqual(payload["state_id"], state)
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_preview_uses_desktop_containment_and_icon_hooks(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('content="width=device-width, initial-scale=1"', html)
        self.assertIn('class="ui-icon nav-icon"', html)
        self.assertIn('class="ui-icon tile-icon"', html)
        self.assertIn("--window-width: 1544px;", css)
        self.assertIn("--window-height: 944px;", css)
        self.assertIn("--sidebar-width: 304px;", css)
        self.assertIn("width: min(var(--window-width), calc(100vw - 56px));", css)
        self.assertIn("height: min(var(--window-height), calc(100vh - 56px));", css)
        self.assertIn("padding: 66px 24px 28px;", css)
        self.assertIn("width: 180px;", css)
        self.assertIn("font-size: 16px;", css)
        self.assertIn("line-height: 20px;", css)
        self.assertIn("display: none;", css)
        self.assertIn("gap: 8px;", css)
        self.assertIn("height: 42px;", css)
        self.assertIn("padding: 0 14px;", css)
        self.assertIn("padding: 48px 40px 32px;", css)
        self.assertIn("--radius-window: 24px;", css)
        self.assertIn("--radius-card: 18px;", css)
        self.assertIn("--radius-button: 12px;", css)
        self.assertIn("--radius-chip: 999px;", css)
        self.assertIn("border-radius: var(--radius-window);", css)
        self.assertIn("border-radius: var(--radius-card);", css)
        self.assertIn("border-radius: var(--radius-button);", css)
        self.assertIn("border-radius: var(--radius-chip);", css)
        self.assertIn("line-height: 20px;", css)
        self.assertIn("line-height: 28px;", css)
        self.assertIn("overflow-x: hidden;", css)
        self.assertIn("@media (max-width: 1420px)", css)
        self.assertIn('@media (max-width: 1320px)', css)
        self.assertIn('--font-ui: "SF Mono"', css)
        self.assertIn("font-family: var(--font-ui);", css)
        self.assertNotIn("--preview-scale", css)
        self.assertNotIn("fitPreviewToViewport", js)

    def test_design_finish_adds_narrow_responsive_stack_and_table_scroll_guards(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('data-table-scroll="accounts"', html)
        self.assertIn('data-table-scroll="api-connections"', html)
        self.assertIn(".table-scroll", css)
        self.assertIn("@media (max-width: 980px)", css)
        self.assertIn(".sidebar,\n  .main {\n    position: static;", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)
        self.assertIn(".header-actions > .button", css)
        self.assertIn(".quick-start-account-row {\n    gap: 10px;\n    grid-template-columns: 32px minmax(0, 1fr);", css)
        self.assertIn(".api-route-builder-card {\n    grid-template-columns: 36px minmax(0, 1fr);", css)

    def test_visual_stabilization_keeps_layout_guards_css_only(self) -> None:
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn("max-width: min(100%, 660px);", css)
        self.assertIn("width: min(236px, 100%);", css)
        self.assertIn("overflow-x: auto;", css)
        self.assertIn("min-width: 980px;", css)
        self.assertIn("flex: 1 1 calc(50% - 4px);", css)
        self.assertIn("max-height: calc(100vh - 372px);", css)
        self.assertIn("max-height: calc(100vh - 448px);", css)
        self.assertIn(".api-route-action-group", css)
        self.assertIn(".api-route-builder-card", css)
        self.assertIn("max-width: 640px;", css)
        self.assertIn("max-height: calc(100vh - 96px);", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(150px, 1fr));", css)
        self.assertIn(".accounts-filter-row", css)
        self.assertIn(".accounts-chips", css)

        self.assertIn("boundedUiActionPayload(uiAction, extraPayload)", js)
        self.assertIn("BROWSER_ACTION_PAYLOAD_KEYS", js)
        self.assertIn("body: JSON.stringify(requestPayload)", js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn('data-ui-action="stable_repair_apply"', (WEB_DESIGN_UI / "index.html").read_text())

    def test_static_preview_can_request_live_readonly_source_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('<option value="live">live только чтение</option>', html)
        self.assertIn('fetch("api/live-readonly"', js)
        self.assertIn('fetch("api/accounts-readonly"', js)
        self.assertIn('fetch("api/api-connections-readonly"', js)
        self.assertIn('fetch("api/actions"', js)
        self.assertIn('snapshot.source === "live_readonly"', js)
        self.assertIn('safeSnapshot.source === "accounts_readonly"', js)
        self.assertIn('safeSnapshot.state_id || safeSnapshot.ui_state', js)
        self.assertNotIn("command_id", js)
        self.assertNotIn("client_path", js)

    def test_codex_custom_model_registry_ui_is_dry_run_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomModelsPanel"', html)
        self.assertIn('id="codexCustomModelSelect"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/models\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/api-compat\")", js)
        self.assertIn('fetch("api/codex/custom/model-dry-run"', js)
        self.assertIn("body: JSON.stringify({ model_id: modelId })", js)
        self.assertIn("openai_compatible_shape_declared === true", js)
        self.assertIn("live_api_checked === true ? \"checked\" : \"not checked\"", js)
        self.assertIn("selected_model_server_issued: packet?.selected_model_server_issued === true", js)
        self.assertIn("network_calls_made: packet?.network_call_summary?.network_calls_made === true", js)
        self.assertIn("responses_called: packet?.responses_called === true", js)
        self.assertIn("chat_completions_called: packet?.chat_completions_called === true", js)
        self.assertIn("token_burn: packet?.token_burn ?? 0", js)
        self.assertNotIn('fetch("api/codex/custom/session"', js)

    def test_codex_launch_mode_split_ui_has_original_and_custom_dry_run_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexLaunchModesPanel"', html)
        self.assertIn('id="originalCodexDryRunAction"', html)
        self.assertIn('id="codexCustomLaunchDryRunAction"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/launch-modes\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/original/status\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/status\")", js)
        self.assertIn('fetch("api/codex/original/launch-dry-run"', js)
        self.assertIn('fetch("api/codex/custom/launch-dry-run"', js)
        self.assertIn("body: JSON.stringify({})", js)
        self.assertIn("current_codex_home_allowed: packet?.current_codex_home_allowed === true", js)
        self.assertIn("real_launch_attempted: packet?.real_launch_attempted === true", js)
        self.assertIn("prompt_attempted: packet?.prompt_attempted === true", js)
        self.assertNotIn('fetch("api/codex/original/launch",', js)
        self.assertNotIn('fetch("api/codex/custom/launch",', js)

    def test_codex_custom_accounts_ui_is_selection_not_inference(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomAccountsPanel"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/accounts\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/account-selection\")", js)
        self.assertIn('fetch("api/codex/custom/account-smoke-dry-run"', js)
        self.assertIn("body: JSON.stringify({ model_id: modelId })", js)
        self.assertIn("selection_dry_run_proven: packet?.selection_dry_run_proven === true", js)
        self.assertIn("live_selection_proven: packet?.live_selection_proven === true", js)
        self.assertIn("selection_proven: packet?.selection_proven === true", js)
        self.assertIn("inference_proven: packet?.inference_proven === true", js)
        self.assertIn("selected_backend_ref: packet?.selected_backend_ref || \"\"", js)
        self.assertIn("selected_backend_id_redacted: packet?.selected_backend_id_redacted === true", js)
        self.assertIn("browser_selected_backend: packet?.browser_selected_backend === true", js)
        self.assertIn("network_calls_made: packet?.network_calls_made === true", js)
        self.assertIn("account_mutation_performed: packet?.account_mutation_performed === true", js)
        self.assertIn("Account packet dry-run", html)
        self.assertIn("Account selection dry-run", html)
        self.assertNotIn("JSON.stringify({ model_id: modelId, account_id", js)
        self.assertNotIn("selected_backend_id: packet?.selected_backend_id", js)
        self.assertNotIn('fetch("api/codex/custom/account-smoke"', js)

    def test_codex_custom_sessions_ui_is_lifecycle_not_inference(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomSessionsPanel"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/sessions\")", js)
        self.assertIn("api/codex/custom/sessions/${encodeURIComponent(codexCustomSelectedSessionId)}", js)
        self.assertIn("body: JSON.stringify(payload)", js)
        self.assertIn("createCodexCustomSession()", js)
        self.assertIn("runCodexCustomSessionPromptDryRun()", js)
        self.assertIn("cancelCodexCustomSession()", js)
        self.assertIn("cleanupCodexCustomSession()", js)
        self.assertIn("postCodexCustomSessionAction(\"create\", { model_id: modelId })", js)
        self.assertIn("postCodexCustomSessionAction(\"prompt-dry-run\", { prompt: promptNode ? promptNode.value : \"\" })", js)
        self.assertIn("runCodexCustomSessionPrompt()", js)
        self.assertIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\" })", js)
        self.assertIn('id="codexCustomSessionPromptRunAction"', html)
        self.assertIn('document.getElementById("codexCustomSessionPromptRunAction")?.addEventListener("click", () => runCodexCustomSessionPrompt())', js)
        self.assertIn("selection_dry_run_proven: selectionDryRun", js)
        self.assertIn("live_selection_proven: liveSelection", js)
        self.assertIn("source_provenance_status: packet?.source_provenance_status || session?.source_provenance_status || \"\"", js)
        self.assertIn("source_provenance_proven: packet?.source_provenance_proven === true || session?.source_provenance_proven === true", js)
        self.assertIn("selected_source_provenance: packet?.selected_source_provenance || \"\"", js)
        self.assertIn("authorization_status: packet?.authorization_status || \"\"", js)
        self.assertIn("owner_authorization_phrase_present: packet?.owner_authorization_phrase_present === true", js)
        self.assertIn("live_prompt_admitted: packet?.live_prompt_admitted === true", js)
        self.assertIn("live_prompt_executed: packet?.live_prompt_executed === true", js)
        self.assertIn("live_prompt_full_success: packet?.live_prompt_full_success === true", js)
        self.assertIn("prompt_runner_called: packet?.prompt_runner_called === true", js)
        self.assertIn("raw_prompt_not_stored: packet?.raw_prompt_not_stored === true", js)
        self.assertIn("network_calls_made: packet?.network_calls_made === true || session?.network_calls_made === true", js)
        self.assertIn("model_response_present: modelResponsePresent", js)
        self.assertIn("response_digest: packet?.response_digest || \"\"", js)
        self.assertIn("wbp_path_configured: packet?.wbp_path_configured === true", js)
        self.assertIn("cli_proxy_api_path_configured: packet?.cli_proxy_api_path_configured === true", js)
        self.assertIn("wbp_path_observed: packet?.wbp_path_observed === true", js)
        self.assertIn("cli_proxy_api_path_observed: packet?.cli_proxy_api_path_observed === true", js)
        self.assertIn("wbp_path_proven: packet?.wbp_path_proven === true", js)
        self.assertIn("cli_proxy_api_path_proven: packet?.cli_proxy_api_path_proven === true", js)
        self.assertIn("independent_wbp_trace_observed: packet?.independent_wbp_trace_observed === true", js)
        self.assertIn("trace_path: packet?.trace_path || \"\"", js)
        self.assertIn("upstream_status: packet?.upstream_status ?? null", js)
        self.assertIn("forwarded_to_wbp: packet?.forwarded_to_wbp === true", js)
        self.assertIn("isolated_engine_home_proven: packet?.isolated_engine_home_proven === true", js)
        self.assertIn("current_codex_touched: packet?.current_codex_touched === true", js)
        self.assertIn("configured_wire_api: packet?.configured_wire_api || \"\"", js)
        self.assertIn("path_proof_status: packet?.path_proof_status || \"\"", js)
        self.assertIn("fallback_attempted: packet?.fallback_attempted === true", js)
        self.assertIn("process_kill_claimed: packet?.process_kill_claimed === true", js)
        self.assertIn("owned_session_root_only: packet?.owned_session_root_only === true", js)
        self.assertIn("current_codex_home_touched: packet?.current_codex_home_touched === true", js)
        self.assertIn("arbitrary_path_accepted: packet?.arbitrary_path_accepted === true", js)
        self.assertIn("inference_proven: inference", js)
        self.assertIn("token_burn: tokenBurn", js)
        self.assertNotIn("postCodexCustomSessionAction(\"create\", { model_id: modelId, account_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"create\", { model_id: modelId, backend_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt-dry-run\", { prompt: promptNode ? promptNode.value : \"\", backend_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\", backend_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\", model_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"cleanup\", { path", js)

    def test_codex_custom_recovery_surface_is_bounded_and_readonly(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomRecoveryPanel"', html)
        self.assertIn('id="codexCustomRecoveryContractAction"', html)
        self.assertIn('id="codexCustomRecoverySessionActionsAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwnerAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmissionAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmissionAction"', html)
        self.assertIn('id="codexCustomRecoveryAdmittedSessionActions"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwner"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPoint"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmission"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmission"', html)
        self.assertIn('id="codexCustomRecoveryAdmittedSessionActionsPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwnerPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmissionPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmissionPacket"', html)
        self.assertIn('id="codexCustomRecoveryContractActions"', html)
        self.assertIn('id="codexCustomRecoveryContractPacket"', html)
        self.assertIn('id="codexCustomRecoveryPacket"', html)
        self.assertIn('"machine_error_code": "RECOVERY_CONTRACT_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_contract_dry_run_only"', html)
        self.assertIn('"contract_endpoint_mutation_allowed": false', html)
        self.assertIn('"recovery_live_ready": false', html)
        self.assertIn('"operator_ready_claimed": false', html)
        self.assertIn('"machine_error_code": "ADMITTED_SESSION_ACTIONS_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_admitted_session_actions_only"', html)
        self.assertIn('"session_admitted_actions_ready": false', html)
        self.assertIn('"selected_session_cancel_ready": false', html)
        self.assertIn('"owned_session_cleanup_ready": false', html)
        self.assertIn('"recovery_operator_ready": false', html)
        self.assertIn('"rollback_operator_ready": false', html)
        self.assertIn('"process_kill_operator_ready": false', html)
        self.assertIn('"diagnostics_counted_as_recovery_action": false', html)
        self.assertIn('"readonly_checks_counted_as_mutation": false', html)
        self.assertIn('"session_create_counted_as_recovery_action": false', html)
        self.assertIn('"machine_error_code": "ROLLBACK_PROCESS_OWNER_CONTRACT_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_process_owner_dry_run_contract_only"', html)
        self.assertIn('"rollback_contract_defined": false', html)
        self.assertIn('"rollback_live_ready": false', html)
        self.assertIn('"rollback_apply_admitted": false', html)
        self.assertIn('"process_owner_contract_defined": false', html)
        self.assertIn('"process_kill_live_ready": false', html)
        self.assertIn('"process_kill_admitted": false', html)
        self.assertIn('"browser_payload_allowed_keys": []', html)
        self.assertIn('"machine_error_code": "ROLLBACK_POINT_DRY_RUN_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_point_dry_run_only"', html)
        self.assertIn('"rollback_point_contract_defined": false', html)
        self.assertIn('"rollback_point_present": false', html)
        self.assertIn('"rollback_point_create_admitted": false', html)
        self.assertIn('"rollback_write_surfaces_contract_defined": false', html)
        self.assertIn('"rollback_write_surfaces_machine_checked": false', html)
        self.assertIn('"rollback_write_surfaces_dry_run_checked": false', html)
        self.assertIn('"rollback_verification_packet_defined": false', html)
        self.assertIn('"filesystem_write_performed": false', html)
        self.assertIn('"snapshot_file_created": false', html)
        self.assertIn('"auth_material_allowed_surface": false', html)
        self.assertIn('"arbitrary_path_allowed_surface": false', html)
        self.assertIn('"machine_error_code": "ROLLBACK_POINT_CREATE_ADMISSION_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_point_create_admission_only"', html)
        self.assertIn('"rollback_point_dry_run_contract_valid": false', html)
        self.assertIn('"rollback_point_create_admission_defined": false', html)
        self.assertIn('"rollback_point_create_admitted_for_current_contour": false', html)
        self.assertIn('"rollback_point_create_performed": false', html)
        self.assertIn('"rollback_point_created": false', html)
        self.assertIn('"write_surface_machine_check_performed": false', html)
        self.assertIn('"write_surfaces_all_eligible": false', html)
        self.assertIn('"claim_scope": "custom_recovery_surface_readonly_checks_only"', html)
        self.assertIn('"action_scope": "bounded_custom_session_only"', html)
        self.assertIn('"current_codex_touched": false', html)
        self.assertIn('"original_codex_touched": false', html)
        self.assertIn('"owned_session_root_only": true', html)
        self.assertIn('"arbitrary_path_accepted": false', html)
        self.assertIn('"browser_forbidden_fields_rejected": true', html)
        self.assertIn('"accounts_readonly_ok": false', html)
        self.assertIn('"api_readonly_ok": false', html)
        self.assertIn('"process_kill_claimed": false', html)
        self.assertIn('"rollback_claimed": false', html)
        self.assertIn('"live_recovery_proof_claimed": false', html)
        self.assertIn('"historical_isolation_proof_only": true', html)
        self.assertIn('"fresh_truth": false', html)
        self.assertIn('"load_or_rotation_claimed": false', html)
        self.assertIn('"diagnostics_support_artifact_only": true', html)
        self.assertIn('"dangerous_actions_disabled": true', html)

        self.assertIn("refreshCodexCustomRecoveryContract()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/contract")', js)
        self.assertIn("refreshCodexCustomRecoveryAdmittedSessionActions()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/admitted-session-actions")', js)
        self.assertIn("renderCodexCustomRecoveryAdmittedSessionActions", js)
        self.assertIn("refreshCodexCustomRecoveryRollbackProcessOwnerContract()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/rollback-process-owner-contract")', js)
        self.assertIn("renderCodexCustomRecoveryRollbackProcessOwnerContract", js)
        self.assertIn("refreshCodexCustomRecoveryRollbackPointDryRun()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point-dry-run")', js)
        self.assertIn("renderCodexCustomRecoveryRollbackPointDryRun", js)
        self.assertIn("refreshCodexCustomRecoveryRollbackPointCreateAdmission()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point-create-admission")', js)
        self.assertIn("renderCodexCustomRecoveryRollbackPointCreateAdmission", js)
        self.assertIn("createCodexCustomRecoveryRollbackPoint()", js)
        self.assertIn('fetch("api/codex/custom/recovery/rollback-point", {', js)
        self.assertIn('body: JSON.stringify({})', js)
        self.assertIn("renderCodexCustomRecoveryRollbackPointCreate", js)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_point_create_live_only"', html)
        self.assertIn('"rollback_point_artifact_path_redacted": true', html)
        self.assertIn('"rollback_point_artifact_digest_present": false', html)
        self.assertIn("verifyCodexCustomRecoveryRollbackPoint()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point/verify")', js)
        self.assertIn("renderCodexCustomRecoveryRollbackPointVerify", js)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_point_verify_only"', html)
        self.assertIn('"rollback_point_verify_performed": false', html)
        self.assertIn('"rollback_point_digest_verified": false', html)
        self.assertIn('"rollback_point_provenance_verified": false', html)
        self.assertIn('"rollback_apply_ready": false', html)
        self.assertIn('"machine_error_code": "ROLLBACK_APPLY_ADMISSION_DRY_RUN_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_apply_admission_dry_run_only"', html)
        self.assertIn('"rollback_apply_admission_evaluated": false', html)
        self.assertIn('"rollback_apply_admission_result": "not_evaluated"', html)
        self.assertIn('"rollback_apply_admission_eligible_for_next_contour": false', html)
        self.assertIn('"rollback_point_verify_valid": false', html)
        self.assertIn('"rollback_point_manifest_verified": false', html)
        self.assertIn('"process_kill_performed": false', html)
        self.assertIn("refreshCodexCustomRecoveryRollbackApplyAdmissionDryRun()", js)
        self.assertIn(
            'fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/admission-dry-run")',
            js,
        )
        self.assertIn("renderCodexCustomRecoveryRollbackApplyAdmissionDryRun", js)
        self.assertIn("rollback_apply_admission_evaluated: evaluated", js)
        self.assertIn("rollback_apply_admission_result: result", js)
        self.assertIn("rollback_apply_admission_eligible_for_next_contour: eligible", js)
        self.assertIn("rollback_point_verify_valid: packet?.rollback_point_verify_valid === true", js)
        self.assertIn("rollback_point_manifest_verified: packet?.rollback_point_manifest_verified === true", js)
        self.assertIn("process_kill_performed: packet?.process_kill_performed === true", js)
        self.assertIn("rollback_contract_defined: rollbackDefined", js)
        self.assertIn("rollback_live_ready: packet?.rollback_live_ready === true", js)
        self.assertIn("rollback_apply_admitted: packet?.rollback_apply_admitted === true", js)
        self.assertIn("rollback_point_required: packet?.rollback_point_required === true", js)
        self.assertIn("rollback_point_present: packet?.rollback_point_present === true", js)
        self.assertIn("process_owner_contract_defined: processDefined", js)
        self.assertIn("process_kill_live_ready: packet?.process_kill_live_ready === true", js)
        self.assertIn("process_kill_admitted: packet?.process_kill_admitted === true", js)
        self.assertIn("owned_process_identity_required: packet?.owned_process_identity_required === true", js)
        self.assertIn("owned_process_identity_present: packet?.owned_process_identity_present === true", js)
        self.assertIn("current_codex_process_exclusion_required: packet?.current_codex_process_exclusion_required === true", js)
        self.assertIn("current_codex_process_excluded: packet?.current_codex_process_excluded === true", js)
        self.assertIn("current_codex_process_candidate: packet?.current_codex_process_candidate === true", js)
        self.assertIn("rollback_point_contract_defined: contractDefined", js)
        self.assertIn("rollback_point_create_admitted: packet?.rollback_point_create_admitted === true", js)
        self.assertIn("rollback_write_surfaces_contract_defined: packet?.rollback_write_surfaces_contract_defined === true", js)
        self.assertIn("rollback_write_surfaces_machine_checked: packet?.rollback_write_surfaces_machine_checked === true", js)
        self.assertIn("rollback_write_surfaces_dry_run_checked: packet?.rollback_write_surfaces_dry_run_checked === true", js)
        self.assertIn("rollback_verification_packet_defined: packet?.rollback_verification_packet_defined === true", js)
        self.assertIn("filesystem_write_performed: packet?.filesystem_write_performed === true", js)
        self.assertIn("snapshot_file_created: packet?.snapshot_file_created === true", js)
        self.assertIn("rollback_point_dry_run_contract_valid: packet?.rollback_point_dry_run_contract_valid === true", js)
        self.assertIn("rollback_point_create_admission_defined: admissionDefined", js)
        self.assertIn("rollback_point_create_admitted_scope: packet?.rollback_point_create_admitted_scope || \"\"", js)
        self.assertIn("rollback_point_create_admitted_for_current_contour: packet?.rollback_point_create_admitted_for_current_contour === true", js)
        self.assertIn("rollback_point_create_performed: performed", js)
        self.assertIn("rollback_point_created: packet?.rollback_point_created === true", js)
        self.assertIn("write_surface_machine_check_performed: packet?.write_surface_machine_check_performed === true", js)
        self.assertIn("write_surfaces_all_eligible: packet?.write_surfaces_all_eligible === true", js)
        self.assertIn("allowed_write_surfaces: Array.isArray(packet?.allowed_write_surfaces) ? packet.allowed_write_surfaces : []", js)
        self.assertIn("forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : []", js)
        self.assertIn('"snapshot_path"', js)
        self.assertIn('"rollback_target"', js)
        self.assertIn('"pid"', js)
        self.assertIn('"process_id"', js)
        self.assertIn("session_admitted_actions_ready: ready", js)
        self.assertIn("selected_session_cancel_ready: packet?.selected_session_cancel_ready === true", js)
        self.assertIn("owned_session_cleanup_ready: packet?.owned_session_cleanup_ready === true", js)
        self.assertIn("recovery_operator_ready: packet?.recovery_operator_ready === true", js)
        self.assertIn("rollback_operator_ready: packet?.rollback_operator_ready === true", js)
        self.assertIn("process_kill_operator_ready: packet?.process_kill_operator_ready === true", js)
        self.assertIn("diagnostics_counted_as_recovery_action: packet?.diagnostics_counted_as_recovery_action === true", js)
        self.assertIn("readonly_checks_counted_as_mutation: packet?.readonly_checks_counted_as_mutation === true", js)
        self.assertIn("session_create_counted_as_recovery_action: packet?.session_create_counted_as_recovery_action === true", js)
        self.assertIn("renderCodexCustomRecoveryContract", js)
        self.assertIn("contract_aggregator_only: packet?.contract_aggregator_only === true", js)
        self.assertIn("contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true", js)
        self.assertIn("recovery_live_ready: liveReady", js)
        self.assertIn("operator_ready_claimed: operatorReady", js)
        self.assertIn("rollback_claimed: packet?.rollback_claimed === true", js)
        self.assertIn("process_kill_claimed: packet?.process_kill_claimed === true", js)
        self.assertIn('document.getElementById("codexCustomRecoveryContractAction")?.addEventListener("click", () => refreshCodexCustomRecoveryContract())', js)
        self.assertIn('document.getElementById("codexCustomRecoverySessionActionsAction")?.addEventListener("click", () => refreshCodexCustomRecoveryAdmittedSessionActions())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackProcessOwnerAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackProcessOwnerContract())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointDryRun())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointCreateAdmission())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointCreateAction")?.addEventListener("click", () => createCodexCustomRecoveryRollbackPoint())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointVerifyAction")?.addEventListener("click", () => verifyCodexCustomRecoveryRollbackPoint())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackApplyAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackApplyAdmissionDryRun())', js)
        self.assertIn("runCodexCustomRecoveryChecks()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/original/status")', js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/status")', js)
        self.assertIn("loadAccountsReadonly()", js)
        self.assertIn("loadApiConnectionsReadonly()", js)
        self.assertIn('const accountsOk = accountsSnapshot?.status === "ok" && accountsSnapshot?.primary_truth_ok === true', js)
        self.assertIn('const apiOk = apiSnapshot?.status === "ok" && apiSnapshot?.primary_truth_ok === true', js)
        self.assertIn("const checksOk = originalOk && customOk && accountsOk && apiOk", js)
        self.assertIn('status: checksOk ? "ok" : "blocked"', js)
        self.assertIn('machine_error_code: checksOk ? "RECOVERY_READONLY_CHECKS_COMPLETE" : "RECOVERY_READONLY_CHECKS_BLOCKED"', js)
        self.assertIn("accounts_readonly_ok: accountsOk", js)
        self.assertIn("api_readonly_ok: apiOk", js)
        self.assertIn("cancelCodexCustomRecoverySession()", js)
        self.assertIn("cleanupCodexCustomRecoverySession()", js)
        self.assertIn('postCodexCustomSessionAction("cancel", {})', js)
        self.assertIn('postCodexCustomSessionAction("cleanup", {})', js)
        self.assertIn('document.getElementById("codexCustomRecoveryCheckAllAction")?.addEventListener("click", () => runCodexCustomRecoveryChecks())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryCancelAction")?.addEventListener("click", () => cancelCodexCustomRecoverySession())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryCleanupAction")?.addEventListener("click", () => cleanupCodexCustomRecoverySession())', js)

        self.assertIn("kill arbitrary process", html)
        self.assertIn("cleanup arbitrary path", html)
        self.assertIn("rollback without rollback point", html)
        self.assertIn("mutate credentials", html)
        self.assertIn("touch Original Codex profile", html)
        self.assertNotIn('data-ui-action="kill_process"', html)
        self.assertNotIn('data-ui-action="cleanup_path"', html)
        self.assertNotIn('data-ui-action="rollback_apply"', html)
        self.assertNotIn('data-ui-action="global_reset"', html)
        self.assertNotIn('data-ui-action="credentials_mutate"', html)
        self.assertNotIn('data-ui-action="route_remove"', html)
        self.assertNotIn('fetch("api/codex/custom/recovery/contract"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/contract", { method: "POST"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/admitted-session-actions"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/admitted-session-actions", { method: "POST"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-process-owner-contract"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-process-owner-contract", { method: "POST"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-point-dry-run"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-point-create-admission"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-point/verify"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-apply/admission-dry-run"', js)
        self.assertNotIn("artifact_id: codexCustomSelectedSessionId", js)
        self.assertNotIn("artifact_path: ", js)
        self.assertNotIn("digest: codexCustomSelectedSessionId", js)
        self.assertNotIn('path: "/tmp', js)
        self.assertNotIn("session_id: codexCustomSelectedSessionId", js)
        self.assertNotIn('fetch("api/codex/custom/recovery/snapshot"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/apply"', js)
        self.assertNotIn('fetch("api/codex/custom/kill"', js)
        self.assertNotIn('fetch("api/codex/custom/rollback"', js)
        self.assertNotIn('postCodexCustomSessionAction("cleanup", { path', js)
        self.assertNotIn("CODEX_CUSTOM_ROTATION_READY", html[html.find('id="codexCustomRecoveryPanel"'):html.find('id="codexCustomBoundedLoadProofPanel"')])
        self.assertNotIn("CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS", html + js)

    def test_codex_custom_recovery_blocks_when_readonly_probe_fails(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.textContent = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

const responses = {
  "api/codex/original/status": {
    status: "ok",
    proxy_injection_allowed: false,
    launch_claim_scope: "status_only"
  },
  "api/codex/custom/status": {
    status: "ok"
  },
  "api/accounts-readonly": {
    status: "integration_failure",
    primary_truth_ok: false,
    summary: {
      visible_count: 0,
      machine_error_code: "UI_ACCOUNTS_READONLY_FETCH_FAILED"
    }
  },
  "api/api-connections-readonly": {
    status: "ok",
    primary_truth_ok: true,
    summary: {
      routes_count: 1,
      enabled_count: 1
    }
  }
};

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch: async (url) => ({
    ok: true,
    json: async () => responses[url] || { status: "ok", primary_truth_ok: true, summary: {} }
  })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.refreshCodexLaunchModesPanel = async () => {};
sandbox.refreshCodexCustomModelsPanel = async () => {};
sandbox.refreshCodexCustomAccountsPanel = async () => {};
sandbox.refreshCodexCustomSessionsPanel = async () => {};
sandbox.actionMetadata = {};

sandbox.runCodexCustomRecoveryChecks().then(() => {
  const packet = JSON.parse(node("codexCustomRecoveryPacket").textContent);
  if (packet.status !== "blocked") {
    throw new Error(`readonly failure must block recovery checks, got ${packet.status}`);
  }
  if (packet.machine_error_code !== "RECOVERY_READONLY_CHECKS_BLOCKED") {
    throw new Error(`wrong machine code: ${packet.machine_error_code}`);
  }
  if (packet.accounts_readonly_ok !== false || packet.api_readonly_ok !== true) {
    throw new Error(`readonly booleans not preserved: ${JSON.stringify(packet)}`);
  }
  if (node("codexCustomRecoveryChip").lastElementChild.textContent !== "blocked") {
    throw new Error(`chip did not show blocked: ${node("codexCustomRecoveryChip").lastElementChild.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_codex_custom_recovery_contract_render_is_dry_run_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.textContent = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.append(...items);
  }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

const packet = {
  status: "blocked",
  machine_error_code: "RECOVERY_CONTRACT_DRY_RUN_ONLY",
  contract_block_reason_code: "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
  claim_scope: "custom_codex_recovery_contract_dry_run_only",
  contract_owner: "wbp_control_layer_contract_aggregator",
  contract_endpoint: "/api/codex/custom/recovery/contract",
  contract_aggregator_only: true,
  contract_endpoint_mutation_allowed: false,
  recovery_live_ready: false,
  operator_ready_claimed: false,
  rollback_claimed: false,
  process_kill_claimed: false,
  current_codex_touched: false,
  original_codex_touched: false,
  browser_forbidden_fields_rejected: true,
  browser_payload_allowed: false,
  browser_payload_allowed_keys: [],
  forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
  fresh_truth: false,
  historical_isolation_proof_only: true,
  dangerous_actions_disabled: true,
  diagnostics_support_artifact_only: true,
  readonly_sources: {
    original_status_ok: true,
    custom_status_ok: true,
    accounts_readonly_ok: false,
    api_readonly_ok: true
  },
  actions: [
    { id: "rollback_readiness", status: "dry_run_only", owner: "not_admitted", layer: "recovery_policy", mutation_allowed: false, browser_payload_allowed: false, disabled_reason_code: "ROLLBACK_CONTRACT_NOT_ADMITTED" },
    { id: "cleanup_arbitrary_path", status: "disabled", owner: "not_admitted", layer: "filesystem_policy", mutation_allowed: false, browser_payload_allowed: false, disabled_reason_code: "ARBITRARY_PATH_FORBIDDEN" }
  ]
};

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomRecoveryContract(packet);
const rendered = JSON.parse(node("codexCustomRecoveryContractPacket").textContent);
if (rendered.status !== "blocked") {
  throw new Error(`contract render must preserve blocked status: ${rendered.status}`);
}
if (rendered.recovery_live_ready !== false || rendered.operator_ready_claimed !== false) {
  throw new Error(`contract render overclaimed readiness: ${JSON.stringify(rendered)}`);
}
if (rendered.contract_endpoint_mutation_allowed !== false) {
  throw new Error(`contract endpoint must remain read-only: ${JSON.stringify(rendered)}`);
}
if (rendered.rollback_claimed !== false || rendered.process_kill_claimed !== false) {
  throw new Error(`contract render overclaimed recovery action: ${JSON.stringify(rendered)}`);
}
if (rendered.readonly_sources.accounts_readonly_ok !== false || rendered.readonly_sources.api_readonly_ok !== true) {
  throw new Error(`readonly source truth not preserved: ${JSON.stringify(rendered)}`);
}
if (rendered.action_counts.dry_run_only !== 1 || rendered.action_counts.disabled !== 1) {
  throw new Error(`action counts wrong: ${JSON.stringify(rendered.action_counts)}`);
}
if (node("codexCustomRecoveryChip").lastElementChild.textContent !== "dry-run only") {
  throw new Error(`chip must avoid green live claim: ${node("codexCustomRecoveryChip").lastElementChild.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_codex_custom_bounded_load_proof_ui_is_bounded_display_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomBoundedLoadProofPanel"', html)
        self.assertIn('id="codexCustomBoundedProofPacket"', html)
        self.assertIn('"status": "display_only"', html)
        self.assertIn('"machine_error_code": "BOUNDED_ARTIFACT_DISPLAY_ONLY"', html)
        self.assertIn("bounded_summary_only_not_rotation_ready", html)
        self.assertIn("CODEX_CUSTOM_LOAD_READY", html)
        self.assertIn("CODEX_CUSTOM_ROTATION_READY", html)
        self.assertIn("not rotation ready", html)
        self.assertIn("bounded proof only", html)
        self.assertIn("current touch 0", html)
        self.assertIn("401 0", html)
        self.assertIn("leaks none", html)
        self.assertNotIn("fetchCodexLaunchJson(\"api/codex/custom/bounded-load-proof\")", js)
        self.assertNotIn("codexCustomBoundedProofRefreshAction", html + js)
        self.assertNotIn('fetch("api/codex/custom/load"', js)
        self.assertNotIn('data-ui-action="codex_custom_load"', html)
        self.assertNotIn('data-ui-action="run_load"', html)
        self.assertNotIn("CODEX_CUSTOM_FULL_SESSION_MANAGER_READY", html + js)
        self.assertIn("EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY", html)
        self.assertIn('"EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"', html)

    def test_overview_nav_and_action_hierarchy_are_product_first(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        nav_match = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        nav = nav_match.group(1)
        self.assertLess(nav.find('data-screen-link="quick-start"'), nav.find('data-screen-link="overview"'))
        self.assertIn('data-screen-link="quick-start"', nav)
        self.assertIn('data-screen-link="overview"', nav)
        self.assertIn('data-screen-link="accounts"', nav)
        self.assertIn('data-screen-link="api-connections"', nav)
        self.assertIn('data-screen-link="diagnostics"', nav)
        self.assertIn('data-screen-link="settings"', nav)
        self.assertNotIn('data-screen-link="setup"', nav)
        self.assertNotIn('data-screen-link="select-client"', nav)
        self.assertNotIn('data-screen-link="import-existing"', nav)

        overview = self._section_html(html, "overviewScreen")
        self.assertEqual(html.count('class="button primary live-action overview-only"'), 1)
        self.assertIn('id="launchClientAction" class="button primary live-action overview-only"', html)
        self.assertIn('aria-label="Запустить клиент"', html)
        self.assertIn('class="button ghost live-action overview-only"', html)
        self.assertIn("secondary-action-tile", overview)
        self.assertIn("overview-utility-strip", overview)
        self.assertIn("compact-action-panel", overview)
        self.assertIn('id="uiLaneExitSummary"', overview)
        self.assertIn("STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION", overview + (WEB_DESIGN_UI / "scripts" / "overview.js").read_text())
        self.assertNotIn('data-ui-action="STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION"', overview)
        self.assertLess(overview.find('class="card system-card"'), overview.find('id="actionPanel"'))
        self.assertLess(overview.find('id="eventList"'), overview.find('id="actionPanel"'))
        self.assertIn(".secondary-action-tile", css)
        self.assertIn(".overview-utility-strip", css)
        self.assertIn(".compact-action-panel", css)
        self.assertIn('.desktop[data-screen="overview"] .main-header', css)
        self.assertIn('.desktop[data-screen="overview"] .overview-top', css)
        self.assertIn("grid-template-columns: minmax(500px, 1fr) minmax(500px, 1fr)", css)
        self.assertIn('.desktop[data-screen="overview"] .kpi-card', css)
        self.assertIn("min-height: 92px", css)
        self.assertIn("events.slice(0, 2)", (WEB_DESIGN_UI / "scripts" / "overview.js").read_text())
        self.assertIn("log-empty", css + (WEB_DESIGN_UI / "scripts" / "overview.js").read_text())

    def test_quick_start_daily_control_panel_is_summary_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        nav_match = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        nav = nav_match.group(1)
        self.assertLess(nav.find('data-screen-link="quick-start"'), nav.find('data-screen-link="overview"'))
        self.assertIn('href="?screen=quick-start"', nav)
        self.assertIn('src="assets/icons/phosphor/lightning.png"', nav)
        self.assertIn(
            'const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
            js,
        )

        section = self._section_html(html, "quickStartScreen")
        self.assertIn('data-screen="quick-start"', section)
        self.assertIn("Аккаунты Codex", section)
        self.assertIn("Основной API", section)
        self.assertIn("Упрощённый режим показывает только итоговые статусы и безопасные действия.", section + js)
        self.assertIn("Первый запуск: пустые состояния не являются ошибкой.", js)
        self.assertIn("Live-readonly данные недоступны. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Основной route не подтверждён", section + js)
        self.assertIn("secret_ref: —", section)
        self.assertIn('href="?screen=api-connections"', section)
        self.assertIn('href="?screen=accounts"', section)
        self.assertIn('data-ui-action="onboard_account_dry_run"', section)
        self.assertIn('data-ui-action="api_route_check"', section)
        self.assertIn('data-route-id=""', section)
        self.assertIn("quickStartAccountsFixtureFromOverview", js)
        self.assertIn("quickStartApiFixtureFromOverview", js)
        self.assertIn("quickStartApiModel", js)
        self.assertIn("Live snapshot не содержит confirmed main route", js)
        self.assertIn('snapshot.status === "stale"', js)
        self.assertIn('if (snapshotStatus === "stale")', js)
        self.assertIn("setVisualClass(banner, \"fixture-banner\", bannerVisual)", js)
        self.assertIn("setVisualClass(sidebarDot, \"dot\", bannerVisual)", js)
        self.assertIn('safeAccounts.status === "integration_failure"', js)
        self.assertIn('? "нет данных"', js)
        self.assertIn('id="quickStartApiRouteHint"', section)
        self.assertIn("route · открыть API-подключения", section + js)
        self.assertIn(".quick-start-grid", css)
        self.assertIn(".quick-start-card", css)
        self.assertIn(".quick-start-account-row", css)
        self.assertIn(".quick-start-account-row .quick-start-account-index", css)
        self.assertIn('font-feature-settings: "tnum" 1', css)
        self.assertIn("font-variant-numeric: tabular-nums", css)
        self.assertIn("letter-spacing: 0", css)
        self.assertIn("height: 34px", css)
        self.assertIn("width: 34px", css)
        self.assertIn("text-overflow: clip", css)
        self.assertIn(".quick-start-api-status", css)
        self.assertIn("--qs-main-padding: 36px", css)
        self.assertIn("--qs-section-gap: 24px", css)
        self.assertIn("--qs-card-padding: 22px", css)
        self.assertIn("--qs-row-height: 58px", css)
        self.assertIn("--qs-control-height: 40px", css)
        self.assertIn("width: 180px", css)
        self.assertIn("font-size: 16px", css)
        self.assertIn("line-height: 20px", css)
        self.assertIn("display: none", css)
        self.assertIn('document.getElementById("brandCaption").textContent = "";', js)
        self.assertNotIn('function liveBrandCaptionForScreen', js)
        self.assertNotIn('.desktop[data-screen="quick-start"] .brand img', css)
        self.assertNotIn('.desktop[data-screen="quick-start"] .brand .name', css)
        self.assertNotIn('.desktop[data-screen="quick-start"] .brand .caption', css)
        self.assertNotIn("quick start · live readonly", html + js)
        self.assertNotIn("quick start · v0.2.0", html + js)
        self.assertIn("align-items: start", css)
        self.assertIn("grid-template-columns: minmax(620px, 1fr) minmax(380px, 460px)", css)
        self.assertIn("height: auto", css)
        self.assertIn("padding: var(--qs-main-padding) var(--qs-main-padding) 28px", css)
        self.assertIn("@media (max-width: 1511px)", css)
        self.assertIn("font-size: 34px", css)
        self.assertIn("min-height: 76px", css)
        self.assertIn("min-height: 102px", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn("quickStartFormatCheckLabel", js)
        self.assertIn("quickStartAccountControl", js)
        self.assertIn(".quick-start-row-action", css)
        self.assertIn("grid-template-columns: 36px minmax(0, 1fr) minmax(132px, 156px)", css)
        self.assertIn(".quick-start-route-hint", css)
        self.assertIn('id="quickStartCheckAllAction" class="button quick-start-only check-all-action"', html)
        self.assertIn('data-ui-action="quick_start_check_all"', html)
        self.assertNotIn('id="quickStartCheckAllAction" class="button primary', html)
        self.assertIn(".header-actions #quickStartCheckAllAction:disabled", css)
        self.assertIn('document.getElementById("quickStartCheckAllAction")?.addEventListener("click"', js)
        self.assertIn('maybeConfirmAndRun(button.dataset.uiAction || "quick_start_check_all")', js)

        for forbidden in (
            "<canvas",
            "<textarea",
            "<pre",
            'type="file"',
            "raw JSON",
            "raw logs",
            "machine-code dump",
            "route table",
            "secret value",
            "route JSON",
            "provider config",
            "auth file",
        ):
            self.assertNotIn(forbidden, section)
        self.assertNotIn("<svg", section.lower())
        self.assertNotIn("command_id", section + js)
        self.assertNotIn("client_path", section + js)
        self.assertNotIn("source_dir", section + js)
        self.assertNotIn("showOpenFilePicker", section + js)
        self.assertIn('src="assets/icons/phosphor/users.png"', section)
        self.assertIn('src="assets/icons/phosphor/share-network.png"', section)
        self.assertIn('src="assets/icons/phosphor/key.png"', section)
        self.assertIn('src="assets/icons/phosphor/terminal-window.png"', section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', section)
        self.assertIn("missing_secret_ref", js)
        self.assertIn('setQuickStartChecklistChip("quickStartApiSecretChip", apiModel.state === "missing_secret_ref" ? "amber"', js)
        self.assertIn('const primary = source === "live"', js)

    def test_quick_start_live_rows_format_operator_copy(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.type = "";
    this.src = "";
    this.alt = "";
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name)) {
          this.className = `${this.className} ${name}`.trim();
        }
      }
    };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
      item.parentNode = this;
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...nodes) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  }
  addEventListener() {}
  setAttribute(name, value) {
    this[name] = value;
  }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderQuickStartAccountRows({
  status: "ok",
  accounts: [
    {
      id: "open17-plus",
      pool: "retired",
      pool_label: "Выведен",
      status: "down",
      visual_state: "red",
      manual_hold: false,
      last_success: "2026-05-08T20:56:41.885472+00:00",
      last_error_summary: ""
    },
    {
      id: "k-gpt-pro-2",
      pool: "active",
      status: "healthy",
      visual_state: "green",
      manual_hold: false,
      last_success: "2026-05-11T15:20:29.052628+00:00",
      last_error_summary: ""
    },
    {
      id: "reserve",
      pool: "reserve",
      status: "healthy",
      visual_state: "blue",
      manual_hold: false,
      last_success: "",
      last_error_summary: ""
    }
  ]
});

function collectText(item) {
  if (!item) {
    return "";
  }
  return [item.textContent || "", ...item.children.map((child) => collectText(child))].join(" ");
}
function descendants(item) {
  return [item, ...item.children.flatMap((child) => descendants(child))];
}

const list = node("quickStartAccountList");
const text = collectText(list);
if (text.includes("2026-05-08T") || text.includes("last check")) {
  throw new Error(`quick-start leaked raw timestamp copy: ${text}`);
}
if (!text.includes("Выведен · проверка 08.05, 20:56")) {
  throw new Error(`retired row was not operator formatted: ${text}`);
}
if (!text.includes("Активен · проверка 11.05, 15:20")) {
  throw new Error(`active row was not operator formatted: ${text}`);
}
if (!text.includes("Резерв · проверки нет")) {
  throw new Error(`reserve row did not show no-check copy: ${text}`);
}
const firstRow = list.children[0];
const control = firstRow.children[2];
if (control.tag !== "span" || !String(control.className).includes("quick-start-row-action")) {
  throw new Error(`problem row control should be an inert action marker, got ${control.tag} ${control.className}`);
}
if (control["data-ui-action"] || control.dataset.action) {
  throw new Error("quick-start check marker must not expose a command action payload");
}
if (descendants(control).some((item) => String(item.className || "").split(/\s+/).includes("dot"))) {
  throw new Error("quick-start check action must not include a floating status dot");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_accounts_screen_is_readonly_and_redacted(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        accounts_markup = self._section_html(html, "accountsScreen")

        self.assertIn('data-screen-link="accounts"', html)
        self.assertIn('id="accountsScreen"', html)
        self.assertIn('id="accountsTableBody"', html)
        self.assertIn("renderAccountsSnapshot", js)
        self.assertIn("accountsFixtureFromOverview", js)
        self.assertIn("Массовые lifecycle-действия отложены", js)
        self.assertIn("validate_account", js)
        self.assertIn("recheck_account", js)
        self.assertIn("promote_account", js)
        self.assertIn("demote_account", js)
        self.assertIn("retire_account", js)
        self.assertIn("onboard_account_dry_run", html + js)
        self.assertIn("onboard_account", html + js)
        self.assertIn('id="accountAddAction" class="button primary accounts-only onboard-action"', html)
        self.assertIn('data-ui-action="onboard_account_dry_run"', html)
        self.assertIn("function accountTableCheckLabel", js)
        self.assertIn("accountTableCheckLabel(account.last_success || account.cooldown_until)", js)
        self.assertIn('.desktop[data-screen="accounts"] .accounts-filter-row', css)
        self.assertIn('.desktop[data-screen="accounts"] .accounts-table-card', css)
        self.assertIn('.desktop[data-screen="accounts"] .account-detail-drawer', css)
        self.assertIn('class="search" aria-label="Поиск аккаунта"', accounts_markup)
        self.assertIn("Только текущий accounts JSON.", accounts_markup)
        self.assertIn("Опасные действия", accounts_markup)
        self.assertNotIn("Danger zone", accounts_markup)
        self.assertNotIn('type="file"', accounts_markup)
        self.assertNotIn("showOpenFilePicker", html + js)
        self.assertNotIn("browser-submitted", html + js)

        script = r"""
const fs = require("fs");
const vm = require("vm");
const sandbox = { console, document: { addEventListener() {} }, window: { location: { search: "" }, history: { replaceState() {} } }, URL, URLSearchParams };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
const formatted = sandbox.accountTableCheckLabel("2026-05-08T20:56:41.885472+00:00");
if (formatted !== "08.05, 20:56") {
  throw new Error(`account table leaked raw timestamp: ${formatted}`);
}
if (sandbox.accountTableCheckLabel("") !== "—") {
  throw new Error("account table empty check label should be dash");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_account_detail_drawer_projects_accounts_snapshot_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('id="accountDetailOverlay"', html)
        self.assertIn('id="accountDetailDrawer"', html)
        self.assertIn('id="accountDetailActions"', html)
        self.assertIn("currentAccountsSnapshot", js)
        self.assertIn("selectedAccountId", js)
        self.assertIn("function openAccountDrawer", js)
        self.assertIn("function renderAccountDetailDrawer", js)
        self.assertIn("function renderMissingAccountDrawer", js)
        self.assertIn("function renderAccountDetailTimeline", js)
        self.assertIn("function renderAccountDetailActions", js)
        self.assertIn("function renderAccountDetailLastCommand", js)
        self.assertIn("function isInteractiveAccountRowTarget", js)
        self.assertIn("function safeAccountDetailText", js)
        self.assertIn("function redactUiSensitiveText", js)
        self.assertIn("accountActionEligibility(account).filter((item) => item.enabled)", js)
        self.assertIn("account_missing_after_refresh", html + js)
        self.assertIn("Открыть drawer. Данные берутся только из текущего accounts JSON.", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('row.addEventListener("click"', js)
        self.assertIn("Открыть детали", js)
        self.assertIn('id="accountDetailDangerActions"', html)
        self.assertIn('id="accountDetailTimeline"', html)
        self.assertIn('id="accountDetailLastCommandChip"', html)
        self.assertIn("Payload только ui_action + account_id", html)
        self.assertIn("Command result не является состоянием аккаунта до refresh", html)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("readAsText", js)
        self.assertIn(".account-detail-drawer", css)
        self.assertIn(".account-detail-action-group", css)
        self.assertIn(".account-detail-timeline", css)
        self.assertIn(".account-detail-danger", css)

        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.type = "";
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name)) {
          this.className = `${this.className} ${name}`.trim();
        }
      },
      toggle: () => {}
    };
  }
  append(...nodes) {
    for (const node of nodes) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
        allNodes.push(node);
        this.lastElementChild = node;
      }
    }
  }
  replaceChildren(...nodes) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  }
  addEventListener() {}
  focus() {}
  remove() {
    if (!this.parentNode) {
      return;
    }
    this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
  }
  querySelector(selector) {
    const className = selector.startsWith(".") ? selector.slice(1) : "";
    return this.children.find((child) => child.classList?.contains(className)) || null;
  }
}

const allNodes = [];
const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
    allNodes.push(nodes[id]);
  }
  return nodes[id];
}

for (const id of [
  "sourcePicker", "statePicker", "brandCaption", "refreshFixture", "accountsBanner",
  "accountsActiveChip", "accountsReserveChip", "accountsHoldChip", "accountsProblemChip",
  "accountsRegistryStatus", "accountsVisibleCount", "accountsPagination",
  "accountsTableBody", "sidebarDot", "sidebarStatus", "sourceFooter", "subtitleText",
  "diagnosticsFixtureChart", "diagnosticsFixtureRecords", "diagnosticsHistoryDeferred",
  "diagnosticsRecordsDeferred", "diagnosticsHistoryModeChip", "diagnosticsRecordsModeChip",
  "accountDetailOverlay", "accountDetailBackdrop", "accountDetailDrawer", "accountDetailClose",
  "accountDetailMissing", "accountDetailTitle", "accountDetailSubtitle",
  "accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip",
  "accountDetailTruthChip", "accountDetailId", "accountDetailLabel", "accountDetailPoolValue",
  "accountDetailLifecycle", "accountDetailHoldValue", "accountDetailEnabled",
  "accountDetailChecks24h", "accountDetailFail", "accountDetailLatency", "accountDetailRecovery",
  "accountDetailLastSuccess", "accountDetailError", "accountDetailCounterNote",
  "accountDetailTimeline", "accountDetailActions", "accountDetailDangerActions",
  "accountDetailLastCommandChip", "accountDetailLastCommandAction", "accountDetailLastCommandCode",
  "accountDetailLastCommandNext", "accountDetailLastCommandRefresh", "settingsLaunchAvailability"
]) {
  node(id);
}
node("refreshFixture").lastElementChild = { textContent: "" };
for (const id of ["accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip", "accountDetailTruthChip", "accountDetailLastCommandChip", "diagnosticsHistoryModeChip", "diagnosticsRecordsModeChip"]) {
  node(id).lastElementChild = { textContent: "" };
}
node("accountDetailOverlay").hidden = true;

const desktop = new Node();
desktop.dataset = { screen: "accounts", source: "live" };
allNodes.push(desktop);

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) {
      const created = new Node(tag);
      allNodes.push(created);
      return created;
    },
    addEventListener() {},
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector.includes(".account-action")) {
        return allNodes.filter((item) => item.classList?.contains("account-action"));
      }
      return [];
    }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=accounts&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.actionMetadata = {
  validate_account: { available: true },
  demote_account: { available: true },
  hold_account: { available: true },
  retire_account: { available: true }
};

const snapshot = {
  schema_version: 1,
  status: "ok",
  source: "accounts_readonly",
  registry_identity: { status: "ok", machine_error_code: "OK", next_action: "none" },
  summary: {
    active: 1,
    reserve: 0,
    retired: 0,
    hold: 0,
    problem: 0,
    visible_count: 1,
    human_message: "Accounts listed.",
    machine_error_code: "OK"
  },
  accounts: [{
    id: "backend-a",
    label: "operator@example.com",
    pool: "active",
    pool_label: "Активные",
    status: "healthy",
    status_label: "Работает",
    visual_state: "green",
    manual_hold: false,
    enabled: true,
    fail_count: 0,
    success_count: 3,
    last_success: "Сегодня, 12:00",
    last_error_summary: "",
    cooldown_until: "",
    notes_summary: "snapshot note"
  }]
};

sandbox.renderAccountsSnapshot(snapshot);
sandbox.openAccountDrawer("backend-a");
if (node("accountDetailOverlay").hidden) {
  throw new Error("drawer should open");
}
if (node("accountDetailId").textContent !== "backend-a") {
  throw new Error(`drawer did not render selected account id: ${node("accountDetailId").textContent}`);
}
if (!node("accountDetailSubtitle").textContent.includes("ope***@***.com")) {
  throw new Error(`drawer label was not redacted: ${node("accountDetailSubtitle").textContent}`);
}
if (node("accountDetailLifecycle").textContent !== "available") {
  throw new Error(`drawer did not derive bounded lifecycle: ${node("accountDetailLifecycle").textContent}`);
}
if (node("accountDetailChecks24h").textContent !== "3") {
  throw new Error(`drawer did not render bounded checks: ${node("accountDetailChecks24h").textContent}`);
}
if (!node("accountDetailTimeline").children.length) {
  throw new Error("drawer timeline should render bounded fixture/check summary");
}
const actionButtons = node("accountDetailActions").children.filter((child) => child.dataset?.accountId === "backend-a");
if (!actionButtons.length || actionButtons.some((child) => child.dataset.uiAction === undefined)) {
  throw new Error("drawer did not reuse bounded account action buttons");
}
const disabledRoutine = node("accountDetailActions").children.filter((child) => child.disabled);
if (!disabledRoutine.length) {
  throw new Error("drawer should show disabled routine actions with reasons");
}
const dangerButtons = node("accountDetailDangerActions").children.filter((child) => child.dataset?.uiAction === "retire_account");
if (dangerButtons.length !== 1 || dangerButtons[0].dataset.accountId !== "backend-a") {
  throw new Error("drawer did not isolate retire action in danger zone");
}

sandbox.renderAccountsSnapshot({
  ...snapshot,
  accounts: [{
    ...snapshot.accounts[0],
    last_error_summary: "/Users/kirill/.codex auth_token=SECRET123",
    timeline: [{
      at: "/Volumes/Work/private-state.json",
      message: "secret=VERYSECRET path=/tmp/private-state.json",
      visual_state: "red"
    }]
  }]
});
sandbox.openAccountDrawer("backend-a");
function collectText(item) {
  if (!item) {
    return "";
  }
  return [
    item.textContent || "",
    ...((item.children || []).map((child) => collectText(child)))
  ].join(" ");
}
const sensitiveDrawerText = [
  collectText(node("accountDetailError")),
  collectText(node("accountDetailTimeline"))
].join(" ");
if (sensitiveDrawerText.includes("/Users/") || sensitiveDrawerText.includes("/Volumes/") || sensitiveDrawerText.includes("/tmp/private-state") || sensitiveDrawerText.includes("SECRET123") || sensitiveDrawerText.includes("VERYSECRET")) {
  throw new Error(`drawer leaked sensitive account text: ${sensitiveDrawerText}`);
}

sandbox.renderAccountsSnapshot({ ...snapshot, accounts: [], summary: { ...snapshot.summary, visible_count: 0 } });
if (node("accountDetailMissing").hidden) {
  throw new Error("missing account state should be visible after refresh");
}
if (node("accountDetailLabel").textContent !== "account_missing_after_refresh") {
  throw new Error("missing state did not replace stale account values");
}
if (!node("accountDetailActions").children[0].disabled) {
  throw new Error("missing account state should disable lifecycle actions");
}
if (!node("accountDetailDangerActions").children[0].disabled) {
  throw new Error("missing account state should disable danger actions");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_api_connections_screen_is_readonly_and_product_safe(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="api-connections"', html)
        self.assertIn('id="apiConnectionsScreen"', html)
        self.assertIn('id="apiConnectionsTableBody"', html)
        self.assertIn("renderApiConnectionsSnapshot", js)
        self.assertIn("apiConnectionsFixtureFromOverview", js)
        self.assertIn("loadApiConnectionsReadonly", js)
        self.assertIn("api_route_validate", js)
        self.assertIn("api_route_check", js)
        self.assertIn("api_route_allow", js)
        self.assertIn("api_route_disable", js)
        self.assertIn("api_route_remove", js)
        self.assertIn("api_route_profile", js)
        self.assertIn("api_route_evidence_capture", js)
        self.assertIn("routeActionButtons", js)
        self.assertIn("routeActionButton", js)
        self.assertIn("routeValidationChip", js)
        self.assertIn("routeSecretRef", js)
        self.assertIn("routeTableCheckLabel", js)
        self.assertIn("routeDisabledMenuButton", js)
        self.assertIn("apiRouteRemoveDisabledReason", js)
        self.assertIn("apiRouteStateRequirement", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId })', js)

        api_screen = self._section_html(html, "apiConnectionsScreen")
        self.assertIn('data-api-connections-mode="readonly-registry"', api_screen)
        self.assertIn('data-api-registry-surface="readonly-list"', api_screen)
        self.assertIn('data-api-builder-mode="deferred"', api_screen)
        self.assertIn("Маршруты недоступны", js)
        self.assertIn("Демо-режим. Маршруты показаны как ограниченная сводка", api_screen + js)
        self.assertIn("Live-readonly маршруты недоступны", js)
        self.assertIn("Новый маршрут", api_screen)
        self.assertIn("server-owned", api_screen)
        self.assertIn("Подключить API", api_screen)
        self.assertIn('data-ui-action="api_route_connect"', api_screen)
        self.assertIn('id="apiConnectionsCredentialLane"', api_screen)
        self.assertIn('id="apiConnectionsCredentialCheckAction"', api_screen)
        self.assertIn('data-ui-action="api_route_credential_check"', api_screen)
        self.assertIn('maybeConfirmAndRun("api_route_connect")', js)
        self.assertIn('maybeConfirmAndRun("api_route_credential_check")', js)
        self.assertIn("credential_expected_refs", js)
        self.assertIn("provider_dashboard", js)
        self.assertIn("browser_api_key_intake", js)
        self.assertNotIn('name="api_key"', html)
        self.assertNotIn('placeholder="API key"', html)
        self.assertIn("Разрешены", api_screen)
        self.assertIn("<th>Состояние</th>", api_screen)
        self.assertIn("<th>Проверка</th>", api_screen)
        self.assertIn("enabled", api_screen + js)
        self.assertIn("disabled", api_screen + js)
        self.assertIn("not checked", js)
        self.assertIn("blocked by secret", js)
        self.assertIn("не проверялся", js)
        self.assertIn("нет секрета", js)
        self.assertIn("Секрет", api_screen)
        self.assertIn("OPENROUTER_PRIMARY", js)
        self.assertIn("available", js)
        self.assertIn("missing", js)
        self.assertIn("Пакет профиля", js)
        self.assertIn("Свидетельство", js)
        self.assertIn("UI не читает evidence file", js)
        self.assertNotIn('data-ui-action="api_route_create"', api_screen)
        self.assertNotIn('data-ui-action="api_route_update"', api_screen)
        self.assertNotIn('data-ui-action="api_route_draft"', api_screen)
        self.assertNotIn("<textarea", api_screen)
        self.assertNotIn("<input", api_screen)
        self.assertNotIn("<select", api_screen)
        self.assertNotIn('type="file"', api_screen)
        self.assertNotIn("raw_route_json", api_screen + js)
        self.assertNotIn("route_config", api_screen + js)
        self.assertNotIn("endpoint_path", api_screen + js)
        self.assertNotIn("base_url", api_screen + js)
        self.assertNotIn("Registry enabled", api_screen)
        self.assertNotIn("Last check", api_screen)
        self.assertNotIn("missing surface", api_screen)
        self.assertNotIn("api_route_create", api_screen + js)
        self.assertNotIn("api_route_update", api_screen + js)
        self.assertNotIn("api_route_draft", api_screen + js)
        self.assertIn('routeActionButton(route, "api_route_allow", "Разрешить маршрут"', js)
        self.assertIn('routeActionButton(route, "api_route_disable", "Отключить маршрут"', js)
        self.assertIn('routeActionButton(route, "api_route_check", "Проверить запросом"', js)
        self.assertIn('routeActionButton(route, "api_route_remove", "Удалить route"', js)
        self.assertIn('routeActionButton(route, "api_route_profile", "Пакет профиля"', js)
        self.assertIn('routeActionButton(route, "api_route_evidence_capture", "Свидетельство"', js)
        self.assertNotIn("Вкл", api_screen + js)
        self.assertNotIn("Сделать активным", api_screen + js)
        self.assertNotIn("Подключить Codex", api_screen + js)
        self.assertNotIn("Профиль готов", api_screen + js)
        self.assertNotIn("Основной", api_screen)
        self.assertNotIn("Непрерывный поток", api_screen + js)
        self.assertNotIn("Сетка", api_screen + js)
        self.assertNotIn("primary route", api_screen + js)
        self.assertNotIn("failover", api_screen + js)
        self.assertNotIn("provider healthy", api_screen + js)
        self.assertNotIn("token valid", api_screen + js)
        self.assertNotIn("config saved", api_screen + js)
        self.assertIn('id="onboardOverlay"', html)
        self.assertIn('id="runOnboardAction"', html)
        self.assertIn('id="actionOnboardingOutcome"', html)
        self.assertIn('id="actionOnboardingReserveProof"', html)
        self.assertIn('id="actionOnboardingBackend"', html)
        self.assertIn('id="onboardingResultFlow"', html)
        self.assertIn('id="onboardingResultBanner"', html)
        self.assertIn('id="onboardingResultNewIds"', html)
        self.assertIn('id="onboardingResultSelected"', html)
        self.assertIn('id="onboardingResultReserveChip"', html)
        self.assertIn('id="onboardingResultNextAction"', html)
        self.assertIn("Итог onboarding", html)
        self.assertIn("Аккаунт не подключён", js)
        self.assertIn('class="onboard-facts-grid"', html)
        self.assertIn('class="onboard-technical-boundaries"', html)
        self.assertIn('id="onboardingResultStatusProofChip"', html)
        self.assertIn('id="onboardingResultPoolChip"', html)
        self.assertIn("hold_account", js)
        self.assertIn("release_account", js)
        self.assertIn("account_id", js)
        self.assertIn("route_id", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('maybeConfirmAndRun(onboardingLiveReadyInSession() ? "onboard_account" : "onboard_account_dry_run")', js)
        self.assertIn("Dry-run preview готов", js)
        self.assertIn(".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action", js)
        self.assertIn("Сначала выполняется безопасный dry-run preview", html)
        self.assertIn("Web не принимает токены, файлы и локальные пути.", html)
        self.assertIn("После admitted preview можно вернуться и подтвердить live connect в sandbox.", html)
        self.assertIn("терминальный вывод из lifecycle", js)
        self.assertIn("accountActionButtons", js)
        self.assertIn("Маршрут отключён. Это действие доступно только для разрешённых маршрутов.", js)
        self.assertIn("Маршрут уже разрешён. Это действие доступно только для отключённых маршрутов.", js)
        self.assertIn("Это не утверждение состояния runtime.", js)
        self.assertIn("secret_references", js)
        self.assertNotIn("auth_ref", html + js)
        self.assertNotIn("accounts validate", html + js)
        self.assertNotIn("accounts hold", html + js)
        self.assertNotIn("accounts promote", html + js)
        self.assertNotIn("accounts demote", html + js)
        self.assertNotIn("accounts release", html + js)
        self.assertNotIn("accounts retire", html + js)
        self.assertNotIn("accounts onboard", html + js)
        self.assertNotIn("auth_ref", html + js)
        self.assertNotIn("source_dir", html + js)
        self.assertNotIn('type="file"', html)
        self.assertNotIn('name="password"', html)
        self.assertNotIn('name="credentials"', html)
        self.assertNotIn('name="backend_id"', html)
        self.assertNotIn("auto-promote", html + js)
        self.assertNotIn("delete", html + js)
        self.assertNotIn("reactivation", html + js)
        self.assertNotIn("reactivate", html + js)
        self.assertNotIn("restore later", html + js)
        self.assertNotIn("pilot", html + js)
        self.assertNotIn("scale proof", html + js)

    def test_diagnostics_screen_is_support_artifact_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="diagnostics"', html)
        self.assertIn('id="diagnosticsScreen"', html)
        self.assertIn('id="diagnosticsExportAction" class="button live-action diagnostics-only"', html)
        self.assertIn('id="diagnosticsFullCheckAction" class="button diagnostics-only diagnostics-blocked-action"', html)
        self.assertIn("Полная проверка требует отдельной admitted command surface", html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn("Диагностический пакет поддержки", html + js)
        self.assertIn("Истина о здоровье runtime не изменялась", js)
        self.assertIn("только метаданные:", js)
        self.assertIn("const data = result.data || {}", js)
        self.assertIn("actionVisualClass", js)
        self.assertIn('payload.action_role === "support_artifact"', js)
        self.assertIn("Пакет поддержки", html)
        self.assertIn('data-diagnostics-region="history_chart_slot"', html)
        self.assertIn('data-diagnostics-region="latest_records"', html)
        self.assertIn('data-diagnostics-mode="fixture-demo"', html)
        self.assertIn('data-fixture-only="true"', html)
        self.assertIn('data-live-state="deferred"', html)
        self.assertIn("ограниченная сводка", html)
        self.assertIn('class="diagnostics-line-chart"', html)
        self.assertIn('class="telemetry-scale"', html)
        self.assertIn('class="tick failure"', html)
        self.assertIn('class="tick success"', html)
        self.assertEqual(html.count('class="tick '), 100)
        self.assertIn("аккаунт Codex", html)
        self.assertIn("Норма", html)
        self.assertIn("Устарело", html)
        self.assertIn("сбой", html)
        self.assertIn("устарело", html)
        self.assertIn("нет данных", html)
        self.assertIn("история недоступна", html)
        self.assertIn("записи недоступны", html)
        self.assertIn("заблокировано", html)
        self.assertIn("Live-история появится только после отдельного redacted JSON packet", html)
        self.assertIn("Live-записи не выводятся из журнального потока", html)
        self.assertIn("updateDiagnosticsDetailSource", js)
        self.assertIn('node.hidden = !fixtureOnly', js)
        self.assertIn('node.hidden = fixtureOnly', js)
        self.assertIn(".diagnostics-fixture-chart[hidden]", css := (WEB_DESIGN_UI / "styles" / "overview.css").read_text())
        self.assertIn(".fixture-banner.blue", css)
        self.assertIn(".diagnostics-line-chart", css)
        self.assertIn("grid-template-columns: repeat(48", css)
        self.assertIn(".diagnostics-detail-stack", css)
        self.assertIn(".diagnostics-support-meta", css)
        self.assertIn(".diagnostics-deferred-state[hidden]", css)
        self.assertIn(".diag-detail .diagnostics-actions-card .action-note", css)
        self.assertNotIn("runtime summary", (html + js).lower())
        self.assertIn("нет командной поверхности", html)
        self.assertIn("открытие журналов отложено", html)
        self.assertNotIn("Ссылка на артефакт", html)
        self.assertIn(
            'const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
            js,
        )
        self.assertIn("renderDiagnosticsAction", js)
        self.assertIn("artifactReference(data.bundle_path)", js)
        self.assertNotIn("Показать журнал", html)
        self.assertNotIn("Открыть auth", html)
        self.assertNotIn("В резерв", html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("readAsText", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("diagnostics export --json", html + js)
        self.assertNotIn("runtime healthy", (html + js).lower())
        self.assertNotIn("pilot", html + js)
        self.assertNotIn("scale proof", html + js)
        diagnostics_markup = html.split('id="diagnosticsScreen"', 1)[1].split('id="settingsScreen"', 1)[0]
        self.assertEqual(diagnostics_markup.count('data-ui-action="export_diagnostics"'), 0)
        self.assertNotIn("bounded history view", diagnostics_markup)
        self.assertNotIn("history unavailable", diagnostics_markup)
        self.assertNotIn("records unavailable", diagnostics_markup)
        self.assertNotIn("missing command surface · human-open deferred", diagnostics_markup)
        self.assertNotIn("Codex account", diagnostics_markup)
        self.assertNotIn("Proxy process", diagnostics_markup)
        self.assertNotIn('data-ui-action="stable_repair_apply"', diagnostics_markup)
        self.assertNotIn('data-ui-action="promote_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="demote_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="hold_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="release_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="retire_account"', diagnostics_markup)

    def test_diagnostics_detail_switches_fixture_visuals_and_live_deferred_state(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function node(id) {
  return {
    id,
    hidden: false,
    className: "",
    lastElementChild: { textContent: "" }
  };
}

const nodes = {
  diagnosticsFixtureChart: node("diagnosticsFixtureChart"),
  diagnosticsFixtureRecords: node("diagnosticsFixtureRecords"),
  diagnosticsHistoryDeferred: node("diagnosticsHistoryDeferred"),
  diagnosticsRecordsDeferred: node("diagnosticsRecordsDeferred"),
  diagnosticsHistoryModeChip: node("diagnosticsHistoryModeChip"),
  diagnosticsRecordsModeChip: node("diagnosticsRecordsModeChip")
};

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      return nodes[id] || { textContent: "", className: "", lastElementChild: { textContent: "" } };
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.updateDiagnosticsDetailSource("fixture");
if (nodes.diagnosticsFixtureChart.hidden || nodes.diagnosticsFixtureRecords.hidden) {
  throw new Error("fixture diagnostics visuals should be visible in fixture source");
}
if (!nodes.diagnosticsHistoryDeferred.hidden || !nodes.diagnosticsRecordsDeferred.hidden) {
  throw new Error("deferred live states should be hidden in fixture source");
}
if (nodes.diagnosticsHistoryModeChip.lastElementChild.textContent !== "демо") {
  throw new Error("fixture chip was not marked demo");
}

sandbox.updateDiagnosticsDetailSource("live");
if (!nodes.diagnosticsFixtureChart.hidden || !nodes.diagnosticsFixtureRecords.hidden) {
  throw new Error("fixture diagnostics visuals should be hidden in live source");
}
if (nodes.diagnosticsHistoryDeferred.hidden || nodes.diagnosticsRecordsDeferred.hidden) {
  throw new Error("deferred live states should be visible in live source");
}
if (nodes.diagnosticsRecordsModeChip.lastElementChild.textContent !== "отложено") {
  throw new Error("live chip was not marked deferred");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_settings_screen_is_readonly_with_safe_actions_and_deferred_controls(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        settings_hub_markup = settings_markup.split('<section id="accountsPolicyPanel"', 1)[0]
        accounts_policy_markup = settings_markup.split('<section id="accountsPolicyPanel"', 1)[1].split('<section id="clientLaunchPanel"', 1)[0]
        client_markup = settings_markup.split('<section id="clientLaunchPanel"', 1)[1].split('<section id="diagnosticsPrivacyPanel"', 1)[0]
        diagnostics_privacy_markup = settings_markup.split('<section id="diagnosticsPrivacyPanel"', 1)[1].split('<section id="runtimeModePanel"', 1)[0]
        runtime_markup = settings_markup.split('<section id="runtimeModePanel"', 1)[1].split('<section id="advancedSettingsPanel"', 1)[0]
        advanced_markup = settings_markup.split('<section id="advancedSettingsPanel"', 1)[1].split('<section id="dataLayoutPanel"', 1)[0]
        data_layout_markup = settings_markup.split('<section id="dataLayoutPanel"', 1)[1]

        self.assertIn('data-screen-link="settings"', html)
        self.assertIn('id="settingsScreen"', html)
        self.assertIn('data-visual-reference="14_settings_main_hub"', settings_markup)
        self.assertIn('data-config-mode="readonly"', settings_markup)
        self.assertIn('id="settingsHub"', settings_markup)
        self.assertIn('data-settings-subscreen-mode="hub-with-runtime-client-accounts-policy-diagnostics-privacy-advanced-and-data-layout"', settings_markup)
        self.assertIn('id="accountsPolicyPanel"', settings_markup)
        self.assertIn('data-settings-subflow="accounts-policy"', settings_markup)
        self.assertIn('data-accounts-policy-surface="readonly-snapshot-and-policy-invariants"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=accounts-policy"', settings_markup)
        self.assertIn('data-settings-section-link="accounts-policy"', settings_markup)
        self.assertIn('id="clientLaunchPanel"', settings_markup)
        self.assertIn('data-settings-subflow="client"', settings_markup)
        self.assertIn('data-client-launch-surface="bounded-dispatch-preview"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=client"', settings_markup)
        self.assertIn('data-settings-section-link="client"', settings_markup)
        self.assertIn('id="diagnosticsPrivacyPanel"', settings_markup)
        self.assertIn('data-settings-subflow="diagnostics-privacy"', settings_markup)
        self.assertIn('data-diagnostics-privacy-surface="support-artifact-boundary"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=diagnostics-privacy"', settings_markup)
        self.assertIn('data-settings-section-link="diagnostics-privacy"', settings_markup)
        self.assertIn('id="runtimeModePanel"', settings_markup)
        self.assertIn('data-settings-subflow="runtime"', settings_markup)
        self.assertIn('data-runtime-mode-surface="packet-owned-preview"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=runtime"', settings_markup)
        self.assertIn('data-settings-section-link="runtime"', settings_markup)
        self.assertIn('id="advancedSettingsPanel"', settings_markup)
        self.assertIn('data-settings-subflow="advanced"', settings_markup)
        self.assertIn('data-advanced-surface="boundary-reference-only"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=advanced"', settings_markup)
        self.assertIn('data-settings-section-link="advanced"', settings_markup)
        self.assertIn('id="dataLayoutPanel"', settings_markup)
        self.assertIn('data-settings-subflow="data-layout"', settings_markup)
        self.assertIn('data-installer-layout-mode="preview-only"', settings_markup)
        self.assertIn('href="?screen=settings&amp;section=data-layout"', settings_markup)
        self.assertIn('data-settings-section-link="data-layout"', settings_markup)
        self.assertIn("Данные приложения", settings_markup)
        self.assertIn("Состояние установки", settings_markup)
        self.assertIn("Каталог данных", settings_markup)
        self.assertIn("Структура пакета", settings_markup)
        self.assertIn("Permissions", settings_markup)
        self.assertIn("Snapshot / rollback", settings_markup)
        self.assertIn("Опасные операции", settings_markup)
        self.assertIn("Выбранный клиент", client_markup)
        self.assertIn("Launch readiness", client_markup)
        self.assertIn("Запуск клиента", client_markup)
        self.assertIn("Candidate / selection boundary", client_markup)
        self.assertIn("Deferred native actions", client_markup)
        self.assertIn("Policy invariants", accounts_policy_markup)
        self.assertIn("Capacity / targets", accounts_policy_markup)
        self.assertIn("Pool meanings", accounts_policy_markup)
        self.assertIn("Validation policy", accounts_policy_markup)
        self.assertIn("Hold / release behavior", accounts_policy_markup)
        self.assertIn("Observed pool snapshot", accounts_policy_markup)
        self.assertIn("Deferred controls", accounts_policy_markup)
        self.assertIn("policy invariants · observed pool snapshot · no lifecycle mutation", accounts_policy_markup)
        self.assertIn("reserve-first", accounts_policy_markup.lower())
        self.assertIn("Snapshot показывает наблюдаемое состояние пула, не сохранённую policy config.", accounts_policy_markup)
        self.assertIn("Lifecycle actions", accounts_policy_markup)
        self.assertIn("Accounts / Detail only", accounts_policy_markup)
        self.assertIn("missing admitted policy command surface", accounts_policy_markup)
        self.assertIn("selected client · readiness · bounded dispatch only", client_markup)
        self.assertIn("Command OK означает dispatch requested, не app/session truth.", client_markup)
        self.assertIn("Запрос запуска отправлен ≠ активная app session", client_markup)
        self.assertIn("Launch dispatch показывает запрос запуска, не здоровье runtime", client_markup)
        self.assertIn("Web path payload forbidden", client_markup)
        self.assertIn("inert display only", client_markup)
        self.assertIn("Текущий режим", runtime_markup)
        self.assertIn("Запрос режима", runtime_markup)
        self.assertIn("Source of truth", runtime_markup)
        self.assertIn("Last command", runtime_markup)
        self.assertIn("Disabled reasons", runtime_markup)
        self.assertIn("Режим запрошен ≠ режим применён ≠ здоровье runtime.", runtime_markup)
        self.assertIn("Operator mode", advanced_markup)
        self.assertIn("Command surface rules", advanced_markup)
        self.assertIn("Deferred dangerous actions", advanced_markup)
        self.assertIn("Owner approval gates", advanced_markup)
        self.assertIn("Safe links", advanced_markup)
        self.assertIn("Last command compact", advanced_markup)
        self.assertIn("System notes", advanced_markup)
        self.assertIn("Raw commands forbidden", advanced_markup)
        self.assertNotIn('data-ui-action=', advanced_markup)
        self.assertNotIn("live-action", advanced_markup)
        self.assertIn("Показать в Finder", html)
        self.assertIn("desktop/native или admitted human-open surface", html)
        for section in [
            "runtime-mode",
            "client-launch",
            "accounts-policy",
            "api-routes",
            "diagnostics-privacy",
            "security-boundary",
            "advanced-boundary",
            "about",
            "data-installer",
        ]:
            self.assertIn(f'data-settings-section="{section}"', settings_markup)
        self.assertEqual(settings_markup.count('data-settings-card="true"'), 9)
        self.assertIn("Runtime / Mode", settings_markup)
        self.assertIn("Client / Launch", settings_markup)
        self.assertIn("Accounts Policy", settings_markup)
        self.assertIn("API Routes", settings_markup)
        self.assertIn("Diagnostics / Privacy", settings_markup)
        self.assertIn("Export rules", diagnostics_privacy_markup)
        self.assertIn("Redaction policy", diagnostics_privacy_markup)
        self.assertIn("Support metadata categories", diagnostics_privacy_markup)
        self.assertIn("Never included / never rendered", diagnostics_privacy_markup)
        self.assertIn("Human-open deferred actions", diagnostics_privacy_markup)
        self.assertIn("support evidence, not health truth", diagnostics_privacy_markup)
        self.assertIn("Security", settings_markup)
        self.assertIn("Advanced", settings_markup)
        self.assertIn("About", settings_markup)
        self.assertIn("Data / Installer", settings_markup)
        self.assertIn("Wild Boar Proxy", settings_markup)
        self.assertIn("AGPL-3.0-or-later", settings_markup)
        self.assertIn("Readonly metadata, not release proof.", settings_markup)
        self.assertIn("local control layer", settings_markup)
        self.assertIn("web design preview", settings_markup)
        self.assertIn("not packaged", settings_markup)
        self.assertIn("local preview not published", settings_markup)
        self.assertIn("not exposed to browser UI", settings_markup)
        self.assertIn("CLIProxyAPI boundary", settings_markup)
        self.assertIn("desktop owner-gated", settings_markup)
        self.assertIn("readonly metadata", settings_markup)
        self.assertIn("About does not read runtime state, git metadata, or package metadata.", settings_markup)
        self.assertIn("Демо-режим настроек", settings_markup + js)
        self.assertIn("admitted layout, не runtime config truth", settings_markup + js)
        self.assertIn("Live-readonly настройки недоступны", js)
        self.assertIn("saved state", js)
        self.assertIn("наблюдается, не редактируется", js)
        self.assertIn("renderSettingsSnapshot", js)
        self.assertIn("updateSettingsActionMetadata", js)
        self.assertIn("missing surface", settings_markup)
        self.assertNotIn("manual picker deferred", settings_markup)
        self.assertIn("desktop/native only", settings_markup)
        self.assertIn("owner approval", settings_markup)
        self.assertIn("support artifact", settings_markup)
        self.assertIn("display deferred", settings_markup)
        self.assertIn("separate packet", settings_markup)
        self.assertIn("protected", settings_markup)
        self.assertIn("admitted", settings_markup)
        self.assertIn('data-screen-link="api-connections"', settings_markup)
        self.assertIn('data-screen-link="diagnostics"', settings_markup)
        self.assertNotIn("Безопасные доступные действия", settings_markup)
        self.assertNotIn("Отложенные элементы настроек", settings_markup)
        self.assertNotIn("Save settings", settings_markup)
        self.assertNotIn("Cancel settings", settings_markup)
        self.assertNotIn("Save", settings_markup)
        self.assertNotIn("Apply", settings_markup)
        self.assertNotIn("Browse", settings_markup)
        self.assertNotIn("Open installer", settings_markup)
        self.assertNotIn("Install now", settings_markup)
        self.assertNotIn("Сохранить", settings_markup)
        self.assertNotIn("Отмена", settings_markup)
        self.assertNotIn('data-ui-action=', settings_hub_markup)
        self.assertNotIn('data-ui-action=', accounts_policy_markup)
        self.assertNotIn('data-ui-action=', data_layout_markup)
        self.assertNotIn("live-action", settings_hub_markup)
        self.assertNotIn("live-action", accounts_policy_markup)
        self.assertNotIn("live-action", data_layout_markup)
        self.assertNotIn("account-action", accounts_policy_markup)
        self.assertNotIn("onboard-action", accounts_policy_markup)
        self.assertNotIn("api-route-action", accounts_policy_markup)
        self.assertIn('data-ui-action="export_diagnostics"', diagnostics_privacy_markup)
        self.assertEqual(diagnostics_privacy_markup.count("data-ui-action="), 1)
        for allowed_action in [
            "set_mode_managed",
            "set_mode_stable",
            "sync_runtime",
            "launch_smoke",
            "refresh_health_detail",
            "stable_repair_plan",
        ]:
            self.assertIn(f'data-ui-action="{allowed_action}"', runtime_markup)
        self.assertEqual(runtime_markup.count("data-ui-action="), 6)
        for allowed_action in [
            "launch_client_dispatch",
            "launch_smoke",
        ]:
            self.assertIn(f'data-ui-action="{allowed_action}"', client_markup)
        self.assertEqual(client_markup.count("data-ui-action="), 2)
        self.assertIn('data-screen-link="select-client"', client_markup)
        self.assertIn('data-screen-link="diagnostics"', client_markup)
        self.assertIn('data-screen-link="accounts"', accounts_policy_markup)
        self.assertIn('id="accountsPolicyOpenLedgerAction"', accounts_policy_markup)
        self.assertIn("client-launch-action", client_markup)
        self.assertIn("runtime-mode-action", runtime_markup)
        self.assertIn("confirmation и canonical refresh proof", runtime_markup)
        self.assertIn("Green появляется только после fresh consistent packet", runtime_markup)
        self.assertNotIn("<svg", settings_markup)
        self.assertNotIn("<input", settings_markup)
        self.assertNotIn("<textarea", settings_markup)
        self.assertNotIn("<select", settings_markup)
        self.assertNotIn('type="file"', settings_markup)
        self.assertNotIn('contenteditable="true"', settings_markup)
        self.assertNotIn('data-ui-action="stable_repair_apply"', settings_markup)
        self.assertNotIn("installer_init", settings_markup + js)
        self.assertNotIn("save_selection", settings_markup + js)
        self.assertNotIn("import_apply", settings_markup + js)
        self.assertNotIn("showOpenFilePicker", settings_markup + js)
        self.assertNotIn("showDirectoryPicker", settings_markup + js)
        self.assertNotIn("webkitdirectory", settings_markup + js)
        self.assertNotIn("readAsText", settings_markup + js)
        self.assertNotIn("localStorage", settings_markup + js)
        self.assertNotIn("policy_stage", html + js)
        self.assertNotIn("rollout stage", html + js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn("client_path", settings_markup)
        self.assertNotIn("app_path", settings_markup)
        self.assertNotIn("working_dir", settings_markup)
        self.assertNotIn("candidate_path", settings_markup)
        self.assertNotIn("source_dir", settings_markup)
        self.assertNotIn("data_dir", settings_markup)
        self.assertNotIn("secret_ref", settings_markup)
        self.assertNotIn("base_url", settings_markup)
        self.assertNotIn("endpoint_path", settings_markup)
        self.assertNotIn("api_route_create", settings_markup)
        self.assertNotIn("api_route_update", settings_markup)
        self.assertNotIn("config.toml", settings_markup)
        self.assertNotIn("state.json", settings_markup)
        self.assertNotIn("supervisor-state", settings_markup)
        self.assertNotIn("routes.json", settings_markup)
        self.assertNotIn("secrets.env", settings_markup)
        self.assertNotIn("installer init", settings_markup.lower())
        self.assertNotIn("settings ready", settings_markup.lower() + js.lower())
        self.assertNotIn("token value", settings_markup.lower())
        self.assertNotIn("password value", settings_markup.lower())
        self.assertNotIn("saved successfully", settings_markup.lower() + js.lower())
        self.assertNotIn("settings saved", settings_markup.lower() + js.lower())
        for forbidden_claim in [
            "verified package",
            "package verified",
            "release ready",
            "desktop ready",
            "runtime version confirmed",
            "installed version",
            "update available",
            "all dependencies compliant",
            "third-party notices complete",
            "license audit passed",
            "packaging contents verified",
            "production ready",
            "release build",
            "certified",
            "support available",
            "shipped app",
            "stable release",
            "cliproxyapi licensed as our product",
            "git rev-parse",
            "api/about",
            "api/version",
        ]:
            self.assertNotIn(forbidden_claim, settings_markup.lower())
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        self.assertIn(".settings-layout", css)
        self.assertIn(".settings-hub", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("min-height: 144px", css)
        self.assertNotIn("min-height: 216px", css)
        self.assertIn(".settings-card-head", css)
        self.assertIn(".settings-card-icon", css)
        self.assertIn(".settings-card-facts", css)
        self.assertIn(".settings-hidden-field", css)
        self.assertIn(".settings-data-layout", css)
        self.assertIn(".data-layout-grid", css)
        self.assertIn("grid-template-areas:", css)
        self.assertIn(".data-layout-danger-card", css)
        self.assertIn(".settings-runtime-mode", css)
        self.assertIn(".runtime-mode-grid", css)
        self.assertIn(".runtime-mode-disabled-list", css)
        self.assertIn(".settings-client-launch", css)
        self.assertIn(".client-launch-grid", css)
        self.assertIn(".client-launch-disabled-list", css)
        self.assertIn(".settings-diagnostics-privacy", css)
        self.assertIn(".diagnostics-privacy-grid", css)
        self.assertIn(".diagnostics-privacy-disabled-list", css)
        self.assertIn(".settings-advanced", css)
        self.assertIn(".advanced-settings-grid", css)
        self.assertIn(".advanced-settings-disabled-list", css)
        self.assertIn(".settings-accounts-policy", css)
        self.assertIn(".accounts-policy-grid", css)
        self.assertIn(".accounts-policy-disabled-list", css)

    def test_settings_data_layout_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        data_layout_markup = settings_markup.split('<section id="dataLayoutPanel"', 1)[1]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"data-layout"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn("settingsSectionFromLocation", js)
        self.assertIn("setSettingsSection", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn('if (key !== "section")', js)
        self.assertIn('data-settings-section-link="data-layout"', settings_markup)
        self.assertNotIn('data-screen-link="data-layout"', html)
        nav_markup = html.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn('id="dataLayoutNav"', nav_markup)
        self.assertNotIn(">Data Layout<", nav_markup)
        self.assertNotIn('section=data-layout', nav_markup)

        self.assertIn("DATA_LAYOUT_FIXTURES", js)
        self.assertIn("initialized_healthy", js)
        self.assertIn("permissions_warning", js)
        self.assertIn("no_data_dir_known", js)
        self.assertIn("rollback_required", js)
        self.assertIn("live_integration_failure", js)
        self.assertIn('"stale"', js)
        self.assertIn("renderDataLayoutSnapshot", js)
        self.assertIn("Live-readonly статус данных недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Stale preview не является зелёным состоянием", js)

        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "showDirectoryPicker",
            "showOpenFilePicker",
            "webkitdirectory",
            "readAsText",
            "localStorage",
            "sessionStorage",
            "window.open",
            "data-ui-action",
            "stable_repair_apply",
            "installer_init",
            "settings_write",
            "save_settings",
            "raw_command",
            "target_path",
            "source_dir",
            "client_path",
            "config_path",
            "auth_file",
            "token value",
            "secret value",
            "config.toml",
            "state.json",
            "routes.json",
            "secrets.env",
        ]:
            self.assertNotIn(forbidden, data_layout_markup)
        self.assertNotIn("showDirectoryPicker", js)
        self.assertNotIn("showOpenFilePicker", js)
        self.assertNotIn("webkitdirectory", js)

        self.assertIn("Snapshot требует отдельного admitted command surface", settings_markup)
        self.assertIn("Rollback требует server-owned rollback point", settings_markup)
        self.assertIn("Reinitialize требует strong confirmation", settings_markup)
        self.assertIn("Очистка данных недоступна из web preview", settings_markup)
        self.assertIn("Сброс layout недоступен без rollback semantics", settings_markup)

    def test_settings_runtime_mode_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        runtime_markup = settings_markup.split('<section id="runtimeModePanel"', 1)[1].split('<section id="advancedSettingsPanel"', 1)[0]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"runtime"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn('href="?screen=settings&amp;section=runtime"', settings_markup)
        self.assertIn('data-settings-section-link="runtime"', settings_markup)
        self.assertIn('data-settings-subflow="runtime"', runtime_markup)
        self.assertIn("runtimeModeModelFromSnapshot", js)
        self.assertIn("renderRuntimeModeSnapshot", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn("Runtime mode недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Данные режима устарели. Требуется обновление из canonical source.", js)
        self.assertIn("command result не подменяет runtime truth", settings_markup)

        for allowed_action in [
            "set_mode_managed",
            "set_mode_stable",
            "sync_runtime",
            "launch_smoke",
            "refresh_health_detail",
            "stable_repair_plan",
        ]:
            self.assertIn(f'data-ui-action="{allowed_action}"', runtime_markup)
        self.assertEqual(runtime_markup.count("data-ui-action="), 6)
        self.assertIn("metadata.confirmation_required", js)
        self.assertIn("confirmationPolicyFor(uiAction, metadata)", js)
        self.assertIn("set_mode_managed:", js)
        self.assertIn("set_mode_stable:", js)
        self.assertIn("Фактический режим должен быть подтверждён обновлённым JSON.", js)
        self.assertIn("ok_refresh_pending", js)
        self.assertIn("canonical refresh pending", js)
        self.assertIn("ok_refresh_failed", js)
        self.assertIn("canonical refresh failed", js)
        self.assertIn("mismatch", js)
        self.assertIn('model.key === "stale"', js)
        self.assertIn("stale", runtime_markup + js)
        self.assertIn("Применить восстановление", runtime_markup)
        self.assertIn("Применение восстановления требует отдельного confirmation gate", runtime_markup)
        self.assertNotIn('data-ui-action="stable_repair_apply"', runtime_markup)
        self.assertNotIn("stable_repair_apply:", js)
        self.assertNotIn("policy_stage", runtime_markup + js)
        self.assertNotIn("rollout_stage", runtime_markup + js)
        self.assertNotIn("stable_target", runtime_markup + js)
        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "mode_override",
            "config_path",
            "state_path",
            "raw_command",
            "argv",
            "shell",
            "Сохранить",
            "config saved",
            "mode applied",
            "production ready",
        ]:
            self.assertNotIn(forbidden, runtime_markup)
        self.assertNotIn("<svg", runtime_markup)
        self.assertIn('assets/icons/phosphor/pulse.png', runtime_markup)
        self.assertIn('assets/icons/phosphor/shield-check.png', runtime_markup)
        self.assertIn('assets/icons/phosphor/arrows-clockwise.png', runtime_markup)
        self.assertIn('assets/icons/phosphor/warning.png', runtime_markup)

    def test_settings_advanced_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        advanced_markup = settings_markup.split('<section id="advancedSettingsPanel"', 1)[1].split('<section id="dataLayoutPanel"', 1)[0]
        nav_markup = html.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"advanced"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn('href="?screen=settings&amp;section=advanced"', settings_markup)
        self.assertIn('data-settings-section-link="advanced"', settings_markup)
        self.assertNotIn('data-screen-link="advanced"', html)
        self.assertNotIn("section=advanced", nav_markup)
        self.assertIn('data-settings-subflow="advanced"', advanced_markup)
        self.assertIn('data-advanced-surface="boundary-reference-only"', advanced_markup)

        self.assertIn("advancedModelFromSnapshot", js)
        self.assertIn("renderAdvancedSettingsSnapshot", js)
        self.assertIn("renderAdvancedAction", js)
        self.assertIn("Advanced status недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Deferred gates не становятся зелёным состоянием.", js)
        self.assertIn("Демо-режим. Advanced показывает policy preview, не активные системные переключатели.", js)
        self.assertIn('nextSettingsSection === "advanced"', js)
        self.assertIn('id="advancedSettingsBackAction"', advanced_markup)
        self.assertIn('id="advancedOpenLedgerAction"', advanced_markup)

        for expected in [
            "Operator mode",
            "Command surface rules",
            "Deferred dangerous actions",
            "Owner approval gates",
            "Safe links",
            "Last command compact",
            "System notes",
            "stable_repair_apply",
            "policy controls",
            "rollout prove / advance",
            "route create / update",
            "secret reference selector",
            "desktop/native bridge",
            "human-open local files",
            "owner approval required",
            "Raw commands forbidden",
            "Action result требует canonical refresh",
        ]:
            self.assertIn(expected, advanced_markup)

        self.assertIn('{ "ui_action": "..." }', advanced_markup)
        self.assertIn('{ "ui_action": "...", "account_id": "..." }', advanced_markup)
        self.assertIn('{ "ui_action": "...", "route_id": "..." }', advanced_markup)
        self.assertIn('data-screen-link="diagnostics"', advanced_markup)
        self.assertIn('data-screen-link="api-connections"', advanced_markup)
        self.assertIn('data-settings-section-link="hub"', advanced_markup)

        self.assertNotIn('data-ui-action=', advanced_markup)
        self.assertNotIn("live-action", advanced_markup)
        self.assertNotIn("api-route-action", advanced_markup)
        self.assertNotIn("account-action", advanced_markup)
        self.assertNotIn('data-ui-action="stable_repair_apply"', advanced_markup)
        self.assertNotIn("stable_repair_apply:", js)
        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "showOpenFilePicker",
            "showDirectoryPicker",
            "webkitdirectory",
            "readAsText",
            "localStorage",
            "sessionStorage",
            "window.open",
            "command_id",
            "raw_command",
            "argv",
            "shell",
            "client_path",
            "app_path",
            "working_dir",
            "config_path",
            "state_path",
            "log_path",
            "route_json",
            "policy_stage",
            "rollout_stage",
            "stable_target",
            "token value",
            "secret value",
            "textarea",
            "admin console active",
            "enable all",
        ]:
            self.assertNotIn(forbidden, advanced_markup)
        self.assertNotIn("<svg", advanced_markup)
        self.assertIn('assets/icons/phosphor/gear.png', advanced_markup)
        self.assertIn('assets/icons/phosphor/shield-check.png', advanced_markup)
        self.assertIn('assets/icons/phosphor/warning.png', advanced_markup)
        self.assertIn('assets/icons/phosphor/terminal-window.png', advanced_markup)
        self.assertIn('assets/icons/phosphor/arrows-clockwise.png', advanced_markup)
        self.assertIn(".settings-advanced", (WEB_DESIGN_UI / "styles" / "overview.css").read_text())
        self.assertIn(".advanced-settings-grid", (WEB_DESIGN_UI / "styles" / "overview.css").read_text())
        self.assertIn(".advanced-settings-disabled-list", (WEB_DESIGN_UI / "styles" / "overview.css").read_text())

    def test_settings_client_launch_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        client_markup = settings_markup.split('<section id="clientLaunchPanel"', 1)[1].split('<section id="diagnosticsPrivacyPanel"', 1)[0]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"client"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn('href="?screen=settings&amp;section=client"', settings_markup)
        self.assertIn('data-settings-section-link="client"', settings_markup)
        self.assertIn('data-settings-subflow="client"', client_markup)
        self.assertIn('data-client-launch-surface="bounded-dispatch-preview"', client_markup)
        self.assertIn("clientLaunchModelFromSnapshot", js)
        self.assertIn("launchPreflightSummary", js)
        self.assertIn("renderClientLaunchSnapshot", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn("Client status недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Client status устарел. Требуется refresh из bounded packet.", js)
        self.assertIn("Демо-режим. Изолированная копия admitted только через server-owned preflight.", js)
        self.assertIn("Демо-режим. Изолированная копия не admitted без server-owned preflight.", js)

        self.assertIn("Выбранный клиент", client_markup)
        self.assertIn("Launch readiness", client_markup)
        self.assertIn("Запуск клиента", client_markup)
        self.assertIn("Candidate / selection boundary", client_markup)
        self.assertIn("Deferred native actions", client_markup)
        self.assertIn("selected client · readiness · bounded dispatch only", client_markup)
        self.assertIn("Client preview не является runtime readiness или доказательством локального файла.", client_markup)
        self.assertIn("Command OK означает dispatch requested, не app/session truth.", client_markup)
        self.assertIn("Copy preflight", client_markup)
        self.assertIn("Process proof", client_markup)
        self.assertIn("Запрос запуска отправлен ≠ активная app session", client_markup)
        self.assertIn("Launch dispatch показывает запрос запуска, не здоровье runtime", client_markup)
        self.assertIn("Preflight first.", client_markup)
        self.assertIn("Кандидаты выбираются только из command-owned list.", client_markup)
        self.assertIn("Ручной выбор файла: desktop/native only.", client_markup)
        self.assertIn("Web path payload forbidden.", client_markup)
        self.assertIn("Показать в Finder · human-open not admitted", client_markup)
        self.assertIn("Запустить копию", client_markup)
        self.assertIn('id="clientActionPreflight"', client_markup)
        self.assertIn('id="clientActionPhase"', client_markup)

        self.assertIn('data-ui-action="launch_client_dispatch"', client_markup)
        self.assertIn('data-ui-action="launch_smoke"', client_markup)
        self.assertEqual(client_markup.count("data-ui-action="), 2)
        self.assertIn('data-screen-link="select-client"', client_markup)
        self.assertIn('data-screen-link="diagnostics"', client_markup)
        self.assertIn("launch_client_dispatch:", js)
        self.assertIn("bounded-dispatch", js)
        self.assertIn("Это не доказывает старт приложения или здоровье runtime.", js)
        self.assertIn("metadata.available !== false", js)
        self.assertIn("UI_ACTION_UNAVAILABLE", js)

        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "showOpenFilePicker",
            "showDirectoryPicker",
            "webkitdirectory",
            "readAsText",
            "localStorage",
            "sessionStorage",
            "window.open",
            "client_path",
            "app_path",
            "working_dir",
            "candidate_path",
            "config_path",
            "state_path",
            "raw_command",
            "argv",
            "shell",
            "token",
            "secret",
            "config.toml",
            "state.json",
            "routes.json",
            "secrets.env",
            "Клиент запущен",
            "client running",
            "launch success",
            "runtime ready",
        ]:
            self.assertNotIn(forbidden, client_markup)
        self.assertNotIn("<svg", client_markup)
        self.assertIn('assets/icons/phosphor/play.png', client_markup)
        self.assertIn('assets/icons/phosphor/terminal-window.png', client_markup)
        self.assertIn('assets/icons/phosphor/shield-check.png', client_markup)
        self.assertIn('assets/icons/phosphor/warning.png', client_markup)

    def test_settings_diagnostics_privacy_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        diagnostics_privacy_markup = settings_markup.split('<section id="diagnosticsPrivacyPanel"', 1)[1].split('<section id="runtimeModePanel"', 1)[0]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"diagnostics-privacy"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn('href="?screen=settings&amp;section=diagnostics-privacy"', settings_markup)
        self.assertIn('data-settings-section-link="diagnostics-privacy"', settings_markup)
        self.assertIn('data-settings-subflow="diagnostics-privacy"', diagnostics_privacy_markup)
        self.assertIn('data-diagnostics-privacy-surface="support-artifact-boundary"', diagnostics_privacy_markup)
        self.assertIn("diagnosticsPrivacyModelFromSnapshot", js)
        self.assertIn("renderDiagnosticsPrivacySnapshot", js)
        self.assertIn("renderDiagnosticsPrivacyAction", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn("Diagnostics privacy status недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Redaction proof требует свежий packet.", js)
        self.assertIn("Демо-режим. Правила диагностики показаны как preview, не как содержимое bundle.", js)

        self.assertIn("Export rules", diagnostics_privacy_markup)
        self.assertIn("Redaction policy", diagnostics_privacy_markup)
        self.assertIn("Support metadata categories", diagnostics_privacy_markup)
        self.assertIn("Never included / never rendered", diagnostics_privacy_markup)
        self.assertIn("Export result", diagnostics_privacy_markup)
        self.assertIn("Human-open deferred actions", diagnostics_privacy_markup)
        self.assertIn("Last command compact", diagnostics_privacy_markup)
        self.assertIn("support evidence, not health truth", diagnostics_privacy_markup)
        self.assertIn("support artifact metadata only", diagnostics_privacy_markup)
        self.assertIn("UI never renders bundle contents.", diagnostics_privacy_markup)
        self.assertIn("bundle content", diagnostics_privacy_markup)
        self.assertIn("API keys", diagnostics_privacy_markup)
        self.assertIn("auth tokens", diagnostics_privacy_markup)
        self.assertIn("raw auth files", diagnostics_privacy_markup)
        self.assertIn("secret values", diagnostics_privacy_markup)
        self.assertIn("private command argv", diagnostics_privacy_markup)
        self.assertIn("raw logs in UI", diagnostics_privacy_markup)
        self.assertIn("requires human-open admission", diagnostics_privacy_markup)
        self.assertIn("server-owned bounded target", diagnostics_privacy_markup)
        self.assertIn("Artifact created is support readiness, not runtime health.", diagnostics_privacy_markup)

        self.assertIn('data-ui-action="export_diagnostics"', diagnostics_privacy_markup)
        self.assertEqual(diagnostics_privacy_markup.count("data-ui-action="), 1)
        self.assertIn("diagnosticsExportResultModel(payload)", js)
        self.assertIn("artifactReference(data.bundle_path)", js)
        self.assertIn("redactionStatus === \"enabled\" ? \"green\"", js)
        self.assertIn("redaction_unreported", js)
        self.assertIn("не runtime health truth", js)
        self.assertIn("claim_scope=support_artifact_only", js)

        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "showOpenFilePicker",
            "showDirectoryPicker",
            "webkitdirectory",
            "readAsText",
            "localStorage",
            "sessionStorage",
            "window.open",
            "data-ui-action=\"read_logs\"",
            "data-ui-action=\"read_bundle\"",
            "data-ui-action=\"open_logs\"",
            "data-ui-action=\"open_state\"",
            "bundle_path",
            "log_path",
            "state_path",
            "registry_path",
            "raw_command",
            "shell",
            "token value",
            "secret value input",
            "raw stack trace",
            "Диагностика успешна",
            "Система исправна",
            "Runtime OK",
            "runtime healthy",
        ]:
            self.assertNotIn(forbidden, diagnostics_privacy_markup)
        self.assertNotIn("<svg", diagnostics_privacy_markup)
        self.assertIn('assets/icons/phosphor/download-simple.png', diagnostics_privacy_markup)
        self.assertIn('assets/icons/phosphor/shield-check.png', diagnostics_privacy_markup)
        self.assertIn('assets/icons/phosphor/warning.png', diagnostics_privacy_markup)
        self.assertIn('assets/icons/phosphor/info.png', diagnostics_privacy_markup)

    def test_settings_accounts_policy_subflow_is_bounded_and_section_routed(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]
        accounts_policy_markup = settings_markup.split('<section id="accountsPolicyPanel"', 1)[1].split('<section id="clientLaunchPanel"', 1)[0]

        self.assertIn('const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]', js)
        self.assertNotIn('"accounts-policy"', js.split("const SCREENS =", 1)[1].split("];", 1)[0])
        self.assertIn('const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"]', js)
        self.assertIn('href="?screen=settings&amp;section=accounts-policy"', settings_markup)
        self.assertIn('data-settings-section-link="accounts-policy"', settings_markup)
        self.assertIn('data-settings-subflow="accounts-policy"', accounts_policy_markup)
        self.assertIn('data-accounts-policy-surface="readonly-snapshot-and-policy-invariants"', accounts_policy_markup)
        self.assertIn("accountsPolicyModelFromSnapshot", js)
        self.assertIn("renderAccountsPolicySnapshot", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn("Accounts policy недоступна. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Accounts policy snapshot устарел. Stale counts не являются зелёным состоянием.", js)
        self.assertIn("Демо-режим. Политика аккаунтов показана как preview, не как config truth.", js)

        self.assertIn("Policy invariants", accounts_policy_markup)
        self.assertIn("Pool meanings", accounts_policy_markup)
        self.assertIn("Validation policy", accounts_policy_markup)
        self.assertIn("Hold / release behavior", accounts_policy_markup)
        self.assertIn("Observed pool snapshot", accounts_policy_markup)
        self.assertIn("Deferred controls", accounts_policy_markup)
        self.assertIn("Reserve-first", accounts_policy_markup)
        self.assertIn("enforced by canon / preview", accounts_policy_markup + js)
        self.assertIn("future policy packet / unavailable", accounts_policy_markup + js)
        self.assertIn("accounts list readonly snapshot", accounts_policy_markup + js)
        self.assertIn("Snapshot показывает наблюдаемое состояние пула, не сохранённую policy config.", accounts_policy_markup + js)
        self.assertIn("Targets are informational only until a policy packet exists.", accounts_policy_markup)
        self.assertIn("Capacity target", accounts_policy_markup)
        self.assertIn("design target preview", accounts_policy_markup + js)
        self.assertIn("Auto-promote", accounts_policy_markup)
        self.assertIn("not admitted", accounts_policy_markup + js)
        self.assertIn("no auto-green", accounts_policy_markup)
        self.assertIn("Active", accounts_policy_markup)
        self.assertIn("Reserve", accounts_policy_markup)
        self.assertIn("Held", accounts_policy_markup)
        self.assertIn("Problem", accounts_policy_markup)
        self.assertIn("Retired", accounts_policy_markup)
        self.assertIn("Открыть аккаунты", accounts_policy_markup)
        self.assertIn('data-screen-link="accounts"', accounts_policy_markup)
        self.assertIn("missing admitted policy command surface", accounts_policy_markup)

        self.assertNotIn('data-ui-action=', accounts_policy_markup)
        self.assertNotIn("live-action", accounts_policy_markup)
        self.assertNotIn("account-action", accounts_policy_markup)
        self.assertNotIn("onboard-action", accounts_policy_markup)
        self.assertNotIn("api-route-action", accounts_policy_markup)
        for forbidden in [
            "<input",
            "<textarea",
            "<select",
            'type="file"',
            "contenteditable",
            "policy_write",
            "capacity_target",
            "reserve_target",
            "active_target",
            "pool_policy",
            "account_ids",
            "backend_ids",
            "auto_promote",
            "auto-promote action",
            "validate_account",
            "recheck_account",
            "promote_account",
            "demote_account",
            "hold_account",
            "release_account",
            "retire_account",
            "onboard_account",
            "auth path",
            "token",
            "config path",
            "raw_command",
            "argv",
            "shell",
            "policy_stage",
            "rollout_stage",
            "policy stage set",
            "accounts promote",
            "accounts demote",
            "accounts hold",
            "accounts release",
            "accounts retire",
            "accounts onboard",
            "saved policy",
            "policy saved",
            "active routing changed",
        ]:
            self.assertNotIn(forbidden, accounts_policy_markup)
        self.assertNotIn("<svg", accounts_policy_markup)
        self.assertIn('assets/icons/phosphor/users.png', accounts_policy_markup)
        self.assertIn('assets/icons/phosphor/shield-check.png', accounts_policy_markup)
        self.assertIn('assets/icons/phosphor/pause-circle.png', accounts_policy_markup)
        self.assertIn('assets/icons/phosphor/warning.png', accounts_policy_markup)

    def test_setup_select_import_screens_are_inert_skeletons(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertNotIn('id="setupNav"', html)
        self.assertNotIn('id="selectClientNav"', html)
        self.assertNotIn('id="importExistingNav"', html)
        self.assertIn('id="setupScreen"', html)
        self.assertIn('id="selectClientScreen"', html)
        self.assertIn('id="importExistingScreen"', html)
        self.assertIn('data-screen="setup"', html)
        self.assertIn('data-screen="select-client"', html)
        self.assertIn('data-screen="import-existing"', html)
        self.assertIn('data-setup-mode="admission-wizard"', html)
        self.assertIn('data-setup-flow-frame="left-step-rail"', html)
        self.assertIn('data-visual-reference="10_first_run_setup_wizard"', html)
        self.assertIn('data-visual-reference="11_select_client_screen"', html)
        self.assertIn('data-visual-reference="12_import_existing_wizard"', html)
        self.assertIn("setup-flow-rail", html)
        self.assertIn("setup-bottom-bar", html)
        self.assertIn("Настройка Wild Boar Proxy", js)
        self.assertIn("Безопасная подготовка локального контура без изменения рабочих файлов Codex.", html + js)
        self.assertIn("Live-readonly setup недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Экран показывает setup preview, не результат настройки.", html + js)
        self.assertIn("setup preview, не результат настройки", js)
        self.assertIn("Первичная настройка", html)
        self.assertIn("Готовность локального контура", html)
        self.assertIn("admission state", html)
        self.assertIn("Codex client candidate", html)
        self.assertIn("Manual picker", html)
        self.assertIn("Data directory", html)
        self.assertIn("Проверка", html)
        self.assertIn("Runtime status", html)
        self.assertIn("Client surface", html)
        self.assertIn("Accounts pool", html)
        self.assertIn("Diagnostics export", html)
        self.assertIn("Desktop bridge", html)
        self.assertIn("Setup proof", html)
        self.assertNotIn("Setup complete", html)
        self.assertIn("no browser path", html)
        self.assertIn("command surface missing", html)
        self.assertIn("future desktop/native flow", html)
        self.assertIn("owner-gated", html)
        self.assertIn("Продолжить · requires proof", html)
        self.assertIn("Проверить готовность · missing surface", html)
        self.assertIn("setup proof packet", html)
        self.assertIn("Закрыть", html)
        self.assertIn('data-select-client-mode="candidate-preview"', html)
        self.assertIn("Демо-режим. Кандидаты показаны как fixture preview", html)
        self.assertIn("Выберите локальный клиент Codex из безопасно предоставленных кандидатов.", js)
        self.assertIn("Список клиентов недоступен. Ручной выбор ожидает desktop/native flow.", js)
        self.assertIn("Клиент", html)
        self.assertIn("candidate preview", html)
        self.assertIn("Поиск по кандидату · local filter only", html)
        self.assertIn("source: fixture candidate display", html)
        self.assertIn("Предпросмотр выбора", html)
        self.assertIn("Preview не является saved selection или runtime readiness.", html)
        self.assertIn("browser path payload forbidden", html)
        self.assertIn("Выбрать кандидата · disabled", html)
        self.assertIn("Проверить кандидатов · missing surface", html)
        self.assertIn("Сохранить выбор · requires candidate proof", html)
        self.assertIn("inert display only", html)
        self.assertIn("not claimed here", html)
        self.assertIn('data-import-mode="transaction-preview"', html)
        self.assertIn('data-legacy-reference="08_import_existing"', html)
        self.assertIn("Transaction wizard", html)
        self.assertIn("Кандидат импорта", html)
        self.assertIn("План импорта", html)
        self.assertIn("Безопасность", html)
        self.assertIn("Результат", html)
        self.assertIn("candidate preview", html)
        self.assertIn("dry-run required", html)
        self.assertIn("snapshot required", html)
        self.assertIn("rollback not confirmed", html)
        self.assertIn("apply disabled", html)
        self.assertIn("Preview не является runtime truth", html)
        self.assertIn("Partial import не считается success", html)
        self.assertIn("Rollback обязателен для apply", html)
        self.assertIn("Найти установку · missing surface", html)
        self.assertIn("Проверить · requires dry-run", html)
        self.assertIn("Создать snapshot · deferred", html)
        self.assertIn("Откатить · no rollback point", html)
        self.assertIn("Применить · requires packet proof", html)

        for screen_id in ["setupScreen", "selectClientScreen", "importExistingScreen"]:
            section = self._section_html(html, screen_id)
            self.assertNotIn("data-ui-action", section)
            self.assertNotIn("live-action", section)
            self.assertNotIn('type="file"', section)
            self.assertNotIn("<input", section)
            self.assertNotIn("<select", section)
            self.assertNotIn("readAsText", section)
            self.assertNotIn("window.open", section)
            self.assertNotIn("localStorage", section)
            self.assertNotIn("client_path", section)
            self.assertNotIn("source_dir", section)
            self.assertNotIn("source-dir", section)
            self.assertNotIn("auth_ref", section)
            self.assertNotIn("password", section)
            self.assertNotIn("backend_id", section)
            self.assertNotIn("installer init", section)
            self.assertNotIn("legacy import", section)
            self.assertNotIn("Проверка завершена. Импорт можно применить.", section)
            self.assertNotIn("28 accounts", section)
            self.assertNotIn("Применить</button>", section)
        setup_section = self._section_html(html, "setupScreen")
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', setup_section)
        self.assertIn('src="assets/icons/phosphor/sliders-horizontal.png"', setup_section)
        self.assertIn('src="assets/icons/phosphor/squares-four.png"', setup_section)
        self.assertNotIn('src="assets/icons/phosphor/x-circle.png"', setup_section)
        self.assertNotIn("setup-component-icon red", setup_section)
        self.assertNotIn("setup-card-icon red", setup_section)
        self.assertNotIn("chip red", setup_section)
        self.assertNotIn("<svg", setup_section.lower())
        for forbidden in (
            "Установка завершена",
            "Клиент найден",
            "Конфигурация сохранена",
            "найдено приложение",
            "production",
            "путь сохранён",
            "данные инициализированы",
        ):
            self.assertNotIn(forbidden, setup_section + js)
        self.assertNotIn('class="button primary small">Продолжить', setup_section)
        self.assertNotIn('class="button primary small disabled" type="button" disabled title="Continue requires setup proof packet.">Продолжить', setup_section)
        self.assertRegex(
            setup_section,
            r'<button class="button small disabled setup-continue-disabled"[^>]*disabled[^>]*>Продолжить · requires proof</button>',
        )
        select_client_section = self._section_html(html, "selectClientScreen")
        self.assertIn('src="assets/icons/phosphor/magnifying-glass.png"', select_client_section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', select_client_section)
        self.assertIn('src="assets/icons/phosphor/x-circle.png"', select_client_section)
        self.assertNotIn("<svg", select_client_section.lower())
        self.assertNotIn("Поиск по имени или пути", select_client_section)
        self.assertNotIn("Поиск по пути", select_client_section)
        self.assertNotIn('class="button primary small">Сохранить', select_client_section)
        self.assertNotIn('class="button primary small disabled"', select_client_section)
        self.assertRegex(
            select_client_section,
            r'<button class="button small disabled setup-save-disabled"[^>]*disabled[^>]*>Сохранить выбор · requires candidate proof</button>',
        )
        import_section = self._section_html(html, "importExistingScreen")
        self.assertIn('src="assets/icons/phosphor/magnifying-glass.png"', import_section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', import_section)
        self.assertIn('src="assets/icons/phosphor/arrows-clockwise.png"', import_section)
        self.assertIn('src="assets/icons/phosphor/warning.png"', import_section)
        self.assertIn('src="assets/icons/phosphor/check-circle.png"', import_section)
        self.assertIn('src="assets/icons/phosphor/info.png"', import_section)
        self.assertNotIn("<svg", import_section.lower())
        self.assertNotIn("showOpenFilePicker", import_section)
        self.assertNotIn("source_path", import_section)
        self.assertNotIn("auth_file", import_section)
        self.assertNotIn("config_path", import_section)
        self.assertNotIn("raw_plan_json", import_section)
        self.assertNotIn("argv", import_section)
        self.assertNotIn("command_id", import_section)
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        self.assertIn(".setup-flow-layout", css)
        self.assertIn("grid-template-columns: minmax(220px, 236px) minmax(0, 1fr)", css)
        self.assertIn(".setup-flow-rail", css)
        self.assertIn(".setup-bottom-bar", css)
        self.assertIn(".setup-card-head", css)
        self.assertIn(".setup-card-icon", css)
        self.assertIn(".setup-readiness-card", css)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr))", css)
        self.assertIn(".setup-component-row", css)
        self.assertIn(".setup-boundary-grid", css)
        self.assertIn(".setup-action-reasons", css)
        self.assertIn(".select-client-candidate-row", css)
        self.assertIn(".candidate-path", css)
        self.assertIn(".select-client-detail-grid", css)
        self.assertIn(".import-phase-row", css)
        self.assertIn(".import-existing-screen", css)
        self.assertIn(".import-transaction-layout", css)
        self.assertIn(".import-step-rail", css)
        self.assertIn(".import-card-grid", css)
        self.assertIn(".import-bottom-bar", css)
        self.assertIn(".import-apply-disabled", css)
        self.assertIn("padding: 24px", css)

    def test_import_existing_transaction_wizard_is_bounded_preview(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        section = self._section_html(html, "importExistingScreen")

        self.assertIn('data-import-mode="transaction-preview"', section)
        self.assertIn("Найти", section)
        self.assertIn("Проверить", section)
        self.assertIn("Снимок", section)
        self.assertIn("Применить", section)
        self.assertIn("Демо-режим. План импорта показан как preview, не как найденные локальные файлы.", section)
        self.assertIn("Импорт требует command-owned discovery, dry-run, snapshot и rollback packet.", section)
        self.assertIn("fixture candidate display", section)
        self.assertIn("preview count · not confirmed", section)
        self.assertIn("Ожидает command-owned discovery", section)
        self.assertIn("Dry-run preview без raw config, auth files или mutable path.", section)
        self.assertIn("Partial import не считается success", section)
        self.assertIn("Rollback обязателен для apply", section)
        self.assertIn("Применить · requires packet proof", section)
        self.assertIn("Apply отключён", section)
        self.assertIn("Preview не является runtime truth", section)

        for forbidden in (
            "data-ui-action",
            "live-action",
            "<input",
            "<select",
            "<textarea",
            'type="file"',
            "showOpenFilePicker",
            "readAsText",
            "localStorage",
            "source_path",
            "source-dir",
            "source_dir",
            "auth_file",
            "config_path",
            "raw_plan_json",
            "token",
            "secret",
            "argv",
            "command_id",
            "Применить</button>",
            "Импорт завершён",
            "Готово",
            "Найдено 28 аккаунтов",
            "Можно применить",
        ):
            self.assertNotIn(forbidden, section)

        self.assertIn("updateImportExistingCopy", js)
        self.assertIn("canonicalImportVariant", js)
        self.assertIn("importVariantModel", js)
        self.assertIn("setImportVisualClass", js)
        self.assertIn("live_failure", js)
        self.assertIn("Import discovery недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("live packet unavailable", js)
        self.assertIn("UI не переиспользует fixture path, fixture count или preview как live truth.", js)
        self.assertIn("Partial import не считается success", js)
        self.assertIn("Snapshot preview готов, но apply остаётся disabled без admitted command surface.", js)
        self.assertIn("Rollback preview доступен только как model state; apply остаётся disabled.", js)
        self.assertNotIn("import_existing_apply", html + js)
        self.assertNotIn("import_existing_preflight", html + js)

    def test_setup_select_import_routes_are_static_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('"setup"', js)
        self.assertIn('"select-client"', js)
        self.assertIn('"import-existing"', js)
        self.assertNotIn('?screen=setup', html)
        self.assertIn('?screen=select-client', html)
        nav_markup = html.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn('?screen=select-client', nav_markup)
        self.assertNotIn('?screen=import-existing', html)
        self.assertNotIn("setup_discovery", html + js)
        self.assertNotIn("verify_path", html + js)
        self.assertNotIn("save_selection", html + js)
        self.assertNotIn("legacy_import", html + js)
        self.assertNotIn("installer_init", html + js)
        self.assertNotIn("import_apply", html + js)

    def test_static_preview_uses_ui_action_for_basic_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-ui-action="refresh_health_detail"', html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn('data-ui-action="stable_repair_plan"', html)
        self.assertIn('data-ui-action="sync_runtime"', html)
        self.assertIn('data-ui-action="set_mode_stable"', html)
        self.assertIn('data-ui-action="set_mode_managed"', html)
        self.assertIn('data-ui-action="launch_smoke"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertNotIn('data-ui-action="launch_client"', html)
        self.assertNotIn('data-ui-action="stable_repair_apply"', html)
        self.assertIn('fetch("api/action"', js)
        self.assertIn("boundedUiActionPayload(uiAction, extraPayload)", js)
        self.assertIn("body: JSON.stringify(requestPayload)", js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn("client_path", html + js)
        self.assertNotIn("sync --json", html + js)
        self.assertNotIn("mode set stable --json", html + js)
        self.assertNotIn("launch smoke --json", html + js)
        self.assertNotIn("launch client", html + js)

    def test_static_preview_requires_confirmation_for_mutating_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        onboard_modal = self._overlay_html(html, "onboardOverlay", "confirmOverlay")

        self.assertIn("confirmOverlay", html)
        self.assertIn('id="confirmModal"', html)
        self.assertIn('data-modal-surface="action-command-request"', html)
        self.assertIn('data-modal-surface="onboard-reserve-request"', html)
        self.assertIn('class="confirm-boundary"', html)
        self.assertIn('class="onboard-facts-grid"', onboard_modal)
        self.assertIn('class="onboard-technical-boundaries"', onboard_modal)
        self.assertIn("Показать технические границы", onboard_modal)
        self.assertIn("Browser не передаёт secrets, auth files или local paths.", onboard_modal)
        self.assertNotIn("live request admitted", onboard_modal)
        self.assertNotIn("live request denied", onboard_modal)
        self.assertNotIn("reserve-first success only", onboard_modal)
        self.assertNotIn("accounts-readonly refresh", onboard_modal)
        self.assertIn("Не меняет другие routes и не утверждает runtime readiness.", js)
        self.assertIn("command request", html)
        self.assertIn("не runtime truth", html)
        self.assertIn("нужен JSON refresh", html)
        self.assertIn("confirmAction", html)
        self.assertIn("cancelAction", html)
        self.assertIn("confirmSeverity", html)
        self.assertIn("confirmPolicy", html)
        self.assertIn("confirmTruthWarning", html)
        self.assertIn("confirmDispatchState", html)
        self.assertIn("accountActionPreflight", html)
        self.assertIn("Account action summary", html)
        self.assertIn("Current pool", html)
        self.assertIn("Requested action", html)
        self.assertIn("Подтверждением результата остаётся command packet плюс canonical refresh.", html)
        self.assertIn("launchClientPreflight", html)
        self.assertIn("Isolated copy preflight", html)
        self.assertIn("Separate profile", html)
        self.assertIn("Separate data dir", html)
        self.assertIn("Separate port", html)
        self.assertIn("Process proof", html)
        self.assertIn("apiRouteRemovePreflight", html)
        self.assertIn("Route exists", html)
        self.assertIn("remove registry route", html)
        self.assertIn("Сервер повторно проверит disabled-state", html)
        self.assertIn("CONFIRMATION_POLICY", js)
        self.assertIn("CONSERVATIVE_CONFIRMATION_POLICY", js)
        self.assertIn("confirmationInFlight", js)
        self.assertIn("setConfirmationInFlight", js)
        self.assertIn("maybeConfirmAndRun", js)
        self.assertIn("metadata.confirmation_required", js)
        self.assertIn("confirmationPolicyFor(uiAction, metadata)", js)
        self.assertIn("confirmModal.dataset.confirmSeverity", js)
        self.assertIn("function closeConfirmation()", js)
        self.assertIn("if (confirmationInFlight)", js)
        self.assertIn("pendingConfirmedAction = null;", js)
        self.assertIn("runUiAction(pending.uiAction, pending.extraPayload);", js)
        self.assertIn("post_action_refresh_required", js)
        self.assertIn("setLiveReadonly(false)", js)
        self.assertIn("ACCOUNT_UI_ACTIONS", js)
        self.assertIn("renderAccountActionPreflight", js)
        self.assertIn("renderLaunchClientPreflight", js)
        self.assertIn("findAccountById", js)
        self.assertIn("confirmationReadyLabel", js)
        self.assertIn("renderApiRouteRemovePreflight", js)
        self.assertIn("apiRouteRemoveRefreshState", js)
        self.assertIn("apiRoutePresentInSnapshot", js)

    def test_static_onboarding_modal_is_operator_simplified_without_browser_inputs(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        onboard_modal = self._overlay_html(html, "onboardOverlay", "confirmOverlay")

        self.assertIn("<h2 id=\"onboardTitle\">Проверить подключение аккаунта</h2>", onboard_modal)
        self.assertIn("id=\"onboardIntro\"", onboard_modal)
        self.assertIn("Сначала выполняется безопасный dry-run preview. Реальное добавление в резерв на этом шаге не выполняется.", onboard_modal)
        self.assertIn("<dt>Источник</dt><dd id=\"onboardSourceValue\">server-owned preview</dd>", onboard_modal)
        self.assertIn("<dt>Режим</dt><dd id=\"onboardModeValue\">Dry-run</dd>", onboard_modal)
        self.assertIn("<dt>После команды</dt><dd id=\"onboardAfterValue\">Live accounts не меняются</dd>", onboard_modal)
        self.assertIn("<dt>Результат</dt><dd id=\"onboardResultValue\">packet preview only</dd>", onboard_modal)
        self.assertIn("Web не принимает токены, файлы и локальные пути.", onboard_modal)
        self.assertIn("<details class=\"onboard-technical-boundaries\">", onboard_modal)
        self.assertNotIn("<details class=\"onboard-technical-boundaries\" open", onboard_modal)
        self.assertIn("id=\"onboardTechnicalCommand\"", onboard_modal)
        self.assertIn("id=\"onboardTechnicalPreview\"", onboard_modal)
        self.assertIn("Команда запускается только как <span class=\"mono-value\">onboard_account_dry_run</span>.", onboard_modal)
        self.assertIn("Preview не импортирует auth и не меняет registry.", onboard_modal)
        self.assertIn("No-new-auth не считается live-успехом.", onboard_modal)
        self.assertIn("Ambiguous identity требует действия оператора.", onboard_modal)
        self.assertIn("id=\"onboardTechnicalNextStep\"", onboard_modal)
        self.assertIn("После admitted preview можно вернуться и подтвердить live connect в sandbox.", onboard_modal)
        self.assertIn('id="runOnboardAction" class="button primary" type="button">Проверить подключение</button>', onboard_modal)
        self.assertIn("populateOnboardModal()", js)
        self.assertIn('maybeConfirmAndRun(onboardingLiveReadyInSession() ? "onboard_account" : "onboard_account_dry_run")', js)
        self.assertIn('return "Проверить подключение";', js)
        self.assertIn('return "Подключить в резерв";', js)
        self.assertIn('id="actionPanel" class="action-panel neutral compact-action-panel" aria-live="polite" tabindex="-1"', html)
        self.assertIn("revealActionPanel(display.displayState);", js)
        self.assertIn('panel.scrollIntoView({ behavior: "smooth", block: "start" });', js)
        self.assertIn('panel.focus({ preventScroll: true });', js)
        self.assertIn('const ACTION_URL = MODEL.serverOrigin ? MODEL.serverOrigin + "/api/action" : "api/action";', js)
        self.assertIn('document.getElementById("checkButton")?.addEventListener("click", () => requestAction("account_login_status"));', js)
        self.assertIn('document.getElementById("completeButton")?.addEventListener("click", () => requestAction("account_login_complete"));', js)
        self.assertIn('document.getElementById("cancelButton")?.addEventListener("click", () => requestAction("account_login_cancel"));', js)
        self.assertIn("URL.createObjectURL(new Blob([html], { type: \"text/html;charset=utf-8\" }))", js)
        self.assertNotIn("data:text/html;charset=utf-8", js)
        self.assertIn('const checkHidden = model?.canCheck === false ? " hidden" : "";', js)
        self.assertIn('const completeHidden = model?.canComplete === true ? "" : " hidden";', js)
        self.assertIn('const cancelHidden = model?.canCancel === false ? " hidden" : "";', js)

        self.assertNotIn("onboard-stepper", onboard_modal)
        self.assertNotIn("onboard-source-card", onboard_modal)
        self.assertNotIn("modal-state-list", onboard_modal)
        self.assertNotIn("raw auth surface", onboard_modal)
        self.assertNotIn("backend id", onboard_modal)
        self.assertNotIn("existing live path", onboard_modal)
        self.assertNotIn("packet proof only", onboard_modal)
        self.assertNotIn("active-ready", onboard_modal)
        self.assertNotIn("showOpenFilePicker", onboard_modal + js)
        self.assertNotIn('type="file"', onboard_modal)
        self.assertNotIn("<textarea", onboard_modal)
        self.assertNotIn("<input", onboard_modal)
        self.assertNotIn("browser-submitted", onboard_modal + js)
        self.assertNotIn("source_dir", onboard_modal)
        self.assertNotIn("auth_ref", onboard_modal)

    def test_static_confirmation_modal_matches_locked_visual_tokens(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('class="confirm-modal onboard-modal"', html)
        self.assertIn('class="confirm-modal action-confirm-modal"', html)
        self.assertIn("padding: 40px;", css)
        self.assertIn("border-radius: 24px;", css)
        self.assertIn("padding: 32px;", css)
        self.assertIn("0 32px 96px rgba(30, 27, 24, .18)", css)
        self.assertIn("width: min(100%, 640px);", css)
        self.assertIn("width: min(100%, 600px);", css)
        self.assertIn(".confirm-modal-header", css)
        self.assertIn(".confirm-boundary", css)
        self.assertIn(".modal-state-list", css)
        self.assertIn(".modal-state-row", css)
        self.assertIn(".onboard-facts-grid", css)
        self.assertIn(".onboard-technical-boundaries", css)
        self.assertIn("max-height: min(760px, calc(100vh - 96px));", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"critical\"]::before", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"high\"]::before", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"medium\"]::before", css)
        self.assertIn("overflow-y: auto;", css)
        self.assertIn(".onboard-modal .confirm-actions", css)
        self.assertIn("@media (max-width: 1120px)", css)
        self.assertIn(".confirm-actions .button", css)

    def test_action_ledger_normalizes_error_states_without_false_green(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('id="actionDisplayState"', html)
        self.assertIn('id="actionTruthNote"', html)
        self.assertIn('id="actionSupportDetails"', html)
        self.assertIn('id="actionPanel" class="action-panel neutral compact-action-panel"', html)
        self.assertIn('id="actionDisplayChip"', html)
        self.assertIn('id="actionOpenLedgerAction"', html)
        self.assertIn('id="actionLedgerOverlay"', html)
        self.assertIn('id="actionLedgerPanel"', html)
        self.assertIn('id="actionLedgerList"', html)
        self.assertIn('id="actionLedgerScope"', html)
        self.assertIn("Текущая UI-сессия", html)
        self.assertIn("не сохраняется", html)
        self.assertIn("ACTION_STATUS_VISUAL_CLASS", js)
        self.assertIn("ACTION_LEDGER_LIMIT = 5", js)
        self.assertIn("let actionLedger = []", js)
        self.assertIn("let actionLedgerFilter = \"all\"", js)
        self.assertIn("let activeActionRequestKey = \"\"", js)
        self.assertIn("recordActionLedgerEntry", js)
        self.assertIn("renderActionLedger", js)
        self.assertIn("openActionLedgerPanel", js)
        self.assertIn("setActionLedgerFilter", js)
        self.assertIn("safeLedgerText", js)
        self.assertIn("row.open = false", js)
        self.assertIn("changedFilesCount", js)
        self.assertIn('duplicate_blocked: "neutral"', js)
        self.assertIn('ok_refresh_pending: "amber"', js)
        self.assertIn('ok_refresh_complete: "green"', js)
        self.assertIn('ok_refresh_failed: "amber"', js)
        self.assertIn('refresh_mismatch: "amber"', js)
        self.assertIn('command_error: "red"', js)
        self.assertIn('integration_failure: "red"', js)
        self.assertIn('invalid_json: "red"', js)
        self.assertIn('timeout: "amber"', js)
        self.assertIn('stale: "amber"', js)
        self.assertIn('unknown: "neutral"', js)
        self.assertIn("payload.status || result.status", js)
        self.assertIn("actionSupportDetails(payload)", js)
        self.assertIn("artifactReference(data.evidence_path)", js)
        self.assertIn('displayState = "ok_refresh_failed"', js)
        self.assertIn('displayState = "refresh_mismatch"', js)
        self.assertIn("canonical refresh failed", js)
        self.assertIn("canonical refresh mismatch", js)
        self.assertIn("UI_ACTION_INVALID_JSON", js)
        self.assertIn("UI_ACTION_TIMEOUT", js)
        self.assertIn("UI_DUPLICATE_SUBMIT_BLOCKED", js)
        self.assertIn("а не успех", js)
        self.assertIn(".action-ledger-panel", css)
        self.assertIn(".action-summary-head", css)
        self.assertIn(".action-panel.green", css)
        self.assertIn(".action-panel.blue", css)
        self.assertIn(".action-panel.amber", css)
        self.assertIn(".action-panel.red", css)
        self.assertIn(".action-panel.neutral", css)
        self.assertIn(".action-ledger-row.green", css)
        self.assertIn(".action-ledger-row.blue", css)
        self.assertIn(".action-ledger-row.amber", css)
        self.assertIn(".action-ledger-row.red", css)
        self.assertIn(".onboarding-result-flow", css)
        self.assertIn(".onboarding-result-banner.green", css)
        self.assertIn(".onboarding-state-row", css)

    def test_onboarding_result_flow_renders_reserve_first_without_active_claim(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.children = [];
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "onboardingResultFlow",
  "onboardingResultModeChip",
  "onboardingResultTitle",
  "onboardingResultSummary",
  "onboardingResultSummaryNote",
  "onboardingResultBanner",
  "onboardingResultNewIds",
  "onboardingResultSelected",
  "onboardingResultSelectionChip",
  "onboardingResultPoolChip",
  "onboardingResultReserveChip",
  "onboardingResultValidateChip",
  "onboardingResultSyncChip",
  "onboardingResultStatusProofChip",
  "onboardingResultRefreshChip",
  "onboardingResultNextAction"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.onboardingResultModeChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setActionPanel({
  status: "ok",
  ui_action: "account_login_complete",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
      human_message: "Onboarding owner packet emitted.",
      next_action: "none",
      changed_files: [],
      onboarding: {
        ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-new",
      new_backend_ids: ["acct-new"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "reserve",
      active_routing_changed: false,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
	}, "complete");

const serialized = JSON.stringify(elements);
if (elements.onboardingResultFlow.hidden !== false) {
  throw new Error("onboarding result flow must be visible for account_login_complete");
}
if (elements.onboardingResultBanner.className !== "onboarding-result-banner green") {
  throw new Error(`success banner must be green: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel green") {
  throw new Error(`success panel must be green: ${elements.actionPanel.className}`);
}
if (!elements.onboardingResultBanner.textContent.includes("Аккаунт добавлен в резерв")) {
  throw new Error(`reserve-first success copy missing: ${elements.onboardingResultBanner.textContent}`);
}
if (elements.onboardingResultSelected.textContent !== "acct-new") {
  throw new Error(`safe selected backend id missing: ${elements.onboardingResultSelected.textContent}`);
}
if (elements.onboardingResultReserveChip.textContent !== "доказано") {
  throw new Error(`reserve proof chip missing: ${elements.onboardingResultReserveChip.textContent}`);
}
if (elements.onboardingResultStatusProofChip.textContent !== "confirmed") {
  throw new Error(`status proof chip missing: ${elements.onboardingResultStatusProofChip.textContent}`);
}
if (elements.onboardingResultPoolChip.textContent !== "Резерв") {
  throw new Error(`pool chip must show reserve: ${elements.onboardingResultPoolChip.textContent}`);
}
if (!elements.onboardingResultNextAction.textContent.includes("отдельным действием оператора")) {
  throw new Error(`next action must keep promotion separate: ${elements.onboardingResultNextAction.textContent}`);
}
if (serialized.includes("Аккаунт активен") || serialized.includes("Аккаунт продвинут")) {
  throw new Error(`onboarding result overclaimed active/promoted state: ${serialized}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "account_login_complete",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH_FAILED",
    human_message: "Onboarding owner packet emitted.",
    next_action: "refresh_accounts",
    changed_files: [],
    onboarding: {
      ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-refresh-failed",
      new_backend_ids: ["acct-refresh-failed"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "reserve",
      active_routing_changed: false,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
}, "failed");
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("refresh-failed onboarding must not keep outer panel green");
}
if (elements.actionDisplayState.textContent !== "ok_refresh_failed") {
  throw new Error(`refresh-failed onboarding must show ok_refresh_failed: ${elements.actionDisplayState.textContent}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "account_login_complete",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "user_action",
    changed_files: [],
    onboarding: {
      ui_state: "needs_user_action",
      final_outcome: "no_new_auth_detected",
      selected_backend_id: "",
      reserve_first_proven: false,
      selection_status: "not_selected"
    }
  }
});
if (elements.onboardingResultBanner.className !== "onboarding-result-banner amber") {
  throw new Error(`needs_user_action must be amber: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("no-new-auth outer panel must not be green");
}
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("non-success onboarding must not show selected backend");
}
if (!elements.onboardingResultBanner.textContent.includes("не добавило аккаунт")) {
  throw new Error(`non-success copy must not be green: ${elements.onboardingResultBanner.textContent}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "account_login_complete",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "operator_action",
    changed_files: [],
    onboarding: {
      ui_state: "needs_user_action",
      final_outcome: "ambiguous_new_auth_detection",
      selected_backend_id: "acct-hidden",
      reserve_first_proven: false,
      selection_status: "ambiguous"
    }
  }
});
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("ambiguous onboarding must hide selected backend");
}
if (!elements.onboardingResultBanner.textContent.includes("Требуется действие оператора")) {
  throw new Error(`ambiguous copy must require operator action: ${elements.onboardingResultBanner.textContent}`);
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("ambiguous outer panel must not be green");
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "retry",
    changed_files: [],
    onboarding: {
      ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-leaky",
      new_backend_ids: ["acct-leaky"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "active",
      active_routing_changed: true,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
});
if (elements.onboardingResultBanner.className === "onboarding-result-banner green") {
  throw new Error("active routing change must not be rendered green");
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("active routing contradiction must not keep outer panel green");
}
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("selected backend must be hidden when reserve proof contradicts pool");
}

sandbox.setActionPanel({
  ui_action: "account_login_complete",
  action_role: "integration_failure",
  post_action_refresh_required: false,
  result: {
    status: "invalid_json",
    machine_error_code: "UI_ACTION_INVALID_JSON",
    human_message: "invalid json",
    next_action: "retry",
    changed_files: []
  }
});
if (elements.onboardingResultBanner.className !== "onboarding-result-banner red") {
  throw new Error(`onboarding invalid_json banner must be red: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel red") {
  throw new Error(`onboarding invalid_json outer panel must be red: ${elements.actionPanel.className}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboarding_dry_run_flow_stays_preview_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.children = [];
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "onboardingResultFlow",
  "onboardingResultModeChip",
  "onboardingResultTitle",
  "onboardingResultSummary",
  "onboardingResultSummaryNote",
  "onboardingResultBanner",
  "onboardingResultNewIds",
  "onboardingResultSelected",
  "onboardingResultSelectionChip",
  "onboardingResultPoolChip",
  "onboardingResultReserveChip",
  "onboardingResultValidateChip",
  "onboardingResultSyncChip",
  "onboardingResultStatusProofChip",
  "onboardingResultRefreshChip",
  "onboardingResultNextAction"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.onboardingResultModeChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account_dry_run",
  action_role: "account_onboarding_preview",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Dry-run preview prepared.",
    next_action: "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
    changed_files: [],
    onboarding: {
      preview_only: true,
      ui_state: "dry_run_ready",
      final_outcome: "dry_run_preview_ready",
      candidate_source_kind: "server_owned_only",
      reserve_first_boundary: "required",
      required_follow_up: "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
      blocked_reasons: [],
      operator_action_required: true
    }
  }
});

const serialized = JSON.stringify(elements);
if (elements.onboardingResultFlow.hidden !== false) {
  throw new Error("dry-run onboarding flow must be visible");
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("dry-run preview must not render green outer panel");
}
if (!elements.onboardingResultBanner.textContent.includes("Dry-run preview")) {
  throw new Error(`dry-run banner missing: ${elements.onboardingResultBanner.textContent}`);
}
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error(`dry-run preview must not show selected backend: ${elements.onboardingResultSelected.textContent}`);
}
if (!elements.onboardingResultSummary.textContent.includes("Аккаунт не подключён")) {
  throw new Error(`dry-run summary overclaims success: ${elements.onboardingResultSummary.textContent}`);
}
if (!elements.onboardingResultNextAction.textContent.includes("WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS")) {
  throw new Error(`dry-run next step missing: ${elements.onboardingResultNextAction.textContent}`);
}
if (serialized.includes("Аккаунт добавлен в резерв") || serialized.includes("можно использовать")) {
  throw new Error(`dry-run preview leaked success wording: ${serialized}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboard_modal_switches_to_live_connect_after_admitted_preview(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: () => false,
      add: () => {},
      remove: () => {},
      toggle: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  focus() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "onboardingResultFlow",
  "onboardingResultModeChip",
  "onboardingResultTitle",
  "onboardingResultSummary",
  "onboardingResultSummaryNote",
  "onboardingResultBanner",
  "onboardingResultNewIds",
  "onboardingResultSelected",
  "onboardingResultSelectionChip",
  "onboardingResultPoolChip",
  "onboardingResultReserveChip",
  "onboardingResultValidateChip",
  "onboardingResultSyncChip",
  "onboardingResultStatusProofChip",
  "onboardingResultRefreshChip",
  "onboardingResultNextAction",
  "onboardOverlay",
  "onboardTitle",
  "onboardIntro",
  "onboardSourceValue",
  "onboardModeValue",
  "onboardAfterValue",
  "onboardResultValue",
  "onboardTechnicalCommand",
  "onboardTechnicalPreview",
  "onboardTechnicalNextStep",
  "runOnboardAction"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.onboardingResultModeChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/actions") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          actions: {
            onboard_account_dry_run: {
              ui_action: "onboard_account_dry_run",
              display_name: "Проверить подключение аккаунта",
              human_meaning: "dry-run onboarding preview",
              action_role: "account_onboarding_preview",
              mutates_runtime: false,
              affects_primary_truth: false,
              confirmation_required: false,
              post_action_refresh_required: false,
              action_claim_scope: "preview_only",
              available: true,
              availability_state: "displayable_readonly",
              disabled_reason_code: "",
              disabled_reasons: [],
              unavailable_reason: ""
            },
            onboard_account: {
              ui_action: "onboard_account",
              display_name: "Подключить аккаунт в резерв",
              human_meaning: "live reserve-first onboarding",
              action_role: "account_onboarding",
              mutates_runtime: true,
              affects_primary_truth: true,
              confirmation_required: true,
              post_action_refresh_required: true,
              action_claim_scope: "packet_plus_refresh",
              available: true,
              availability_state: "displayable_readonly",
              disabled_reason_code: "",
              disabled_reasons: [],
              unavailable_reason: ""
            }
          }
        })
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.loadActionMetadata();
  sandbox.setActionPanel({
    status: "ok",
    ui_action: "onboard_account_dry_run",
    action_role: "account_onboarding_preview",
    post_action_refresh_required: false,
    result: {
      status: "ok",
      machine_error_code: "OK",
      human_message: "Dry-run preview prepared.",
      next_action: "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
      changed_files: [],
      onboarding: {
        preview_only: true,
        ui_state: "dry_run_ready",
        final_outcome: "dry_run_preview_ready",
        candidate_source_kind: "server_owned_only",
        reserve_first_boundary: "required",
        required_follow_up: "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
        blocked_reasons: []
      }
    }
  });
  sandbox.openOnboardModal();
  if (elements.onboardTitle.textContent !== "Подключить аккаунт в резерв") {
    throw new Error(`modal must switch to live title: ${elements.onboardTitle.textContent}`);
  }
  if (elements.onboardModeValue.textContent !== "Live reserve-first") {
    throw new Error(`modal must switch to live mode: ${elements.onboardModeValue.textContent}`);
  }
  if (elements.onboardSourceValue.textContent !== "owner login bridge") {
    throw new Error(`modal must expose owner login bridge source: ${elements.onboardSourceValue.textContent}`);
  }
  if (elements.onboardAfterValue.textContent !== "owner login -> onboard -> refresh") {
    throw new Error(`modal must expose login->onboard->refresh chain: ${elements.onboardAfterValue.textContent}`);
  }
  if (elements.onboardResultValue.textContent !== "login packet + onboard packet + refresh proof") {
    throw new Error(`modal must expose result proof chain: ${elements.onboardResultValue.textContent}`);
  }
  if (!elements.onboardTechnicalCommand.textContent.includes("onboard_account")) {
    throw new Error(`modal must expose live command lane: ${elements.onboardTechnicalCommand.textContent}`);
  }
  if (!elements.onboardTechnicalCommand.textContent.includes("owner login bridge")) {
    throw new Error(`modal must describe owner login bridge: ${elements.onboardTechnicalCommand.textContent}`);
  }
  if (!elements.onboardTechnicalPreview.textContent.includes("engine-owned Codex login/onboard lane")) {
    throw new Error(`modal must describe engine-owned Codex login lane: ${elements.onboardTechnicalPreview.textContent}`);
  }
  if (elements.runOnboardAction.textContent !== "Подключить в резерв") {
    throw new Error(`modal action must switch to live label: ${elements.runOnboardAction.textContent}`);
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_action_support_details_surface_login_bridge_without_secrets(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const details = sandbox.actionSupportDetails({
  ui_action: "onboard_account",
  result: {
    data: {
      login_bridge: {
        status: "waiting_for_user",
        provider: "codex",
        phase: "start",
        session_id: "codex-session",
        device_url: "https://auth.openai.com/codex/device",
        device_code_present: true,
        auth_ref_scope: "sandbox",
        browser_secret_intake: false
      }
    }
  }
});
if (!details.includes("login_bridge=waiting_for_user")) {
  throw new Error(`login bridge status missing: ${details}`);
}
if (!details.includes("device_url=present")) {
  throw new Error(`device handoff marker missing: ${details}`);
}
if (!details.includes("device_code=present")) {
  throw new Error(`device code marker missing: ${details}`);
}
if (!details.includes("browser_secret_intake=false")) {
  throw new Error(`browser_secret_intake marker missing: ${details}`);
}
if (details.includes("/tmp/") || details.includes("token") || details.includes("secret=")) {
  throw new Error(`support details leaked sensitive data: ${details}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_action_support_details_surface_api_credential_missing_handoff(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const details = sandbox.actionSupportDetails({
  ui_action: "api_route_connect",
  result: {
    data: {
      credential_phase: "credential_missing",
      credential_present: false,
      credential_admitted: false,
      credential_ref: "OPENROUTER_API_KEY",
      credential_supported_sources: ["owner-env"],
      credential_expected_refs: [
        "OPENROUTER_API_KEY",
        "WBP_OPENROUTER_API_KEY",
        "WBP_PROVIDER_OPENROUTER_API_KEY"
      ],
      credential_provider_dashboard_url: "https://openrouter.ai/settings/keys",
      browser_api_key_intake: false,
      secret_value_exposed: false
    }
  }
});
for (const expected of [
  "credential_phase=credential_missing",
  "credential_present=false",
  "credential_admitted=false",
  "credential_ref=OPENROUTER_API_KEY",
  "supported_sources=owner-env",
  "expected_refs=OPENROUTER_API_KEY,WBP_OPENROUTER_API_KEY,WBP_PROVIDER_OPENROUTER_API_KEY",
  "provider_dashboard=https://openrouter.ai/settings/keys",
  "browser_api_key_intake=false",
  "secret_exposed=false"
]) {
  if (!details.includes(expected)) {
    throw new Error(`missing ${expected}: ${details}`);
  }
}
if (details.includes("sk-") || details.includes("secret=") || details.includes("token=")) {
  throw new Error(`support details leaked sensitive material: ${details}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_render_api_credential_lane_surfaces_missing_owner_env_inline(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function makeNode() {
  const child = { textContent: "" };
  return {
    textContent: "",
    hidden: true,
    className: "",
    href: "",
    title: "",
    dataset: {},
    lastElementChild: child,
    classList: { toggle() {} },
    focus() {},
    scrollIntoView() {}
  };
}

const nodes = {};
for (const id of [
  "quickStartApiCredentialLane",
  "quickStartApiCredentialTitle",
  "quickStartApiCredentialSummary",
  "quickStartApiCredentialChip",
  "quickStartApiCredentialBanner",
  "quickStartApiCredentialProvider",
  "quickStartApiCredentialRef",
  "quickStartApiCredentialRefs",
  "quickStartApiCredentialSource",
  "quickStartApiCredentialRestart",
  "quickStartApiCredentialCheckAction",
  "quickStartApiCredentialRetryAction",
  "quickStartApiCredentialDashboardAction"
]) {
  nodes[id] = makeNode();
}

const sandbox = {
  console,
  document: {
    getElementById(id) { return nodes[id] || null; },
    createElement() { return makeNode(); },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.renderApiCredentialSetupLane({
  ui_action: "api_route_connect",
  result: {
    status: "command_error",
    machine_error_code: "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
    human_message: "Owner credential source is missing for provider: openrouter.",
    data: {
      credential_phase: "credential_missing",
      credential_present: false,
      credential_admitted: false,
      credential_provider: "openrouter",
      credential_ref: "OPENROUTER_API_KEY",
      credential_supported_sources: ["owner-env"],
      credential_expected_refs: [
        "OPENROUTER_API_KEY",
        "WBP_OPENROUTER_API_KEY",
        "WBP_PROVIDER_OPENROUTER_API_KEY"
      ],
      credential_provider_dashboard_url: "https://openrouter.ai/settings/keys",
      browser_api_key_intake: false,
      secret_value_exposed: false
    }
  }
}, "none");

if (nodes.quickStartApiCredentialLane.hidden !== false) {
  throw new Error("credential lane should be visible");
}
if (!nodes.quickStartApiCredentialTitle.textContent.includes("owner credential")) {
  throw new Error(`unexpected title: ${nodes.quickStartApiCredentialTitle.textContent}`);
}
if (!nodes.quickStartApiCredentialChip.lastElementChild.textContent.includes("missing")) {
  throw new Error(`unexpected chip: ${nodes.quickStartApiCredentialChip.lastElementChild.textContent}`);
}
if (!nodes.quickStartApiCredentialRefs.textContent.includes("WBP_PROVIDER_OPENROUTER_API_KEY")) {
  throw new Error(`expected refs missing: ${nodes.quickStartApiCredentialRefs.textContent}`);
}
if (nodes.quickStartApiCredentialDashboardAction.href !== "https://openrouter.ai/settings/keys") {
  throw new Error(`unexpected dashboard href: ${nodes.quickStartApiCredentialDashboardAction.href}`);
}
if (nodes.quickStartApiCredentialCheckAction.hidden !== false) {
  throw new Error("check action should remain visible");
}
if (nodes.quickStartApiCredentialRetryAction.hidden !== false) {
  throw new Error("retry action should remain visible");
}
if (!nodes.quickStartApiCredentialRestart.textContent.includes("restart")) {
  throw new Error(`restart note missing: ${nodes.quickStartApiCredentialRestart.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_render_api_credential_lane_marks_connected_after_refresh_proof(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function makeNode() {
  const child = { textContent: "" };
  return {
    textContent: "",
    hidden: true,
    className: "",
    href: "",
    title: "",
    dataset: {},
    lastElementChild: child,
    classList: { toggle() {} },
    focus() {},
    scrollIntoView() {}
  };
}

const nodes = {};
for (const id of [
  "apiConnectionsCredentialLane",
  "apiConnectionsCredentialTitle",
  "apiConnectionsCredentialSummary",
  "apiConnectionsCredentialChip",
  "apiConnectionsCredentialBanner",
  "apiConnectionsCredentialProvider",
  "apiConnectionsCredentialRef",
  "apiConnectionsCredentialRefs",
  "apiConnectionsCredentialSource",
  "apiConnectionsCredentialRestart",
  "apiConnectionsCredentialCheckAction",
  "apiConnectionsCredentialRetryAction",
  "apiConnectionsCredentialDashboardAction"
]) {
  nodes[id] = makeNode();
}

const sandbox = {
  console,
  document: {
    getElementById(id) { return nodes[id] || null; },
    createElement() { return makeNode(); },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "api-connections", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=api-connections" },
    history: { replaceState() {} },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.renderApiCredentialSetupLane({
  ui_action: "api_route_connect",
  result: {
    status: "ok",
    human_message: "API route connected.",
    data: {
      credential_phase: "credential_admitted",
      credential_present: true,
      credential_admitted: true,
      credential_provider: "openrouter",
      credential_ref: "OPENROUTER_API_KEY",
      credential_supported_sources: ["owner-env"],
      credential_expected_refs: ["OPENROUTER_API_KEY"],
      credential_provider_dashboard_url: "https://openrouter.ai/settings/keys",
      validate_status: "ok"
    }
  }
}, "complete");

if (nodes.apiConnectionsCredentialLane.hidden !== false) {
  throw new Error("credential lane should remain visible for connected proof");
}
if (!nodes.apiConnectionsCredentialTitle.textContent.includes("подключён")) {
  throw new Error(`unexpected connected title: ${nodes.apiConnectionsCredentialTitle.textContent}`);
}
if (!nodes.apiConnectionsCredentialChip.lastElementChild.textContent.includes("connected")) {
  throw new Error(`unexpected connected chip: ${nodes.apiConnectionsCredentialChip.lastElementChild.textContent}`);
}
if (nodes.apiConnectionsCredentialCheckAction.hidden !== true) {
  throw new Error("check action should be hidden after connected proof");
}
if (nodes.apiConnectionsCredentialRetryAction.hidden !== true) {
  throw new Error("retry action should be hidden after connected proof");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboard_account_opens_device_login_window_with_session_handoff(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const opened = { href: "", closed: false };
const openCalls = [];
const writes = [];
const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    open(url, target, features) {
      openCalls.push({ url, target, features });
      return {
        document: {
          open() {},
          write(value) { writes.push(value); },
          close() {}
        },
        location: {
          set href(value) { opened.href = value; },
          get href() { return opened.href; }
        },
        close() { opened.closed = true; }
      };
    }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/action") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          status: "ok",
          ui_action: "onboard_account",
          action_role: "account_onboarding",
          post_action_refresh_required: false,
          result: {
            status: "ok",
            machine_error_code: "OK",
            human_message: "done",
            next_action: "wait_for_login",
            changed_files: [],
            data: {
              login_bridge: {
                status: "waiting_for_user",
                provider: "codex",
                phase: "start",
                session_id: "codex-session",
                device_url: "https://auth.openai.com/codex/device",
                device_code: "WBP-1234",
                device_code_present: true,
                login_url_present: true,
                login_url_kind: "device_code"
              }
            }
          }
        })
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.runUiAction("onboard_account");
  if (openCalls.length !== 1 || openCalls[0].features) {
    throw new Error(`owner login pre-open must stay controllable, got ${JSON.stringify(openCalls)}`);
  }
  const html = writes.join("\n");
  if (!html.includes("Codex login is starting")) {
    throw new Error("owner login window did not receive a visible waiting page");
  }
  const hasDeviceHtml = html.includes("Codex device login")
    && html.includes("https://auth.openai.com/codex/device")
    && html.includes("WBP-1234");
  const navigatedToDeviceUrl = opened.href === "https://auth.openai.com/codex/device";
  if (!hasDeviceHtml && !navigatedToDeviceUrl) {
    throw new Error(`device handoff missing from login window: html=${html} href=${opened.href}`);
  }
  if (opened.closed) {
    throw new Error("owner login window should stay open when login_url is present");
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboard_account_owner_login_window_shows_blocked_status_when_start_packet_fails(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const opened = { href: "", closed: false };
const writes = [];
const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    open() {
      return {
        document: {
          open() {},
          write(value) { writes.push(value); },
          close() {}
        },
        location: {
          set href(value) { opened.href = value; },
          get href() { return opened.href; }
        },
        close() { opened.closed = true; }
      };
    }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/action") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          status: "command_error",
          ui_action: "onboard_account",
          action_role: "account_onboarding",
          post_action_refresh_required: false,
          result: {
            status: "command_error",
            machine_error_code: "UI_LOGIN_START_PACKET_INVALID",
            human_message: "login start failed",
            next_action: "retry",
            changed_files: [],
            data: { login_bridge: { status: "failed", provider: "codex", phase: "start", login_url_present: false, login_url_kind: "missing" } }
          }
        })
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.runUiAction("onboard_account");
  const html = writes.join("\n");
  if (!html.includes("Codex login is starting")) {
    throw new Error("owner login window did not show initial waiting state");
  }
  if (!html.includes("Codex login failed")) {
    throw new Error(`owner login window did not show failed start status: ${html}`);
  }
  if (opened.closed) {
    throw new Error("owner login window should stay visible with a diagnostic instead of closing blank");
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboard_account_codex_auth_materialized_status_shows_completion_step(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const opened = { href: "", closed: false };
const writes = [];
const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    open() {
      return {
        document: {
          open() {},
          write(value) { writes.push(value); },
          close() {}
        },
        location: {
          set href(value) { opened.href = value; },
          get href() { return opened.href; }
        },
        close() { opened.closed = true; }
      };
    }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/action") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          status: "ok",
          ui_action: "account_login_status",
          action_role: "account_login_status",
          post_action_refresh_required: false,
          session_id: "codex-session",
          result: {
            status: "ok",
            machine_error_code: "OK",
            human_message: "done",
            next_action: "accounts_onboard",
            changed_files: [],
            data: {
              login_bridge: {
                provider: "codex",
                status: "auth_materialized",
                phase: "status",
                session_id: "codex-session",
                device_url: "https://auth.openai.com/codex/device",
                device_code_present: true,
                auth_materialized: true,
                auth_ref_present: true,
                auth_ref_scope: "sandbox"
              }
            }
          }
        })
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.handleActionPayload({
    status: "ok",
    ui_action: "account_login_status",
    action_role: "account_login_status",
    post_action_refresh_required: false,
    session_id: "codex-session",
    result: {
      status: "ok",
      machine_error_code: "OK",
      human_message: "done",
      next_action: "accounts_onboard",
      changed_files: [],
      data: {
        login_bridge: {
          provider: "codex",
          status: "auth_materialized",
          phase: "status",
          session_id: "codex-session",
          device_url: "https://auth.openai.com/codex/device",
          device_code_present: true,
          auth_materialized: true,
          auth_ref_present: true,
          auth_ref_scope: "sandbox"
        }
      }
    }
  }, sandbox.openOnboardLoginWindow());
  const html = writes.join("\n");
  if (!html.includes("Codex login is starting")) {
    throw new Error("owner login window did not show initial waiting state");
  }
  if (!html.includes("Codex auth materialized")) {
    throw new Error(`owner login window did not show auth materialized handoff: ${html}`);
  }
  if (!html.includes("Завершить")) {
    throw new Error(`owner login window did not expose completion button: ${html}`);
  }
  if (opened.href && opened.href !== "https://auth.openai.com/codex/device") {
    throw new Error(`Codex owner handoff navigated to unexpected URL: ${opened.href}`);
  }
  if (opened.closed) {
    throw new Error("owner login window should stay visible with completion status");
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_api_route_connect_does_not_render_onboard_login_overlay(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

let overlayCalls = 0;
let windowCalls = 0;
const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    open() {
      throw new Error("api route connect must not open onboard login window");
    }
  },
  URL,
  URLSearchParams,
  fetch() {
    throw new Error("api route connect test should not fetch directly");
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderOnboardLoginOverlay = () => { overlayCalls += 1; };
sandbox.maybeNavigateOnboardLoginWindow = () => { windowCalls += 1; };
sandbox.setActionPanel = () => {};
sandbox.setMiniPill = () => {};
sandbox.text = () => {};
sandbox.currentScreen = () => "quick-start";
sandbox.setLiveReadonly = async () => ({
  status: "ok",
  apiConnections: {
    status: "ok",
    routes: [{ route_id: "wbp-web-primary-openrouter", enabled: true }]
  }
});

(async () => {
  await sandbox.handleActionPayload({
    status: "ok",
    ui_action: "api_route_connect",
    action_role: "api_route_admission",
    post_action_refresh_required: true,
    result: {
      status: "ok",
      machine_error_code: "OK",
      human_message: "API connected",
      next_action: "none",
      changed_files: [],
      data: {
        route_id: "wbp-web-primary-openrouter",
        api_route_connect_phase: "created_and_validated",
        credential_phase: "credential_admitted",
        credential_present: true,
        credential_admitted: true,
        credential_ref: "OPENROUTER_API_KEY",
        browser_secret_intake: false
      }
    }
  });
  if (overlayCalls !== 0) {
    throw new Error(`api route connect should not render onboard login overlay: ${overlayCalls}`);
  }
  if (windowCalls !== 0) {
    throw new Error(`api route connect should not mutate onboard login window: ${windowCalls}`);
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_onboarding_refresh_uses_accounts_snapshot_from_quick_start_composite_payload(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const payload = {
  ui_action: "onboard_account",
  result: {
    onboarding: {
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-new"
    }
  }
};
const refreshed = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-new", pool: "reserve" }]
  },
  apiConnections: {
    status: "ok",
    routes: []
  }
};
if (sandbox.actionRefreshSucceeded(payload, refreshed) !== true) {
  throw new Error("composite quick-start refresh must be treated as successful for onboarding");
}
if (sandbox.canonicalActionRefreshState(payload, refreshed) !== "complete") {
  throw new Error(`expected onboarding refresh complete, got ${sandbox.canonicalActionRefreshState(payload, refreshed)}`);
}
const mismatch = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-new", pool: "active" }]
  },
  apiConnections: {
    status: "ok",
    routes: []
  }
};
if (sandbox.canonicalActionRefreshState(payload, mismatch) !== "mismatch") {
  throw new Error("active pool after live onboarding must yield refresh mismatch");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_account_lifecycle_refresh_requires_accounts_and_runtime_truth(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const promotePayload = {
  ui_action: "promote_account",
  account_id: "acct-reserve",
  result: { status: "ok" }
};
const promoted = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-reserve", pool: "active", manual_hold: false }]
  },
  runtime: {
    status: "ok",
    source: "live_readonly"
  }
};
if (sandbox.actionRefreshSucceeded(promotePayload, promoted) !== true) {
  throw new Error("account lifecycle refresh should require both accounts and runtime ok");
}
if (sandbox.canonicalActionRefreshState(promotePayload, promoted) !== "complete") {
  throw new Error(`expected promote refresh complete, got ${sandbox.canonicalActionRefreshState(promotePayload, promoted)}`);
}
const promoteMismatch = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-reserve", pool: "reserve", manual_hold: false }]
  },
  runtime: {
    status: "ok",
    source: "live_readonly"
  }
};
if (sandbox.canonicalActionRefreshState(promotePayload, promoteMismatch) !== "mismatch") {
  throw new Error("unchanged pool after promote must yield refresh mismatch");
}
const releasePayload = {
  ui_action: "release_account",
  account_id: "acct-hold",
  result: { status: "ok" }
};
const released = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-hold", pool: "reserve", manual_hold: false }]
  },
  runtime: {
    status: "ok",
    source: "live_readonly"
  }
};
if (sandbox.canonicalActionRefreshState(releasePayload, released) !== "complete") {
  throw new Error(`expected release refresh complete, got ${sandbox.canonicalActionRefreshState(releasePayload, released)}`);
}
const failedRuntime = {
  accounts: {
    status: "ok",
    accounts: [{ id: "acct-hold", pool: "reserve", manual_hold: false }]
  },
  runtime: {
    status: "integration_failure",
    source: "live_readonly"
  }
};
if (sandbox.actionRefreshSucceeded(releasePayload, failedRuntime) !== false) {
  throw new Error("account lifecycle refresh must fail without runtime status truth");
}
const recheckPayload = {
  ui_action: "recheck_account",
  account_id: "acct-active",
  result: { status: "ok" }
};
const rechecked = {
  status: "ok",
  accounts: [{ id: "acct-active", pool: "active", manual_hold: false }]
};
if (sandbox.actionRefreshSucceeded(recheckPayload, rechecked) !== true) {
  throw new Error("recheck should rely on accounts readonly refresh only");
}
if (sandbox.canonicalActionRefreshState(recheckPayload, rechecked) !== "complete") {
  throw new Error(`expected recheck refresh complete, got ${sandbox.canonicalActionRefreshState(recheckPayload, rechecked)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_api_route_refresh_uses_api_snapshot_from_quick_start_composite_payload(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const payload = {
  ui_action: "api_route_check",
  route_id: "wbp-deepseek-v3",
  result: { status: "ok" }
};
const refreshed = {
  accounts: {
    status: "ok",
    accounts: []
  },
  apiConnections: {
    status: "ok",
    routes: [{ route_id: "wbp-deepseek-v3", enabled: true }]
  }
};
if (sandbox.actionRefreshSucceeded(payload, refreshed) !== true) {
  throw new Error("composite quick-start refresh must be treated as successful for api route check");
}
if (sandbox.canonicalActionRefreshState(payload, refreshed) !== "complete") {
  throw new Error(`expected api route refresh complete, got ${sandbox.canonicalActionRefreshState(payload, refreshed)}`);
}
const mismatch = {
  accounts: {
    status: "ok",
    accounts: []
  },
  apiConnections: {
    status: "ok",
    routes: []
  }
};
if (sandbox.canonicalActionRefreshState(payload, mismatch) !== "mismatch") {
  throw new Error("missing route after api route check must yield refresh mismatch");
}
const failedConnectPayload = {
  ui_action: "api_route_connect",
  result: {
    status: "command_error",
    machine_error_code: "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING"
  }
};
if (sandbox.canonicalActionRefreshState(failedConnectPayload, mismatch) !== "complete") {
  throw new Error("failed api route connect must not create a false refresh mismatch");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_all_refresh_uses_quick_start_composite_snapshots_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    getElementById() { return { textContent: "", lastElementChild: { textContent: "" }, classList: { toggle() {} } }; },
    createElement() { return {}; },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const payload = {
  ui_action: "quick_start_check_all",
  post_action_refresh_required: true,
  result: {
    status: "partial_success",
    data: {
      bundle_verdict: "partial"
    }
  }
};
const refreshed = {
  accounts: {
    status: "ok",
    accounts: []
  },
  apiConnections: {
    status: "ok",
    routes: [{ route_id: "wbp-deepseek-v3", enabled: true }]
  }
};
if (sandbox.actionRefreshSucceeded(payload, refreshed) !== true) {
  throw new Error("check all refresh must require only quick-start accounts/api composite truth");
}
if (sandbox.canonicalActionRefreshState(payload, refreshed) !== "complete") {
  throw new Error(`expected check-all refresh complete, got ${sandbox.canonicalActionRefreshState(payload, refreshed)}`);
}
const failedRefresh = {
  accounts: {
    status: "integration_failure",
    accounts: []
  },
  apiConnections: {
    status: "ok",
    routes: [{ route_id: "wbp-deepseek-v3", enabled: true }]
  }
};
if (sandbox.actionRefreshSucceeded(payload, failedRefresh) !== false) {
  throw new Error("failed accounts refresh must block check-all refresh proof");
}
if (sandbox.canonicalActionRefreshState(payload, failedRefresh) !== "failed") {
  throw new Error("failed composite refresh must render failed for check-all");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_action_ledger_rendering_executes_status_mapping(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");
const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend"
];
const elements = Object.fromEntries(ids.map((id) => [id, {
  className: "",
  textContent: "",
  lastElementChild: { textContent: "" }
}]));
const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = { className: "", textContent: "", lastElementChild: { textContent: "" } };
      }
      return elements[id];
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "overview", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

function render(payload, refreshState) {
  sandbox.setActionPanel(payload, refreshState);
  return {
    panel: elements.actionPanel.className,
    status: elements.actionStatus.textContent,
    display: elements.actionDisplayState.textContent,
    truth: elements.actionTruthNote.textContent,
    support: elements.actionSupportDetails.textContent
  };
}

const commandError = render({
  status: "command_error",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "COMMAND_FAILED",
    human_message: "nested ok must not win",
    next_action: "retry",
    changed_files: []
  }
});
const invalidJson = render({
  ui_action: "refresh_health_detail",
  action_role: "read_only_detail",
  post_action_refresh_required: false,
  result: {
    status: "invalid_json",
    machine_error_code: "UI_ACTION_INVALID_JSON",
    human_message: "invalid json",
    next_action: "retry",
    changed_files: []
  }
});
const staleRefresh = render({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "ok",
    next_action: "none",
    changed_files: []
  }
}, "failed");
const profileSupport = render({
  status: "ok",
  ui_action: "api_route_profile",
  action_role: "api_route_profile_packet",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "profile packet",
    next_action: "none",
    changed_files: [],
    data: {
      writes_external_config: false,
      profile_ready: false,
      listener_proven: false,
      runtime_claim_blocked: true
    }
  }
});
const evidenceSupport = render({
  status: "ok",
  ui_action: "api_route_evidence_capture",
  action_role: "api_route_local_evidence_capture",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "evidence packet",
    next_action: "none",
    changed_files: ["/tmp/wbp-evidence/wbp-deepseek-v3.json"],
    data: {
      evidence_path: "/tmp/wbp-evidence/wbp-deepseek-v3.json"
    }
  }
});
const diagnosticsSupport = render({
  status: "ok",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "diagnostics exported",
    next_action: "none",
    changed_files: ["/private/tmp/wbp-diagnostics-secret"],
    data: {
      bundle_path: "/private/tmp/wbp-diagnostics-secret"
    }
  }
});

if (commandError.panel !== "action-panel compact-action-panel red" || commandError.status !== "command_error") {
  throw new Error(`command_error not red: ${JSON.stringify(commandError)}`);
}
if (invalidJson.panel !== "action-panel compact-action-panel red" || invalidJson.display !== "invalid_json") {
  throw new Error(`invalid_json not red: ${JSON.stringify(invalidJson)}`);
}
if (staleRefresh.panel !== "action-panel compact-action-panel amber" || staleRefresh.display !== "ok_refresh_failed") {
  throw new Error(`failed refresh not refresh-failed amber: ${JSON.stringify(staleRefresh)}`);
}
if (!profileSupport.support.includes("writes_external_config=false") || !profileSupport.support.includes("runtime_claim_blocked=true")) {
  throw new Error(`profile support packet details missing: ${JSON.stringify(profileSupport)}`);
}
if (!evidenceSupport.support.includes("wbp-deepseek-v3.json") || evidenceSupport.support.includes("/tmp/wbp-evidence/")) {
  throw new Error(`evidence support should show only artifact basename metadata: ${JSON.stringify(evidenceSupport)}`);
}
if (diagnosticsSupport.panel !== "action-panel compact-action-panel amber" || diagnosticsSupport.display !== "redaction_unreported") {
  throw new Error(`diagnostics support artifact without redaction proof should be amber, not runtime green: ${JSON.stringify(diagnosticsSupport)}`);
}
if (!diagnosticsSupport.support.includes("wbp-diagnostics-secret") || diagnosticsSupport.support.includes("/private/tmp/")) {
  throw new Error(`diagnostics support should show only artifact basename metadata: ${JSON.stringify(diagnosticsSupport)}`);
}
        if (!commandError.truth.includes("не должен показывать это как успех")) {
  throw new Error(`missing command_error truth note: ${commandError.truth}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_action_ledger_blocks_duplicate_dispatch_in_ui_session(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.dataset = {};
    this.classList = {
      contains: () => false,
      toggle: () => {},
      add: () => {},
      remove: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionDisplayChip",
  "actionSummaryTitle",
  "actionSummaryMeta",
  "actionSummaryMessage",
  "actionSummaryTarget",
  "actionSummaryRefresh",
  "actionLedgerList"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
let fetchCount = 0;
let resolveFetch;
const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() {
    fetchCount += 1;
    return new Promise((resolve) => {
      resolveFetch = () => resolve({
        ok: true,
        json: async () => ({
          status: "ok",
          ui_action: "validate_account",
          account_id: "acc-021",
          action_role: "account_lifecycle",
          post_action_refresh_required: false,
          result: {
            status: "ok",
            machine_error_code: "OK",
            human_message: "validated",
            next_action: "none",
            changed_files: []
          }
        })
      });
    });
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext("renderSettingsSnapshot = () => {};", sandbox);

(async () => {
  const first = sandbox.runUiAction("validate_account", { account_id: "acc-021" });
  const second = sandbox.runUiAction("validate_account", { account_id: "acc-021" });
  if (fetchCount !== 1) {
    throw new Error(`duplicate dispatch should not call fetch twice: ${fetchCount}`);
  }
  if (elements.actionDisplayState.textContent !== "duplicate_blocked") {
    throw new Error(`duplicate should render duplicate_blocked: ${elements.actionDisplayState.textContent}`);
  }
  if (!JSON.stringify(elements.actionLedgerList).includes("UI_DUPLICATE_SUBMIT_BLOCKED")) {
    throw new Error(`duplicate ledger entry missing: ${JSON.stringify(elements.actionLedgerList)}`);
  }
  resolveFetch();
  await Promise.all([first, second]);
  if (fetchCount !== 1) {
    throw new Error(`duplicate dispatch leaked after resolve: ${fetchCount}`);
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_confirmation_cancel_aborts_inflight_onboard_wait_and_recovers_modal(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.dataset = {};
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.classList = {
      add: () => {},
      remove: () => {},
      toggle: () => {},
      contains: () => false
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  appendChild(item) {
    this.append(item);
    return item;
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  focus() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionDisplayChip",
  "actionSummaryTitle",
  "actionSummaryMeta",
  "actionSummaryMessage",
  "actionSummaryTarget",
  "actionSummaryRefresh",
  "actionLedgerList",
  "confirmOverlay",
  "confirmAction",
  "cancelAction",
  "confirmDispatchState"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.confirmOverlay.hidden = false;
elements.confirmAction.dataset.readyLabel = "Подключить в резерв";

let fetchCount = 0;
let aborted = false;
const sandbox = {
  console,
  Node,
  AbortController,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "quick-start", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=quick-start" },
    history: { replaceState() {} },
    open() { return null; }
  },
  URL,
  URLSearchParams,
  fetch(_url, options = {}) {
    fetchCount += 1;
    return new Promise((_resolve, reject) => {
      if (options.signal) {
        options.signal.addEventListener("abort", () => {
          aborted = true;
          const error = new Error("The operation was aborted.");
          error.name = "AbortError";
          reject(error);
        }, { once: true });
      }
    });
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext("renderSettingsSnapshot = () => {};", sandbox);
vm.runInContext('pendingConfirmedAction = { uiAction: "onboard_account", extraPayload: {} };', sandbox);

(async () => {
  const runPromise = sandbox.confirmPendingAction();
  if (fetchCount !== 1) {
    throw new Error(`confirm dispatch should start exactly one fetch, got ${fetchCount}`);
  }
  if (elements.cancelAction.textContent !== "Отменить ожидание") {
    throw new Error(`cancel button must switch to wait-cancel label: ${elements.cancelAction.textContent}`);
  }
  if (elements.cancelAction.disabled) {
    throw new Error("cancel button must stay enabled while waiting for owner/server packet");
  }
  sandbox.closeConfirmation();
  await runPromise;
  if (!aborted) {
    throw new Error("cancel confirmation must abort in-flight wait");
  }
  if (elements.confirmOverlay.hidden !== true) {
    throw new Error("confirmation overlay must close after cancelling wait");
  }
  if (elements.actionMachineCode.textContent !== "UI_ACTION_WAIT_CANCELLED") {
    throw new Error(`cancelled wait machine code missing: ${elements.actionMachineCode.textContent}`);
  }
  if (elements.actionDisplayState.textContent !== "cancelled") {
    throw new Error(`cancelled wait display state missing: ${elements.actionDisplayState.textContent}`);
  }
  if (elements.cancelAction.textContent !== "Отмена") {
    throw new Error(`cancel button label must recover after abort: ${elements.cancelAction.textContent}`);
  }
  if (elements.confirmAction.textContent !== "Подключить в резерв") {
    throw new Error(`confirm button label must recover after abort: ${elements.confirmAction.textContent}`);
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_overview_live_readonly_sets_pending_live_state_before_fetch_resolves(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.dataset = {};
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.classList = {
      add: () => {},
      remove: () => {},
      toggle: () => {},
      contains: () => false
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  querySelector() {
    return new Node();
  }
  querySelectorAll() {
    return [];
  }
  setAttribute(name, value) {
    this[name] = value;
  }
  removeAttribute(name) {
    delete this[name];
  }
}

const ids = [
  "refreshFixture",
  "sourcePicker",
  "statePicker",
  "brandCaption",
  "sourceFooter",
  "subtitleText",
  "sourcePill",
  "runtimeChip",
  "desiredMode",
  "effectiveMode",
  "endpoint",
  "lastError",
  "activeCount",
  "reserveCount",
  "holdCount",
  "problemCount",
  "activeNote",
  "reserveNote",
  "holdNote",
  "problemNote",
  "fixtureBanner",
  "sidebarDot",
  "sidebarStatus"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.refreshFixture.lastElementChild = { textContent: "" };
elements.runtimeChip.lastElementChild = { textContent: "" };
elements.sourcePill.lastElementChild = { textContent: "" };
elements.sourcePicker.value = "fixture";
elements.statePicker.value = "healthy";
const desktop = new Node("div");
desktop.dataset = { screen: "overview", source: "fixture", fixtureState: "healthy", settingsSection: "hub" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "?screen=overview&source=live", href: "http://127.0.0.1/?screen=overview&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url !== "api/live-readonly" && url !== "api/actions") {
      throw new Error(`unexpected fetch ${url}`);
    }
    return new Promise(() => {});
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
(async () => {
  sandbox.setLiveReadonly(false);
  await Promise.resolve();

  if (desktop.dataset.source !== "live") {
    throw new Error(`desktop source must switch to live immediately: ${desktop.dataset.source}`);
  }
  if (elements.sourcePicker.value !== "live") {
    throw new Error(`source picker must switch to live immediately: ${elements.sourcePicker.value}`);
  }
  if (elements.statePicker.disabled !== true) {
    throw new Error("state picker must be disabled while live readonly is pending");
  }
  if (elements.brandCaption.textContent !== "") {
    throw new Error(`overview live brand caption must stay empty: ${elements.brandCaption.textContent}`);
  }
  if (elements.runtimeChip.lastElementChild.textContent !== "Загрузка") {
    throw new Error(`runtime chip must show loading while fetch pending: ${elements.runtimeChip.lastElementChild.textContent}`);
  }
  if (elements.activeCount.textContent !== "—" || elements.problemCount.textContent !== "—") {
    throw new Error(`overview counters must not keep fixture values while live fetch pending: active=${elements.activeCount.textContent}, problem=${elements.problemCount.textContent}`);
  }
  if (!elements.fixtureBanner.textContent.includes("Загрузка live-readonly")) {
    throw new Error(`overview banner must show live pending copy: ${elements.fixtureBanner.textContent}`);
  }
  if (elements.sidebarStatus.textContent !== "Загрузка live-readonly…") {
    throw new Error(`sidebar status must show live pending copy: ${elements.sidebarStatus.textContent}`);
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_set_live_readonly_retries_action_metadata_after_initial_failure(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.dataset = {};
    this.children = [];
    this.attributes = {};
    this.style = {};
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (token) => this.className.split(/\s+/).filter(Boolean).includes(token),
      add: () => {},
      remove: () => {},
      toggle: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  querySelector() {
    return new Node();
  }
  querySelectorAll() {
    return [];
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
}

const ids = [
  "refreshFixture",
  "sourcePicker",
  "statePicker",
  "brandCaption",
  "sourceFooter",
  "subtitleText",
  "sourcePill",
  "runtimeChip",
  "desiredMode",
  "effectiveMode",
  "endpoint",
  "lastError",
  "activeCount",
  "reserveCount",
  "holdCount",
  "problemCount",
  "activeNote",
  "reserveNote",
  "holdNote",
  "problemNote",
  "fixtureBanner",
  "sidebarDot",
  "sidebarStatus"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.refreshFixture.lastElementChild = { textContent: "" };
elements.runtimeChip.lastElementChild = { textContent: "" };
elements.sourcePill.lastElementChild = { textContent: "" };
elements.sourcePicker.value = "live";
elements.statePicker.value = "healthy";
const desktop = new Node("div");
desktop.dataset = { screen: "overview", source: "fixture", fixtureState: "healthy", settingsSection: "hub" };

const onboardButton = new Node("button");
onboardButton.className = "button primary onboard-action";
onboardButton.dataset = { uiAction: "onboard_account_dry_run" };

let actionsFetchCount = 0;
const liveSnapshot = {
  schema_version: 1,
  state_id: "healthy",
  status: "ok",
  ui_state: "healthy",
  source: "live_readonly",
  fixture_notice: "live readonly ok",
  runtime: {
    visual_state: "healthy",
    status_label: "Готово",
    desired_mode: "managed",
    effective_mode: "managed",
    endpoint: "http://127.0.0.1:8765",
    machine_error_code: "",
    human_message: "ok",
    last_error: "",
    observed_at_utc: "2026-05-16T00:00:00Z"
  },
  pool_summary: {
    active: 1,
    reserve: 0,
    hold: 0,
    problem: 0,
    active_note: "ok",
    reserve_note: "ok",
    hold_note: "ok",
    problem_note: "ok"
  },
  events: []
};

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action") {
        return [onboardButton];
      }
      return [];
    }
  },
  window: {
    location: { search: "?screen=overview&source=live", href: "http://127.0.0.1/?screen=overview&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/actions") {
      actionsFetchCount += 1;
      if (actionsFetchCount === 1) {
        return Promise.resolve({ ok: false, status: 503, text: async () => "" });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          actions: {
            onboard_account_dry_run: {
              ui_action: "onboard_account_dry_run",
              display_name: "Проверить подключение аккаунта",
              human_meaning: "dry-run onboarding preview",
              action_role: "account_onboarding_preview",
              mutates_runtime: false,
              affects_primary_truth: false,
              confirmation_required: false,
              post_action_refresh_required: false,
              action_claim_scope: "preview_only",
              available: true,
              availability_state: "displayable_readonly",
              disabled_reason_code: "",
              disabled_reasons: [],
              unavailable_reason: ""
            }
          }
        })
      });
    }
    if (url === "api/live-readonly") {
      return Promise.resolve({
        ok: true,
        json: async () => liveSnapshot
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  desktop.dataset.source = "live";
  await sandbox.loadActionMetadata();
  sandbox.applyActionAvailability();
  if (onboardButton.disabled !== true || onboardButton.dataset.disabledReasonCode !== "UI_ACTION_METADATA_UNAVAILABLE") {
    throw new Error(`initial metadata failure must disable onboard button, got disabled=${onboardButton.disabled} reason=${onboardButton.dataset.disabledReasonCode}`);
  }

  await sandbox.setLiveReadonly(false);

  if (actionsFetchCount !== 2) {
    throw new Error(`setLiveReadonly must retry action metadata, got ${actionsFetchCount} fetches`);
  }
  if (desktop.dataset.source !== "live") {
    throw new Error(`desktop source must stay live after refresh, got ${desktop.dataset.source}`);
  }
  if (onboardButton.disabled !== false) {
    throw new Error("onboard button must recover after metadata refresh succeeds");
  }
  if (onboardButton.dataset.available !== "true") {
    throw new Error(`onboard button availability must recover, got ${onboardButton.dataset.available}`);
  }
  if (onboardButton.dataset.disabledReasonCode !== "") {
    throw new Error(`disabled reason must clear after recovery, got ${onboardButton.dataset.disabledReasonCode}`);
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_live_source_pill_switches_to_sandbox_when_action_phase_is_admitted(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.dataset = {};
    this.children = [];
    this.attributes = {};
    this.style = {};
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (token) => this.className.split(/\s+/).filter(Boolean).includes(token),
      add: () => {},
      remove: () => {},
      toggle: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  querySelector() {
    return new Node();
  }
  querySelectorAll() {
    return [];
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
}

const ids = [
  "refreshFixture",
  "sourcePicker",
  "statePicker",
  "brandCaption",
  "sourceFooter",
  "subtitleText",
  "sourcePill",
  "runtimeChip",
  "desiredMode",
  "effectiveMode",
  "endpoint",
  "lastError",
  "activeCount",
  "reserveCount",
  "holdCount",
  "problemCount",
  "activeNote",
  "reserveNote",
  "holdNote",
  "problemNote",
  "fixtureBanner",
  "sidebarDot",
  "sidebarStatus"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.refreshFixture.lastElementChild = { textContent: "" };
elements.runtimeChip.lastElementChild = { textContent: "" };
elements.sourcePill.lastElementChild = { textContent: "" };
elements.sourcePicker.value = "live";
elements.statePicker.value = "healthy";
const desktop = new Node("div");
desktop.dataset = { screen: "quick-start", source: "fixture", fixtureState: "healthy", settingsSection: "hub" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "?screen=quick-start&source=live", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch(url) {
    if (url === "api/actions") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          action_phase: "sandbox_actions",
          sandbox_preflight: {
            status: "admitted",
            machine_error_code: "OK",
            reason: "sandbox proven",
            separate_profile: true,
            separate_data_dir: true,
            separate_port: true,
            current_session_untouched: true,
            sandbox_target_proven: true
          },
          actions: {}
        })
      });
    }
    if (url === "api/accounts-readonly") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ status: "ok", source: "accounts_readonly", summary: { human_message: "" }, accounts: [], schema_version: 1, primary_truth_ok: true, registry_identity: { status: "ok", machine_error_code: "OK", next_action: "none" }, pool_summary: { total: 0, active: 0, reserve: 0, hold: 0, problem: 0 }, warnings: [] })
      });
    }
    if (url === "api/api-connections-readonly") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ status: "ok", source: "api_connections_readonly", summary: { human_message: "" }, routes: [], schema_version: 1, primary_truth_ok: true, warnings: [] })
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.setLiveReadonly(false);
  if (elements.sourcePill.textContent !== "Sandbox") {
    throw new Error(`source pill must show Sandbox, got ${elements.sourcePill.textContent}`);
  }
  if (!elements.sourceFooter.textContent.includes("sandbox phase")) {
    throw new Error(`source footer must mention sandbox phase, got ${elements.sourceFooter.textContent}`);
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_diagnostics_export_result_renders_safe_artifact_metadata(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "diagnosticsStatusChip",
  "diagnosticsMessage",
  "diagnosticsPacketStatus",
  "diagnosticsExitCode",
  "diagnosticsMachineCode",
  "diagnosticsNextAction",
  "diagnosticsChangedFiles",
  "diagnosticsBundleRef",
  "diagnosticsBanner"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.diagnosticsStatusChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setActionPanel({
  status: "ok",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  mutates_runtime: false,
  affects_primary_truth: false,
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Diagnostics exported.",
    exit_code: 0,
    next_action: "none",
    changed_files: ["/private/tmp/wild-boar-proxy-diagnostics-secret"],
    data: {
      bundle_path: "/private/tmp/wild-boar-proxy-diagnostics-secret"
    }
  }
});

const domText = JSON.stringify(elements);
if (elements.diagnosticsStatusChip.className !== "chip amber") {
  throw new Error(`diagnostics status chip must be amber when redaction is unreported: ${elements.diagnosticsStatusChip.className}`);
}
if (elements.diagnosticsBanner.className !== "fixture-banner amber") {
  throw new Error(`diagnostics banner must be amber when redaction is unreported: ${elements.diagnosticsBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel amber") {
  throw new Error(`action panel must be amber when redaction is unreported: ${elements.actionPanel.className}`);
}
if (elements.diagnosticsChangedFiles.textContent !== "1") {
  throw new Error(`changed_files should render count only: ${elements.diagnosticsChangedFiles.textContent}`);
}
if (!elements.diagnosticsBundleRef.textContent.includes("wild-boar-proxy-diagnostics-secret")) {
  throw new Error(`artifact basename missing: ${elements.diagnosticsBundleRef.textContent}`);
}
if (elements.diagnosticsBundleRef.textContent.includes("/private/tmp/") || domText.includes("/private/tmp/")) {
  throw new Error(`diagnostics DOM leaked full local path: ${domText}`);
}
if (!elements.diagnosticsBanner.textContent.includes("runtime health truth")) {
  throw new Error(`diagnostics banner broadened truth claim: ${elements.diagnosticsBanner.textContent}`);
}
if (!elements.diagnosticsBanner.textContent.includes("redaction не подтверждена")) {
  throw new Error(`diagnostics banner should not invent redaction proof: ${elements.diagnosticsBanner.textContent}`);
}
if (!elements.actionSupportDetails.textContent.includes("redaction=unreported")) {
  throw new Error(`support details should show unreported redaction: ${elements.actionSupportDetails.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_diagnostics_export_result_maps_redaction_states_without_runtime_green(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "diagnosticsStatusChip",
  "diagnosticsMessage",
  "diagnosticsPacketStatus",
  "diagnosticsExitCode",
  "diagnosticsMachineCode",
  "diagnosticsNextAction",
  "diagnosticsChangedFiles",
  "diagnosticsBundleRef",
  "diagnosticsBanner"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.diagnosticsStatusChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

function render(redactionStatus) {
  sandbox.setActionPanel({
    status: "ok",
    ui_action: "export_diagnostics",
    action_role: "support_artifact",
    mutates_runtime: false,
    affects_primary_truth: false,
    post_action_refresh_required: false,
    result: {
      status: "ok",
      machine_error_code: "OK",
      human_message: "Diagnostics exported.",
      exit_code: 0,
      next_action: "none",
      changed_files: ["diagnostics_bundle"],
      data: {
        bundle_path: "wbp-diagnostics.zip",
        redaction_status: redactionStatus
      }
    }
  });
}

render("enabled");
if (elements.actionPanel.className !== "action-panel compact-action-panel blue") {
  throw new Error(`enabled redaction should be blue support artifact: ${elements.actionPanel.className}`);
}
if (elements.actionDisplayState.textContent !== "created") {
  throw new Error(`enabled redaction should render created: ${elements.actionDisplayState.textContent}`);
}
if (elements.actionPanel.className.includes("green") || elements.diagnosticsStatusChip.className.includes("green")) {
  throw new Error("support artifact must not render runtime-health green");
}
if (!elements.diagnosticsBanner.textContent.includes("support artifact")) {
  throw new Error(`enabled copy should preserve support-artifact scope: ${elements.diagnosticsBanner.textContent}`);
}

render("failed");
if (elements.actionPanel.className !== "action-panel compact-action-panel red") {
  throw new Error(`failed redaction should be red: ${elements.actionPanel.className}`);
}
if (elements.actionDisplayState.textContent !== "redaction_failed") {
  throw new Error(`failed redaction should render redaction_failed: ${elements.actionDisplayState.textContent}`);
}
if (!elements.diagnosticsBanner.textContent.includes("redaction failure")) {
  throw new Error(`failed copy should name redaction failure: ${elements.diagnosticsBanner.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_action_ledger_recent_entries_are_session_only_and_count_paths(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
    this.dataset = {};
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name)) {
          this.className = `${this.className} ${name}`.trim();
        }
      }
    };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend",
  "actionLedgerList",
  "actionLedgerScope"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.actionLedgerScope.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "overview", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const bounded = sandbox.boundedUiActionPayload("validate_account", {
  account_id: "backend-a",
  route_id: "wbp-route",
  ["command" + "_id"]: "forbidden",
  argv: "forbidden",
  path: "/tmp/forbidden"
});
if (bounded["command" + "_id"] || bounded.argv || bounded.path) {
  throw new Error(`bounded action payload leaked forbidden fields: ${JSON.stringify(bounded)}`);
}
if (bounded.ui_action !== "validate_account" || bounded.account_id !== "backend-a" || bounded.route_id !== "wbp-route") {
  throw new Error(`bounded action payload dropped admitted fields: ${JSON.stringify(bounded)}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "sync packet ok",
    next_action: "none",
    changed_files: ["/tmp/runtime-state-a.json", "/tmp/runtime-state-b.json"]
  }
});
let first = elements.actionLedgerList.children[0];
const firstText = JSON.stringify(first);
if (!first.className.includes("amber") || !firstText.includes("ok_refresh_pending")) {
  throw new Error(`ok command packet requiring refresh should stay amber pending: ${first.className} ${firstText}`);
}
if (!firstText.includes("changed files") || !firstText.includes("2 metadata entries")) {
  throw new Error(`ledger should show changed_files count only: ${firstText}`);
}
if (firstText.includes("/tmp/runtime-state") || firstText.includes("runtime-state-b.json")) {
  throw new Error(`ledger leaked changed_files path identity: ${firstText}`);
}
if (!firstText.includes("command packet outcome only")) {
  throw new Error(`ledger did not keep not-runtime-truth copy: ${firstText}`);
}
if (!firstText.includes("target - · machine OK · refresh canonical refresh pending")) {
  throw new Error(`ledger collapsed meta should be operator-readable, not debug key/value dump: ${firstText}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "sync packet ok",
    next_action: "none",
    changed_files: []
  }
}, "complete");
first = elements.actionLedgerList.children[0];
if (!first.className.includes("green") || !JSON.stringify(first).includes("ok_refresh_complete")) {
  throw new Error(`refresh-complete action should become green: ${JSON.stringify(first)}`);
}

sandbox.setActionPanel({
  status: "command_error",
  ui_action: "set_mode_managed",
  action_role: "",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "COMMAND_FAILED",
    human_message: "nested ok must not win",
    next_action: "retry",
    changed_files: []
  }
});
if (!elements.actionLedgerList.children[0].className.includes("red")) {
  throw new Error("command_error ledger row must not be green");
}
const commandErrorText = JSON.stringify(elements.actionLedgerList.children[0]);
if (commandErrorText.includes("command_id=") || commandErrorText.includes("argv=")) {
  throw new Error(`ledger leaked raw dispatch fields: ${commandErrorText}`);
}

sandbox.setActionPanel({
  status: "command_error",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  post_action_refresh_required: false,
  result: {
    status: "command_error",
    machine_error_code: "COMMAND_FAILED",
    human_message: "failed command_id=diagnostics_export argv=diagnostics secret=VERYSECRET /Users/kirill/private.log",
    next_action: "retry /tmp/private-state.json",
    changed_files: []
  }
});
const sensitiveLedgerText = JSON.stringify(elements.actionLedgerList.children[0]);
const sensitiveCompactText = [
  elements.actionSummaryMessage.textContent,
  elements.actionMessage.textContent,
  elements.actionNextAction.textContent,
  elements.actionSupportDetails.textContent
].join(" ");
if (sensitiveLedgerText.includes("diagnostics_export") || sensitiveLedgerText.includes("argv=diagnostics") || sensitiveLedgerText.includes("VERYSECRET") || sensitiveLedgerText.includes("/Users/") || sensitiveLedgerText.includes("/tmp/private-state")) {
  throw new Error(`ledger leaked sensitive or raw dispatch text: ${sensitiveLedgerText}`);
}
if (sensitiveCompactText.includes("diagnostics_export") || sensitiveCompactText.includes("argv=diagnostics") || sensitiveCompactText.includes("VERYSECRET") || sensitiveCompactText.includes("/Users/") || sensitiveCompactText.includes("/tmp/private-state")) {
  throw new Error(`compact action summary leaked sensitive or raw dispatch text: ${sensitiveCompactText}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "mode packet ok",
    next_action: "none",
    changed_files: []
  }
});
sandbox.setActionPanel({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "mode packet ok",
    next_action: "none",
    changed_files: []
  }
}, "failed");
const staleRow = elements.actionLedgerList.children[0];
if (!staleRow.className.includes("amber") || !JSON.stringify(staleRow).includes("ok_refresh_failed")) {
  throw new Error(`failed refresh should replace ok row with refresh-failed amber: ${JSON.stringify(staleRow)}`);
}
sandbox.setActionPanel({
  status: "ok",
  ui_action: "api_route_remove",
  route_id: "wbp-disabled",
  action_role: "api_route_registry_cleanup",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "route remove packet ok",
    next_action: "refresh_api_connections",
    changed_files: ["/tmp/registry.json"]
  }
}, "mismatch");
const mismatchRow = elements.actionLedgerList.children[0];
const mismatchText = JSON.stringify(mismatchRow);
if (!mismatchRow.className.includes("amber") || !mismatchText.includes("refresh_mismatch")) {
  throw new Error(`route still present after refresh must be mismatch amber: ${mismatchText}`);
}
if (!mismatchText.includes("canonical refresh mismatch") || mismatchText.includes("/tmp/registry.json")) {
  throw new Error(`mismatch row should show bounded refresh label and no path: ${mismatchText}`);
}
if (elements.actionLedgerList.children.length > 5) {
  throw new Error("ledger should stay bounded to five rows");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_snapshot_command_ledger_renders_bounded_readonly_commands(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.dataset = {};
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      toggle: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  setAttribute(name, value) {
    this[name] = value;
  }
}

const ids = [
  "snapshotCommandLedgerList",
  "snapshotCommandLedgerScope",
  "snapshotCommandLedgerSurface",
  "actionLedgerList"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.snapshotCommandLedgerScope.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "overview", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setSnapshotCommandLedgerFromSnapshots("overview live-readonly", {
  status: "integration_failure",
  source: "live_readonly",
  has_warnings: true,
  commands: {
    status: {
      status: "ok",
      ui_state: "healthy",
      role: "primary",
      machine_error_code: "OK",
      exit_code: 0,
      next_action: "none",
      human_message: "do not render secret=VERYSECRET /Users/kirill/private.log",
      argv: ["status", "--json"],
      packet: { raw_json: "forbidden" }
    },
    rollout_rotation_inspect: {
      status: "command_error",
      ui_state: "degraded",
      role: "detail",
      machine_error_code: "LOCK_HELD",
      exit_code: 1,
      next_action: "retry /tmp/runtime-state.json command_id=sync"
    }
  }
});

const ledgerText = JSON.stringify(elements.snapshotCommandLedgerList);
const sessionText = JSON.stringify(elements.actionLedgerList);
if (!ledgerText.includes("status · primary") || !ledgerText.includes("rollout_rotation_inspect · detail")) {
  throw new Error(`snapshot command summaries missing: ${ledgerText}`);
}
if (!ledgerText.includes("command packet outcome only · not runtime health proof")) {
  throw new Error(`snapshot command ledger broadened truth scope: ${ledgerText}`);
}
if (ledgerText.includes("human_message") || ledgerText.includes("VERYSECRET") || ledgerText.includes("/Users/") || ledgerText.includes("/tmp/runtime-state") || ledgerText.includes("argv") || ledgerText.includes("raw_json") || ledgerText.includes("forbidden")) {
  throw new Error(`snapshot command ledger leaked raw/private fields: ${ledgerText}`);
}
if (ledgerText.includes("command_id=sync")) {
  throw new Error(`snapshot command ledger leaked browser command_id field: ${ledgerText}`);
}
if (ledgerText.includes("chip green") || ledgerText.includes("action-ledger-row green")) {
  throw new Error(`snapshot command ledger must not turn command ok into runtime green: ${ledgerText}`);
}
if (!ledgerText.includes("[redacted-path]") || !ledgerText.includes("command_id=[redacted]")) {
  throw new Error(`snapshot command ledger did not redact bounded next_action fields: ${ledgerText}`);
}
if (!elements.snapshotCommandLedgerSurface.textContent.includes("overview live-readonly")) {
  throw new Error(`snapshot surface label missing: ${elements.snapshotCommandLedgerSurface.textContent}`);
}
if (!elements.snapshotCommandLedgerScope.className.includes("red")) {
  throw new Error(`integration failure snapshot must mark scope red: ${elements.snapshotCommandLedgerScope.className}`);
}
if (sessionText.includes("status · primary") || sessionText.includes("rollout_rotation_inspect")) {
  throw new Error(`snapshot command ledger polluted session action ledger: ${sessionText}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_ui_readonly_lane_exit_summary_stays_display_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.dataset = {};
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      toggle: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  setAttribute(name, value) {
    this[name] = value;
  }
}

const ids = [
  "uiLaneExitChip",
  "uiLaneExitSource",
  "uiLaneExitTruthNote",
  "uiLaneExitCurrentSource",
  "uiLaneExitSnapshotState",
  "uiLaneExitLiveChain",
  "uiLaneExitMetadataStatus",
  "uiLaneExitSafeSummary",
  "uiLaneExitNextContour",
  "uiLaneExitBlockedList",
  "uiLaneExitSafeList",
  "uiLaneExitForbiddenList",
  "snapshotCommandLedgerList",
  "snapshotCommandLedgerScope",
  "snapshotCommandLedgerSurface"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.uiLaneExitChip.lastElementChild = { textContent: "" };
elements.snapshotCommandLedgerScope.lastElementChild = { textContent: "" };
const desktop = new Node("div");
desktop.dataset = { screen: "overview", source: "live" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
actionMetadata = {
  sync_runtime: {
    available: false,
    availability_state: "disabled_live_action",
    disabled_reason_code: "RUNTIME_LIVE_ACTION_CHAIN_PARKED"
  },
  launch_smoke: {
    available: false,
    availability_state: "disabled_live_action",
    disabled_reason_code: "RUNTIME_LIVE_ACTION_CHAIN_PARKED"
  },
  refresh_health_detail: {
    available: false,
    availability_state: "disabled_live_action",
    disabled_reason_code: "RUNTIME_LIVE_ACTION_CHAIN_PARKED"
  }
};
`, sandbox);

sandbox.setSnapshotCommandLedgerFromSnapshots("overview snapshot", {
  status: "ok",
  source: "live_readonly",
  has_warnings: true,
  commands: {
    status: {
      status: "ok",
      ui_state: "healthy",
      role: "primary",
      machine_error_code: "OK",
      exit_code: 0,
      next_action: "none"
    }
  }
});
sandbox.renderUiReadonlyLaneExitSummary();

const blockedText = JSON.stringify(elements.uiLaneExitBlockedList);
const safeText = JSON.stringify(elements.uiLaneExitSafeList);
const forbiddenText = JSON.stringify(elements.uiLaneExitForbiddenList);
if (elements.uiLaneExitChip.className.includes("green")) {
  throw new Error(`exit summary must not be green: ${elements.uiLaneExitChip.className}`);
}
if (!elements.uiLaneExitTruthNote.textContent.includes("runtime diagnosis")) {
  throw new Error(`exit summary must hand off to runtime diagnosis: ${elements.uiLaneExitTruthNote.textContent}`);
}
if (elements.uiLaneExitCurrentSource.textContent !== "live-readonly") {
  throw new Error(`unexpected current source: ${elements.uiLaneExitCurrentSource.textContent}`);
}
if (!elements.uiLaneExitSnapshotState.textContent.includes("1 bounded summaries")) {
  throw new Error(`unexpected snapshot state: ${elements.uiLaneExitSnapshotState.textContent}`);
}
if (!elements.uiLaneExitMetadataStatus.textContent.includes("3 live actions blocked")) {
  throw new Error(`unexpected metadata status: ${elements.uiLaneExitMetadataStatus.textContent}`);
}
if (elements.uiLaneExitNextContour.textContent !== "STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION") {
  throw new Error(`unexpected next contour: ${elements.uiLaneExitNextContour.textContent}`);
}
if (!blockedText.includes("LOCK_HELD") || !blockedText.includes("policy_drift_detected")) {
  throw new Error(`blocked list missing canon blockers: ${blockedText}`);
}
if (!safeText.includes("Read-only truth display only.") || !safeText.includes("Snapshot command summary inspection.")) {
  throw new Error(`safe list missing readonly scope: ${safeText}`);
}
if (!forbiddenText.includes("runtime sync dispatch") || !forbiddenText.includes("route mutation")) {
  throw new Error(`forbidden list missing blocked scope: ${forbiddenText}`);
}
if (blockedText.includes("data-ui-action") || forbiddenText.includes("data-ui-action")) {
  throw new Error(`exit summary must stay display-only: blocked=${blockedText} forbidden=${forbiddenText}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_static_confirmation_policy_covers_risky_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        for ui_action in [
            "sync_runtime",
            "set_mode_stable",
            "set_mode_managed",
            "launch_client_dispatch",
            "onboard_account",
            "validate_account",
            "recheck_account",
            "promote_account",
            "demote_account",
            "hold_account",
            "release_account",
            "retire_account",
            "api_route_validate",
            "api_route_check",
            "api_route_allow",
            "api_route_disable",
            "api_route_remove",
            "api_route_profile",
            "api_route_evidence_capture",
        ]:
            self.assertIn(f"{ui_action}:", js)

        self.assertIn("terminal-account-lifecycle", js)
        self.assertIn("api-route-validate", js)
        self.assertIn("api-route-check", js)
        self.assertIn("api-route-allow", js)
        self.assertIn("api-route-disable", js)
        self.assertIn("api-route-registry-cleanup", js)
        self.assertIn("api-route-profile-packet", js)
        self.assertIn("api-route-local-evidence", js)
        self.assertIn("metadata-fallback", js)
        self.assertIn("однократная отправка", js)
        self.assertIn("доказательство ёмкости", js)
        self.assertIn("evidence готовности", js)
        self.assertNotIn('data-ui-action="stable_repair_apply"', html)
        self.assertNotIn("stable_repair_apply:", js)
        self.assertNotIn("setup_discovery:", js)
        self.assertNotIn("select_client:", js)
        self.assertNotIn("legacy_import:", js)
        self.assertNotIn("installer_init:", js)

    def test_static_preview_applies_action_availability_from_metadata(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="launchClientAction"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertIn("disabled", html)
        self.assertIn("applyActionAvailability", js)
        self.assertIn("actionAvailabilityForButton", js)
        self.assertIn("metadata.availability_state", js)
        self.assertIn("metadata.disabled_reason_code", js)
        self.assertIn("metadata.disabled_reasons", js)
        self.assertIn("metadata.unavailable_reason", js)
        self.assertIn("launch_preflight", js)
        self.assertIn("UI_ACTION_UNAVAILABLE", js)
        self.assertIn("unknown_disabled", js)
        self.assertIn("LIVE_SOURCE_REQUIRED", js)
        self.assertIn("ROUTE_STATE_REQUIREMENT_NOT_MET", js)
        self.assertIn(".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action", js)
        self.assertIn(".diagnostics-only", js)
        self.assertIn(".settings-only", js)

    def test_api_route_action_buttons_require_live_source_and_enabled_route(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function makeClassList(classes) {
  return { contains(name) { return classes.includes(name); } };
}

const settingsLaunchAvailability = { textContent: "" };
const desktop = { dataset: { source: "fixture", screen: "api-connections" } };
const enabledButton = {
  dataset: { uiAction: "api_route_validate", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const disabledRouteButton = {
  dataset: { uiAction: "api_route_check", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowDisabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowEnabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const removeDisabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const removeEnabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const profileDisabledRouteButton = {
  dataset: { uiAction: "api_route_profile", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "any" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const evidenceDisabledRouteButton = {
  dataset: { uiAction: "api_route_evidence_capture", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "any" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      if (id === "settingsLaunchAvailability") {
        return settingsLaunchAvailability;
      }
      return { textContent: "", className: "", lastElementChild: { textContent: "" } };
    },
    addEventListener() {},
    querySelectorAll(selector) {
      if (selector === ".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action") {
        return [
          enabledButton,
          disabledRouteButton,
          allowDisabledRouteButton,
          allowEnabledRouteButton,
          removeDisabledRouteButton,
          removeEnabledRouteButton,
          profileDisabledRouteButton,
          evidenceDisabledRouteButton
        ];
      }
      return [];
    },
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return { dataset: { source: "fixture", screen: "overview" } };
    }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
actionMetadata = {
  api_route_validate: { available: true, unavailable_reason: "", ui_action: "api_route_validate" },
  api_route_check: { available: true, unavailable_reason: "", ui_action: "api_route_check" },
  api_route_allow: { available: true, unavailable_reason: "", ui_action: "api_route_allow" },
  api_route_remove: { available: true, unavailable_reason: "", ui_action: "api_route_remove" },
  api_route_profile: { available: true, unavailable_reason: "", ui_action: "api_route_profile" },
  api_route_evidence_capture: { available: true, unavailable_reason: "", ui_action: "api_route_evidence_capture" },
  launch_client_dispatch: {
    available: false,
    unavailable_reason: "preflight не подтверждён",
    ui_action: "launch_client_dispatch",
    launch_preflight: {
      status: "denied",
      reason: "Изолированная копия не admitted.",
      target_kind: "app_bundle",
      separate_profile: false,
      separate_data_dir: false,
      separate_port: false,
      process_confirmation_possible: false,
      current_session_untouched: false
    }
  }
};
`, sandbox);

function assertAvailability(button, expected) {
  for (const [key, value] of Object.entries(expected)) {
    if (button.dataset[key] !== value) {
      throw new Error(`unexpected ${key} for ${button.dataset.uiAction}: ${button.dataset[key]} !== ${value}; ${JSON.stringify(button)}`);
    }
  }
}

desktop.dataset.source = "fixture";
sandbox.applyActionAvailability();
if (!enabledButton.disabled || !enabledButton.title.includes("Переключите экран на live-источник")) {
  throw new Error(`enabled route in fixture source should be blocked: ${JSON.stringify(enabledButton)}`);
}
assertAvailability(enabledButton, {
  available: "false",
  availabilityState: "not_admitted",
  disabledReasonCode: "LIVE_SOURCE_REQUIRED",
  disabledReasons: JSON.stringify(["live_source_required"])
});

desktop.dataset.source = "live";
sandbox.applyActionAvailability();
if (enabledButton.disabled) {
  throw new Error(`enabled route in live source should be available: ${JSON.stringify(enabledButton)}`);
}
assertAvailability(enabledButton, {
  available: "true",
  availabilityState: "displayable_readonly",
  disabledReasonCode: "",
  disabledReasons: ""
});
if (!disabledRouteButton.disabled || !disabledRouteButton.title.includes("Маршрут отключён")) {
  throw new Error(`disabled route should stay blocked: ${JSON.stringify(disabledRouteButton)}`);
}
assertAvailability(disabledRouteButton, {
  available: "false",
  availabilityState: "not_admitted",
  disabledReasonCode: "ROUTE_STATE_REQUIREMENT_NOT_MET",
  disabledReasons: JSON.stringify(["route_state_requirement_not_met"])
});
if (allowDisabledRouteButton.disabled) {
  throw new Error(`allow should be available for proven disabled route in live source: ${JSON.stringify(allowDisabledRouteButton)}`);
}
assertAvailability(allowDisabledRouteButton, {
  available: "true",
  availabilityState: "displayable_readonly",
  disabledReasonCode: "",
  disabledReasons: ""
});
if (!allowEnabledRouteButton.disabled) {
  throw new Error(`allow should be blocked for enabled route: ${JSON.stringify(allowEnabledRouteButton)}`);
}
assertAvailability(allowEnabledRouteButton, {
  available: "false",
  availabilityState: "not_admitted",
  disabledReasonCode: "ROUTE_STATE_REQUIREMENT_NOT_MET",
  disabledReasons: JSON.stringify(["route_state_requirement_not_met"])
});
if (removeDisabledRouteButton.disabled) {
  throw new Error(`remove should be available only for proven disabled route in live source: ${JSON.stringify(removeDisabledRouteButton)}`);
}
assertAvailability(removeDisabledRouteButton, {
  available: "true",
  availabilityState: "displayable_readonly",
  disabledReasonCode: "",
  disabledReasons: ""
});
if (!removeEnabledRouteButton.disabled || !removeEnabledRouteButton.title.includes("Маршрут уже разрешён")) {
  throw new Error(`remove should be blocked for enabled route: ${JSON.stringify(removeEnabledRouteButton)}`);
}
assertAvailability(removeEnabledRouteButton, {
  available: "false",
  availabilityState: "not_admitted",
  disabledReasonCode: "ROUTE_STATE_REQUIREMENT_NOT_MET",
  disabledReasons: JSON.stringify(["route_state_requirement_not_met"])
});
if (profileDisabledRouteButton.disabled) {
  throw new Error(`profile packet should be available for proven route in live source: ${JSON.stringify(profileDisabledRouteButton)}`);
}
assertAvailability(profileDisabledRouteButton, {
  available: "true",
  availabilityState: "displayable_readonly",
  disabledReasonCode: "",
  disabledReasons: ""
});
if (evidenceDisabledRouteButton.disabled) {
  throw new Error(`evidence capture should be available for proven route in live source: ${JSON.stringify(evidenceDisabledRouteButton)}`);
}
assertAvailability(evidenceDisabledRouteButton, {
  available: "true",
  availabilityState: "displayable_readonly",
  disabledReasonCode: "",
  disabledReasons: ""
});
if (settingsLaunchAvailability.textContent.indexOf("preflight blocked") === -1) {
  throw new Error(`settings availability was not updated: ${settingsLaunchAvailability.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_boar_logo_is_sharp_and_transparent(self) -> None:
        logo_path = WEB_DESIGN_UI / "assets" / "boar_mark.png"
        image = Image.open(logo_path).convert("RGBA")
        alpha = image.getchannel("A")
        transparent_pixels = sum(1 for value in alpha.getdata() if value == 0)

        self.assertGreaterEqual(image.width, 800)
        self.assertGreaterEqual(image.height, 800)
        self.assertGreater(transparent_pixels, 0)

    def _section_html(self, html: str, section_id: str) -> str:
        needle = f'<section id="{section_id}"'
        start = html.find(needle)
        self.assertNotEqual(start, -1, f"Missing section {section_id}")
        next_match = re.search(r'\n        <section id="[^"]+" class="screen', html[start + len(needle):])
        if next_match is None:
            next_overlay = html.find('\n      <div id="onboardOverlay"', start + len(needle))
            end = next_overlay if next_overlay != -1 else len(html)
        else:
            end = start + len(needle) + next_match.start()
        return html[start:end]

    def _overlay_html(self, html: str, overlay_id: str, next_overlay_id: str) -> str:
        needle = f'<div id="{overlay_id}"'
        start = html.find(needle)
        self.assertNotEqual(start, -1, f"Missing overlay {overlay_id}")
        next_overlay = html.find(f'<div id="{next_overlay_id}"', start + len(needle))
        end = next_overlay if next_overlay != -1 else len(html)
        return html[start:end]

    def _fetch_with_retry(self, url: str) -> str:
        last_error: Exception | None = None
        for _ in range(20):
            try:
                with NO_PROXY_OPENER.open(url, timeout=1) as response:
                    return response.read().decode("utf-8")
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = exc
                time.sleep(0.05)
        raise AssertionError(f"Could not fetch {url}: {last_error}")


if __name__ == "__main__":
    unittest.main()

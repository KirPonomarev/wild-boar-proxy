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

    def test_c7_minimal_shell_uses_clean_design_without_local_render_paths(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-c7-minimal-shell="agent-alias-display-metadata"', html)
        self.assertIn('--c7-design-source: "iosevka-clean-minimal-shell";', css)
        self.assertIn('"Iosevka Term Local", "Iosevka Term", "SF Mono"', css)
        self.assertNotIn("file://", html + css + js)
        self.assertNotIn("кабан дизайн iosevka clean", html + css + js)

    def test_referenced_phosphor_png_assets_exist_and_tokens_are_declared(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        icon_refs = set(re.findall(r'assets/icons/phosphor/([^"\']+\.png)', html + css))
        self.assertIn("folder.png", icon_refs)
        for icon_ref in icon_refs:
            self.assertTrue((WEB_DESIGN_UI / "assets" / "icons" / "phosphor" / icon_ref).is_file(), icon_ref)
        self.assertNotIn("var(--mono)", css)

    def test_all_post_fetches_attach_web_token_and_csrf_headers(self) -> None:
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        post_blocks = re.findall(
            r"fetch\([^\n]+\{[\s\S]*?method: \"POST\"[\s\S]*?\n\s*\}\)",
            js,
        )

        self.assertGreater(len(post_blocks), 20)
        for block in post_blocks:
            self.assertTrue(
                "webPostHeaders" in block or '"X-WBP-CSRF"' in block,
                block[:240],
            )

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
        self.assertIn('--font-ui: "Iosevka Term Local", "Iosevka Term", "SF Mono"', css)
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
        self.assertIn('if (source === "fixture")', js)
        self.assertIn('return desktop?.dataset?.source === "live" ? "live" : "fixture";', js)
        self.assertLess(
            js.index('if (source === "fixture")'),
            js.index('return desktop?.dataset?.source === "live" ? "live" : "fixture";'),
        )
        self.assertIn('snapshot.source === "live_readonly"', js)
        self.assertIn('safeSnapshot.source === "accounts_readonly"', js)
        self.assertIn('safeSnapshot.state_id || safeSnapshot.ui_state', js)
        self.assertNotIn("command_id", js)
        self.assertNotIn("client_path", js)

    def test_review_bridge_panel_uses_existing_query_and_command_surfaces_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="reviewBridgePanel"', html)
        self.assertIn('id="reviewPacketInput"', html)
        self.assertIn('id="reviewRefreshAction"', html)
        self.assertIn('id="reviewImportAction"', html)
        self.assertIn('id="reviewApplyAction"', html)
        self.assertIn('id="reviewClearAction"', html)
        self.assertIn('id="reviewReceiptPacket"', html)
        self.assertIn('id="reviewCommandResponse"', html)
        self.assertIn("existing review command/query surfaces only", html)
        self.assertIn("bounded JSON payload", html)
        self.assertNotIn('type="file"', html)

        self.assertIn('fetchReviewJson("api/review-surface")', js)
        self.assertIn('fetchReviewJson("api/review-commands")', js)
        self.assertIn('fetch("api/review-command"', js)
        self.assertIn('const commandField = "command" + "_id";', js)
        self.assertIn('JSON.stringify({ [commandField]: commandId, payload })', js)
        self.assertIn("function reviewLiveSourceSelected()", js)
        self.assertIn('if (!reviewLiveSourceSelected()) {', js)
        self.assertIn('reviewRejectNonLiveCommand("import_review_packet")', js)
        self.assertIn('reviewRejectNonLiveCommand("apply_exact_text_change")', js)
        self.assertIn('reviewRejectNonLiveCommand("clear_review_session")', js)
        self.assertIn('postReviewCommand("import_review_packet", { review_packet: reviewPacket })', js)
        self.assertIn('postReviewCommand("apply_exact_text_change", {})', js)
        self.assertIn('postReviewCommand("clear_review_session", {})', js)
        self.assertIn('preflight?.data?.future_apply_admissible === true', js)
        self.assertIn('REVIEW_APPLY_TARGET_RESOLVED_ADMITTED', js)
        self.assertIn('reviewLastCommandPacket ? JSON.stringify(reviewLastCommandPacket, null, 2) : "command packet pending"', js)
        self.assertNotIn("showOpenFilePicker", js)
        self.assertNotIn("FileReader", js)
        self.assertNotIn("readAsText", js)
        self.assertNotIn("input.files", js)

    def test_codex_custom_model_registry_ui_is_dry_run_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomModelsPanel"', html)
        self.assertIn('id="codexCustomModelSelect"', html)
        self.assertIn('id="codexCustomApiModelSelect"', html)
        self.assertIn('id="codexCustomExecutionModeSelect"', html)
        self.assertIn('value="chatgpt_only"', html)
        self.assertIn('value="chatgpt_plus_api"', html)
        self.assertIn('value="api_only"', html)
        self.assertIn('id="codexCustomExecutionModeDryRunAction"', html)
        self.assertIn('id="codexCustomExecutionModeState"', html)
        self.assertIn('id="codexCustomExecutionModeResponse"', html)
        self.assertIn('id="codexCustomDeepSeekLiveFormatAction"', html)
        self.assertIn('id="codexCustomDeepSeekLiveFormatResponse"', html)
        self.assertIn("Живой тест DeepSeek", html)
        self.assertIn("пакет живого теста DeepSeek ожидает запуска", html)
        self.assertNotIn("Live test DeepSeek", html)
        self.assertIn('id="codexCustomModelCatalog"', html)
        self.assertIn('id="codexCustomChatLaneCatalog"', html)
        self.assertIn('id="codexCustomApiLaneCatalog"', html)
        self.assertIn('id="codexCustomSeedLaneCatalog"', html)
        self.assertIn('id="codexCustomApiActionGateAction"', html)
        self.assertIn('class="action-row codex-custom-api-action-row"', html)
        self.assertIn('id="codexCustomApiActionGateResponse"', html)
        self.assertIn('id="codexCustomApiActionProvider"', html)
        self.assertIn('id="codexCustomApiActionRoute"', html)
        self.assertIn('id="codexCustomApiActionCost"', html)
        self.assertIn('id="codexCustomApiActionCredential"', html)
        self.assertIn('id="codexCustomSelectorIntentDryRunAction"', html)
        self.assertIn('id="codexCustomSelectorIntentResponse"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/model-selector\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/api-compat\")", js)
        self.assertIn('fetch("api/codex/custom/api-action-gate"', js)
        self.assertIn('fetch("api/codex/custom/execution-mode-dry-run"', js)
        self.assertIn('fetch("api/codex/custom/api-only-deepseek/live-format"', js)
        self.assertIn('fetch("api/codex/custom/model-selector-dry-run"', js)
        self.assertIn('fetch("api/codex/custom/model-dry-run"', js)
        self.assertIn("body: JSON.stringify({ api_model_id: apiModelId })", js)
        self.assertIn("api_reasoning_option_id: apiReasoningOptionId", js)
        self.assertIn("body: JSON.stringify({ chatgpt_model_id: chatgptModelId, api_model_id: apiModelId })", js)
        self.assertIn("body: JSON.stringify({ model_id: modelId })", js)
        self.assertIn("renderCodexCustomApiActionGate(await response.json())", js)
        self.assertIn("renderCodexCustomExecutionMode(await response.json())", js)
        self.assertIn("renderCodexCustomDeepSeekLiveFormat(await response.json())", js)
        self.assertIn("document.getElementById(\"codexCustomExecutionModeDryRunAction\")?.addEventListener(\"click\", () => runCodexCustomExecutionModeDryRun())", js)
        self.assertIn("document.getElementById(\"codexCustomDeepSeekLiveFormatAction\")?.addEventListener(\"click\", () => runCodexCustomDeepSeekLiveFormat())", js)
        self.assertIn("primary_model_slot: packet?.primary_model_slot || {}", js)
        self.assertIn("coding_agent_model_slot: packet?.coding_agent_model_slot || {}", js)
        self.assertIn("owner_authorization_phrase_present:", js)
        self.assertIn("state_written: packet?.state_written === true", js)
        self.assertIn("evidence_written: packet?.evidence_written === true", js)
        self.assertIn("secret_value_exposed: packet?.secret_value_exposed === true", js)
        self.assertIn("selector_packet_truth_only: packet?.selector_packet_truth_only === true", js)
        self.assertIn("ui_text_counts_as_runtime_truth: packet?.ui_text_counts_as_runtime_truth === true", js)
        self.assertIn("asar_touched: packet?.asar_touched === true", js)
        self.assertIn("wbp_patch_applier_used: packet?.wbp_patch_applier_used === true", js)
        self.assertIn("execution_proven: choice?.execution_proven === true", js)
        self.assertIn("provider_response_observed: choice?.provider_response_observed === true", js)
        self.assertIn("route_snapshot_counted_as_provider_response", js)
        self.assertIn("browser_raw_backend_authority_widened", js)
        self.assertIn("live_call_attempted: boundary?.live_call_attempted === true", js)
        self.assertIn("paid_route_used: boundary?.paid_route_used === true", js)
        self.assertIn("original_codex_touched: boundary?.original_codex_touched === true", js)
        self.assertIn("registry?.chatgpt_lane?.default_model_id", js)
        self.assertIn("registry?.api_lane?.default_model_id", js)
        self.assertIn("quickStartLaunchPayloadFromSelects", js)
        self.assertIn("customLaunchPayloadRequiresModelRefresh", js)
        self.assertIn("renderCodexCustomModelCatalog(\"codexCustomChatLaneCatalog\", chatEntries)", js)
        self.assertIn("renderCodexCustomModelCatalog(\"codexCustomApiLaneCatalog\", apiEntries)", js)
        self.assertIn("renderCodexCustomModelCatalog(\"codexCustomSeedLaneCatalog\", seedEntries)", js)
        self.assertIn("entry?.provider_label || entry?.provider_class || \"unknown\"", js)
        self.assertIn("entry?.selection_enabled === true", js)
        self.assertIn("selection_disabled_reason_code", js)
        self.assertIn("openai_compatible_shape_declared === true", js)
        self.assertIn("live_api_checked === true ? \"checked\" : \"not checked\"", js)
        self.assertIn("selection_intent_only: packet?.selection_intent_only === true", js)
        self.assertIn("simultaneous_execution_proven: packet?.simultaneous_execution_proven === true", js)
        self.assertIn("role_slot_binding_proven: packet?.role_slot_binding_proven === true", js)
        self.assertIn("current_execution_path_model_id: packet?.current_execution_path_model_id || \"\"", js)
        self.assertIn("current_execution_path_source: packet?.current_execution_path_source || \"\"", js)
        self.assertIn("selected_models_are_server_issued: packet?.selected_models_are_server_issued === true", js)
        self.assertIn("browser_selected_chatgpt_matches_current_execution_path:", js)
        self.assertIn("selected_model_server_issued: packet?.selected_model_server_issued === true", js)
        self.assertIn("selected_model_selectable: packet?.selected_model_selectable === true", js)
        self.assertIn("network_calls_made: packet?.network_call_summary?.network_calls_made === true", js)
        self.assertIn("responses_called: packet?.responses_called === true", js)
        self.assertIn("chat_completions_called: packet?.chat_completions_called === true", js)
        self.assertIn("token_burn: packet?.token_burn ?? 0", js)
        self.assertIn("ChatGPT lane feeds current launch/session path; API lane remains selection intent only", js)
        self.assertIn("Selecting both lanes does not prove simultaneous execution semantics.", html)
        self.assertIn(".codex-custom-api-action-row", css := (WEB_DESIGN_UI / "styles" / "overview.css").read_text())
        self.assertIn("grid-template-columns: max-content minmax(0, 1fr);", css)
        self.assertIn("white-space: nowrap;", css)
        self.assertIn("overflow-wrap: anywhere;", css)
        self.assertNotIn("ready to run", (html + js).lower())
        self.assertNotIn("active executor", (html + js).lower())
        self.assertNotIn("attached agent", (html + js).lower())
        self.assertNotIn("execution ready", (html + js).lower())
        self.assertNotIn("live now", (html + js).lower())
        self.assertNotIn('fetch("api/codex/custom/session"', js)

    def test_codex_launch_mode_split_ui_has_launch_and_dry_run_surfaces(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexLaunchModesPanel"', html)
        self.assertIn('id="originalCodexDryRunAction"', html)
        self.assertIn('id="originalCodexLaunchAction"', html)
        self.assertIn('id="codexCustomLaunchDryRunAction"', html)
        self.assertIn('id="codexCustomLaunchAction"', html)
        self.assertIn('id="codexCustomVisibleHistoryConfirmAction"', html)
        self.assertIn('id="customVisibleHistoryOpenCheck"', html)
        self.assertIn('id="customVisibleHistoryOldChatCheck"', html)
        self.assertIn('id="customVisibleHistoryNoRawContentCheck"', html)
        self.assertIn('id="codexCustomVisibleHistoryResponse"', html)
        self.assertIn('id="safeAppCopyLaunchDryRunAction"', html)
        self.assertIn('id="safeAppCopyLiveAdmissionAction"', html)
        self.assertIn('id="safeAppCopyLaunchAction"', html)
        self.assertIn('id="safeAppCopyStatus"', html)
        self.assertIn('id="safeAppCopyAdmission"', html)
        self.assertIn('id="safeAppCopyIsolation"', html)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/launch-modes\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/original/status\")", js)
        self.assertIn("fetchCodexLaunchJson(\"api/codex/custom/status\")", js)
        self.assertIn('fetch("api/codex/original/launch-dry-run"', js)
        self.assertIn('fetch("api/codex/original/launch"', js)
        self.assertIn('fetch("api/codex/custom/launch-dry-run"', js)
        self.assertIn('fetch("api/codex/custom/native-launch"', js)
        self.assertIn('const controller = typeof AbortController === "function" ? new AbortController() : null;', js)
        self.assertIn("const CUSTOM_NATIVE_LAUNCH_REQUEST_TIMEOUT_MS = 120000;", js)
        self.assertIn(
            "setTimeout(() => controller.abort(), CUSTOM_NATIVE_LAUNCH_REQUEST_TIMEOUT_MS)",
            js,
        )
        self.assertIn('machine_error_code: timedOut ? "CUSTOM_LAUNCH_REQUEST_TIMEOUT" : "CUSTOM_LAUNCH_FETCH_FAILED"', js)
        self.assertIn("execution_mode: executionMode", js)
        self.assertIn("chatgpt_model_id: chatgptModelId", js)
        self.assertIn("api_model_id: apiModelId", js)
        self.assertIn('fetch("api/codex/custom/visible-history/owner-confirmation"', js)
        self.assertIn("raw_thread_content_not_recorded", js)
        self.assertIn("VISIBLE_THREAD_HISTORY_NOT_PROVEN_WITH_STORAGE_CONTINUITY", js)
        self.assertIn('fetch("api/codex/app-copy/launch-dry-run"', js)
        self.assertIn('fetch("api/codex/app-copy/live-admission"', js)
        self.assertIn('fetch("api/codex/app-copy/launch"', js)
        self.assertIn("body: JSON.stringify({})", js)
        self.assertIn("server_issued_plan: packet?.server_issued_plan === true", js)
        self.assertIn("browser_forbidden_fields_absent: packet?.browser_forbidden_fields_absent === true", js)
        self.assertIn("browser_forbidden_field_policy_enforced: packet?.browser_forbidden_field_policy_enforced === true", js)
        self.assertIn("app_path_redacted: packet?.app_path_redacted === true", js)
        self.assertIn("raw_pid_exposed: packet?.raw_pid_exposed === true", js)
        self.assertIn("packet?.raw_path_exposed === false", js)
        self.assertIn("packet?.raw_pid_exposed === false", js)
        self.assertIn("packet?.raw_env_exposed === false", js)
        self.assertIn("pid_not_exposed_to_browser: packet?.pid_not_exposed_to_browser === true", js)
        self.assertIn('packet?.machine_error_code === "WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY"', js)
        self.assertIn('packet?.machine_error_code === "WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY"', js)
        self.assertIn("bounded_live_launch_execution_ready: packet?.bounded_live_launch_execution_ready === true", js)
        self.assertIn("launch_ready_claimed: packet?.launch_ready_claimed === true", js)
        self.assertIn("bounded_helper_execution: packet?.bounded_helper_execution === true", js)
        self.assertIn("real_codex_app_launched: packet?.real_codex_app_launched === true", js)
        self.assertIn("cleanup_or_stop_completed: packet?.cleanup_or_stop_completed === true", js)
        self.assertIn("receipt_redacted: packet?.receipt_redacted === true", js)
        self.assertIn("current_codex_home_allowed: packet?.current_codex_home_allowed === true", js)
        self.assertIn("real_launch_attempted: packet?.real_launch_attempted === true", js)
        self.assertIn("prompt_attempted: packet?.prompt_attempted === true", js)
        self.assertIn("running_status: packet?.running_status === true", js)
        self.assertIn("workbench_ready: packet?.workbench_ready === true", js)
        self.assertIn("process_started: packet?.process_started === true", js)
        self.assertIn("expected_custom_identity_observed: packet?.expected_custom_identity_observed === true", js)
        self.assertIn("native_window_observed: packet?.native_window_observed === true", js)

    def test_overview_fallback_packets_do_not_put_error_prose_in_machine_fields(self) -> None:
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertNotIn("next_action: error.message", js)
        self.assertNotIn("operator_action: error.message", js)
        self.assertNotIn("machine_error_code: error.message", js)
        self.assertNotIn("status: error.message", js)
        self.assertIn("native_app_usable: packet?.native_app_usable === true", js)
        self.assertIn("browser_route_injection: packet?.browser_route_injection === true", js)
        self.assertIn("browser_backend_injection: packet?.browser_backend_injection === true", js)

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
        self.assertIn('id="codexCustomSessionSlots"', html)
        self.assertIn("primary_model_id: primaryModelId", js)
        self.assertIn("coding_agent_model_id: codingAgentModelId", js)
        self.assertIn("current_execution_slot_id", js)
        self.assertIn("current_execution_path_source", js)
        self.assertIn("role_slot_binding_count", js)
        self.assertIn("slot_catalog_revalidated", js)
        self.assertIn("role_slots: roleSlots", js)
        self.assertIn('status: "loaded"', js)
        self.assertIn("postCodexCustomSessionAction(\"prompt-dry-run\", { prompt: promptNode ? promptNode.value : \"\" })", js)
        self.assertIn("runCodexCustomSessionPrompt()", js)
        self.assertIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\" })", js)
        self.assertIn('id="codexCustomSessionPromptRunAction"', html)
        self.assertIn('document.getElementById("codexCustomSessionPromptRunAction")?.addEventListener("click", () => runCodexCustomSessionPrompt())', js)
        self.assertIn('id="codexCustomProductCoderTask"', html)
        self.assertIn("Задача для DeepSeek", html)
        self.assertIn("Запустить DeepSeek-кодер", html)
        self.assertIn("Очистить worktree", html)
        self.assertIn('id="codexCustomProductCoderResponse"', html)
        self.assertIn('id="codexCustomProductCoderDiff"', html)
        self.assertIn('document.getElementById("codexCustomProductCoderRunAction")?.addEventListener("click", () => runCodexCustomProductCoder())', js)
        self.assertIn('document.getElementById("codexCustomProductCoderCleanupAction")?.addEventListener("click", () => cleanupCodexCustomProductCoderWorktree())', js)
        self.assertIn('postCodexCustomSessionAction("safe-worktree-coder", {', js)
        self.assertIn("api_model_id: apiModelId", js)
        self.assertIn("task", js)
        self.assertIn("api/codex/custom/worktrees/${encodeURIComponent(worktreeId)}/cleanup", js)
        self.assertIn("working_dir_override_admitted: packet?.working_dir_override_admitted === true", js)
        self.assertIn("main_worktree_mutated_by_run: packet?.main_worktree_mutated_by_run === true", js)
        self.assertIn("wbp_patch_applier_used: packet?.wbp_patch_applier_used === true", js)
        product_coder_section = js.split("async function runCodexCustomProductCoder()", 1)[1].split(
            "async function cancelCodexCustomSession()", 1
        )[0]
        self.assertNotIn("worktree_path:", product_coder_section)
        self.assertNotIn("base_url:", product_coder_section)
        self.assertNotIn("api_key:", product_coder_section)
        self.assertNotIn("secret_ref:", product_coder_section)
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
        self.assertNotIn("postCodexCustomSessionAction(\"create\", { model_id: modelId })", js)
        self.assertNotIn('renderCodexCustomSessionPacket({ status: "ok", machine_error_code: "OK", session: selected })', js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt-dry-run\", { prompt: promptNode ? promptNode.value : \"\", backend_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\", backend_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"prompt\", { prompt: promptNode ? promptNode.value : \"\", model_id", js)
        self.assertNotIn("postCodexCustomSessionAction(\"cleanup\", { path", js)

    def test_codex_custom_session_render_shows_bounded_dual_lane_without_green_readiness(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
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
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
  }
  return nodes[id];
}

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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomSessionPacket({
  status: "loaded",
  machine_error_code: "SESSION_LOADED_FROM_LIST",
  session: {
    session_id: "ccs-proof",
    status: "prompt_completed_e2e",
    model_id: "gpt-5.5",
    current_execution_slot_id: "coding_agent_model_slot",
    role_slot_binding_count: 2,
    role_slots: {
      primary_model_slot: { binding_status: "bound", model_id: "gpt-5.5" },
      coding_agent_model_slot: { binding_status: "bound", model_id: "wbp-deepseek-chat" }
    },
    inference_proven: true,
    model_response_present: true,
    session_dual_lane_dispatch: {
      status: "ok",
      machine_error_code: "OK",
      final_status: "SESSION_DUAL_LANE_DISPATCH_PROVEN_WITH_LIMITS",
      proof_status: "proven_with_limits",
      same_session_dispatch_proven: true,
      primary_dispatch_proven: true,
      coding_dispatch_proven: true,
      fallback_used: false,
      does_not_prove_native_launch: true,
      does_not_claim_product_readiness: true,
      runtime_readiness_claimed: false
    }
  }
});
`, sandbox);

if (node("codexCustomSessionInference").textContent !== "response proof · session dual-lane proven") {
  throw new Error(`session dual-lane mirror missing: ${node("codexCustomSessionInference").textContent}`);
}
if (node("codexCustomSessionsChip").className.includes("green")) {
  throw new Error(`session bounded proof must not make chip green: ${node("codexCustomSessionsChip").className}`);
}
const rendered = JSON.parse(node("codexCustomSessionResponse").textContent);
if (rendered.session_dual_lane_dispatch_proven_with_limits !== true) {
  throw new Error(`bounded proof flag missing: ${node("codexCustomSessionResponse").textContent}`);
}
if (
  rendered.session_dual_lane_does_not_prove_native_launch !== true ||
  rendered.session_dual_lane_does_not_claim_product_readiness !== true ||
  rendered.session_dual_lane_dispatch.runtime_readiness_claimed !== false
) {
  throw new Error(`bounded proof safety flags missing: ${node("codexCustomSessionResponse").textContent}`);
}
vm.runInContext(`
renderCodexCustomSessionList({
  status: "ok",
  machine_error_code: "OK",
  session_count: 2,
  sessions: [
    {
      session_id: "ccs-old",
      status: "prompt_completed_e2e",
      updated_at_utc: "2026-06-11T22:28:48.476911Z",
      inference_proven: true,
      model_response_present: true,
      session_dual_lane_dispatch: {
        status: "blocked",
        machine_error_code: "SESSION_DUAL_LANE_DISPATCH_NOT_PROVEN",
        final_status: "SESSION_DUAL_LANE_DISPATCH_NOT_PROVEN",
        proof_status: "not_proven",
        does_not_prove_native_launch: true,
        does_not_claim_product_readiness: true,
        runtime_readiness_claimed: false
      }
    },
    {
      session_id: "ccs-new",
      status: "prompt_completed_e2e",
      updated_at_utc: "2026-06-11T22:45:47.170740Z",
      inference_proven: true,
      model_response_present: true,
      session_dual_lane_dispatch: {
        status: "ok",
        machine_error_code: "OK",
        final_status: "SESSION_DUAL_LANE_DISPATCH_PROVEN_WITH_LIMITS",
        proof_status: "proven_with_limits",
        same_session_dispatch_proven: true,
        primary_dispatch_proven: true,
        coding_dispatch_proven: true,
        fallback_used: false,
        does_not_prove_native_launch: true,
        does_not_claim_product_readiness: true,
        runtime_readiness_claimed: false
      }
    }
  ]
});
`, sandbox);
if (node("codexCustomSelectedSession").textContent !== "ccs-new") {
  throw new Error(`latest session was not selected: ${node("codexCustomSelectedSession").textContent}`);
}
if (node("codexCustomSessionInference").textContent !== "response proof · session dual-lane proven") {
  throw new Error(`latest bounded proof not mirrored: ${node("codexCustomSessionInference").textContent}`);
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

    def test_codex_custom_session_render_shows_api_agent_direct_reply_block(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
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
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
  }
  return nodes[id];
}

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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomSessionPacket({
  status: "ok",
  machine_error_code: "OK",
  direct_api_reply_block: true,
  reply_block_kind: "api_agent_direct_reply",
  reply_author_alias: "DIP",
  reply_agent_id: "dip",
  reply_lane: "api_route",
  reply_provider_label: "deepseek",
  reply_text: "WBP_DIRECT_UI_OK",
  reply_text_sha256: "sha",
  reply_proof_summary: {
    prompt_runner_called: false,
    tools_wbp_dip_invoked: false,
    dip_run_invoked: false,
    final_answer_was_repo_tool_call: false
  },
  direct_reply_proven: true,
  auto_router_decision: "api_direct_reply",
  session: {
    session_id: "ccs-direct",
    status: "prompt_completed_e2e",
    model_id: "gpt-5.5",
    current_execution_slot_id: "coding_agent_model_slot",
    role_slot_binding_count: 2,
    role_slots: {}
  }
});
`, sandbox);

const rendered = JSON.parse(node("codexCustomSessionResponse").textContent);
if (rendered.direct_api_reply_block !== true) {
  throw new Error(`direct reply block flag missing: ${node("codexCustomSessionResponse").textContent}`);
}
if (
  rendered.reply_author_alias !== "DIP" ||
  rendered.reply_agent_id !== "dip" ||
  rendered.reply_lane !== "api_route" ||
  rendered.reply_provider_label !== "deepseek" ||
  rendered.reply_text !== "WBP_DIRECT_UI_OK"
) {
  throw new Error(`direct reply block fields missing: ${node("codexCustomSessionResponse").textContent}`);
}
if (
  rendered.reply_proof_summary.prompt_runner_called !== false ||
  rendered.reply_proof_summary.tools_wbp_dip_invoked !== false ||
  rendered.reply_proof_summary.dip_run_invoked !== false ||
  rendered.reply_proof_summary.final_answer_was_repo_tool_call !== false
) {
  throw new Error(`direct reply proof missing: ${node("codexCustomSessionResponse").textContent}`);
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

    def test_codex_custom_recovery_surface_is_bounded_and_readonly(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="codexCustomRecoveryPanel"', html)
        self.assertIn('id="codexCustomRecoveryContractAction"', html)
        self.assertIn('id="codexCustomRecoveryOperatorMatrixAction"', html)
        self.assertIn('id="codexCustomRecoverySessionActionsAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwnerAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmissionAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmissionAction"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyPreflightAction"', html)
        self.assertIn('id="codexCustomRecoveryProcessKillPreflightAction"', html)
        self.assertIn('id="codexCustomRecoveryAdmittedSessionActions"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwner"', html)
        self.assertIn('id="codexCustomRecoveryProcessKillPreflight"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPoint"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmission"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmission"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyPreflight"', html)
        self.assertIn('id="codexCustomRecoveryAdmittedSessionActionsPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackProcessOwnerPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackPointAdmissionPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyAdmissionPacket"', html)
        self.assertIn('id="codexCustomRecoveryRollbackApplyPreflightPacket"', html)
        self.assertIn('id="codexCustomRecoveryProcessKillPreflightPacket"', html)
        self.assertIn('id="codexCustomRecoveryContractActions"', html)
        self.assertIn('id="codexCustomRecoveryContractPacket"', html)
        self.assertIn('id="codexCustomRecoveryOperatorMatrixPacket"', html)
        self.assertIn('id="codexCustomRecoveryPacket"', html)
        self.assertIn('"machine_error_code": "RECOVERY_CONTRACT_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_contract_dry_run_only"', html)
        self.assertIn('"contract_endpoint_mutation_allowed": false', html)
        self.assertIn('"recovery_live_ready": false', html)
        self.assertIn('"operator_ready_claimed": false', html)
        self.assertIn('"machine_error_code": "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_operator_surface_bounded_local_use"', html)
        self.assertIn('"operator_recovery_matrix_complete": false', html)
        self.assertIn('"bounded_local_operator_surface_ready": false', html)
        self.assertIn('"diagnostics_export_redacted": false', html)
        self.assertIn('"machine_error_code": "ADMITTED_SESSION_ACTIONS_NOT_LOADED"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_admitted_session_actions_only"', html)
        self.assertIn('"session_admitted_actions_ready": false', html)
        self.assertIn('"selected_session_cancel_ready": false', html)
        self.assertIn('"owned_session_cleanup_ready": false', html)
        self.assertIn('"machine_error_code": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_stop_cleanup_preflight_only"', html)
        self.assertIn('"verified_scope": "not_verified"', html)
        self.assertIn('"contract_endpoint": "/api/codex/custom/recovery/stop-cleanup/preflight"', html)
        self.assertIn('"contract_source_endpoint": "/api/codex/custom/recovery/admitted-session-actions"', html)
        self.assertIn('"stop_cleanup_preflight_ready": false', html)
        self.assertIn('"selected_session_source": "server_selected_latest_owned_custom_session"', html)
        self.assertIn('"selected_session_id_redacted": true', html)
        self.assertIn('"process_kill_ready": false', html)
        self.assertIn('"session_cancel_performed": false', html)
        self.assertIn('"owned_cleanup_performed": false', html)
        self.assertIn('"filesystem_write_performed": false', html)
        self.assertIn('"human_summary": "stop/cleanup preflight verified · no action performed"', html)
        self.assertIn('"machine_error_code": "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_stop_cleanup_live_only"', html)
        self.assertIn('"declared_write_surface": "owned_temp_session_root_cleanup_only"', html)
        self.assertIn('"preflight_required": true', html)
        self.assertIn('"preflight_verified": false', html)
        self.assertIn('"raw_session_id_omitted": true', html)
        self.assertIn('"same_selected_session_ref": false', html)
        self.assertIn('"session_cancel_verified": false', html)
        self.assertIn('"owned_cleanup_verified": false', html)
        self.assertIn('"filesystem_write_scope": ""', html)
        self.assertIn('"human_summary": "owned session cancelled and cleaned · not system recovery"', html)
        self.assertIn('"machine_error_code": "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_process_kill_preflight_only"', html)
        self.assertIn('"contract_endpoint": "/api/codex/custom/recovery/process-kill/preflight"', html)
        self.assertIn('"raw_pid_omitted": true', html)
        self.assertIn('"raw_process_path_omitted": true', html)
        self.assertIn('"owned_process_identity_required": true', html)
        self.assertIn('"owned_process_identity_present": false', html)
        self.assertIn('"current_codex_process_exclusion_required": true', html)
        self.assertIn('"process_kill_preflight_evaluated": false', html)
        self.assertIn('"process_kill_preflight_ready": false', html)
        self.assertIn('"process_kill_claimed": false', html)
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
        self.assertIn("refreshCodexCustomRecoveryOperatorMatrix()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/operator-ready")', js)
        self.assertIn("renderCodexCustomRecoveryOperatorMatrix", js)
        self.assertIn("refreshCodexCustomRecoveryAdmittedSessionActions()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/admitted-session-actions")', js)
        self.assertIn("renderCodexCustomRecoveryAdmittedSessionActions", js)
        self.assertIn("refreshCodexCustomRecoveryStopCleanupPreflight()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/stop-cleanup/preflight")', js)
        self.assertIn("renderCodexCustomRecoveryStopCleanupPreflight", js)
        self.assertIn("runCodexCustomRecoveryStopCleanupLive()", js)
        self.assertIn('fetch("api/codex/custom/recovery/stop-cleanup", {', js)
        self.assertIn("renderCodexCustomRecoveryStopCleanupLive", js)
        self.assertIn("refreshCodexCustomRecoveryProcessKillPreflight()", js)
        self.assertIn('fetchCodexLaunchJson("api/codex/custom/recovery/process-kill/preflight")', js)
        self.assertIn("renderCodexCustomRecoveryProcessKillPreflight", js)
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
        self.assertIn('"machine_error_code": "ROLLBACK_APPLY_LIVE_PREFLIGHT_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_apply_live_preflight_only"', html)
        self.assertIn('"rollback_apply_live_preflight_evaluated": false', html)
        self.assertIn('"rollback_apply_live_preflight_result": "not_evaluated"', html)
        self.assertIn('"rollback_apply_live_preflight_eligible_for_next_contour": false', html)
        self.assertIn('"rollback_apply_dry_run_eligible": false', html)
        self.assertIn('"future_write_surfaces_declared": false', html)
        self.assertIn('"future_write_surfaces_all_owned": false', html)
        self.assertIn('"current_codex_excluded": true', html)
        self.assertIn('"original_codex_excluded": true', html)
        self.assertIn('"auth_material_excluded": true', html)
        self.assertIn('"arbitrary_path_rejected": true', html)
        self.assertIn('"process_kill_not_admitted": true', html)
        self.assertIn('"source_filesystem_read_performed": false', html)
        self.assertIn('"source_filesystem_read_scope": ""', html)
        self.assertIn('"filesystem_read_scope": ""', html)
        self.assertIn("refreshCodexCustomRecoveryRollbackApplyLivePreflight()", js)
        self.assertIn(
            'fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/live-preflight")',
            js,
        )
        self.assertIn("renderCodexCustomRecoveryRollbackApplyLivePreflight", js)
        self.assertIn("rollback_apply_live_preflight_evaluated: evaluated", js)
        self.assertIn("rollback_apply_live_preflight_result: result", js)
        self.assertIn("rollback_apply_live_preflight_eligible_for_next_contour: eligible", js)
        self.assertIn("rollback_apply_dry_run_eligible: packet?.rollback_apply_dry_run_eligible === true", js)
        self.assertIn("future_write_surfaces_declared: packet?.future_write_surfaces_declared === true", js)
        self.assertIn("future_write_surfaces_all_owned: packet?.future_write_surfaces_all_owned === true", js)
        self.assertIn("rollback_target_browser_supplied: packet?.rollback_target_browser_supplied === true", js)
        self.assertIn("source_filesystem_read_performed: packet?.source_filesystem_read_performed === true", js)
        self.assertIn("source_filesystem_read_scope: packet?.source_filesystem_read_scope || \"\"", js)
        self.assertIn("filesystem_read_scope: packet?.filesystem_read_scope || \"\"", js)
        self.assertIn("rollback_contract_defined: rollbackDefined", js)
        self.assertIn("rollback_live_ready: packet?.rollback_live_ready === true", js)
        self.assertIn("rollback_apply_admitted: packet?.rollback_apply_admitted === true", js)
        self.assertIn('"machine_error_code": "ROLLBACK_APPLY_BOUNDED_LIVE_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_apply_bounded_live_only"', html)
        self.assertIn('"rollback_apply_bounded_live_performed": false', html)
        self.assertIn('"rollback_apply_receipt_created": false', html)
        self.assertIn('"rollback_apply_receipt_path_redacted": true', html)
        self.assertIn('"rollback_apply_receipt_digest_present": false', html)
        self.assertIn('"rollback_apply_completed_scope": "not_completed"', html)
        self.assertIn("createCodexCustomRecoveryRollbackApplyReceipt()", js)
        self.assertIn('fetch("api/codex/custom/recovery/rollback-apply", {', js)
        self.assertIn("renderCodexCustomRecoveryRollbackApplyReceipt", js)
        self.assertIn("rollback_apply_bounded_live_performed: performed", js)
        self.assertIn("rollback_apply_receipt_created: packet?.rollback_apply_receipt_created === true", js)
        self.assertIn("rollback_apply_completed_scope: completedScope", js)
        self.assertIn("recovery_operator_ready: packet?.recovery_operator_ready === true", js)
        self.assertIn("process_kill_performed: packet?.process_kill_performed === true", js)
        self.assertIn('"machine_error_code": "ROLLBACK_APPLY_RECEIPT_VERIFY_NOT_RUN"', html)
        self.assertIn('"claim_scope": "custom_codex_recovery_rollback_apply_receipt_verify_only"', html)
        self.assertIn('"receipt_verify_performed": false', html)
        self.assertIn('"receipt_verified": false', html)
        self.assertIn('"rollback_apply_receipt_verified": false', html)
        self.assertIn('"verified_scope": "not_verified"', html)
        self.assertIn('"human_summary": "receipt verified · not system recovery"', html)
        self.assertIn("verifyCodexCustomRecoveryRollbackApplyReceipt()", js)
        self.assertIn(
            'fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/receipt/verify")',
            js,
        )
        self.assertIn("renderCodexCustomRecoveryRollbackApplyReceiptVerify", js)
        self.assertIn("receipt_verify_performed: packet?.receipt_verify_performed === true", js)
        self.assertIn("rollback_apply_receipt_verified: packet?.rollback_apply_receipt_verified === true", js)
        self.assertIn("verified_scope: scope", js)
        self.assertIn("not system recovery", js)
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
        self.assertIn('document.getElementById("codexCustomRecoveryOperatorMatrixAction")?.addEventListener("click", () => refreshCodexCustomRecoveryOperatorMatrix())', js)
        self.assertIn('document.getElementById("codexCustomRecoverySessionActionsAction")?.addEventListener("click", () => refreshCodexCustomRecoveryAdmittedSessionActions())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackProcessOwnerAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackProcessOwnerContract())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointDryRun())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointCreateAdmission())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointCreateAction")?.addEventListener("click", () => createCodexCustomRecoveryRollbackPoint())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackPointVerifyAction")?.addEventListener("click", () => verifyCodexCustomRecoveryRollbackPoint())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackApplyAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackApplyAdmissionDryRun())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryRollbackApplyPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackApplyLivePreflight())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryStopCleanupPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryStopCleanupPreflight())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryStopCleanupLiveAction")?.addEventListener("click", () => runCodexCustomRecoveryStopCleanupLive())', js)
        self.assertIn('document.getElementById("codexCustomRecoveryProcessKillPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryProcessKillPreflight())', js)
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
        self.assertNotIn('fetch("api/codex/custom/recovery/rollback-apply/live-preflight"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/stop-cleanup/preflight"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/stop-cleanup/preflight", { method: "POST"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/process-kill/preflight"', js)
        self.assertNotIn('fetch("api/codex/custom/recovery/process-kill"', js)
        self.assertNotIn('body: JSON.stringify({ session_id', js)
        self.assertNotIn('body: JSON.stringify({ path', js)
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
        overview_js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        self.assertIn("NO_ACTIVE_REPO_FORWARD_PLAN", overview + overview_js)
        forbidden_forward_pointer = "_".join(
            ("STOP_AND_DIAGNOSE", "REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION")
        )
        self.assertNotIn(forbidden_forward_pointer, overview + overview_js)
        self.assertNotIn('data-ui-action="NO_ACTIVE_REPO_FORWARD_PLAN"', overview)
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

        self.assertIn('data-screen="quick-start"', html)
        self.assertIn('id="mainTitle">Быстрый старт</h1>', html)
        self.assertIn('id="quickStartNav" class="nav-item active"', html)
        self.assertIn('id="overviewNav" class="nav-item" href="?screen=overview"', html)
        self.assertIn('const screen = params.get("screen") || "quick-start";', js)
        self.assertIn('return document.querySelector(".desktop").dataset.screen || "quick-start";', js)
        self.assertNotIn('id="quickStartScreen" class="screen quick-start-screen" data-screen="quick-start" data-quick-start-mode="daily-control-panel" hidden', html)
        self.assertIn('id="overviewScreen" class="screen" data-screen="overview" hidden', html)

        nav_match = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        nav = nav_match.group(1)
        self.assertLess(nav.find('data-screen-link="quick-start"'), nav.find('data-screen-link="overview"'))
        self.assertIn('href="?screen=quick-start"', nav)
        self.assertIn('src="assets/icons/phosphor/lightning.png"', nav)
        self.assertIn("<span>Старт</span>", nav)
        self.assertNotIn("<span>Быстрый старт</span>", nav)
        self.assertIn(
            'const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
            js,
        )

        section = self._section_html(html, "quickStartScreen")
        self.assertIn('data-screen="quick-start"', section)
        self.assertIn("Подключения", section)
        self.assertIn("Добавить ChatGPT", section)
        self.assertIn("Добавить API", section)
        self.assertIn("Проверка", section)
        self.assertIn("без перехода в другие разделы", section)
        self.assertIn("Упрощённый режим показывает только итоговые статусы и безопасные действия.", section + js)
        self.assertIn("Первый запуск: пустые состояния не являются ошибкой.", js)
        self.assertIn("Live-readonly данные недоступны. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Основной route не подтверждён", section + js)
        self.assertIn("ключ: не показывается", section)
        self.assertNotIn("secret_ref:", section)
        self.assertNotIn("base_url", section)
        self.assertNotIn("api_key", section)
        self.assertNotIn("CODEX_HOME", section)
        self.assertIn("ключ: доступен серверу · значение скрыто", js)
        self.assertNotIn('text("quickStartApiSecret", `secret_ref:', js)
        self.assertNotIn('href="?screen=api-connections"', section)
        self.assertNotIn('href="?screen=accounts"', section)
        self.assertIn('data-ui-action="onboard_account_dry_run"', section)
        self.assertIn('document.getElementById("quickStartAddAccountAction")?.addEventListener("click", () => openOnboardModal())', js)
        self.assertIn('id="quickStartConnectApiAction" class="quick-start-connect-tile api-route-action api-route-connect-action"', section)
        self.assertIn('document.getElementById("quickStartConnectApiAction")?.addEventListener("click", () => {', js)
        self.assertIn('maybeConfirmAndRunFromButton(document.getElementById("quickStartConnectApiAction"), "api_route_connect")', js)
        check_accounts_match = re.search(r'<button id="quickStartCheckAccountsAction"[^>]*>', section)
        self.assertIsNotNone(check_accounts_match)
        check_accounts_button = check_accounts_match.group(0)
        self.assertIn('disabled', check_accounts_button)
        self.assertIn('data-action-state="deferred"', check_accounts_button)
        self.assertIn('data-disabled-reason-code="UI_ACTION_MAPPING_NOT_ADMITTED"', check_accounts_button)
        self.assertNotIn("data-ui-action", check_accounts_button)
        self.assertNotIn('quickStartCheckAccountsAction")?.addEventListener("click"', js)
        connect_api_match = re.search(r'<button id="quickStartConnectApiAction"[^>]*>', section)
        self.assertIsNotNone(connect_api_match)
        connect_api_button = connect_api_match.group(0)
        self.assertNotIn("data-route-id", connect_api_button)
        self.assertNotIn("route_id", connect_api_button)
        self.assertNotIn("api_key", connect_api_button)
        self.assertNotIn("secret_ref", connect_api_button)
        check_api_match = re.search(r'<button id="quickStartCheckApiAction"[^>]*>', section)
        self.assertIsNotNone(check_api_match)
        check_api_button = check_api_match.group(0)
        self.assertNotIn("api-route-action", check_api_button)
        self.assertNotIn("data-ui-action", check_api_button)
        self.assertNotIn("data-route-id", check_api_button)
        self.assertNotIn("data-route-enabled", check_api_button)
        self.assertNotIn("data-route-state-proven", check_api_button)
        self.assertIn('fetch("api/codex/custom/quick-start/config-admission"', js)
        self.assertIn('runQuickStartConfigAdmission("quickStartCheckApiAction")', js)
        self.assertIn('runQuickStartConfigAdmission("quickStartExecutionModeDryRunAction")', js)
        self.assertIn("launch_admission_summary", js)
        self.assertIn("silent_fallback_used", js)
        self.assertIn("Рабочий маршрут", section)
        self.assertIn('id="quickStartChatModelSelect"', section)
        self.assertIn("<option value=\"\" selected>codex-auto-review</option>", section)
        self.assertIn('id="quickStartApiModelSelect"', section)
        self.assertIn("<option value=\"\" selected>WBP deepseek-chat</option>", section)
        self.assertIn('id="quickStartApiReasoningOptionSelect"', section)
        self.assertIn("Мышление DeepSeek", section)
        self.assertIn("<option value=\"\" selected>по каталогу</option>", section)
        self.assertIn('id="quickStartExecutionModeSelect"', section)
        self.assertIn('<option value="chatgpt_plus_api" selected>ChatGPT + API</option>', section)
        self.assertIn('<option value="api_only">API</option>', section)
        self.assertIn('id="quickStartDeepSeekCoderCheckAction"', section)
        self.assertIn("Проверить DeepSeek-кодера", section)
        self.assertIn('id="quickStartDeepSeekCodeEditProofAction"', section)
        self.assertIn("Проверить DeepSeek-правку", section)
        self.assertIn('id="quickStartCustomLaunchAction"', section)
        self.assertIn("Проверить GPT+API", section)
        self.assertIn('id="quickStartNativeFreeTextProofAction"', section)
        self.assertIn("Проверить native GPT+API", section)
        self.assertIn('id="quickStartModelReasoningMatrixAction"', section)
        self.assertIn("Проверить matrix", section)
        self.assertIn('id="quickStartManualFreeChatRouterRealityAction"', section)
        self.assertIn("Проверить manual router", section)
        self.assertIn('id="quickStartLaunchPreflightAction"', section)
        self.assertIn("Предзапусковая проверка", section)
        self.assertIn('id="quickStartChatSlotState"', section)
        self.assertIn('id="quickStartApiSlotState"', section)
        self.assertIn('id="quickStartOwnerAuthState"', section)
        self.assertIn('id="quickStartBridgeState"', section)
        self.assertIn('id="quickStartWindowState"', section)
        self.assertIn('id="quickStartConfigState"', section)
        self.assertIn('id="quickStartNextActionState"', section)
        self.assertIn(
            'document.getElementById("quickStartCustomLaunchAction")?.addEventListener("click", () => runQuickStartCustomLaunchAction())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartNativeFreeTextProofAction")?.addEventListener("click", () => runQuickStartNativeFreeTextCommandLoopProof())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartModelReasoningMatrixAction")?.addEventListener("click", () => runQuickStartModelReasoningAvailabilityMatrix())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartManualFreeChatRouterRealityAction")?.addEventListener("click", () => runQuickStartManualFreeChatRouterReality())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartRouteRefreshAction")?.addEventListener("click", () => refreshQuickStartRouteStatus({ force: true }))',
            js,
        )
        self.assertIn("async function runQuickStartCustomLaunchAction()", js)
        self.assertIn("async function runQuickStartNativeFreeTextCommandLoopProof()", js)
        self.assertIn('fetch("api/codex/custom/native-natural-dip-command-proof"', js)
        self.assertIn("async function runQuickStartManualFreeChatRouterReality()", js)
        self.assertIn('fetch("api/codex/custom/manual-free-chat-router-reality"', js)
        self.assertIn("async function runQuickStartModelReasoningAvailabilityMatrix()", js)
        self.assertIn('fetch("api/codex/custom/model-reasoning-availability-matrix"', js)
        self.assertIn("renderQuickStartModelReasoningAvailabilityMatrix", js)
        self.assertIn("async function runQuickStartSessionDualLaneExecution()", js)
        self.assertIn('metadataFor("launch_custom_client_native")', js)
        self.assertIn("await runCodexCustomLaunch()", js)
        self.assertIn('fetch("api/codex/custom/sessions"', js)
        self.assertIn("agent-alias-dispatch-proof", js)
        self.assertIn("expected_coding_response", js)
        self.assertIn('document.getElementById("quickStartLaunchPreflightAction")?.addEventListener("click", () => runQuickStartLaunchPreflight())', js)
        self.assertIn('fetch("api/codex/custom/native-launch-preflight"', js)
        self.assertIn("runQuickStartLaunchAdmissionProjection", js)
        self.assertIn("renderQuickStartLaunchPreflight", js)
        self.assertIn("visible_window_counts_as_model_truth", js)
        self.assertIn("bridge_alive_counts_as_model_truth", js)
        self.assertIn("launch_packet_is_truth_source", js)
        self.assertIn('id="quickStartShowCustomWindowAction"', section)
        self.assertIn("Показать окно", section)
        self.assertIn('document.getElementById("quickStartShowCustomWindowAction")?.addEventListener("click", () => showCodexCustomWindow())', js)
        self.assertIn('fetch("api/codex/custom/show-window"', js)
        show_window_match = re.search(r'<button id="quickStartShowCustomWindowAction"[^>]*>', section)
        self.assertIsNotNone(show_window_match)
        show_window_button = show_window_match.group(0)
        self.assertNotIn("href=", show_window_button)
        self.assertNotIn("data-screen-link", show_window_button)
        self.assertNotIn("base_url", show_window_button)
        self.assertNotIn("api_key", show_window_button)
        self.assertNotIn("secret_ref", show_window_button)
        self.assertIn('id="quickStartVisibleHistoryConfirmAction"', section)
        self.assertIn("syncCodexRouteSelects", js)
        self.assertIn("quickStartAdmissionComponentVisual", js)
        self.assertIn("quickStartNextActionLabel", js)
        self.assertIn('return "dispatch proof"', js)
        self.assertIn("apiReasoningOptionForModelEntry", js)
        self.assertIn("provider_declared_max", js)
        self.assertIn("api_reasoning_option_id: apiReasoningOptionId", js)
        self.assertNotIn("reasoning_effort: apiReasoningOptionId", js)
        self.assertIn('label: "Обычное"', js)
        self.assertIn('label: "Глубокое"', js)
        self.assertIn('label: "Усиленное"', js)
        self.assertIn('label: "Авто"', js)
        self.assertNotIn("thinking off", section + js)
        self.assertNotIn("provider-declared", section + js)
        self.assertIn('fetch("api/codex/custom/execution-mode-dry-run"', js)
        self.assertIn('fetch("api/codex/custom/native-launch"', js)
        self.assertIn("execution_mode: executionMode", js)
        self.assertIn("chatgpt_model_id: chatgptModelId", js)
        self.assertIn("api_model_id: apiModelId", js)
        self.assertIn("launch_route_truth_final_status", js)
        self.assertIn("quick_start_stable_custom_launch_final_status", js)
        self.assertIn("profile_final_status", js)
        self.assertIn("session_storage_final_status", js)
        self.assertIn("profile_persistence_proven", js)
        self.assertIn("persistent_profile_reused", js)
        self.assertIn("profile_relaunch_required_for_strong_history_claim", js)
        self.assertIn("route_packet_matches_selection_packet", js)
        self.assertIn("quick_start_launch_route_truth_proven_with_limits", js)
        self.assertIn("response.textContent = JSON.stringify({", js)
        self.assertIn("custom_codex_window_deepseek_smoke_final_status", js)
        self.assertIn("custom_codex_window_deepseek_launch_proven_with_limits", js)
        self.assertIn("manual_prompt_smoke_attempted", js)
        self.assertIn("model_self_report_counts_as_runtime_truth", js)
        self.assertIn("history_persistence_claimed", js)
        self.assertIn("selected_model: packet?.selected_model", js)
        self.assertIn("runQuickStartDeepSeekCoderCheck()", js)
        self.assertIn("api/codex/custom/quick-start/deepseek-safe-worktree-check", js)
        self.assertIn("runQuickStartDeepSeekCodeEditProof()", js)
        self.assertIn("api/codex/custom/quick-start/deepseek-code-edit-proof", js)
        self.assertIn("CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCIBLE_PROVEN_WITH_LIMITS", js)
        self.assertIn("file_content_exact", js)
        self.assertIn("quickStartCustomLaunchAction", js)
        self.assertIn('executionMode === "api_only"', js)
        self.assertIn("DEEPSEEK_LIVE_EXECUTOR_PACKET_PROVEN_WITH_LIMITS", js)
        self.assertIn("QUICK_START_API_ONLY_DEEPSEEK_SAFE_WORKTREE_BUTTON_PROVEN_WITH_LIMITS", js)
        self.assertIn("api_reasoning_option_id: apiReasoningOptionId", js)
        self.assertIn("deepseek_live_executor_packet_proven_with_limits", js)
        self.assertIn("no_chatgpt: packet?.no_chatgpt === true", js)
        self.assertIn("no_fallback: packet?.no_fallback === true", js)
        self.assertIn("no_patch_applier: packet?.no_patch_applier === true", js)
        self.assertIn("main_tree_untouched: packet?.main_tree_untouched === true", js)
        self.assertIn("file_changed_by_codex_tool: packet?.file_changed_by_codex_tool === true", js)
        self.assertIn("main_worktree_mutated_by_probe: packet?.main_worktree_mutated_by_probe === true", js)
        self.assertIn("quickStartRouteResponse", js)
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
        self.assertIn("--qs-main-padding: 28px", css)
        self.assertIn("--qs-section-gap: 18px", css)
        self.assertIn("--qs-card-padding: 18px", css)
        self.assertIn("--qs-row-height: 46px", css)
        self.assertIn("--qs-control-height: 36px", css)
        self.assertIn('width: 156px', css)
        self.assertIn("font-size: 16px", css)
        self.assertIn("line-height: 20px", css)
        self.assertIn("display: none", css)
        self.assertIn('document.getElementById("brandCaption").textContent = "";', js)
        self.assertNotIn('function liveBrandCaptionForScreen', js)
        self.assertIn('.desktop[data-screen="quick-start"] .brand img', css)
        self.assertNotIn('.desktop[data-screen="quick-start"] .brand .name', css)
        self.assertNotIn('.desktop[data-screen="quick-start"] .brand .caption', css)
        self.assertNotIn("quick start · live readonly", html + js)
        self.assertNotIn("quick start · v0.2.0", html + js)
        self.assertIn("align-items: start", css)
        self.assertIn("grid-template-columns: minmax(300px, 1.15fr) minmax(300px, .85fr)", css)
        self.assertIn("max-width: 1110px", css)
        self.assertIn("quick-start-connections-card", html)
        self.assertIn(".quick-start-connection-actions", css)
        self.assertIn(".quick-start-connect-tile", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn(".quick-start-connection-status", css)
        self.assertIn(".quick-start-route-card", css)
        self.assertIn("grid-column: auto", css)
        self.assertIn(".quick-start-route-grid", css)
        self.assertIn("appearance: none", css)
        self.assertIn('content: "..."', css)
        self.assertIn(".quick-start-history-checklist", css)
        self.assertIn("height: auto", css)
        self.assertIn("padding: 32px var(--qs-main-padding) 24px", css)
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn('.desktop[data-screen="quick-start"] .main-header', css)
        self.assertIn("position: fixed", css)
        self.assertIn("z-index: 120", css)
        self.assertIn("padding-top: 112px", css)
        self.assertIn("async function refreshCurrentSource()", js)
        self.assertIn('setRefreshButtonFeedback("busy", "Обновляю...", { disabled: true })', js)
        self.assertIn('setRefreshButtonFeedback("success", "Обновлено", { resetAfterMs: 1000 })', js)
        self.assertIn('setRefreshButtonFeedback("error", "Ошибка", { resetAfterMs: 1800 })', js)
        self.assertIn("resetRefreshButtonLabelIfIdle()", js)
        self.assertIn("grid-template-columns: minmax(280px, 1fr) minmax(280px, .82fr)", css)
        self.assertNotIn("@media (max-width: 1511px)", css)
        self.assertIn(".main-header > div:first-child::before", css)
        self.assertIn('url("../assets/icons/phosphor/lightning.png") center / 22px 22px no-repeat', css)
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
        self.assertNotIn(".quick-start-route-card .quick-start-api-checklist .quick-start-check-row:nth-child(n+2)", css)
        self.assertIn(".header-actions #quickStartCheckAllAction:disabled", css)
        self.assertIn('document.getElementById("quickStartCheckAllAction")?.addEventListener("click"', js)
        self.assertIn('maybeConfirmAndRunFromButton(button, button.dataset.uiAction || "quick_start_check_all")', js)
        self.assertIn("quickStartPresentationActionButton", js)
        self.assertIn("renderBlockedActionFromButton", js)
        blocked_action_body = js.split("function renderBlockedActionFromButton", 1)[1].split("function maybeConfirmAndRunFromButton", 1)[0]
        self.assertIn('route_id: ""', blocked_action_body)
        self.assertNotIn("route_id: extraPayload.route_id", blocked_action_body)
        self.assertIn('machine_error_code: metadata.disabled_reason_code || "UI_ACTION_UNAVAILABLE"', js)
        self.assertIn("disabled_reasons: Array.isArray(metadata.disabled_reasons) ? metadata.disabled_reasons : []", js)
        self.assertIn('button.disabled = quickStartPresentationActionButton(button) ? false : !state.available', js)
        self.assertIn(
            'maybeConfirmAndRunFromButton(document.getElementById("quickStartApiCredentialCheckAction"), "api_route_credential_check")',
            js,
        )
        self.assertIn(
            'maybeConfirmAndRunFromButton(document.getElementById("quickStartApiCredentialRetryAction"), "api_route_connect")',
            js,
        )
        self.assertIn('.desktop[data-screen="quick-start"] #quickStartExecutionModeDryRunAction', css)
        self.assertIn('.desktop[data-screen="quick-start"] .quick-start-route-response', css)
        self.assertIn(".desktop[data-screen=\"quick-start\"] .quick-start-route-actions", css)
        self.assertIn("min-width: 220px", css)

        for forbidden in (
            "<canvas",
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
        self.assertIn('src="assets/icons/phosphor/plus.png"', section)
        self.assertIn('src="assets/icons/phosphor/key.png"', section)
        self.assertIn('src="assets/icons/phosphor/terminal-window.png"', section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', section)
        self.assertIn("missing_secret_ref", js)
        self.assertIn('setQuickStartChecklistChip("quickStartApiSecretChip", apiModel.state === "missing_secret_ref" ? "amber"', js)
        self.assertIn('const primary = source === "live"', js)

    def test_quick_start_voice_draft_is_wbp_local_and_never_autosubmits_custom(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        section = self._section_html(html, "quickStartScreen")
        voice_card_match = re.search(
            r'<section class="card quick-start-card quick-start-voice-card"[\s\S]*?</section>',
            section,
        )
        self.assertIsNotNone(voice_card_match)
        assert voice_card_match is not None
        voice_card = voice_card_match.group(0)
        voice_js = js[
            js.index("function quickStartVoiceRecognitionConstructor"):
            js.index("function lockQuickStartRouteProofResult")
        ]

        self.assertIn('id="quickStartVoiceRecordAction"', voice_card)
        self.assertIn('id="quickStartVoiceClearAction"', voice_card)
        self.assertIn('id="quickStartVoiceCopyAction"', voice_card)
        self.assertIn('id="quickStartVoicePastePreflightAction"', voice_card)
        self.assertIn('id="quickStartVoicePasteCustomAction"', voice_card)
        self.assertIn('id="quickStartVoiceDraftText"', voice_card)
        self.assertIn('id="quickStartVoiceDraftPacket"', voice_card)
        self.assertNotIn("data-ui-action", voice_card)
        self.assertNotIn("href=", voice_card)
        self.assertIn(".quick-start-voice-card", css)
        self.assertIn(".quick-start-voice-draft", css)
        self.assertIn('window.SpeechRecognition || window.webkitSpeechRecognition', voice_js)
        self.assertIn('fetch("api/wbp/voice-draft"', voice_js)
        self.assertIn('fetch("/api/wbp/custom-paste-bridge/preflight"', voice_js)
        self.assertIn('fetch("/api/wbp/custom-paste-bridge/live-paste"', voice_js)
        self.assertIn("navigator.clipboard.writeText(transcript)", voice_js)
        self.assertIn("clipboard_handoff_available: true", voice_js)
        self.assertIn("clipboard_handoff_attempted: overrides.clipboard_handoff_attempted === true", voice_js)
        self.assertIn("clipboard_handoff_ok: overrides.clipboard_handoff_ok === true", voice_js)
        self.assertIn("clipboard_contains_transcript: overrides.clipboard_contains_transcript === true", voice_js)
        self.assertIn("empty_transcript_copy_blocked: overrides.empty_transcript_copy_blocked === true", voice_js)
        self.assertIn("draft_text_in_packet: false", voice_js)
        self.assertIn("submit_action_planned: false", voice_js)
        self.assertIn("enter_key_pressed: false", voice_js)
        self.assertIn("send_button_pressed: false", voice_js)
        self.assertIn("api_called: false", voice_js)
        self.assertIn("model_endpoint_called: false", voice_js)
        self.assertIn("transcript_text_included_in_packet: false", voice_js)
        self.assertIn("server_audio_ingress_enabled: false", voice_js)
        self.assertIn("raw_audio_recorded_by_server: false", voice_js)
        self.assertIn("custom_codex_not_mutated: true", voice_js)
        self.assertIn("custom_window_mutation_attempted: false", voice_js)
        self.assertIn("prompt_not_submitted: true", voice_js)
        self.assertIn("secret_value_exposed: false", voice_js)
        self.assertIn("raw_backend_details_exposed: false", voice_js)
        self.assertIn("TRANSCRIPTION_ENGINE_NOT_CONFIGURED", voice_js)
        self.assertNotIn("MediaRecorder", voice_js)
        self.assertNotIn("api/action", voice_js)
        self.assertNotIn("api/operator/run", voice_js)
        self.assertNotIn("api/codex/custom", voice_js)
        self.assertIn(
            'document.getElementById("quickStartVoiceRecordAction")?.addEventListener("click", () => startQuickStartVoiceDraft())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartVoiceClearAction")?.addEventListener("click", () => clearQuickStartVoiceDraft())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartVoiceCopyAction")?.addEventListener("click", () => copyQuickStartVoiceDraft())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartVoicePastePreflightAction")?.addEventListener("click", () => runQuickStartVoicePastePreflight())',
            js,
        )
        self.assertIn(
            'document.getElementById("quickStartVoicePasteCustomAction")?.addEventListener("click", () => runQuickStartVoicePasteCustom())',
            js,
        )

    def test_quick_start_voice_draft_copy_packets_are_executable_and_redacted(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.id = "";
    this.lastElementChild = { textContent: "" };
    this.readOnly = false;
    this.textContent = "";
    this.value = "";
  }
  addEventListener() {}
  append(...nodes) {
    for (const item of nodes) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  removeAttribute(name) { delete this[name]; }
  replaceChildren(...nodes) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  }
  setAttribute(name, value) { this[name] = value; }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}
function packet() {
  return JSON.parse(node("quickStartVoiceDraftPacket").textContent);
}
function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const sandbox = {
  console,
  document: {
    documentElement: { lang: "ru" },
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; }
  },
  navigator: {
    language: "ru-RU",
    clipboard: {
      async writeText(text) {
        if (sandbox.__clipboardFailure) {
          throw sandbox.__clipboardFailure;
        }
        sandbox.__clipboardText = text;
      }
    }
  },
  window: {
    SpeechRecognition: class {},
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout
};
sandbox.__clipboardText = "";
sandbox.__clipboardFailure = null;

(async () => {
  vm.createContext(sandbox);
  const source = fs.readFileSync("scripts/overview.js", "utf8");
  await vm.runInContext(`${source}
(async () => {
  renderQuickStartVoiceDraft();
  await copyQuickStartVoiceDraft();
  let emptyPacket = JSON.parse(document.getElementById("quickStartVoiceDraftPacket").textContent);
  if (emptyPacket.machine_error_code !== "EMPTY_TRANSCRIPT") {
    throw new Error("empty copy code mismatch: " + emptyPacket.machine_error_code);
  }
  if (emptyPacket.clipboard_handoff_attempted !== true || emptyPacket.clipboard_handoff_ok !== false) {
    throw new Error("empty copy handoff booleans mismatch: " + JSON.stringify(emptyPacket));
  }
  if (emptyPacket.clipboard_contains_transcript !== false || emptyPacket.empty_transcript_copy_blocked !== true) {
    throw new Error("empty copy guard mismatch: " + JSON.stringify(emptyPacket));
  }

  const transcript = "WBP voice clipboard handoff text";
  quickStartVoiceDraftState.transcript = transcript;
  renderQuickStartVoiceDraft();
  if (document.getElementById("quickStartVoiceCopyAction").disabled !== false) {
    throw new Error("copy button must enable when transcript exists");
  }
  await copyQuickStartVoiceDraft();
  let copiedPacket = JSON.parse(document.getElementById("quickStartVoiceDraftPacket").textContent);
  if (copiedPacket.machine_error_code !== "VOICE_DRAFT_COPY_OK") {
    throw new Error("copy code mismatch: " + copiedPacket.machine_error_code);
  }
  if (copiedPacket.clipboard_handoff_attempted !== true || copiedPacket.clipboard_handoff_ok !== true) {
    throw new Error("copy handoff booleans mismatch: " + JSON.stringify(copiedPacket));
  }
  if (copiedPacket.clipboard_contains_transcript !== true || copiedPacket.transcript_length !== transcript.length) {
    throw new Error("copy transcript metadata mismatch: " + JSON.stringify(copiedPacket));
  }
  if (JSON.stringify(copiedPacket).includes(transcript)) {
    throw new Error("packet must not include raw transcript text");
  }
  if (globalThis.__clipboardText !== transcript) {
    throw new Error("clipboard text mismatch: " + globalThis.__clipboardText);
  }

  globalThis.__clipboardFailure = new Error("blocked clipboard");
  await copyQuickStartVoiceDraft();
  let failedPacket = JSON.parse(document.getElementById("quickStartVoiceDraftPacket").textContent);
  if (failedPacket.machine_error_code !== "CLIPBOARD_WRITE_FAILED") {
    throw new Error("failure code mismatch: " + failedPacket.machine_error_code);
  }
  if (failedPacket.clipboard_handoff_attempted !== true || failedPacket.clipboard_handoff_ok !== false) {
    throw new Error("failure handoff booleans mismatch: " + JSON.stringify(failedPacket));
  }
  if (failedPacket.clipboard_contains_transcript !== false) {
    throw new Error("failure packet must not claim clipboard transcript: " + JSON.stringify(failedPacket));
  }
})()`, sandbox);
})().catch((error) => {
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

    def test_quick_start_voice_paste_bridge_packets_are_executable_and_redacted(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.id = "";
    this.lastElementChild = { textContent: "" };
    this.readOnly = false;
    this.textContent = "";
    this.value = "";
  }
  addEventListener() {}
  append(...nodes) {
    for (const item of nodes) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  removeAttribute(name) { delete this[name]; }
  replaceChildren(...nodes) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  }
  setAttribute(name, value) { this[name] = value; }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

const requests = [];
function response(packet) {
  return { ok: true, json: async () => packet };
}

const sandbox = {
  console,
  document: {
    documentElement: { lang: "ru" },
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; }
  },
  navigator: { language: "ru-RU", clipboard: { async writeText() {} } },
  window: {
    SpeechRecognition: class {},
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  requests,
  fetch: async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : {};
    requests.push({ url, body });
    if (url === "/api/wbp/custom-paste-bridge/preflight") {
      return response({
        schema_version: 1,
        packet_kind: "wbp_custom_paste_bridge",
        endpoint: "/api/wbp/custom-paste-bridge/preflight",
        phase: "preflight",
        status: "ok",
        machine_error_code: "OK",
        draft_present: true,
        draft_length: body.draft_length,
        draft_text_in_packet: false,
        custom_window_found: true,
        custom_window_identity_proven: true,
        target_input_unique: true,
        target_input_candidate: "single",
        clipboard_restore_required: true,
        live_paste_attempted: false,
        paste_attempted: false,
        paste_ok: false,
        prompt_submitted: false,
        enter_key_pressed: false,
        send_button_pressed: false,
        api_called: false,
        model_endpoint_called: false
      });
    }
    if (url === "/api/wbp/custom-paste-bridge/live-paste") {
      return response({
        schema_version: 1,
        packet_kind: "wbp_custom_paste_bridge",
        endpoint: "/api/wbp/custom-paste-bridge/live-paste",
        phase: "live_paste",
        status: "ok",
        machine_error_code: "OK",
        draft_present: true,
        draft_length: body.draft_length,
        draft_text_in_packet: false,
        custom_window_found: true,
        custom_window_identity_proven: true,
        target_input_unique: true,
        target_input_candidate: "single",
        clipboard_restore_required: true,
        clipboard_restored: true,
        live_paste_attempted: true,
        paste_attempted: true,
        paste_ok: true,
        custom_mutation_scope: "paste_only",
        prompt_submitted: false,
        submit_action_planned: false,
        enter_key_planned: false,
        enter_key_pressed: false,
        send_button_planned: false,
        send_button_pressed: false,
        api_called: false,
        model_endpoint_called: false,
        operator_run_called: false,
        session_prompt_endpoint_called: false
      });
    }
    throw new Error("unexpected fetch " + url);
  }
};

(async () => {
  vm.createContext(sandbox);
  const source = fs.readFileSync("scripts/overview.js", "utf8");
  await vm.runInContext(`${source}
(async () => {
  const transcript = "WBP paste bridge raw draft";
  quickStartVoiceDraftState.transcript = transcript;
  renderQuickStartVoiceDraft();
  if (document.getElementById("quickStartVoicePastePreflightAction").disabled !== false) {
    throw new Error("preflight button must enable when transcript exists");
  }
  await runQuickStartVoicePastePreflight();
  if (globalThis.requests[0].url !== "/api/wbp/custom-paste-bridge/preflight") {
    throw new Error("preflight endpoint mismatch");
  }
  if ("draft_text" in globalThis.requests[0].body) {
    throw new Error("preflight must not send raw draft text");
  }
  if (document.getElementById("quickStartVoicePasteCustomAction").disabled !== false) {
    throw new Error("live paste button must enable after fresh preflight");
  }
  await runQuickStartVoicePasteCustom();
  if (globalThis.requests[1].url !== "/api/wbp/custom-paste-bridge/live-paste") {
    throw new Error("live endpoint mismatch");
  }
  if (globalThis.requests[1].body.draft_text !== transcript) {
    throw new Error("live paste must send draft text transiently");
  }
  const rendered = document.getElementById("quickStartVoiceDraftPacket").textContent;
  if (rendered.includes(transcript)) {
    throw new Error("rendered packet must not include raw draft text");
  }
  const packet = JSON.parse(rendered);
  if (packet.prompt_submitted !== false || packet.enter_key_pressed !== false || packet.send_button_pressed !== false) {
    throw new Error("submit guard mismatch: " + rendered);
  }
  if (packet.api_called !== false || packet.model_endpoint_called !== false) {
    throw new Error("model/API guard mismatch: " + rendered);
  }
})()`, sandbox);
})().catch((error) => {
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

    def test_quick_start_api_selector_uses_available_api_routes_when_api_lane_is_absent(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "live" } }; },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    createElement() { return {}; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

const entries = sandbox.codexCustomApiModelEntries({
  status: "degraded",
  machine_error_code: "CLAIM_GATE_BLOCKED",
  available_models: [
    {
      model_id: "gpt-5.4",
      selection_enabled: true,
      model_lane: "codex_account_lane",
      source: "server_native_catalog"
    },
    {
      model_id: "wbp-deepseek-v4-pro-max",
      display_name: "WBP DeepSeek V4 Pro · Максимум",
      selection_enabled: true,
      model_lane: "api_route_lane",
      source: "server_owned_external_route",
      thinking: { type: "enabled", reasoning_effort: "max" }
    },
    {
      model_id: "wbp-disabled-openrouter",
      selection_enabled: false,
      model_lane: "api_route_lane",
      source: "server_owned_external_route"
    },
    {
      model_id: "gpt-image-2",
      selection_enabled: true,
      model_lane: "unknown_lane",
      source: "cliproxy_external_alias"
    }
  ]
});

if (entries.length !== 1) {
  throw new Error(`expected one fallback API route entry, got ${entries.length}`);
}
if (entries[0].model_id !== "wbp-deepseek-v4-pro-max") {
  throw new Error(`wrong fallback model: ${entries[0].model_id}`);
}
if (entries[0].thinking.reasoning_effort !== "max") {
  throw new Error("DeepSeek reasoning metadata was not preserved");
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

    def test_quick_start_launch_preflight_renders_relaunch_as_ready_state(self) -> None:
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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderQuickStartLaunchPreflight({
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-v4-pro-max",
  owner_authorization_phrase_present: true,
  bridge_required: true,
  bridge_alive: true,
  custom_process_observed: true,
  config_status: "changed",
  existing_window_reuse_admissible: false,
  existing_window_relaunch_admissible: true,
  new_launch_required: true,
  launch_packet_is_truth_source: true,
  visible_window_counts_as_model_truth: false,
  bridge_alive_counts_as_model_truth: false,
  response_text_counts_as_route_truth: false,
  next_action: "relaunch_custom_codex_with_new_selection"
});

if (!node("quickStartNextActionState").className.includes("green")) {
  throw new Error(`relaunch next action must be green, got ${node("quickStartNextActionState").className}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "relaunch ready") {
  throw new Error(`wrong next action label: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "preflight ok") {
  throw new Error(`wrong launch state: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
const packet = JSON.parse(node("quickStartRouteResponse").textContent);
if (packet.existing_window_relaunch_admissible !== true) {
  throw new Error(`relaunch admissibility missing from packet: ${JSON.stringify(packet)}`);
}
if (packet.visible_window_counts_as_model_truth !== false || packet.bridge_alive_counts_as_model_truth !== false || packet.response_text_counts_as_route_truth !== false) {
  throw new Error(`false-green guard fields changed: ${JSON.stringify(packet)}`);
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

    def test_quick_start_launch_preflight_explicit_runtime_not_ready_is_not_green(self) -> None:
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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderQuickStartLaunchPreflight({
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "chatgpt_plus_api",
  selected_model: "gpt-5.5",
  owner_authorization_phrase_present: true,
  bridge_required: true,
  bridge_alive: true,
  custom_process_observed: true,
  config_status: "matches_last_launch",
  runtime_readiness_claimed: false,
  next_action: "launch_custom_codex"
});

if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`explicit runtime-not-ready preflight must not be green: ${node("quickStartLaunchState").className}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "preflight only") {
  throw new Error(`wrong launch state: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").className.includes("green")) {
  throw new Error(`explicit runtime-not-ready next action must not be green: ${node("quickStartNextActionState").className}`);
}
const packet = JSON.parse(node("quickStartRouteResponse").textContent);
if (packet.runtime_readiness_claimed !== false) {
  throw new Error(`runtime readiness false not preserved: ${JSON.stringify(packet)}`);
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

    def test_quick_start_launch_preflight_renders_orphan_replace_as_ready_state(self) -> None:
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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderQuickStartLaunchPreflight({
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-v4-pro-max",
  owner_authorization_phrase_present: true,
  bridge_required: true,
  bridge_alive: true,
  custom_process_observed: true,
  config_status: "no_previous_launch",
  existing_window_reuse_admissible: false,
  existing_window_relaunch_admissible: false,
  existing_window_orphan_replace_admissible: true,
  orphan_replacement_authority_scope: "same_persistent_custom_profile_process_only",
  new_launch_required: true,
  launch_packet_is_truth_source: true,
  visible_window_counts_as_model_truth: false,
  bridge_alive_counts_as_model_truth: false,
  response_text_counts_as_route_truth: false,
  next_action: "replace_existing_custom_codex_without_launch_packet"
});

if (!node("quickStartNextActionState").className.includes("green")) {
  throw new Error(`replace next action must be green, got ${node("quickStartNextActionState").className}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "replace ready") {
  throw new Error(`wrong next action label: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "preflight ok") {
  throw new Error(`wrong launch state: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
const packet = JSON.parse(node("quickStartRouteResponse").textContent);
if (packet.existing_window_orphan_replace_admissible !== true) {
  throw new Error(`orphan replace admissibility missing from packet: ${JSON.stringify(packet)}`);
}
if (packet.orphan_replacement_authority_scope !== "same_persistent_custom_profile_process_only") {
  throw new Error(`orphan replace scope missing from packet: ${JSON.stringify(packet)}`);
}
if (packet.visible_window_counts_as_model_truth !== false || packet.bridge_alive_counts_as_model_truth !== false || packet.response_text_counts_as_route_truth !== false) {
  throw new Error(`false-green guard fields changed: ${JSON.stringify(packet)}`);
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

    def test_c7_agent_aliases_use_server_runtime_binding_contract(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        section = self._section_html(html, "quickStartScreen")

        alias_match = re.search(
            r'<div class="quick-start-alias-card"[^>]*>(?P<body>.*?)\n              </div>\n\n              <div class="quick-start-api-checklist"',
            section,
            re.S,
        )
        self.assertIsNotNone(alias_match)
        alias_markup = alias_match.group("body")

        self.assertIn("Имена агентов", alias_markup)
        self.assertIn("server-owned runtime bindings", alias_markup)
        self.assertIn("server-issued", alias_markup)
        self.assertIn('id="quickStartPrimaryAgentAliasInput"', alias_markup)
        self.assertIn('value="Codex"', alias_markup)
        self.assertIn('id="quickStartCodingAgentAliasInput"', alias_markup)
        self.assertIn('value="DIP"', alias_markup)
        self.assertIn("Применить имена", alias_markup)
        self.assertIn('data-agent-alias-slot="primary_model_slot"', alias_markup)
        self.assertIn('data-agent-alias-slot="coding_agent_model_slot"', alias_markup)
        self.assertNotIn("data-ui-action", alias_markup)

        self.assertIn('const CODEX_CUSTOM_AGENT_ALIAS_CONFIG_KIND = "server_agent_bindings_packet";', js)
        self.assertIn("/api/codex/custom/agent-bindings", js)
        self.assertIn("codexCustomAgentBindingsPayload", js)
        self.assertIn("codexCustomAgentRuntimeBindingPacket", js)
        self.assertIn("agent-aliases", js)
        self.assertIn("agent-alias-dispatch-proof", js)
        self.assertIn('alias_scope: serverPacket?.alias_scope || "server_runtime_binding_pending"', js)
        self.assertIn("alias_runtime_binding_proven:", js)
        self.assertIn("persisted_in_browser_storage: false", js)
        self.assertIn("semantic_alias_routing_enabled: serverPacket?.semantic_alias_routing_enabled === true", js)
        self.assertIn("native_free_text_alias_routing_proven: false", js)
        self.assertIn("runtime_dispatch_changed: false", js)
        self.assertIn("session_manager_changed: true", js)
        self.assertIn("provider_selection_changed: false", js)
        self.assertIn("command_surface_changed: true", js)
        self.assertIn("browser_can_supply_alias_authority: false", js)
        self.assertIn("browser_can_supply_route_authority: false", js)
        self.assertIn("browser_backend_intake: false", js)
        self.assertIn("browser_secret_intake: false", js)
        self.assertIn("does_not_prove_native_free_text_tool_bridge", js)
        self.assertIn("changed_files: []", js)
        self.assertIn("role_map: roleMap", js)
        self.assertIn("alias_role_map: aliasMetadata.role_map", js)
        self.assertIn("agent_alias_binding: serverAliasBinding || null", js)
        self.assertIn("manual_activation_proven", js)
        self.assertIn("deepseek_response_token_matched", js)
        self.assertIn('let codexCustomAgentAliasBindingSessionId = "";', js)
        self.assertIn("codexCustomAgentAliasBindingSessionId === sessionId", js)
        self.assertIn("boundedTruthGuardsHeld", js)
        self.assertIn("&& boundedTruthGuardsHeld", js)
        self.assertIn("setupCodexCustomAgentAliases();", js)
        alias_js = js.split('const CODEX_CUSTOM_AGENT_ALIAS_CONFIG_KIND = "server_agent_bindings_packet";', 1)[1].split("function codexLaunchSetText", 1)[0]
        self.assertNotIn("localStorage", alias_markup + alias_js)
        self.assertIn(".quick-start-alias-card", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)

    def test_c7_stale_agent_alias_binding_does_not_bleed_between_sessions(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
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
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
  }
  return nodes[id];
}

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
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) })
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
codexCustomAgentAliasBindingPacket = {
  status: "ok",
  packet_kind: "codex_custom_agent_alias_runtime_binding",
  alias_scope: "server_runtime_binding",
  alias_runtime_binding_present: true,
  alias_runtime_binding_proven: true,
  semantic_alias_routing_enabled: true,
  does_not_prove_native_free_text_tool_bridge: true,
  alias_to_slot_map: [
    { alias: "Codex", slot_id: "primary_model_slot" },
    { alias: "DIP", slot_id: "coding_agent_model_slot" }
  ]
};
codexCustomAgentAliasBindingSessionId = "ccs-old";

renderCodexCustomSessionPacket({
  status: "loaded",
  machine_error_code: "SESSION_LOADED_FROM_LIST",
  session: {
    session_id: "ccs-new",
    status: "loaded",
    model_id: "gpt-5.5",
    role_slots: {}
  }
});

const rendered = JSON.parse(document.getElementById("codexCustomSessionResponse").textContent);
if (rendered.agent_alias_binding !== null) {
  throw new Error("stale alias binding leaked into new session: " + JSON.stringify(rendered));
}
if (
  rendered.alias_runtime_binding_present !== false ||
  rendered.alias_runtime_binding_proven !== false ||
  rendered.semantic_alias_routing_enabled !== false
) {
  throw new Error("stale alias proof leaked into new session: " + JSON.stringify(rendered));
}
if (rendered.alias_scope !== "server_runtime_binding_pending") {
  throw new Error("new session should require fresh server binding: " + JSON.stringify(rendered));
}
if (codexCustomAgentAliasBindingPacket !== null || codexCustomAgentAliasBindingSessionId !== "") {
  throw new Error("stale alias cache was not cleared on session swap");
}
`, sandbox);
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_c7_agent_alias_save_uses_runtime_bindings_before_session_aliases(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(value = "") {
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = value;
    this.lastElementChild = { textContent: "" };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
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
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

const nodes = {};
function node(id, value = "") {
  if (!nodes[id]) {
    nodes[id] = new Node(value);
  }
  return nodes[id];
}

[
  ["quickStartPrimaryAgentAliasInput", "Planner"],
  ["quickStartCodingAgentAliasInput", "Builder"],
  ["quickStartAgentOneAliasInput", "Lead"],
  ["quickStartAgentTwoAliasInput", "Worker"],
  ["quickStartExecutionModeSelect", "chatgpt_plus_api"],
  ["quickStartChatModelSelect", "gpt-5.5"],
  ["quickStartApiModelSelect", "wbp-deepseek-chat"],
  ["quickStartApiReasoningOptionSelect", "provider_declared_disabled"],
  ["codexCustomExecutionModeSelect", ""],
  ["codexCustomModelSelect", ""],
  ["codexCustomApiModelSelect", ""],
  ["codexCustomApiReasoningOptionSelect", ""],
  ["quickStartAgentAliasPacket", ""],
  ["quickStartAgentAliasScope", ""],
  ["quickStartAgentAliasPreview", ""],
  ["codexCustomSessionResponse", ""]
].forEach(([id, value]) => node(id, value));

const calls = [];
const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector(selector) {
      if (String(selector).startsWith("meta[")) {
        return { getAttribute() { return "test-token"; } };
      }
      return null;
    },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch: async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({ url: String(url), options, body });
    if (String(url) === "/api/codex/custom/agent-bindings") {
      return {
        ok: true,
        json: async () => ({
          status: "ok",
          machine_error_code: "OK",
          alias_scope: "server_agent_bindings",
          agent_bindings: body.agent_bindings,
          alias_to_agent_id: { Planner: "codex", Builder: "dip" },
          agent_id_to_route: { dip: "wbp-deepseek-chat" },
          allowed_api_route_ids: ["wbp-deepseek-chat"]
        })
      };
    }
    if (String(url) === "api/codex/custom/sessions/ccs-1/agent-aliases") {
      return {
        ok: true,
        json: async () => ({
          status: "ok",
          alias_scope: "session_aliases",
          alias_runtime_binding_present: false,
          alias_runtime_binding_proven: false,
          session: { session_id: "ccs-1" }
        })
      };
    }
    throw new Error("unexpected fetch: " + url);
  }
};

(async () => {
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
  await vm.runInContext(`
    (async () => {
      codexCustomSelectedSessionId = "ccs-1";
      await saveCodexCustomAgentAliasesFromUi();
    })()
  `, sandbox);

  if (calls.length !== 2) {
    throw new Error("expected runtime binding write then session alias write: " + JSON.stringify(calls));
  }
  if (calls[0].url !== "/api/codex/custom/agent-bindings") {
    throw new Error("first call was not runtime binding write: " + JSON.stringify(calls));
  }
  if (calls[1].url !== "api/codex/custom/sessions/ccs-1/agent-aliases") {
    throw new Error("second call was not selected-session alias write: " + JSON.stringify(calls));
  }
  const primary = calls[0].body.agent_bindings[0];
  const api = calls[0].body.agent_bindings[1];
  if (primary.agent_id !== "codex" || primary.lane !== "primary_chatgpt" || primary.model_id !== "gpt-5.5") {
    throw new Error("primary binding malformed: " + JSON.stringify(primary));
  }
  if (api.agent_id !== "dip" || api.lane !== "api_route" || api.route_id !== "wbp-deepseek-chat") {
    throw new Error("api binding malformed: " + JSON.stringify(api));
  }
  for (const alias of ["Planner", "Lead", "Codex", "Agent 1", "1"]) {
    if (!primary.aliases.includes(alias)) {
      throw new Error("missing primary alias " + alias + ": " + JSON.stringify(primary.aliases));
    }
  }
  for (const alias of ["Builder", "Worker", "DIP", "Agent 2", "2"]) {
    if (!api.aliases.includes(alias)) {
      throw new Error("missing api alias " + alias + ": " + JSON.stringify(api.aliases));
    }
  }
  const packetNode = node("quickStartAgentAliasPacket");
  if (packetNode.dataset.aliasScope !== "server_agent_bindings") {
    throw new Error("runtime binding packet did not keep metadata precedence: " + JSON.stringify(packetNode.dataset));
  }
  if (packetNode.dataset.aliasRuntimeBindingProven !== "true") {
    throw new Error("runtime binding proof lost after session save: " + JSON.stringify(packetNode.dataset));
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
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_c7_rejected_agent_runtime_binding_does_not_write_session_aliases(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(value = "") {
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = value;
    this.lastElementChild = { textContent: "" };
  }
  append(...nodes) {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
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
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

const nodes = {};
function node(id, value = "") {
  if (!nodes[id]) {
    nodes[id] = new Node(value);
  }
  return nodes[id];
}

[
  ["quickStartPrimaryAgentAliasInput", "Planner"],
  ["quickStartCodingAgentAliasInput", "Bui\u200blder"],
  ["quickStartAgentOneAliasInput", "Lead"],
  ["quickStartAgentTwoAliasInput", "Worker"],
  ["quickStartExecutionModeSelect", "chatgpt_plus_api"],
  ["quickStartChatModelSelect", "gpt-5.5"],
  ["quickStartApiModelSelect", "wbp-deepseek-chat"],
  ["quickStartApiReasoningOptionSelect", "provider_declared_disabled"],
  ["quickStartAgentAliasPacket", ""],
  ["quickStartAgentAliasScope", ""],
  ["quickStartAgentAliasPreview", ""]
].forEach(([id, value]) => node(id, value));

const calls = [];
const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement() { return new Node(); },
    addEventListener() {},
    querySelector(selector) {
      if (String(selector).startsWith("meta[")) {
        return { getAttribute() { return "test-token"; } };
      }
      return null;
    },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch: async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({ url: String(url), options, body });
    if (String(url) === "/api/codex/custom/agent-bindings") {
      return {
        ok: true,
        json: async () => ({
          status: "rejected",
          machine_error_code: "CUSTOM_AGENT_BINDINGS_INVALID",
          alias_scope: "server_agent_bindings",
          alias_runtime_binding_present: false,
          alias_runtime_binding_proven: false,
          semantic_alias_routing_enabled: false,
          blocking_reasons: ["binding_1_alias_0_forbidden_codepoint"],
          agent_bindings: body.agent_bindings,
          alias_to_agent_id: {},
          agent_id_to_route: {},
          allowed_api_route_ids: []
        })
      };
    }
    throw new Error("session alias write must not happen after rejected runtime binding: " + url);
  }
};

(async () => {
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
  await vm.runInContext(`
    (async () => {
      codexCustomSelectedSessionId = "ccs-rejected";
      await saveCodexCustomAgentAliasesFromUi();
    })()
  `, sandbox);

  if (calls.length !== 1 || calls[0].url !== "/api/codex/custom/agent-bindings") {
    throw new Error("rejected runtime binding should stop after one call: " + JSON.stringify(calls));
  }
  const packetNode = node("quickStartAgentAliasPacket");
  if (packetNode.dataset.aliasRuntimeBindingProven !== "false") {
    throw new Error("rejected runtime binding rendered as proven: " + JSON.stringify(packetNode.dataset));
  }
  const scopeNode = node("quickStartAgentAliasScope");
  if (scopeNode.lastElementChild.textContent !== "binding pending") {
    throw new Error("rejected runtime binding did not leave pending scope: " + scopeNode.lastElementChild.textContent);
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
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_wired_actions_stay_on_first_screen_and_do_not_cross_launch_paths(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        section = self._section_html(html, "quickStartScreen")

        for button_id in (
            "quickStartExecutionModeDryRunAction",
            "quickStartLaunchPreflightAction",
            "quickStartCustomLaunchAction",
            "quickStartShowCustomWindowAction",
        ):
            match = re.search(rf'<button id="{button_id}"[^>]*>', section)
            self.assertIsNotNone(match, button_id)
            button = match.group(0)
            self.assertNotIn("href=", button)
            self.assertNotIn("data-screen-link", button)
            self.assertNotIn("base_url", button)
            self.assertNotIn("api_key", button)
            self.assertNotIn("secret_ref", button)

        preflight_body = re.search(
            r"async function runQuickStartLaunchPreflight\(\) \{(?P<body>.*?)\n\}\n\nfunction renderCodexCustomShowWindow",
            js,
            re.S,
        )
        self.assertIsNotNone(preflight_body)
        preflight_js = preflight_body.group("body")
        self.assertIn('fetch("api/codex/custom/native-launch-preflight"', preflight_js)
        self.assertNotIn(
            'fetch("api/codex/custom/native-launch"',
            preflight_js.replace("native-launch-preflight", ""),
        )
        self.assertNotIn("setScreen(", preflight_js)
        self.assertIn("new_launch_started: false", preflight_js)
        self.assertIn("live_provider_called: false", preflight_js)

        admission_body = re.search(
            r"async function runQuickStartConfigAdmission\(buttonId = \"quickStartCheckApiAction\"\) \{(?P<body>.*?)\n\}\n\nasync function runQuickStartLaunchPreflight",
            js,
            re.S,
        )
        self.assertIsNotNone(admission_body)
        admission_js = admission_body.group("body")
        self.assertIn('fetch("api/codex/custom/quick-start/config-admission"', admission_js)
        self.assertNotIn('fetch("api/codex/custom/native-launch"', admission_js)
        self.assertNotIn("setScreen(", admission_js)
        self.assertIn("live_call_attempted: false", admission_js)
        self.assertIn("provider_called: false", admission_js)
        self.assertIn("silent_fallback_used: false", admission_js)

        show_body = re.search(
            r"async function showCodexCustomWindow\(\) \{(?P<body>.*?)\n\}\n\nasync function confirmCodexCustomVisibleHistory",
            js,
            re.S,
        )
        self.assertIsNotNone(show_body)
        show_js = show_body.group("body")
        self.assertIn('fetch("api/codex/custom/show-window"', show_js)
        self.assertNotIn('fetch("api/codex/custom/native-launch"', show_js)
        self.assertNotIn("setScreen(", show_js)
        self.assertIn("custom_window_visible: false", show_js)

    def test_quick_start_manual_check_snapshot_replays_after_snapshot_refresh(self) -> None:
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        self.assertIn("const QUICK_START_MANUAL_CHECK_REPLAY_MAX_AGE_MS", js)
        self.assertIn("function replayQuickStartManualCheckSnapshot()", js)
        self.assertIn(
            "function replayQuickStartManualCheckSnapshot() {\n  if (quickStartRouteProofResultLocked()) {\n    return;\n  }",
            js,
        )
        self.assertIn("function rememberQuickStartConfigAdmissionSnapshot", js)
        self.assertIn("function rememberQuickStartApiRouteCheckSnapshot", js)
        self.assertIn(
            "renderQuickStartConfigAdmission(admissionPacket, { remember: true, selectionPayload: payload });",
            js,
        )
        self.assertIn(
            "renderQuickStartApiRouteCheckResult(payload, actionOutcome, { remember: true });",
            js,
        )
        self.assertIn("manual_check_replay_active: replayed", js)
        self.assertIn("API_ROUTE_CHECK_ACTION_PACKET_REPLAYED", js)
        self.assertIn('routeOk && refreshOk && !replayed ? "green" : "amber"', js)
        self.assertIn('routeOk && refreshOk ? (replayed ? "cached OK" : "OK")', js)
        self.assertIn("quickStartChatgptRuntimeProofPending(packet)", js)
        self.assertIn('machineCode === "AUTH_UNAVAILABLE" ? "auth pending" : "runtime pending"', js)
        render_match = re.search(
            r"function renderQuickStart\(accountsSnapshot, apiSnapshot, source, fixtureState = \"unknown\"\) \{(?P<body>.*?)\n\}\n\nfunction setQuickStartChecklistChip",
            js,
            re.S,
        )
        self.assertIsNotNone(render_match)
        self.assertIn(
            "applyActionAvailability();\n  replayQuickStartManualCheckSnapshot();\n  applyActionAvailability();",
            render_match.group("body"),
        )

    def test_quick_start_auth_pending_and_replay_do_not_render_fake_green(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartLaunchState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartApiRouteChip",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartConfigAdmission({
  status: "ok",
  machine_error_code: "OK",
  final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
  execution_mode: "chatgpt_only",
  chatgpt_model: { status: "admitted", model_id: "gpt-5.5" },
  api_model: { status: "not_required", model_id: "" },
  api_reasoning: { status: "not_required", option_id: "" },
  api_route: { status: "not_required", route_reference: "" },
  launch_admission: "admitted",
  runtime_health_required_for_chatgpt_lane: true,
  runtime_health_gate: {
    status: "blocked",
    runtime_health_machine_error_code: "AUTH_UNAVAILABLE"
  },
  chatgpt_runtime_proof_status: "not_proven",
  chatgpt_runtime_proof_machine_error_code: "AUTH_UNAVAILABLE",
  dry_server_truth_only: true,
  live_call_attempted: false,
  provider_called: false,
  next_action: "none"
});
`, sandbox);

if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`auth-pending admission must not be green: ${node("quickStartLaunchState").className}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "auth pending") {
  throw new Error(`auth-pending admission label missing: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
let rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.runtime_readiness_claimed !== false || rendered.chatgpt_runtime_proof_status !== "not_proven") {
  throw new Error(`admission rendered runtime readiness incorrectly: ${JSON.stringify(rendered)}`);
}

vm.runInContext(`
renderQuickStartLaunchPreflight({
  status: "ok",
  machine_error_code: "OK",
  packet_kind: "custom_native_launch_preflight",
  execution_mode: "chatgpt_only",
  selected_model: "gpt-5.5",
  bridge_required: false,
  bridge_alive: false,
  custom_process_observed: false,
  config_status: "not_started",
  owner_authorization_phrase_present: true,
  runtime_health_required_for_chatgpt_lane: true,
  runtime_health_gate: {
    status: "blocked",
    runtime_health_machine_error_code: "AUTH_UNAVAILABLE"
  },
  chatgpt_runtime_proof_status: "not_proven",
  chatgpt_runtime_proof_machine_error_code: "AUTH_UNAVAILABLE",
  next_action: "launch_custom_codex"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`auth-pending preflight must not be green: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "auth pending") {
  throw new Error(`auth-pending preflight label missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.runtime_readiness_claimed !== false || rendered.chatgpt_runtime_proof_status !== "not_proven") {
  throw new Error(`preflight rendered runtime readiness incorrectly: ${JSON.stringify(rendered)}`);
}

sandbox.renderQuickStartApiRouteCheckResult(
  { execution_mode: "api_only", api_model_id: "wbp-deepseek-chat", api_reasoning_option_id: "catalog_default" },
  {
    payload: {
      status: "ok",
      machine_error_code: "OK",
      ui_action: "api_route_check",
      route_id: "wbp-deepseek-chat",
      result: {
        status: "ok",
        machine_error_code: "OK",
        changed_files: []
      }
    },
    refreshState: "complete"
  },
  { replayed: true, replayAgeMs: 42 }
);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`manual replay must not be fresh green: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "cached OK") {
  throw new Error(`manual replay cache label missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.manual_check_replay_active !== true || rendered.manual_check_replay_age_ms !== 42) {
  throw new Error(`manual replay metadata missing: ${JSON.stringify(rendered)}`);
}
if (rendered.runtime_readiness_claimed !== false) {
  throw new Error(`manual replay must not claim runtime readiness: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_refresh_button_updates_live_bridge_and_mixed_trace(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.disabled = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
  this.value = "";
}
Node.prototype.setAttribute = function(name, value) {
  if (name === "disabled") {
    this.disabled = true;
  }
  this[name] = value;
};
Node.prototype.removeAttribute = function(name) {
  if (name === "disabled") {
    this.disabled = false;
    return;
  }
  delete this[name];
};

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "refreshFixture",
  "sourcePicker",
  "statePicker",
  "quickStartRouteRefreshAction",
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartRouteResponse",
  "quickStartExecutionModeSelect",
  "quickStartChatModelSelect",
  "quickStartApiModelSelect",
  "quickStartApiReasoningOptionSelect"
]) {
  node(id);
}
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";
node("sourcePicker").value = "live";
node("statePicker").value = "summary";

const calls = [];
const responses = {
  "api/codex/custom/live-bridge-stability": {
    status: "ok",
    machine_error_code: "BRIDGE_READY",
    bridge_status: "BRIDGE_READY",
    execution_mode: "chatgpt_plus_api",
    bridge_alive: true,
    port_alive: true,
    responses_endpoint_available: true,
    launch_id_matches_trace: true,
    response_seen: true,
    next_action: "none"
  },
  "api/codex/custom/chatgpt-plus-api-coder-trace": {
    status: "blocked",
    machine_error_code: "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE",
    mixed_mode_product_decision: "UNSUPPORTED",
    mixed_mode_launch_action: "blocked",
    execution_mode: "chatgpt_plus_api",
    prompt_seen: false,
    coder_dispatch_proven: true,
    launch_proven: true,
    launch_status: "ok",
    launch_packet_stale: true,
    next_action: "run_fresh_chatgpt_plus_api_launch"
  }
};

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} },
    localStorage: {
      getItem() { return null; },
      setItem() {}
    }
  },
  URL,
  URLSearchParams,
  setTimeout(callback) {
    if (typeof callback === "function") {
      callback();
    }
    return 1;
  },
  clearTimeout() {},
  fetch: async (url) => {
    calls.push(url);
    return {
      ok: true,
      json: async () => responses[url] || { status: "ok" }
    };
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.refreshCodexCustomModelsPanel = async () => {
  calls.push("models");
};

sandbox.refreshQuickStartRouteStatus().then(() => {
  const expected = [
    "models",
    "api/codex/custom/live-bridge-stability",
    "api/codex/custom/chatgpt-plus-api-coder-trace"
  ];
  if (JSON.stringify(calls) !== JSON.stringify(expected)) {
    throw new Error(`refresh did not read live route truth in order: ${JSON.stringify(calls)}`);
  }
  if (node("quickStartRouteRefreshAction").disabled !== false) {
    throw new Error("refresh button stayed disabled");
  }
  if (node("refreshFixture").disabled !== false) {
    throw new Error("visible refresh button stayed disabled");
  }
  if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed stale") {
    throw new Error(`mixed trace did not override bridge-only status: ${node("quickStartRouteChip").lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
  if (rendered.machine_error_code !== "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE") {
    throw new Error(`mixed trace packet not rendered: ${node("quickStartRouteResponse").textContent}`);
  }
  if (rendered.bridge_status === "BRIDGE_READY" && rendered.mixed_route_truth_packet !== true) {
    throw new Error(`refresh ended on bridge-only truth: ${node("quickStartRouteResponse").textContent}`);
  }
  calls.length = 0;
  sandbox.setLiveReadonly = async () => {
    calls.push("live");
    return { status: "ok" };
  };
  sandbox.setFixtureState = async () => {
    calls.push("fixture");
    return { status: "ok" };
  };
  return sandbox.refreshCurrentSource();
}).then(() => {
  const expected = [
    "live",
    "models",
    "api/codex/custom/live-bridge-stability",
    "api/codex/custom/chatgpt-plus-api-coder-trace"
  ];
  if (JSON.stringify(calls) !== JSON.stringify(expected)) {
    throw new Error(`visible refresh did not read quick-start route truth: ${JSON.stringify(calls)}`);
  }
  if (node("refreshFixture").disabled !== false) {
    throw new Error("visible refresh button stayed disabled after source refresh");
  }
  if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed stale") {
    throw new Error(`visible refresh ended on wrong route status: ${node("quickStartRouteChip").lastElementChild.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_gap_preserves_launch_without_green_readiness(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  status: "ok",
  machine_error_code: "OK",
  final_status: "CUSTOM_CODEX_LAUNCH_STABILITY_AND_RECOVERY_WITH_LIMITS",
  execution_mode: "chatgpt_plus_api",
  chatgpt_model_id: "gpt-5.5",
  api_model_id: "wbp-deepseek-chat",
  selection_packet: {
    execution_mode: "chatgpt_plus_api",
    chatgpt_model_id: "gpt-5.5",
    api_model_id: "wbp-deepseek-chat"
  },
  launch_claim_scope: "custom_native_app_window_launch_only",
  launch_packet_is_truth_source: true,
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: true,
  expected_custom_identity_observed: true,
  native_window_observed: true,
  native_app_usable: true,
  real_codex_app_launched: true,
  bridge_alive: true,
  route_packet_matches_selection_packet: true,
  stable_bridge_preflight_status: "ok",
  stable_bridge_launch_allowed: true,
  next_action: "none"
});
`, sandbox);

if (!node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`setup launch should initially be green: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "запуск ok") {
  throw new Error(`setup launch label mismatch: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}

vm.runInContext(`
if (quickStartMixedLaunchAvailableWithTraceGap({
  mixed_mode_product_decision: "WORKS_WITH_LIMITS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_available_with_primary_trace_gap: true,
  launch_proven: true,
  api_route_dispatched_without_primary: true,
  primary_replaced_by_api_route: true,
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true
}) !== false) {
  throw new Error("forced primary replacement must not render as launch trace gap");
}
for (const launchEvidenceField of [
  "launch_evidence_proven_with_limits",
  "current_launch_evidence_proven_with_limits",
  "existing_window_reuse_proven_with_limits",
  "native_limited_launch_proven_with_limits"
]) {
  if (quickStartMixedLaunchAvailableWithTraceGap({
    mixed_mode_product_decision: "WORKS_WITH_LIMITS",
    mixed_mode_launch_action: "available",
    mixed_mode_launch_available_with_primary_trace_gap: true,
    launch_proven: false,
    [launchEvidenceField]: true,
    api_route_dispatched_without_primary: true,
    primary_replaced_by_api_route: true,
    chatgpt_replaced_by_api: false,
    coder_dispatch_proven: true,
    coder_work_result_proven_with_limits: true
  }) !== false) {
    throw new Error(launchEvidenceField + " must not bypass primary replacement guard");
  }
}
if (quickStartMixedLaunchAvailableWithTraceGap({
  mixed_mode_product_decision: "WORKS_WITH_LIMITS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_available_with_primary_trace_gap: true,
  launch_proven: false,
  launch_evidence_proven_with_limits: true,
  existing_window_reuse_proven_with_limits: true,
  api_route_dispatched_without_primary: true,
  primary_replaced_by_api_route: false,
  chatgpt_replaced_by_api: false,
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true
}) !== true) {
  throw new Error("limited launch evidence must render as launch trace gap");
}
renderQuickStartMixedCoderTrace({
  status: "degraded",
  machine_error_code: "DUAL_LANE_NATIVE_PROMPT_TRACE_NOT_SUPPORTED",
  final_status: "CHATGPT_PLUS_API_LAUNCH_PROVEN_PRIMARY_TRACE_NOT_PROVEN_WITH_LIMITS",
  mixed_mode_product_decision: "WORKS_WITH_LIMITS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_blocked_reason: "",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: false,
  launch_evidence_proven_with_limits: true,
  launch_status: "ok",
  launch_status_ok: true,
  slot_binding_proven: true,
  prompt_seen: false,
  prompt_seen_blocking_reason: "primary_chatgpt_request_absent_api_route_dispatched",
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true,
  deepseek_route_observed: true,
  api_route_dispatched_without_primary: true,
  direct_api_dispatch_without_primary_trace: true,
  native_mixed_primary_trace_supported: false,
  primary_trace_id_matches_launch: false,
  coder_trace_id_matches_launch: true,
  primary_replacement_trace_id_matches_launch: false,
  native_dual_lane_prompt_trace_missing: true,
  native_current_launch_single_executor_observed: true,
  runtime_executor_lane: "api_route_lane",
  runtime_executor_truth_source: "launch_packet",
  mixed_mode_actual_primary_executor_is_api_route: true,
  capability_proof_scope: "native_window_bridge_trace_current_launch",
  unsupported_evidence: {
    primary_prompt_record_seen: false,
    primary_trace_id_matches_launch: false,
    coder_record_seen: true,
    coder_trace_id_matches_launch: true,
    api_route_dispatched_without_primary: true,
    primary_replaced_by_api_route: false,
    native_current_launch_single_executor_observed: true,
    session_dispatch_probe_boundary_available: true,
    native_dual_lane_dispatcher_observed: false
  },
  fallback_used: false,
  primary_trace_proof_status: "not_proven",
  mixed_mode_launch_available_with_primary_trace_gap: true,
  runtime_readiness_claimed: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  existing_window_reuse_proven_with_limits: true,
  launch_origin: "existing_window",
  fresh_launch_started: false,
  next_action: "continue_in_existing_custom_window"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`trace gap must not claim full green readiness: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed limited") {
  throw new Error(`mixed launch label missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartExecutionModeState").lastElementChild.textContent !== "ChatGPT + API") {
  throw new Error(`mixed execution mode must remain visible: ${node("quickStartExecutionModeState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "старое окно") {
  throw new Error(`mixed launch must stay proven: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartChatSlotState").lastElementChild.textContent !== "primary не доказан") {
  throw new Error(`ChatGPT runtime proof blocker missing: ${node("quickStartChatSlotState").lastElementChild.textContent}`);
}
if (node("quickStartApiSlotState").lastElementChild.textContent !== "proven") {
  throw new Error(`DeepSeek proof should remain visible: ${node("quickStartApiSlotState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "existing window") {
  throw new Error(`next action label missing: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.machine_error_code !== "DUAL_LANE_NATIVE_PROMPT_TRACE_NOT_SUPPORTED") {
  throw new Error(`mixed blocker packet not rendered: ${JSON.stringify(rendered)}`);
}
if (rendered.launch_origin !== "existing_window" || rendered.fresh_launch_started !== false) {
  throw new Error(`existing-window launch origin missing: ${JSON.stringify(rendered)}`);
}
if (rendered.mixed_route_blocked !== false || rendered.runtime_readiness_claimed !== false) {
  throw new Error(`mixed route truth flags wrong: ${JSON.stringify(rendered)}`);
}
if (
  rendered.mixed_mode_product_decision !== "WORKS_WITH_LIMITS" ||
  rendered.mixed_mode_launch_action !== "available" ||
  rendered.mixed_mode_launch_blocked_reason !== "" ||
  rendered.primary_trace_proof_status !== "not_proven" ||
  rendered.mixed_mode_launch_available_with_primary_trace_gap !== true
) {
  throw new Error(`mixed product decision missing: ${JSON.stringify(rendered)}`);
}
if (rendered.prompt_seen !== false || rendered.coder_dispatch_proven !== true) {
  throw new Error(`lane proof split missing: ${JSON.stringify(rendered)}`);
}
if (
  rendered.primary_trace_id_matches_launch !== false ||
  rendered.coder_trace_id_matches_launch !== true ||
  rendered.primary_replacement_trace_id_matches_launch !== false
) {
  throw new Error(`trace identity split missing: ${JSON.stringify(rendered)}`);
}
if (
  rendered.native_dual_lane_prompt_trace_missing !== true ||
  rendered.native_current_launch_single_executor_observed !== true
) {
  throw new Error(`native unsupported evidence missing: ${JSON.stringify(rendered)}`);
}
if (
  rendered.runtime_executor_lane !== "api_route_lane" ||
  rendered.runtime_executor_truth_source !== "launch_packet" ||
  rendered.mixed_mode_actual_primary_executor_is_api_route !== true ||
  rendered.capability_proof_scope !== "native_window_bridge_trace_current_launch"
) {
  throw new Error(`runtime executor evidence missing: ${JSON.stringify(rendered)}`);
}
const expectedUnsupportedEvidence = {
  primary_prompt_record_seen: false,
  primary_trace_id_matches_launch: false,
  coder_record_seen: true,
  coder_trace_id_matches_launch: true,
  api_route_dispatched_without_primary: true,
  primary_replaced_by_api_route: false,
  native_current_launch_single_executor_observed: true,
  session_dispatch_probe_boundary_available: true,
  native_dual_lane_dispatcher_observed: false
};
if (JSON.stringify(rendered.unsupported_evidence) !== JSON.stringify(expectedUnsupportedEvidence)) {
  throw new Error(`unsupported evidence packet missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_gap_does_not_treat_launch_origin_as_reuse_proof(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartLaunchState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartMixedCoderTrace({
  status: "degraded",
  machine_error_code: "DUAL_LANE_NATIVE_PROMPT_TRACE_NOT_SUPPORTED",
  final_status: "CHATGPT_PLUS_API_LAUNCH_PROVEN_PRIMARY_TRACE_NOT_PROVEN_WITH_LIMITS",
  mixed_mode_product_decision: "WORKS_WITH_LIMITS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_blocked_reason: "",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: true,
  launch_status: "ok",
  launch_status_ok: true,
  prompt_seen: false,
  prompt_seen_blocking_reason: "primary_chatgpt_request_absent_api_route_dispatched",
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true,
  api_route_dispatched_without_primary: true,
  primary_replaced_by_api_route: false,
  primary_trace_proof_status: "not_proven",
  mixed_mode_launch_available_with_primary_trace_gap: true,
  runtime_readiness_claimed: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  existing_window_reuse_proven_with_limits: false,
  launch_origin: "existing_window",
  fresh_launch_started: false,
  next_action: "continue_in_existing_custom_window"
});
`, sandbox);

if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed limited") {
  throw new Error(`mixed route label changed: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "запуск ok") {
  throw new Error(`launch_origin alone must not render old-window reuse: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "existing window") {
  throw new Error(`next action label missing: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.launch_origin !== "existing_window") {
  throw new Error(`launch_origin should still be serialized: ${JSON.stringify(rendered)}`);
}
if (rendered.existing_window_reuse_proven_with_limits !== false) {
  throw new Error(`existing-window reuse proof should stay false: ${JSON.stringify(rendered)}`);
}
if (rendered.fresh_launch_started !== false) {
  throw new Error(`fresh launch flag should stay false: ${JSON.stringify(rendered)}`);
}
if (rendered.mixed_mode_launch_available_with_primary_trace_gap !== true) {
  throw new Error(`trace-gap availability should remain true: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_slot_binding_blocker_renders_diagnostic_json(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartMixedCoderTrace({
  status: "blocked",
  machine_error_code: "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  final_status: "KNOWN_BLOCKER_CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  mixed_mode_product_decision: "UNSUPPORTED",
  mixed_mode_launch_action: "blocked",
  mixed_mode_launch_blocked_reason: "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: false,
  launch_status: "blocked",
  launch_status_ok: false,
  native_window_observed: true,
  real_codex_app_launched: true,
  slot_binding_blocking_reasons: ["launch_status_not_ok"],
  slot_binding_proven: false,
  prompt_seen: false,
  prompt_seen_blocking_reason: "chatgpt_primary_trace_record_missing",
  coder_dispatch_proven: false,
  coder_work_result_proven_with_limits: false,
  deepseek_route_observed: false,
  deepseek_record_seen: true,
  api_route_dispatched_without_primary: false,
  direct_api_dispatch_without_primary_trace: false,
  native_mixed_primary_trace_supported: true,
  primary_trace_id_matches_launch: false,
  coder_trace_id_matches_launch: true,
  primary_replacement_trace_id_matches_launch: false,
  native_dual_lane_prompt_trace_missing: false,
  native_current_launch_single_executor_observed: false,
  runtime_executor_lane: "api_route_lane",
  runtime_executor_truth_source: "forced_bridge_route",
  mixed_mode_actual_primary_executor_is_api_route: true,
  capability_proof_scope: "native_window_bridge_trace_current_launch",
  unsupported_evidence: {
    primary_prompt_record_seen: false,
    primary_trace_id_matches_launch: false,
    coder_record_seen: true,
    coder_trace_id_matches_launch: true,
    api_route_dispatched_without_primary: false,
    primary_replaced_by_api_route: false,
    native_current_launch_single_executor_observed: false,
    session_dispatch_probe_boundary_available: true,
    native_dual_lane_dispatcher_observed: false
  },
  fallback_used: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  next_action: "inspect_slot_binding_launch_evidence"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`slot binding blocker must not be green: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "inspect slot") {
  throw new Error(`slot binding next action label missing: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "blocked") {
  throw new Error(`slot binding launch must be blocked: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartChatSlotState").lastElementChild.textContent !== "not proven") {
  throw new Error(`ChatGPT slot label mismatch: ${node("quickStartChatSlotState").lastElementChild.textContent}`);
}
if (node("quickStartApiSlotState").lastElementChild.textContent !== "not proven") {
  throw new Error(`API slot label mismatch: ${node("quickStartApiSlotState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.machine_error_code !== "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN") {
  throw new Error(`slot binding machine code not rendered: ${JSON.stringify(rendered)}`);
}
if (
  rendered.mixed_mode_product_decision !== "UNSUPPORTED" ||
  rendered.mixed_mode_launch_action !== "blocked" ||
  rendered.mixed_mode_launch_blocked_reason !== "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN" ||
  rendered.mixed_mode_launch_available_with_primary_trace_gap !== false
) {
  throw new Error(`slot binding product decision missing: ${JSON.stringify(rendered)}`);
}
if (
  rendered.launch_proven !== false ||
  rendered.launch_status !== "blocked" ||
  rendered.launch_status_ok !== false ||
  rendered.native_window_observed !== true ||
  rendered.real_codex_app_launched !== true
) {
  throw new Error(`launch proof split missing: ${JSON.stringify(rendered)}`);
}
if (JSON.stringify(rendered.slot_binding_blocking_reasons) !== JSON.stringify(["launch_status_not_ok"])) {
  throw new Error(`slot binding reasons missing: ${JSON.stringify(rendered)}`);
}
if (rendered.coder_trace_id_matches_launch !== true || rendered.unsupported_evidence?.coder_record_seen !== true) {
  throw new Error(`DeepSeek record evidence missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_missing_launch_context_requests_fresh_launch(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartLaunchState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartMixedCoderTrace({
  status: "blocked",
  machine_error_code: "CHATGPT_PLUS_API_LAUNCH_CONTEXT_MISSING",
  final_status: "KNOWN_BLOCKER_CHATGPT_PLUS_API_LAUNCH_CONTEXT_MISSING",
  mixed_mode_product_decision: "UNSUPPORTED",
  mixed_mode_launch_action: "blocked",
  mixed_mode_launch_blocked_reason: "CHATGPT_PLUS_API_LAUNCH_CONTEXT_MISSING",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "",
  coding_agent_model_id: "",
  launch_context_present: false,
  launch_context_missing: true,
  launch_context_missing_reason: "last_launch_packet_missing_or_empty",
  persisted_config_counts_as_launch_context: false,
  window_visibility_counts_as_launch_context: false,
  launch_proven: false,
  launch_status: "",
  launch_status_ok: false,
  slot_binding_blocking_reasons: ["launch_context_missing"],
  slot_binding_proven: false,
  prompt_seen: false,
  coder_dispatch_proven: false,
  coder_work_result_proven_with_limits: false,
  runtime_readiness_claimed: false,
  fallback_used: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  next_action: "run_fresh_chatgpt_plus_api_launch"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`missing context must not be green: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "launch context missing") {
  throw new Error(`missing context label mismatch: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartExecutionModeState").lastElementChild.textContent !== "ChatGPT + API") {
  throw new Error(`mixed mode label should remain visible: ${node("quickStartExecutionModeState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`missing launch context must not render launch green: ${node("quickStartLaunchState").className}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "context missing") {
  throw new Error(`missing launch context state missing: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "fresh launch") {
  throw new Error(`fresh launch next action missing: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.machine_error_code !== "CHATGPT_PLUS_API_LAUNCH_CONTEXT_MISSING" ||
  rendered.launch_context_present !== false ||
  rendered.launch_context_missing !== true ||
  rendered.launch_context_missing_reason !== "last_launch_packet_missing_or_empty"
) {
  throw new Error(`missing context diagnostics absent: ${JSON.stringify(rendered)}`);
}
if (
  rendered.persisted_config_counts_as_launch_context !== false ||
  rendered.window_visibility_counts_as_launch_context !== false ||
  rendered.runtime_readiness_claimed !== false
) {
  throw new Error(`missing context greenwash guard absent: ${JSON.stringify(rendered)}`);
}
if (JSON.stringify(rendered.slot_binding_blocking_reasons) !== JSON.stringify(["launch_context_missing"])) {
  throw new Error(`missing context reason absent: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_stale_launch_requests_fresh_launch(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartLaunchState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartMixedCoderTrace({
  status: "blocked",
  machine_error_code: "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE",
  final_status: "KNOWN_BLOCKER_CHATGPT_PLUS_API_LAUNCH_PACKET_STALE",
  mixed_mode_product_decision: "UNSUPPORTED",
  mixed_mode_launch_action: "blocked",
  mixed_mode_launch_blocked_reason: "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: true,
  launch_status: "ok",
  launch_status_ok: true,
  launch_packet_age_seconds: 6200,
  launch_packet_stale: true,
  trace_snapshot_age_seconds: 0,
  trace_snapshot_stale: false,
  current_launch_evidence_proven_with_limits: false,
  current_mixed_trace_evidence_fresh: false,
  native_window_observed: true,
  real_codex_app_launched: true,
  slot_binding_blocking_reasons: ["launch_packet_stale"],
  slot_binding_proven: false,
  prompt_seen: false,
  coder_dispatch_proven: false,
  coder_work_result_proven_with_limits: false,
  native_mixed_primary_trace_supported: true,
  fallback_used: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  next_action: "run_fresh_chatgpt_plus_api_launch"
});
`, sandbox);

if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed stale") {
  throw new Error(`stale route label mismatch: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartExecutionModeState").lastElementChild.textContent !== "ChatGPT + API") {
  throw new Error(`stale mixed mode should stay visible: ${node("quickStartExecutionModeState").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`stale launch must not be green: ${node("quickStartLaunchState").className}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "stale") {
  throw new Error(`stale launch label missing: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "fresh launch") {
  throw new Error(`fresh launch next action missing: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.machine_error_code !== "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE" ||
  rendered.launch_packet_stale !== true ||
  rendered.launch_packet_age_seconds !== 6200 ||
  rendered.current_launch_evidence_proven_with_limits !== false ||
  rendered.current_mixed_trace_evidence_fresh !== false
) {
  throw new Error(`stale launch diagnostics missing: ${JSON.stringify(rendered)}`);
}
if (rendered.launch_proven !== true || rendered.launch_status_ok !== true) {
  throw new Error(`raw launch proof should remain auditable: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_trace_stale_launch_override_keeps_launch_available(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartLaunchState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartMixedCoderTrace({
  status: "degraded",
  machine_error_code: "DUAL_LANE_NATIVE_PROMPT_TRACE_NOT_SUPPORTED",
  final_status: "CHATGPT_PLUS_API_LAUNCH_PROVEN_PRIMARY_TRACE_NOT_PROVEN_WITH_LIMITS",
  mixed_mode_product_decision: "WORKS_WITH_LIMITS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_blocked_reason: "",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: true,
  launch_status: "ok",
  launch_status_ok: true,
  launch_packet_age_seconds: 6200,
  launch_packet_stale: true,
  launch_packet_stale_overridden_by_current_bridge_trace: true,
  current_bridge_trace_matches_launch: true,
  current_provider_record_matches_launch: true,
  current_bridge_identity_bound_rebind_proven: false,
  bridge_identity_matches_launch: true,
  bridge_rebind_counts_as_provider_proof: false,
  trace_snapshot_age_seconds: 0,
  trace_snapshot_stale: false,
  current_launch_evidence_proven_with_limits: true,
  current_mixed_trace_evidence_fresh: true,
  native_window_observed: true,
  real_codex_app_launched: true,
  slot_binding_blocking_reasons: [],
  slot_binding_proven: true,
  prompt_seen: false,
  prompt_seen_blocking_reason: "primary_chatgpt_request_absent_api_route_dispatched",
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true,
  deepseek_route_observed: true,
  api_route_dispatched_without_primary: true,
  direct_api_dispatch_without_primary_trace: true,
  native_mixed_primary_trace_supported: false,
  primary_trace_id_matches_launch: false,
  coder_trace_id_matches_launch: true,
  fallback_used: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  mixed_mode_launch_available_with_primary_trace_gap: true,
  runtime_readiness_claimed: false,
  existing_window_reuse_proven_with_limits: true,
  launch_origin: "existing_window",
  fresh_launch_started: false,
  next_action: "continue_in_existing_custom_window"
});
`, sandbox);

if (node("quickStartRouteChip").lastElementChild.textContent !== "mixed limited") {
  throw new Error(`override route label must not be stale: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "старое окно") {
  throw new Error(`override launch label must stay proven: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartExecutionModeState").lastElementChild.textContent !== "ChatGPT + API") {
  throw new Error(`override mixed mode should stay visible: ${node("quickStartExecutionModeState").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "existing window") {
  throw new Error(`override next action label mismatch: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.launch_packet_stale !== true ||
  rendered.launch_packet_stale_overridden_by_current_bridge_trace !== true ||
  rendered.current_bridge_trace_matches_launch !== true ||
  rendered.current_provider_record_matches_launch !== true ||
  rendered.current_bridge_identity_bound_rebind_proven !== false ||
  rendered.bridge_identity_matches_launch !== true ||
  rendered.bridge_rebind_counts_as_provider_proof !== false ||
  rendered.current_launch_evidence_proven_with_limits !== true ||
  rendered.current_mixed_trace_evidence_fresh !== true
) {
  throw new Error(`override diagnostics missing: ${JSON.stringify(rendered)}`);
}
if (rendered.mixed_route_blocked !== false || rendered.mixed_mode_launch_action !== "available") {
  throw new Error(`override launch availability missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_mixed_blocked_button_runs_command_loop_proof(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.value = "";
  this.attributes = {};
  this.lastElementChild = { textContent: "" };
  this.buttonLabel = { textContent: "" };
  this.querySelector = (selector) => selector === "span" ? this.buttonLabel : null;
  this.append = (...nodes) => {
    for (const item of nodes) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  };
  this.replaceChildren = (...nodes) => {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  };
  this.setAttribute = (name, value) => { this.attributes[name] = value; };
  this.removeAttribute = (name) => { delete this.attributes[name]; };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartLaunchState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartRouteResponse",
  "quickStartCustomLaunchAction",
  "quickStartExecutionModeSelect",
  "quickStartChatModelSelect",
  "quickStartApiModelSelect",
  "quickStartApiReasoningOptionSelect",
  "quickStartPrimaryAgentAliasInput",
  "quickStartCodingAgentAliasInput",
  "quickStartAgentOneAliasInput",
  "quickStartAgentTwoAliasInput",
  "quickStartAgentAliasPacket",
  "quickStartAgentAliasScope",
  "quickStartAgentAliasPreview"
]) {
  node(id);
}
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "normal";
node("quickStartPrimaryAgentAliasInput").value = "Planner";
node("quickStartCodingAgentAliasInput").value = "Builder";
node("quickStartAgentOneAliasInput").value = "Lead";
node("quickStartAgentTwoAliasInput").value = "Worker";

const urls = [];
let traceFetchCount = 0;
const blockedPacket = {
  status: "blocked",
  machine_error_code: "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  final_status: "KNOWN_BLOCKER_CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  mixed_mode_product_decision: "UNSUPPORTED",
  mixed_mode_launch_action: "blocked",
  mixed_mode_launch_blocked_reason: "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN",
  execution_mode: "chatgpt_plus_api",
  primary_model_id: "gpt-5.5",
  coding_agent_model_id: "wbp-deepseek-chat",
  primary_model_slot: { status: "bound", lane: "codex_account_lane", model_id: "gpt-5.5" },
  coding_agent_model_slot: { status: "bound", lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
  launch_proven: false,
  launch_status: "blocked",
  launch_status_ok: false,
  native_window_observed: true,
  real_codex_app_launched: false,
  slot_binding_blocking_reasons: ["launch_status_not_ok", "real_codex_app_not_launched"],
  slot_binding_proven: false,
  prompt_seen: false,
  prompt_seen_blocking_reason: "chatgpt_primary_trace_record_missing",
  coder_dispatch_proven: false,
  coder_work_result_proven_with_limits: false,
  native_mixed_primary_trace_supported: true,
  fallback_used: false,
  next_action: "inspect_slot_binding_launch_evidence"
};
const dispatchNeededPacket = {
  ...blockedPacket,
  machine_error_code: "CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED",
  final_status: "KNOWN_BLOCKER_CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED",
  mixed_mode_launch_blocked_reason: "CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED",
  launch_proven: true,
  launch_status: "ok",
  launch_status_ok: true,
  real_codex_app_launched: true,
  slot_binding_blocking_reasons: [],
  slot_binding_proven: true,
  native_window_observed: true,
  runtime_readiness_claimed: false,
  next_action: "confirm_runtime_can_dispatch_coding_agent_model_slot"
};
const proofPacket = {
  ...dispatchNeededPacket,
  status: "ok",
  machine_error_code: "OK",
  final_status: "CHATGPT_PLUS_API_ROUTE_PROVEN_WITH_LIMITS",
  mixed_mode_product_decision: "WORKS",
  mixed_mode_launch_action: "available",
  mixed_mode_launch_blocked_reason: "",
  prompt_seen: true,
  primary_trace_proof_status: "proven",
  coder_dispatch_proven: true,
  coder_work_result_proven_with_limits: true,
  deepseek_route_observed: true,
  primary_trace_id_matches_launch: true,
  coder_trace_id_matches_launch: true,
  trace_launch_packet_matches: true,
  trace_id_matches_launch: true,
  runtime_executor_lane: "api_route_lane",
  runtime_executor_truth_source: "native_dual_lane_bridge",
  mixed_mode_actual_primary_executor_is_api_route: false,
  fallback_used: false,
  response_text_counts_as_model_truth: false,
  ui_label_counts_as_proof: false,
  native_dispatch_proof_attempted: true,
  native_ui_input_claimed: false,
  browser_trace_authority: false,
  raw_prompt_recorded: false,
  auth_header_recorded: false,
  secret_value_recorded: false,
  raw_backend_details_exposed: false,
  secret_value_exposed: false,
  runtime_readiness_claimed: true,
  next_action: "none"
};

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); },
    createElement() { return new Node(); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} },
    localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} }
  },
  URL,
  URLSearchParams,
  fetch(url, options = {}) {
    urls.push(url);
    const body = options.body ? JSON.parse(options.body) : {};
    if (url === "api/actions") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        action_phase: "full",
        actions: {
          launch_custom_client_native: {
            available: true,
            disabled_reason_code: "",
            availability_state: "enabled"
          }
        }
      }) });
    }
    if (url === "/api/codex/custom/agent-bindings") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        alias_scope: "server_agent_bindings",
        agent_bindings: body.agent_bindings,
        alias_to_agent_id: { Planner: "codex", Builder: "dip" },
        agent_id_to_route: { dip: "wbp-deepseek-chat" },
        allowed_api_route_ids: ["wbp-deepseek-chat"],
        next_action: "none"
      }) });
    }
    if (url === "api/codex/custom/gpt-api-alias-command-loop-proof") {
      if ("prompt" in body || "expected_text" in body || "expected_coding_response" in body) {
        throw new Error(`command-loop browser authority leaked: ${JSON.stringify(body)}`);
      }
      if (!String(body.request_id || "").startsWith("ui-command-loop-")) {
        throw new Error(`command-loop request id missing: ${JSON.stringify(body)}`);
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        final_status: "CUSTOM_CODEX_GPT_API_ALIAS_COMMAND_LOOP_PROVEN_WITH_LIMITS",
        primary_alias: "Planner",
        coding_alias: "Builder",
        primary_binding: { lane: "primary_chatgpt", role: "orchestrator", model_id: "gpt-5.5" },
        coding_binding: { lane: "api_route", role: "coding_agent", route_id: "wbp-deepseek-chat" },
        command_loop_proven: true,
        runtime_context_file_proven: true,
        primary_alias_resolved_from_context: true,
        coding_alias_resolved_from_context: true,
        primary_alias_bound_to_chatgpt_lane: true,
        coding_alias_bound_to_api_lane: true,
        primary_alias_precedes_coding_alias: true,
        reasoning_prerequisite_proven: true,
        api_lane_exact_token_matched: true,
        bridge_or_file_bridge_used: true,
        fallback_used: false,
        local_imitation_used: false,
        secret_value_exposed: false,
        browser_can_supply_route_authority: false,
        browser_can_supply_reasoning_authority: false,
        next_action: "none"
      }) });
    }
    if (url === "api/codex/custom/quick-start/config-admission") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
        execution_mode: "chatgpt_plus_api",
        chatgpt_model: { status: "admitted", model_id: "gpt-5.5" },
        api_model: { status: "admitted", model_id: "wbp-deepseek-chat" },
        api_reasoning: { status: "accepted", option_id: "normal" },
        api_route: { status: "admitted", route_reference: "server-owned-api-route" },
        launch_admission: "admitted",
        dry_server_truth_only: true,
        custom_codex_launch_attempted: false,
        new_launch_started: false,
        network_calls_made: false,
        live_call_attempted: false,
        provider_called: false,
        fallback_used: false,
        silent_fallback_used: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        raw_path_exposed: false,
        original_codex_touched: false,
        asar_touched: false,
        next_action: "native_launch_preflight"
      }) });
    }
    if (url === "api/codex/custom/native-launch-preflight") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        final_status: "CUSTOM_NATIVE_LAUNCH_PREFLIGHT_ADMITTED",
        execution_mode: "chatgpt_plus_api",
        selected_model: "gpt-5.5",
        route_model_id: "wbp-deepseek-chat",
        chatgpt_model_id: "gpt-5.5",
        api_model_id: "wbp-deepseek-chat",
        owner_authorization_phrase_present: true,
        bridge_required: true,
        bridge_alive: true,
        bridge_status: "running",
        custom_process_observed: false,
        window_status: "not_found",
        config_status: "admitted",
        new_launch_started: false,
        custom_codex_launch_attempted: false,
        live_call_attempted: false,
        provider_called: false,
        next_action: "native_launch"
      }) });
    }
    if (url === "api/codex/custom/native-launch") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        final_status: "CUSTOM_CODEX_NATIVE_LAUNCH_PROVEN_WITH_LIMITS",
        execution_mode: "chatgpt_plus_api",
        selected_model: "gpt-5.5",
        launch_model_id: "gpt-5.5",
        route_model_id: "wbp-deepseek-chat",
        chatgpt_model_id: "gpt-5.5",
        api_model_id: "wbp-deepseek-chat",
        running_status: true,
        isolated_home: true,
        isolated_codex_home: true,
        isolated_profile_dir: true,
        server_issued_model_list: true,
        wbp_endpoint_configured: true,
        browser_route_injection: false,
        browser_backend_injection: false,
        current_codex_touched: false,
        process_started: true,
        expected_custom_identity_observed: true,
        native_window_observed: true,
        native_app_usable: true,
        real_codex_app_launched: true,
        bridge_alive: true,
        stable_custom_codex_wbp_bridge_final_status: "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS",
        launch_claim_scope: "custom_native_app_window_launch_only",
        selection_packet: {
          execution_mode: "chatgpt_plus_api",
          chatgpt_model_id: "gpt-5.5",
          api_model_id: "wbp-deepseek-chat",
          api_reasoning_option_id: "normal",
          primary_model_slot: { lane: "codex_account_lane", model_id: "gpt-5.5" },
          coding_agent_model_slot: { lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
          dual_lane_slots_preserved: true,
          chatgpt_line_used_as_executor: false,
          api_line_used_as_executor: true,
          api_only_calls_chatgpt: false,
          chatgpt_only_calls_api: false
        },
        route_packet_matches_selection_packet: true,
        quick_start_launch_route_truth_proven_with_limits: true,
        config_status: "matches_last_launch",
        launch_packet_is_truth_source: true,
        new_launch_started: true,
        custom_codex_launch_attempted: true,
        live_call_attempted: true,
        provider_called: false,
        fallback_used: false,
        silent_fallback_used: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        raw_path_exposed: false,
        original_codex_touched: false,
        asar_touched: false,
        next_action: "none"
      }) });
    }
    if (url === "api/codex/custom/live-bridge-stability") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        bridge_status: "BRIDGE_READY",
        execution_mode: "chatgpt_plus_api",
        chatgpt_model_id: "gpt-5.5",
        api_model_id: "wbp-deepseek-chat",
        bridge_alive: true,
        port_alive: true,
        bridge_session_matches_active_window: true,
        trace_id_matches_launch: true,
        launch_id_matches_trace: true,
        old_window_answered: false,
        fallback_used: false,
        runtime_readiness_claimed: false,
        next_action: "none"
      }) });
    }
    if (url === "api/codex/custom/chatgpt-plus-api-coder-trace") {
      traceFetchCount += 1;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(traceFetchCount === 1 ? dispatchNeededPacket : proofPacket)
      });
    }
    if (url === "api/codex/custom/native-dispatch-proof") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(proofPacket) });
    }
    return Promise.reject(new Error(`unexpected fetch url ${url}`));
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
  actionMetadata = {
    launch_custom_client_native: {
      available: true,
      disabled_reason_code: "",
      availability_state: "enabled"
    }
  };
`, sandbox);
vm.runInContext(`renderQuickStartMixedCoderTrace(${JSON.stringify(blockedPacket)});`, sandbox);

if (node("quickStartCustomLaunchAction").buttonLabel.textContent !== "Проверить GPT+API") {
  throw new Error(`blocked mixed button label not applied: ${node("quickStartCustomLaunchAction").buttonLabel.textContent}`);
}
if (node("quickStartCustomLaunchAction").dataset.mixedModeLaunchBlocked !== "true") {
  throw new Error(`blocked mixed launch guard missing: ${JSON.stringify(node("quickStartCustomLaunchAction").dataset)}`);
}

sandbox.runQuickStartCustomLaunchAction().then(() => {
  const expected = [
    "api/actions",
    "/api/codex/custom/agent-bindings",
    "api/codex/custom/gpt-api-alias-command-loop-proof"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`blocked mixed click must run command-loop proof path: ${JSON.stringify(urls)}`);
  }
  const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
  if (
    rendered.execution_mode !== "chatgpt_plus_api" ||
    rendered.chatgpt_model_id !== "gpt-5.5" ||
    rendered.api_model_id !== "wbp-deepseek-chat" ||
    rendered.gpt_api_alias_command_loop_packet !== true ||
    rendered.command_loop_proven !== true ||
    rendered.runtime_context_file_proven !== true ||
    rendered.primary_alias !== "Planner" ||
    rendered.coding_alias !== "Builder" ||
    rendered.reasoning_prerequisite_proven !== true ||
    rendered.api_lane_exact_token_matched !== true ||
    rendered.launch_attempted !== false ||
    rendered.native_launch_attempted !== false ||
    rendered.runtime_readiness_claimed !== false
  ) {
    throw new Error(`command-loop truth missing: ${node("quickStartRouteResponse").textContent}`);
  }
  if (node("quickStartLaunchState").lastElementChild.textContent !== "loop ok") {
    throw new Error(`command-loop launch state not rendered: ${node("quickStartLaunchState").lastElementChild.textContent}`);
  }
  if (node("quickStartWindowState").lastElementChild.textContent !== "not launched") {
    throw new Error(`command-loop window state not bounded: ${node("quickStartWindowState").lastElementChild.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_config_admission_posts_bounded_selection_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.3-codex";
node("quickStartApiModelSelect").value = "wbp-deepseek-v3";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

let requestBody = null;
let routeCheckCall = null;
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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    if (url !== "api/codex/custom/quick-start/config-admission") {
      throw new Error(`unexpected fetch url ${url}`);
    }
    requestBody = JSON.parse(options.body);
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        status: "ok",
        machine_error_code: "OK",
        final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
        execution_mode: "chatgpt_plus_api",
        chatgpt_model: { status: "admitted", model_id: "gpt-5.3-codex" },
        api_model: { status: "admitted", model_id: "wbp-deepseek-v3" },
        api_reasoning: { status: "defaulted", option_id: "catalog_default" },
        api_route: { status: "admitted", route_reference: "server-owned-api-route" },
        launch_admission: "admitted",
        launch_admission_summary: "ok",
        dry_server_truth_only: true,
        fallback_used: false,
        silent_fallback_used: false,
        live_call_attempted: false,
        provider_called: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        raw_path_exposed: false,
        original_codex_touched: false,
        asar_touched: false
      })
    });
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.runUiAction = async (uiAction, extraPayload = {}) => {
  routeCheckCall = { uiAction, extraPayload };
  return {
    payload: {
      status: "ok",
      ui_action: "api_route_check",
      route_id: extraPayload.route_id,
      action_role: "api_route_smoke_check",
      post_action_refresh_required: true,
      result: {
        status: "ok",
        machine_error_code: "OK",
        human_message: "route check ok",
        next_action: "none",
        changed_files: []
      }
    },
    refreshState: "complete"
  };
};
sandbox.runQuickStartConfigAdmission("quickStartCheckApiAction").then(() => {
  const keys = Object.keys(requestBody).sort();
  const expected = ["api_model_id", "api_reasoning_option_id", "chatgpt_model_id", "execution_mode"];
  if (JSON.stringify(keys) !== JSON.stringify(expected)) {
    throw new Error(`unexpected admission body keys ${JSON.stringify(keys)}`);
  }
  for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
    if (JSON.stringify(requestBody).includes(forbidden)) {
      throw new Error(`forbidden browser field leaked into admission body: ${forbidden}`);
    }
  }
  if (requestBody.execution_mode !== "chatgpt_plus_api" || requestBody.api_model_id !== "wbp-deepseek-v3") {
    throw new Error(`selection body mismatch ${JSON.stringify(requestBody)}`);
  }
  if (!routeCheckCall) {
    throw new Error("API-capable quick start check did not run selected route check");
  }
  if (routeCheckCall.uiAction !== "api_route_check") {
    throw new Error(`wrong chained UI action ${routeCheckCall.uiAction}`);
  }
  if (routeCheckCall.extraPayload.route_id !== "wbp-deepseek-v3") {
    throw new Error(`wrong route check payload ${JSON.stringify(routeCheckCall.extraPayload)}`);
  }
  if (node("quickStartRouteChip").lastElementChild.textContent !== "OK") {
    throw new Error(`route chip did not show OK: ${node("quickStartRouteChip").lastElementChild.textContent}`);
  }
  const routeResponse = JSON.parse(node("quickStartRouteResponse").textContent);
  if (routeResponse.ui_action !== "api_route_check" || routeResponse.action_machine_error_code !== "OK") {
    throw new Error(`route action result not rendered in quick start response: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.route_id !== "wbp-deepseek-v3" || routeResponse.action_refresh_state !== "complete") {
    throw new Error(`route check truth fields missing: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.runtime_readiness_claimed !== false) {
    throw new Error("route check response must not claim runtime readiness");
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_config_admission_runs_selected_route_check_when_requested(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-v3";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

let requestBody = null;
let routeCheckCall = null;
let nativeLaunchFetchSeen = false;
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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    if (url.includes("native-launch")) {
      nativeLaunchFetchSeen = true;
      throw new Error(`selected route check must not launch native Codex: ${url}`);
    }
    if (url !== "api/codex/custom/quick-start/config-admission") {
      throw new Error(`unexpected fetch url ${url}`);
    }
    requestBody = JSON.parse(options.body);
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        status: "blocked",
        machine_error_code: "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED",
        final_status: "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN",
        execution_mode: "api_only",
        chatgpt_model: { status: "not_required", model_id: "" },
        api_model: { status: "admitted", model_id: "wbp-deepseek-v3" },
        api_reasoning: { status: "defaulted", option_id: "catalog_default" },
        api_route: {
          status: "not_confirmed",
          route_reference: "server-owned-api-route",
          machine_error_code: "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED",
          route_status_code: "validation_failed",
          validation_label: "validate failed"
        },
        launch_admission: "blocked",
        launch_admission_summary: "Selected API route needs route check.",
        dry_server_truth_only: true,
        fallback_used: false,
        silent_fallback_used: false,
        live_call_attempted: false,
        provider_called: false,
        custom_codex_launch_attempted: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        raw_path_exposed: false,
        original_codex_touched: false,
        asar_touched: false,
        next_action: "check_selected_api_route"
      })
    });
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.runUiAction = async (uiAction, extraPayload = {}) => {
  routeCheckCall = { uiAction, extraPayload };
  return {
    payload: {
      status: "command_error",
      machine_error_code: "PROVIDER_AUTH_FAILED",
      ui_action: "api_route_check",
      route_id: extraPayload.route_id,
      action_role: "api_route_smoke_check",
      post_action_refresh_required: true,
      result: {
        status: "error",
        machine_error_code: "PROVIDER_AUTH_FAILED",
        human_message: "provider auth failed",
        next_action: "provider_auth",
        changed_files: []
      }
    },
    refreshState: "complete"
  };
};
sandbox.runQuickStartConfigAdmission("quickStartCheckApiAction").then(() => {
  const keys = Object.keys(requestBody).sort();
  const expected = ["api_model_id", "api_reasoning_option_id", "chatgpt_model_id", "execution_mode"];
  if (JSON.stringify(keys) !== JSON.stringify(expected)) {
    throw new Error(`unexpected admission body keys ${JSON.stringify(keys)}`);
  }
  for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
    if (JSON.stringify(requestBody).includes(forbidden)) {
      throw new Error(`forbidden browser field leaked into admission body: ${forbidden}`);
    }
  }
  if (!routeCheckCall) {
    throw new Error("blocked admission with selected route check request did not run api_route_check");
  }
  if (routeCheckCall.uiAction !== "api_route_check") {
    throw new Error(`wrong chained UI action ${routeCheckCall.uiAction}`);
  }
  if (routeCheckCall.extraPayload.route_id !== "wbp-deepseek-v3") {
    throw new Error(`wrong route check payload ${JSON.stringify(routeCheckCall.extraPayload)}`);
  }
  if (nativeLaunchFetchSeen) {
    throw new Error("route check unexpectedly attempted native launch");
  }
  const routeResponse = JSON.parse(node("quickStartRouteResponse").textContent);
  if (routeResponse.ui_action !== "api_route_check" || routeResponse.action_machine_error_code !== "PROVIDER_AUTH_FAILED") {
    throw new Error(`provider blocker not rendered in quick start response: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.route_id !== "wbp-deepseek-v3" || routeResponse.api_route_status !== "blocked") {
    throw new Error(`selected route failure truth missing: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.runtime_readiness_claimed !== false) {
    throw new Error("route check response must not claim runtime readiness");
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_launch_preflight_runs_selected_route_check_when_requested(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

let preflightBody = null;
let routeCheckCall = null;
let nativeLaunchFetchSeen = false;
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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    if (url !== "api/codex/custom/native-launch-preflight") {
      if (url.includes("native-launch")) {
        nativeLaunchFetchSeen = true;
      }
      throw new Error(`unexpected fetch url ${url}`);
    }
    preflightBody = JSON.parse(options.body);
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        status: "blocked",
        machine_error_code: "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED",
        packet_kind: "custom_native_launch_preflight",
        execution_mode: "api_only",
        api_model_id: "wbp-deepseek-chat",
        api_reasoning_option_id: "catalog_default",
        chatgpt_model_id: "",
        selected_model: "wbp-deepseek-chat",
        selection_packet: {
          status: "blocked",
          machine_error_code: "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED",
          execution_mode: "api_only",
          chatgpt_model: { status: "not_required", model_id: "" },
          api_model: { status: "admitted", model_id: "wbp-deepseek-chat" },
          api_reasoning: { status: "defaulted", option_id: "catalog_default" },
          api_route: {
            status: "not_confirmed",
            route_reference: "server-owned-api-route",
            machine_error_code: "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED",
            route_status_code: "validation_failed",
            validation_label: "validate failed",
            validation_visual_state: "red"
          },
          launch_admission: "blocked",
          launch_admission_summary: "Selected API route needs route check.",
          fallback_used: false,
          silent_fallback_used: false,
          live_call_attempted: false,
          provider_called: false,
          custom_codex_launch_attempted: false,
          next_action: "check_selected_api_route"
        },
        show_window_attempted: false,
        new_launch_started: false,
        live_provider_called: false,
        fallback_used: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        raw_path_exposed: false,
        next_action: "check_selected_api_route"
      })
    });
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.runUiAction = async (uiAction, extraPayload = {}) => {
  routeCheckCall = { uiAction, extraPayload };
  return {
    payload: {
      status: "command_error",
      machine_error_code: "PROVIDER_AUTH_FAILED",
      ui_action: "api_route_check",
      route_id: extraPayload.route_id,
      action_role: "api_route_smoke_check",
      post_action_refresh_required: true,
      result: {
        status: "error",
        machine_error_code: "PROVIDER_AUTH_FAILED",
        human_message: "provider auth failed",
        next_action: "provider_auth",
        changed_files: []
      }
    },
    refreshState: "complete"
  };
};
sandbox.runQuickStartLaunchPreflight().then(() => {
  const keys = Object.keys(preflightBody).sort();
  const expected = ["api_model_id", "api_reasoning_option_id", "chatgpt_model_id", "execution_mode"];
  if (JSON.stringify(keys) !== JSON.stringify(expected)) {
    throw new Error(`unexpected preflight body keys ${JSON.stringify(keys)}`);
  }
  for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
    if (JSON.stringify(preflightBody).includes(forbidden)) {
      throw new Error(`forbidden browser field leaked into preflight body: ${forbidden}`);
    }
  }
  if (preflightBody.execution_mode !== "api_only" || preflightBody.api_model_id !== "wbp-deepseek-chat") {
    throw new Error(`preflight selection mismatch ${JSON.stringify(preflightBody)}`);
  }
  if (!routeCheckCall) {
    throw new Error("launch preflight selected route check request did not run api_route_check");
  }
  if (routeCheckCall.uiAction !== "api_route_check") {
    throw new Error(`wrong chained UI action ${routeCheckCall.uiAction}`);
  }
  if (routeCheckCall.extraPayload.route_id !== "wbp-deepseek-chat") {
    throw new Error(`wrong route check payload ${JSON.stringify(routeCheckCall.extraPayload)}`);
  }
  if (nativeLaunchFetchSeen) {
    throw new Error("route check unexpectedly attempted native launch");
  }
  const routeResponse = JSON.parse(node("quickStartRouteResponse").textContent);
  if (routeResponse.ui_action !== "api_route_check" || routeResponse.action_machine_error_code !== "PROVIDER_AUTH_FAILED") {
    throw new Error(`provider blocker not rendered in quick start response: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.route_id !== "wbp-deepseek-chat" || routeResponse.api_route_status !== "blocked") {
    throw new Error(`selected route failure truth missing: ${JSON.stringify(routeResponse)}`);
  }
  if (routeResponse.runtime_readiness_claimed !== false) {
    throw new Error("route check response must not claim runtime readiness");
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_launch_payload_uses_visible_quick_start_selects(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "gpt-5.3-codex";
node("quickStartApiModelSelect").value = "wbp-deepseek-v4-pro-max";
node("quickStartApiReasoningOptionSelect").value = "provider_declared_max";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("payload with visible API selection must not need selector refresh");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.buildCodexCustomLaunchSelectionPayload().then((payload) => {
  if (payload.execution_mode !== "api_only") {
    throw new Error(`wrong execution mode ${JSON.stringify(payload)}`);
  }
  if (payload.chatgpt_model_id !== "") {
    throw new Error(`api-only must not send ChatGPT model ${JSON.stringify(payload)}`);
  }
  if (payload.api_model_id !== "wbp-deepseek-v4-pro-max") {
    throw new Error(`visible API model was dropped ${JSON.stringify(payload)}`);
  }
  if (payload.api_reasoning_option_id !== "provider_declared_max") {
    throw new Error(`visible API reasoning was dropped ${JSON.stringify(payload)}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_preserves_visible_mixed_selection(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "provider_declared_disabled";
node("codexCustomExecutionModeSelect").value = "chatgpt_only";
node("codexCustomModelSelect").value = "gpt-5.3-codex";
node("codexCustomApiModelSelect").value = "wbp-deepseek-chat";
node("codexCustomApiReasoningOptionSelect").value = "provider_declared_disabled";

const storage = new Map();
const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("model render preservation test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.3-codex",
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

const payload = sandbox.quickStartLaunchPayloadFromSelects();
if (payload.execution_mode !== "chatgpt_plus_api") {
  throw new Error(`model refresh reset execution mode: ${JSON.stringify(payload)}`);
}
if (payload.chatgpt_model_id !== "gpt-5.5") {
  throw new Error(`model refresh reset ChatGPT model: ${JSON.stringify(payload)}`);
}
if (payload.api_model_id !== "wbp-deepseek-chat") {
  throw new Error(`model refresh reset API model: ${JSON.stringify(payload)}`);
}
if (node("codexCustomExecutionModeSelect").value !== "chatgpt_plus_api") {
  throw new Error(`master mode did not follow Quick Start: ${node("codexCustomExecutionModeSelect").value}`);
}
if (node("codexCustomModelSelect").value !== "gpt-5.5") {
  throw new Error(`master ChatGPT model did not follow Quick Start: ${node("codexCustomModelSelect").value}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_primary_launch_action_falls_back_to_projection_when_not_admitted(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.className = "";
    this.lastElementChild = { textContent: "" };
  }
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "gpt-5.3-codex";
node("quickStartApiModelSelect").value = "wbp-deepseek-v3";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

const urls = [];
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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options.body);
    for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
      if (JSON.stringify(body).includes(forbidden)) {
        throw new Error(`forbidden browser field leaked into projection body: ${forbidden}`);
      }
    }
    if (url === "api/codex/custom/quick-start/config-admission") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
          execution_mode: "api_only",
          chatgpt_model: { status: "not_required", model_id: "" },
          api_model: { status: "admitted", model_id: "wbp-deepseek-v3" },
          api_reasoning: { status: "defaulted", option_id: "catalog_default" },
          api_route: { status: "admitted", route_reference: "server-owned-api-route" },
          launch_admission: "admitted",
          launch_admission_summary: "Config admission ok; preflight remains separate.",
          dry_server_truth_only: true,
          custom_codex_launch_attempted: false,
          new_launch_started: false,
          network_calls_made: false,
          live_call_attempted: false,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/native-launch-preflight") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "blocked",
          machine_error_code: "OWNER_AUTHORIZATION_REQUIRED",
          human_message: "Owner authorization required.",
          final_status: "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
          execution_mode: "api_only",
          selected_model: "wbp-deepseek-v3",
          owner_authorization_phrase_present: false,
          preflight_claim_scope: "quick_start_launch_guard_no_live_mutation",
          bridge_required: true,
          bridge_alive: false,
          bridge_status: "not_started_or_down",
          custom_process_observed: false,
          window_status: "not_found",
          config_status: "no_previous_launch",
          show_window_attempted: false,
          custom_codex_launch_attempted: false,
          new_launch_started: false,
          network_calls_made: false,
          live_call_attempted: false,
          provider_called: false,
          live_provider_called: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "provide_exact_owner_authorization_phrase"
        })
      });
    }
    throw new Error(`unexpected fetch url ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
  actionMetadata = {
    launch_custom_client_native: {
      available: false,
      disabled_reason_code: "UI_ACTION_PHASE_NOT_ADMITTED",
      availability_state: "disabled_live_action"
    }
  };
`, sandbox);
sandbox.runQuickStartCustomLaunchAction().then(() => {
  const expected = [
    "api/actions",
    "api/codex/custom/quick-start/config-admission",
    "api/codex/custom/native-launch-preflight"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`unexpected projection fetches ${JSON.stringify(urls)}`);
  }
  if (urls.some((url) => url === "api/codex/custom/native-launch")) {
    throw new Error("quick-start projection called live native launch");
  }
  if (nodes.quickStartChatSlotState.lastElementChild.textContent !== "not required") {
    throw new Error(`chat slot not projected: ${nodes.quickStartChatSlotState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartApiSlotState.lastElementChild.textContent !== "admitted") {
    throw new Error(`api slot not projected: ${nodes.quickStartApiSlotState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartOwnerAuthState.lastElementChild.textContent !== "owner auth") {
    throw new Error(`owner auth not projected: ${nodes.quickStartOwnerAuthState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartLaunchState.className.includes("green")) {
    throw new Error(`owner-auth blocked preflight must not be green: ${nodes.quickStartLaunchState.className}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (rendered.owner_authorization_phrase_present !== false) {
    throw new Error(`owner auth truth missing: ${nodes.quickStartRouteResponse.textContent}`);
  }
  for (const field of ["custom_codex_launch_attempted", "new_launch_started", "network_calls_made", "live_call_attempted", "provider_called"]) {
    if (rendered[field] !== false) {
      throw new Error(`${field} must stay false in projection: ${nodes.quickStartRouteResponse.textContent}`);
    }
  }
  if (rendered.next_action !== "provide_exact_owner_authorization_phrase") {
    throw new Error(`next_action not preserved: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_mixed_launch_action_runs_command_loop_when_admitted(self) -> None:
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
    this.value = "";
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "normal";
node("quickStartPrimaryAgentAliasInput").value = "Planner";
node("quickStartCodingAgentAliasInput").value = "Builder";
node("quickStartAgentOneAliasInput").value = "Lead";
node("quickStartAgentTwoAliasInput").value = "Worker";

const urls = [];
const packets = [];
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
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options.body || "{}");
    if (url === "/api/codex/custom/agent-bindings") {
      packets.push(body);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          alias_scope: "server_agent_bindings",
          agent_bindings: body.agent_bindings,
          alias_to_agent_id: { Planner: "codex", Builder: "dip" },
          agent_id_to_route: { dip: "wbp-deepseek-chat" },
          allowed_api_route_ids: ["wbp-deepseek-chat"],
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/gpt-api-alias-command-loop-proof") {
      packets.push(body);
      if ("prompt" in body || "expected_text" in body || "expected_coding_response" in body) {
        throw new Error(`command-loop browser authority leaked: ${JSON.stringify(body)}`);
      }
      if (!String(body.request_id || "").startsWith("ui-command-loop-")) {
        throw new Error(`command-loop request id missing: ${JSON.stringify(body)}`);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_CODEX_GPT_API_ALIAS_COMMAND_LOOP_PROVEN_WITH_LIMITS",
          primary_alias: "Planner",
          coding_alias: "Builder",
          primary_binding: { lane: "primary_chatgpt", role: "orchestrator", model_id: "gpt-5.5" },
          coding_binding: { lane: "api_route", role: "coding_agent", route_id: "wbp-deepseek-chat" },
          command_loop_proven: true,
          runtime_context_file_proven: true,
          primary_alias_resolved_from_context: true,
          coding_alias_resolved_from_context: true,
          primary_alias_bound_to_chatgpt_lane: true,
          coding_alias_bound_to_api_lane: true,
          primary_alias_precedes_coding_alias: true,
          reasoning_prerequisite_proven: true,
          api_lane_exact_token_matched: true,
          bridge_or_file_bridge_used: true,
          fallback_used: false,
          local_imitation_used: false,
          secret_value_exposed: false,
          browser_can_supply_route_authority: false,
          browser_can_supply_reasoning_authority: false,
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/quick-start/config-admission") {
      packets.push(body);
      for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
        if (JSON.stringify(body).includes(forbidden)) {
          throw new Error(`forbidden browser field leaked into launch body: ${forbidden}`);
        }
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
          execution_mode: "chatgpt_plus_api",
          chatgpt_model: { status: "admitted", model_id: "gpt-5.5" },
          api_model: { status: "admitted", model_id: "wbp-deepseek-chat" },
          api_reasoning: { status: "accepted", option_id: "normal" },
          api_route: { status: "admitted", route_reference: "server-owned-api-route" },
          launch_admission: "admitted",
          dry_server_truth_only: true,
          custom_codex_launch_attempted: false,
          new_launch_started: false,
          network_calls_made: false,
          live_call_attempted: false,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "native_launch_preflight"
        })
      });
    }
    if (url === "api/codex/custom/native-launch-preflight") {
      packets.push(body);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_NATIVE_LAUNCH_PREFLIGHT_ADMITTED",
          execution_mode: "chatgpt_plus_api",
          selected_model: "gpt-5.5",
          route_model_id: "wbp-deepseek-chat",
          chatgpt_model_id: "gpt-5.5",
          api_model_id: "wbp-deepseek-chat",
          owner_authorization_phrase_present: true,
          bridge_required: true,
          bridge_alive: true,
          bridge_status: "running",
          custom_process_observed: false,
          window_status: "not_found",
          config_status: "admitted",
          new_launch_started: false,
          custom_codex_launch_attempted: false,
          live_call_attempted: false,
          provider_called: false,
          next_action: "native_launch"
        })
      });
    }
    if (url === "api/codex/custom/native-launch") {
      packets.push(body);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_CODEX_NATIVE_LAUNCH_PROVEN_WITH_LIMITS",
          execution_mode: "chatgpt_plus_api",
          selected_model: "gpt-5.5",
          launch_model_id: "gpt-5.5",
          route_model_id: "wbp-deepseek-chat",
          chatgpt_model_id: "gpt-5.5",
          api_model_id: "wbp-deepseek-chat",
          running_status: true,
          isolated_home: true,
          isolated_codex_home: true,
          isolated_profile_dir: true,
          server_issued_model_list: true,
          wbp_endpoint_configured: true,
          browser_route_injection: false,
          browser_backend_injection: false,
          current_codex_touched: false,
          process_started: true,
          expected_custom_identity_observed: true,
          native_window_observed: true,
          native_app_usable: true,
          real_codex_app_launched: true,
          bridge_alive: true,
          stable_custom_codex_wbp_bridge_final_status: "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS",
          launch_claim_scope: "custom_native_app_window_launch_only",
          selection_packet: {
            execution_mode: "chatgpt_plus_api",
            chatgpt_model_id: "gpt-5.5",
            api_model_id: "wbp-deepseek-chat",
            api_reasoning_option_id: "normal",
            primary_model_slot: { lane: "codex_account_lane", model_id: "gpt-5.5" },
            coding_agent_model_slot: { lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
            dual_lane_slots_preserved: true,
            chatgpt_line_used_as_executor: false,
            api_line_used_as_executor: true,
            api_only_calls_chatgpt: false,
            chatgpt_only_calls_api: false
          },
          route_packet_matches_selection_packet: true,
          quick_start_launch_route_truth_proven_with_limits: true,
          config_status: "matches_last_launch",
          launch_packet_is_truth_source: true,
          new_launch_started: true,
          custom_codex_launch_attempted: true,
          live_call_attempted: true,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/live-bridge-stability") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          bridge_status: "BRIDGE_READY",
          execution_mode: "chatgpt_plus_api",
          chatgpt_model_id: "gpt-5.5",
          api_model_id: "wbp-deepseek-chat",
          bridge_alive: true,
          port_alive: true,
          bridge_session_matches_active_window: true,
          trace_id_matches_launch: true,
          launch_id_matches_trace: true,
          old_window_answered: false,
          fallback_used: false,
          runtime_readiness_claimed: false,
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/chatgpt-plus-api-coder-trace") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CHATGPT_PLUS_API_NATIVE_TRACE_PROVEN_WITH_LIMITS",
          execution_mode: "chatgpt_plus_api",
          primary_model_id: "gpt-5.5",
          coding_agent_model_id: "wbp-deepseek-chat",
          primary_model_slot: { lane: "codex_account_lane", model_id: "gpt-5.5" },
          coding_agent_model_slot: { lane: "api_route_lane", model_id: "wbp-deepseek-chat" },
          mixed_mode_product_decision: "WORKS_WITH_LIMITS",
          mixed_mode_launch_action: "available",
          launch_proven: true,
          launch_status: "ok",
          launch_status_ok: true,
          launch_context_present: true,
          launch_context_missing: false,
          prompt_seen: true,
          primary_trace_proof_status: "proven",
          coder_dispatch_proven: true,
          coder_work_result_proven_with_limits: true,
          deepseek_route_observed: true,
          native_mixed_primary_trace_supported: true,
          native_window_observed: true,
          real_codex_app_launched: true,
          slot_binding_blocking_reasons: [],
          primary_trace_id_matches_launch: true,
          coder_trace_id_matches_launch: true,
          runtime_executor_lane: "api_route_lane",
          runtime_executor_truth_source: "forced_bridge_route",
          mixed_mode_actual_primary_executor_is_api_route: true,
          fallback_used: false,
          response_text_counts_as_model_truth: false,
          ui_label_counts_as_proof: false,
          runtime_readiness_claimed: false,
          next_action: "none"
        })
      });
    }
    throw new Error(`unexpected fetch url ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
  actionMetadata = {
    launch_custom_client_native: {
      available: true,
      disabled_reason_code: "",
      availability_state: "enabled"
    }
  };
  actionMetadataLoaded = true;
`, sandbox);
sandbox.runQuickStartCustomLaunchAction().then(() => {
  const expected = [
    "/api/codex/custom/agent-bindings",
    "api/codex/custom/gpt-api-alias-command-loop-proof"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`unexpected mixed command-loop fetches ${JSON.stringify(urls)}`);
  }
  if (urls.some((url) => String(url).includes("native-launch"))) {
    throw new Error(`mixed command-loop path must not call native launch: ${JSON.stringify(urls)}`);
  }
  if (packets.length !== 2) {
    throw new Error(`command-loop path did not write bindings and proof exactly once: ${JSON.stringify(packets)}`);
  }
  if (packets[0].agent_bindings[0].display_name !== "Planner" || packets[0].agent_bindings[1].display_name !== "Builder") {
    throw new Error(`agent binding payload did not carry aliases: ${JSON.stringify(packets[0])}`);
  }
  if (nodes.quickStartLaunchState.lastElementChild.textContent !== "loop ok") {
    throw new Error(`mixed command-loop label missing: ${nodes.quickStartLaunchState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartBridgeState.lastElementChild.textContent !== "жив") {
    throw new Error(`bridge state must render command-loop file bridge truth: ${nodes.quickStartBridgeState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartWindowState.lastElementChild.textContent !== "not launched") {
    throw new Error(`window state must stay bounded for command-loop proof: ${nodes.quickStartWindowState.lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (
    rendered.machine_error_code !== "OK" ||
    rendered.execution_mode !== "chatgpt_plus_api" ||
    rendered.chatgpt_model_id !== "gpt-5.5" ||
    rendered.api_model_id !== "wbp-deepseek-chat" ||
    rendered.gpt_api_alias_command_loop_packet !== true
  ) {
    throw new Error(`command-loop identity not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
  if (
    rendered.command_loop_proven !== true ||
    rendered.runtime_context_file_proven !== true ||
    rendered.primary_alias !== "Planner" ||
    rendered.coding_alias !== "Builder" ||
    rendered.primary_alias_bound_to_chatgpt_lane !== true ||
    rendered.coding_alias_bound_to_api_lane !== true ||
    rendered.reasoning_prerequisite_proven !== true ||
    rendered.api_lane_exact_token_matched !== true ||
    rendered.launch_attempted !== false ||
    rendered.native_launch_attempted !== false ||
    rendered.runtime_readiness_claimed !== false
  ) {
    throw new Error(`command-loop proof flags missing: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_free_text_action_runs_native_proof_endpoint(self) -> None:
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
    this.value = "";
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartProofRankChip",
  "quickStartProofModeRows",
  "quickStartProofReasoningRows",
  "quickStartProofAgentRows"
]) {
  node(id);
}
node("quickStartRouteResponse");
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "normal";
node("quickStartPrimaryAgentAliasInput").value = "Planner";
node("quickStartCodingAgentAliasInput").value = "Builder";
node("quickStartAgentOneAliasInput").value = "Lead";
node("quickStartAgentTwoAliasInput").value = "Worker";

const urls = [];
const packets = [];
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
  setTimeout,
  clearTimeout,
  AbortController,
  Date,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options?.body || "{}");
    packets.push(body);
    if (url === "/api/codex/custom/agent-bindings") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          alias_scope: "server_agent_bindings",
          agent_bindings: body.agent_bindings,
          alias_to_agent_id: { Planner: "codex", Builder: "dip" },
          agent_id_to_route: { dip: "wbp-deepseek-chat" },
          allowed_api_route_ids: ["wbp-deepseek-chat"],
          next_action: "none"
        })
      });
    }
    if (url === "api/codex/custom/native-natural-dip-command-proof") {
      if (Object.prototype.hasOwnProperty.call(body, "prompt")) {
        throw new Error(`native natural DIP endpoint must not receive browser-authored prompt: ${JSON.stringify(body)}`);
      }
      if (!String(body.request_id || "").startsWith("ui-native-natural-dip-")) {
        throw new Error(`native natural DIP request id missing: ${JSON.stringify(body)}`);
      }
      if (body.expected_coding_response !== `WBP_UI_NATURAL_DIP_OK_${body.request_id}`) {
        throw new Error(`native natural DIP expected token mismatch: ${JSON.stringify(body)}`);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_CODEX_SERVER_OWNED_NATURAL_DIP_COMMAND_PROVEN_WITH_LIMITS",
          packet_kind: "custom_codex_server_owned_natural_dip_command_proof",
          primary_alias: "Planner",
          coding_alias: "Builder",
          primary_binding: { lane: "primary_chatgpt", role: "orchestrator", model_id: "gpt-5.5" },
          coding_binding: { lane: "api_route", role: "coding_agent", route_id: "wbp-deepseek-chat" },
          native_free_chat_dip_command_packet: true,
          native_free_chat_dip_command_proven: true,
          server_owned_native_free_chat_command_path: true,
          native_free_chat_api_lane_proven: true,
          native_free_chat_custom_response_observed: true,
          native_free_chat_request_bound_digest_matched: true,
          native_free_chat_subagent_substitution_blocked: true,
          server_owned_natural_dip_command_packet: true,
          server_owned_natural_dip_command_proven: true,
          server_owned_natural_dip_command_path: true,
          server_owned_natural_command_prompt_source: "server_owned_builder",
          natural_dip_prompt_browser_supplied: false,
          natural_dip_prompt_text_recorded: false,
          api_bridge_transcript_observed: true,
          api_bridge_or_file_bridge_transcript_observed: true,
          custom_response_observed: true,
          browser_authority_contract_enforced: true,
          browser_prompt_authority_rejected: true,
          browser_can_supply_prompt_authority: false,
          browser_can_supply_route_authority: false,
          browser_can_supply_reasoning_authority: false,
          browser_model_authority: false,
          does_not_prove_universal_manual_chat_interception: true,
          universal_manual_chat_interception_proven: false,
          api_lane_truth_source: "server_gpt_api_command_loop_plus_custom_readback",
          native_window_observed: true,
          input_capable_ui_observed: true,
          input_text_insert_attempted: true,
          input_text_insert_succeeded: true,
          prompt_submitted: true,
          native_agent_proof_file_observed: true,
          native_agent_proof_file_valid: true,
          native_free_text_agent_context_sha_match: true,
          native_free_text_alias_routing_proven: true,
          native_free_text_command_loop_proven: true,
          native_free_text_tool_bridge_proven: true,
          native_free_text_observability_proven: true,
          native_submitter_trust_boundary_proven: true,
          native_free_text_activation_proven: true,
          native_free_text_tool_bridge_source: "native_agent_proof_file_plus_server_gpt_api_command_loop",
          native_agent_provider_call_directly_observed: false,
          custom_codex_response_text_read_proven: true,
          custom_response_exact_token_observed: true,
          custom_response_bound_to_request: true,
          custom_response_expected_sha256: "ui-native-free-text-hash",
          custom_response_expected_sha256_match: true,
          custom_response_observer_attempted: true,
          custom_response_observer_scan_performed: true,
          custom_response_text_read_without_storing: true,
          native_codex_subagent_used_as_dip: false,
          native_codex_subagent_absence_proven: true,
          command_loop_proven: true,
          runtime_context_file_proven: true,
          custom_codex_agent_runtime_context_proven: true,
          primary_alias_bound_to_chatgpt_lane: true,
          coding_alias_bound_to_api_lane: true,
          primary_alias_precedes_coding_alias: true,
          reasoning_prerequisite_proven: true,
          api_lane_exact_token_matched: true,
          bridge_or_file_bridge_used: true,
          fallback_used: false,
          local_imitation_used: false,
          prompt_text_recorded: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          proof_file_path_redacted: true,
          nested_packets_redacted: true,
          browser_can_supply_route_authority: false,
          browser_can_supply_reasoning_authority: false,
          next_action: "none"
        })
      });
    }
    throw new Error(`unexpected fetch url ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext("actionMetadataLoaded = true;", sandbox);
sandbox.runQuickStartNativeFreeTextCommandLoopProof().then(() => {
  const expected = [
    "/api/codex/custom/agent-bindings",
    "api/codex/custom/native-natural-dip-command-proof"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`unexpected native free-text fetches ${JSON.stringify(urls)}`);
  }
  if (packets.length !== 2) {
    throw new Error(`native free-text path did not write bindings and proof exactly once: ${JSON.stringify(packets)}`);
  }
  if (packets[0].agent_bindings[0].display_name !== "Planner" || packets[0].agent_bindings[1].display_name !== "Builder") {
    throw new Error(`agent binding payload did not carry aliases: ${JSON.stringify(packets[0])}`);
  }
  if (Object.prototype.hasOwnProperty.call(packets[1], "prompt")) {
    throw new Error(`native free-text body leaked browser prompt: ${JSON.stringify(packets[1])}`);
  }
  if (nodes.quickStartRouteChip.lastElementChild.textContent !== "natural DIP ok") {
    throw new Error(`native route label missing: ${nodes.quickStartRouteChip.lastElementChild.textContent}`);
  }
  if (nodes.quickStartLaunchState.lastElementChild.textContent !== "natural DIP ok") {
    throw new Error(`native launch label missing: ${nodes.quickStartLaunchState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartWindowState.lastElementChild.textContent !== "input ok") {
    throw new Error(`native window proof not rendered: ${nodes.quickStartWindowState.lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (
    rendered.machine_error_code !== "OK" ||
    rendered.execution_mode !== "chatgpt_plus_api" ||
    rendered.chatgpt_model_id !== "gpt-5.5" ||
    rendered.api_model_id !== "wbp-deepseek-chat" ||
    rendered.native_free_text_command_loop_packet !== true ||
    rendered.native_free_chat_dip_command_packet !== true ||
    rendered.native_free_chat_dip_command_proven !== true ||
    rendered.server_owned_native_free_chat_command_path !== true ||
    rendered.native_free_chat_api_lane_proven !== true ||
    rendered.native_free_chat_custom_response_observed !== true ||
    rendered.native_free_chat_request_bound_digest_matched !== true ||
    rendered.native_free_chat_subagent_substitution_blocked !== true ||
    rendered.server_owned_natural_dip_command_packet !== true ||
    rendered.server_owned_natural_dip_command_proven !== true ||
    rendered.server_owned_natural_dip_command_path !== true ||
    rendered.server_owned_natural_command_prompt_source !== "server_owned_builder" ||
    rendered.natural_dip_prompt_browser_supplied !== false ||
    rendered.natural_dip_prompt_text_recorded !== false ||
    rendered.api_bridge_transcript_observed !== true ||
    rendered.api_bridge_or_file_bridge_transcript_observed !== true ||
    rendered.custom_response_observed !== true ||
    rendered.browser_authority_contract_enforced !== true ||
    rendered.browser_prompt_authority_rejected !== true ||
    rendered.browser_can_supply_prompt_authority !== false ||
    rendered.browser_can_supply_route_authority !== false ||
    rendered.browser_can_supply_reasoning_authority !== false ||
    rendered.browser_model_authority !== false ||
    rendered.does_not_prove_universal_manual_chat_interception !== true ||
    rendered.universal_manual_chat_interception_proven !== false ||
    rendered.api_lane_truth_source !== "server_gpt_api_command_loop_plus_custom_readback" ||
    rendered.gpt_api_alias_command_loop_packet !== true
  ) {
    throw new Error(`native free-text identity not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
  if (
    rendered.native_free_text_command_loop_proven !== true ||
    rendered.native_free_text_tool_bridge_proven !== true ||
    rendered.native_free_text_observability_proven !== true ||
    rendered.native_submitter_trust_boundary_proven !== true ||
    rendered.native_window_observed !== true ||
    rendered.input_capable_ui_observed !== true ||
    rendered.input_text_insert_succeeded !== true ||
    rendered.prompt_submitted !== true ||
    rendered.native_agent_proof_file_valid !== true ||
    rendered.native_free_text_agent_context_sha_match !== true ||
    rendered.native_free_text_alias_routing_proven !== true ||
    rendered.command_loop_proven !== true ||
    rendered.runtime_context_file_proven !== true ||
    rendered.api_lane_exact_token_matched !== true ||
    rendered.launch_attempted !== false ||
    rendered.native_launch_attempted !== false ||
    rendered.runtime_readiness_claimed !== false ||
    rendered.native_agent_provider_call_directly_observed !== false ||
    rendered.custom_codex_response_text_read_proven !== true ||
    rendered.custom_response_exact_token_observed !== true ||
    rendered.custom_response_bound_to_request !== true ||
    rendered.custom_response_expected_sha256_match !== true ||
    rendered.custom_response_observer_attempted !== true ||
    rendered.custom_response_observer_scan_performed !== true ||
    rendered.custom_response_text_read_without_storing !== true ||
    rendered.native_codex_subagent_used_as_dip !== false ||
    rendered.native_codex_subagent_absence_proven !== true ||
    rendered.prompt_text_recorded !== false ||
    rendered.raw_backend_details_exposed !== false ||
    rendered.nested_packets_redacted !== true ||
    rendered.secret_value_exposed !== false
  ) {
    throw new Error(`native free-text proof flags missing: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_manual_free_chat_router_reality_stays_fail_closed(self) -> None:
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
    this.value = "";
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
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      item.parentNode = this;
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartProofRankChip",
  "quickStartProofModeRows",
  "quickStartProofReasoningRows",
  "quickStartProofAgentRows",
  "quickStartManualFreeChatRouterRealityAction"
]) {
  node(id);
}
node("quickStartRouteResponse");
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "deep";

const urls = [];
const packets = [];
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
  setTimeout,
  clearTimeout,
  AbortController,
  Date,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options?.body || "{}");
    packets.push(body);
    if (url !== "api/codex/custom/manual-free-chat-router-reality") {
      throw new Error(`unexpected manual-router fetch url ${url}`);
    }
    for (const forbidden of ["prompt", "route_id", "model_id", "api_reasoning_option_id", "expected_text"]) {
      if (Object.prototype.hasOwnProperty.call(body, forbidden)) {
        throw new Error(`manual-router body leaked ${forbidden}: ${JSON.stringify(body)}`);
      }
    }
    if (!String(body.request_id || "").startsWith("ui-manual-router-")) {
      throw new Error(`manual-router request id missing: ${JSON.stringify(body)}`);
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        status: "blocked",
        machine_error_code: "MANUAL_USER_PROMPT_NOT_OBSERVED",
        final_status: "CUSTOM_CODEX_MANUAL_FREE_CHAT_ROUTER_REALITY_NOT_PROVEN",
        packet_kind: "custom_codex_manual_free_chat_router_reality",
        request_id: body.request_id,
        manual_free_chat_router_reality_proven: false,
        manual_user_prompt_observed: false,
        manual_user_prompt_source: "not_observed",
        manual_user_prompt_digest_present: false,
        wbp_owned_router_hook_observed: false,
        router_hook_truth_source: "not_observable",
        router_hook_transcript_digest_present: false,
        native_free_chat_hook_status: "not_observable",
        native_free_chat_hook_machine_error_code: "NATIVE_FREE_CHAT_HOOK_NOT_OBSERVABLE",
        native_free_chat_hook_observed: false,
        native_free_chat_hook_truth_source: "not_observable",
        bridge_or_file_bridge_used: false,
        command_loop_provider_call_count: 0,
        api_lane_exact_token_matched: false,
        allowed_api_route_ids_enforced: false,
        api_lane_proven: false,
        codex_subagent_used_as_dip: false,
        native_codex_subagent_used_as_dip: false,
        server_owned_proof_counts_as_manual_router: false,
        server_owned_natural_proof_counts_as_manual_router: false,
        server_owned_proof_counts_as_native_free_chat_hook: false,
        server_owned_natural_proof_counts_as_native_free_chat_hook: false,
        server_owned_natural_dip_command_proven: true,
        browser_authority_contract_enforced: true,
        browser_prompt_authority_rejected: true,
        browser_can_supply_prompt_authority: false,
        browser_can_supply_route_authority: false,
        browser_can_supply_reasoning_authority: false,
        browser_model_authority: false,
        does_not_prove_universal_manual_chat_interception: true,
        universal_manual_chat_interception_proven: false,
        fallback_used: false,
        local_imitation_used: false,
        prompt_text_recorded: false,
        raw_prompt_recorded: false,
        raw_backend_details_exposed: false,
        secret_value_exposed: false,
        next_action: "manual_user_prompt_not_observed"
      })
    });
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext("actionMetadataLoaded = true;", sandbox);
sandbox.runQuickStartManualFreeChatRouterReality().then(() => {
  if (JSON.stringify(urls) !== JSON.stringify(["api/codex/custom/manual-free-chat-router-reality"])) {
    throw new Error(`unexpected manual-router fetches ${JSON.stringify(urls)}`);
  }
  if (packets.length !== 1) {
    throw new Error(`manual-router should perform one probe fetch: ${JSON.stringify(packets)}`);
  }
  if (nodes.quickStartRouteChip.className.includes("green")) {
    throw new Error(`manual-router reality must not render green: ${nodes.quickStartRouteChip.className}`);
  }
  if (nodes.quickStartRouteChip.lastElementChild.textContent !== "manual unseen") {
    throw new Error(`manual-router blocked label missing: ${nodes.quickStartRouteChip.lastElementChild.textContent}`);
  }
  if (nodes.quickStartWindowState.lastElementChild.textContent !== "not observable") {
    throw new Error(`manual-router hook label missing: ${nodes.quickStartWindowState.lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (
    rendered.machine_error_code !== "MANUAL_USER_PROMPT_NOT_OBSERVED" ||
    rendered.manual_free_chat_router_reality_packet !== true ||
    rendered.manual_free_chat_router_reality_proven !== false ||
    rendered.manual_user_prompt_observed !== false ||
    rendered.manual_user_prompt_source !== "not_observed" ||
    rendered.manual_user_prompt_digest_present !== false ||
    rendered.wbp_owned_router_hook_observed !== false ||
    rendered.router_hook_truth_source !== "not_observable" ||
    rendered.router_hook_transcript_digest_present !== false ||
    rendered.native_free_chat_hook_status !== "not_observable" ||
    rendered.native_free_chat_hook_machine_error_code !== "NATIVE_FREE_CHAT_HOOK_NOT_OBSERVABLE" ||
    rendered.native_free_chat_hook_observed !== false ||
    rendered.native_free_chat_hook_truth_source !== "not_observable" ||
    rendered.api_lane_proven !== false ||
    rendered.bridge_or_file_bridge_used !== false ||
    rendered.command_loop_provider_call_count !== 0 ||
    rendered.api_lane_exact_token_matched !== false ||
    rendered.allowed_api_route_ids_enforced !== false ||
    rendered.codex_subagent_used_as_dip !== false ||
    rendered.server_owned_proof_counts_as_manual_router !== false ||
    rendered.server_owned_natural_proof_counts_as_manual_router !== false ||
    rendered.server_owned_proof_counts_as_native_free_chat_hook !== false ||
    rendered.server_owned_natural_proof_counts_as_native_free_chat_hook !== false ||
	    rendered.server_owned_natural_dip_command_proven !== true ||
	    rendered.chatgpt_model_id !== "" ||
	    rendered.api_model_id !== "" ||
	    rendered.does_not_prove_universal_manual_chat_interception !== true ||
    rendered.universal_manual_chat_interception_proven !== false ||
    rendered.browser_can_supply_prompt_authority !== false ||
    rendered.browser_can_supply_route_authority !== false ||
    rendered.browser_model_authority !== false ||
    rendered.prompt_text_recorded !== false ||
    rendered.raw_prompt_recorded !== false ||
    rendered.raw_backend_details_exposed !== false ||
    rendered.secret_value_exposed !== false ||
    rendered.launch_attempted !== false ||
    rendered.native_launch_attempted !== false ||
    rendered.runtime_readiness_claimed !== false
  ) {
    throw new Error(`manual-router reality flags missing: ${nodes.quickStartRouteResponse.textContent}`);
  }
  sandbox.renderQuickStartManualFreeChatRouterReality({
    status: "blocked",
    machine_error_code: "MANUAL_FREE_CHAT_ROUTER_NOT_OBSERVABLE",
    packet_kind: "custom_codex_manual_free_chat_router_reality",
    manual_free_chat_router_reality_proven: false,
    manual_user_prompt_observed: true,
    manual_user_prompt_source: "wbp_owned_router_hook",
    manual_user_prompt_digest_present: true,
    wbp_owned_router_hook_observed: true,
    router_hook_truth_source: "wbp_owned_router_candidate",
    router_hook_transcript_digest_present: false,
    native_free_chat_hook_status: "with_limits",
    native_free_chat_hook_machine_error_code: "NATIVE_FREE_CHAT_HOOK_WITH_LIMITS",
    native_free_chat_hook_observed: false,
    native_free_chat_hook_truth_source: "wbp_owned_router_candidate",
    bridge_or_file_bridge_used: false,
    command_loop_provider_call_count: 0,
    api_lane_exact_token_matched: false,
    allowed_api_route_ids_enforced: false,
    api_lane_proven: false,
    codex_subagent_used_as_dip: false,
    native_codex_subagent_used_as_dip: false,
    server_owned_proof_counts_as_manual_router: false,
    server_owned_natural_proof_counts_as_manual_router: false,
    server_owned_proof_counts_as_native_free_chat_hook: false,
    server_owned_natural_proof_counts_as_native_free_chat_hook: false,
    browser_authority_contract_enforced: true,
    browser_prompt_authority_rejected: true,
    browser_can_supply_prompt_authority: false,
    browser_can_supply_route_authority: false,
    browser_can_supply_reasoning_authority: false,
    browser_model_authority: false,
    does_not_prove_universal_manual_chat_interception: true,
    universal_manual_chat_interception_proven: false,
    fallback_used: false,
    local_imitation_used: false,
    prompt_text_recorded: false,
    raw_prompt_recorded: false,
    raw_backend_details_exposed: false,
    secret_value_exposed: false,
    next_action: "manual_free_chat_router_not_observable"
  });
  if (!nodes.quickStartWindowState.className.includes("amber")) {
    throw new Error(`limited hook must stay amber: ${nodes.quickStartWindowState.className}`);
  }
  if (nodes.quickStartWindowState.lastElementChild.textContent !== "hook limited") {
    throw new Error(`limited hook label mismatch: ${nodes.quickStartWindowState.lastElementChild.textContent}`);
  }
  const limitedRendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (
    limitedRendered.native_free_chat_hook_status !== "with_limits" ||
    limitedRendered.native_free_chat_hook_observed !== false ||
    limitedRendered.server_owned_proof_counts_as_native_free_chat_hook !== false ||
    limitedRendered.server_owned_natural_proof_counts_as_native_free_chat_hook !== false
  ) {
    throw new Error(`limited hook fields missing: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_free_text_renderer_blocks_missing_agent_proof(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState"
]) {
  node(id);
}
node("quickStartRouteResponse");

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_AGENT_PROOF_INVALID" }) !== "proof invalid") {
  throw new Error("proof invalid blocker label missing");
}
if (quickStartNativeFreeTextWindowLabel({
  machine_error_code: "CUSTOM_NATIVE_AGENT_PROOF_INVALID",
  native_window_observed: true,
  input_capable_ui_observed: true,
  prompt_submitted: true,
  native_agent_proof_file_valid: false
}) !== "proof invalid") {
  throw new Error("proof invalid window label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_ACTIVATION_NOT_CONFIGURED" }) !== "activation missing") {
  throw new Error("activation missing blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_AUTH_WALL_OBSERVED" }) !== "auth wall") {
  throw new Error("auth wall blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_KEYCHAIN_OR_PERMISSION_PROMPT" }) !== "permission prompt") {
  throw new Error("permission prompt blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_RENDERER_NO_INPUT_SURFACE" }) !== "input missing") {
  throw new Error("renderer no input blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_AUTH_PASSED_INPUT_READY" }) !== "input ready") {
  throw new Error("input ready blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_RESUME_AFTER_AUTH_READY" }) !== "resume ready") {
  throw new Error("resume ready blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN" }) !== "observer missing") {
  throw new Error("observer missing blocker label missing");
}
if (quickStartNativeFreeTextBlockerLabel({ machine_error_code: "CUSTOM_NATIVE_FREE_TEXT_CODEX_SUBAGENT_USED_AS_DIP" }) !== "sub-agent fail") {
  throw new Error("sub-agent fail blocker label missing");
}
renderQuickStartNativeFreeTextCommandLoopProof({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_AGENT_PROOF_FILE_MISSING",
  final_status: "CUSTOM_CODEX_NATIVE_FREE_TEXT_COMMAND_LOOP_NOT_PROVEN",
  primary_alias: "Planner",
  coding_alias: "Builder",
  native_window_observed: true,
  input_capable_ui_observed: true,
  input_text_insert_attempted: true,
  input_text_insert_succeeded: true,
  prompt_submitted: true,
  native_agent_proof_file_observed: false,
  native_agent_proof_file_valid: false,
  native_free_text_agent_context_sha_match: false,
  native_free_text_alias_routing_proven: false,
  native_free_text_command_loop_proven: false,
  native_free_text_tool_bridge_proven: false,
  native_free_text_observability_proven: false,
  native_submitter_trust_boundary_proven: false,
  native_agent_provider_call_directly_observed: false,
  custom_codex_response_text_read_proven: false,
  custom_response_exact_token_observed: false,
  custom_response_bound_to_request: false,
  custom_response_expected_sha256_match: false,
  custom_response_observer_attempted: false,
  custom_response_observer_scan_performed: false,
  custom_response_text_read_without_storing: false,
  native_codex_subagent_used_as_dip: false,
  native_codex_subagent_absence_proven: false,
  command_loop_proven: false,
  runtime_context_file_proven: false,
  api_lane_exact_token_matched: false,
  bridge_or_file_bridge_used: false,
  fallback_used: false,
  local_imitation_used: false,
  prompt_text_recorded: false,
  secret_value_exposed: false,
  nested_packets_redacted: true,
  next_action: "stop_and_diagnose_native_free_text_command_loop"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`missing native proof must not render green route chip: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`missing native proof must not render green launch chip: ${node("quickStartLaunchState").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "proof missing") {
  throw new Error(`proof missing label missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.native_free_text_command_loop_packet !== true ||
  rendered.native_free_text_command_loop_proven !== false ||
  rendered.native_free_text_tool_bridge_proven !== false ||
  rendered.native_free_text_observability_proven !== false ||
  rendered.native_submitter_trust_boundary_proven !== false ||
  rendered.native_agent_proof_file_valid !== false ||
  rendered.native_agent_provider_call_directly_observed !== false ||
  rendered.custom_codex_response_text_read_proven !== false ||
  rendered.custom_response_exact_token_observed !== false ||
  rendered.custom_response_bound_to_request !== false ||
  rendered.custom_response_expected_sha256_match !== false ||
  rendered.custom_response_observer_attempted !== false ||
  rendered.custom_response_observer_scan_performed !== false ||
  rendered.custom_response_text_read_without_storing !== false ||
  rendered.native_codex_subagent_used_as_dip !== false ||
  rendered.native_codex_subagent_absence_proven !== false ||
  rendered.command_loop_proven !== false ||
  rendered.runtime_context_file_proven !== false ||
  rendered.prompt_submitted !== true ||
  rendered.prompt_text_recorded !== false ||
  rendered.nested_packets_redacted !== true ||
  rendered.secret_value_exposed !== false
) {
  throw new Error(`missing native proof flags not preserved: ${node("quickStartRouteResponse").textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_reasoning_matrix_blocks_partial_api_as_combined_success(
        self,
    ) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState"
]) {
  node(id);
}
node("quickStartRouteResponse");

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartModelReasoningAvailabilityMatrix({
  packet_kind: "model_reasoning_availability_matrix_truth",
  captured_at_utc: "2026-01-01T00:00:00Z",
  request_id: "ui-matrix-test",
  status: "blocked",
  machine_error_code: "COMBINED_MODE_BLOCKED_NATIVE_AUTH",
  final_status: "MODEL_REASONING_AVAILABILITY_MATRIX_NOT_PROVEN",
  execution_mode: "chatgpt_plus_api",
  allowed_browser_fields: ["api_model_id", "api_reasoning_option_id", "chatgpt_model_id", "execution_mode", "request_id"],
  forbidden_fields: [],
  forbidden_fields_redacted: true,
  forbidden_field_count: 0,
  forbidden_field_categories: [],
  matrix_rows: [
    { execution_mode: "chatgpt_only", intelligence_measured: false, not_intelligence_proof: true },
    { execution_mode: "api_only", intelligence_measured: false, not_intelligence_proof: true },
    { execution_mode: "chatgpt_plus_api", intelligence_measured: false, not_intelligence_proof: true }
  ],
  reasoning_level_rows: [
    { operator_level: "fast", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true },
    { operator_level: "high", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true },
    { operator_level: "max", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true }
  ],
  proof_rank: "api_reasoning_live_only",
  proof_rank_score: 70,
  proof_rank_status: "partial",
  proof_rank_label: "API live; ChatGPT native not proven",
  proof_rank_counts_as_full_success: false,
  proof_rank_machine_error_code: "COMBINED_MODE_BLOCKED_NATIVE_AUTH",
  proof_mode_rows: [
    { proof_axis: "execution_mode", execution_mode: "chatgpt_only", display_name: "ChatGPT", status: "blocked", proof_level: "CUSTOM_NATIVE_AUTH_WALL_OBSERVED", counts_as_full_success: false, counts_as_partial_api_success: false },
    { proof_axis: "execution_mode", execution_mode: "api_only", display_name: "API / DeepSeek", status: "ok", proof_level: "LIVE_API_FORMAT_PROVEN", counts_as_full_success: false, counts_as_partial_api_success: true },
    { proof_axis: "execution_mode", execution_mode: "chatgpt_plus_api", display_name: "ChatGPT + API", status: "blocked", proof_level: "COMBINED_MODE_BLOCKED_NATIVE_AUTH", counts_as_full_success: false, counts_as_partial_api_success: false }
  ],
  proof_reasoning_rows: [
    { proof_axis: "api_reasoning_level", operator_level: "fast", status: "ok", proof_level: "LIVE_API_FORMAT_PROVEN", provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, counts_as_intelligence_proof: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true },
    { proof_axis: "api_reasoning_level", operator_level: "high", status: "ok", proof_level: "LIVE_API_FORMAT_PROVEN", provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, counts_as_intelligence_proof: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true },
    { proof_axis: "api_reasoning_level", operator_level: "max", status: "ok", proof_level: "LIVE_API_FORMAT_PROVEN", provider_reasoning_proof_level: "PROVIDER_DECLARED_REASONING_LEVEL_PROVEN", provider_declared_reasoning_level_proven: true, reasoning_level_access_proven: true, provider_reasoning_level_source: "provider_spec_and_live_call", counts_as_provider_level_proof: true, counts_as_independent_quality_benchmark: false, counts_as_intelligence_proof: false, independent_quality_benchmark_proven: false, benchmark_required_for_provider_level_proof: false, quality_benchmark_status: "not_required_for_provider_level_proof", intelligence_measured: false, not_intelligence_proof: true }
  ],
  proof_agent_rows: [
    { proof_axis: "agent_slot", agent_slot: "primary_model_slot", display_name: "Planner", aliases: ["Planner", "Agent 1", "1"], status: "ok", proof_level: "ALIAS_BINDING_PROVEN", native_execution_proven: false, display_aliases_are_separate_agents: false },
    { proof_axis: "agent_slot", agent_slot: "coding_agent_model_slot", display_name: "Builder", aliases: ["Builder", "Agent 2", "2"], status: "ok", proof_level: "LIVE_API_FORMAT_PROVEN", api_route_execution_proven: true, display_aliases_are_separate_agents: false }
  ],
  display_aliases_are_runtime_aliases: true,
  display_aliases_are_separate_agents: false,
  chatgpt_lane_proven: false,
  api_lane_proven: true,
  alias_binding_proven: true,
  combined_full_proven: false,
  partial_api_lane_proven: true,
  combined_status_counts_as_full_success: false,
  api_success_counts_as_combined_success: false,
  native_auth_wall_observed: true,
  native_execution_proven: false,
  reasoning_dispatch_matrix_proven: true,
  provider_declared_reasoning_levels_proven: true,
  provider_reasoning_level_source: "provider_spec_and_live_call",
  provider_reasoning_level_proof_count: 3,
  provider_reasoning_level_expected_count: 3,
  independent_quality_benchmark_proven: false,
  benchmark_required_for_provider_level_proof: false,
  quality_benchmark_status: "not_required_for_provider_level_proof",
  command_loop_proven: true,
  runtime_context_file_proven: true,
  primary_alias_bound_to_chatgpt_lane: true,
  coding_alias_bound_to_api_lane: true,
  api_lane_exact_token_matched: true,
  file_bridge_acceptance_proven: true,
  agent_alias_route_acceptance_proven: true,
  allowed_api_route_ids_enforced: true,
  forbidden_stale_route_ids_enforced: true,
  bridge_or_file_bridge_used: true,
  command_loop_route_authority_proven: true,
  command_loop_provider_call_count: 1,
  reasoning_provider_call_count: 3,
  browser_can_supply_route_authority: false,
  browser_can_supply_reasoning_authority: false,
  browser_model_authority: false,
  api_reasoning_operator_level: "max",
  fallback_used: false,
  local_imitation_used: false,
  secret_value_exposed: false,
  raw_backend_details_exposed: false,
  intelligence_measured: false,
  not_intelligence_proof: true,
  next_action: "stop_and_diagnose_model_reasoning_matrix"
});
`, sandbox);

if (node("quickStartRouteChip").className.includes("green")) {
  throw new Error(`partial API matrix must not render green route chip: ${node("quickStartRouteChip").className}`);
}
if (node("quickStartLaunchState").className.includes("green")) {
  throw new Error(`partial API matrix must not render green launch chip: ${node("quickStartLaunchState").className}`);
}
if (!node("quickStartApiSlotState").className.includes("green")) {
  throw new Error(`API lane proof should remain visible: ${node("quickStartApiSlotState").className}`);
}
if (node("quickStartChatSlotState").className.includes("green")) {
  throw new Error(`auth wall ChatGPT lane must not render green: ${node("quickStartChatSlotState").className}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "auth wall") {
  throw new Error(`matrix auth wall label missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (!node("quickStartProofRankChip").className.includes("amber")) {
  throw new Error(`partial rank chip must be amber: ${node("quickStartProofRankChip").className}`);
}
if (node("quickStartProofRankChip").lastElementChild.textContent !== "API live; ChatGPT native not proven") {
  throw new Error(`partial rank label missing: ${node("quickStartProofRankChip").lastElementChild.textContent}`);
}
if (!node("quickStartProofModeRows").textContent.includes("API / DeepSeek")) {
  throw new Error(`mode proof row missing API lane: ${node("quickStartProofModeRows").textContent}`);
}
if (!node("quickStartProofReasoningRows").textContent.includes("fast")) {
  throw new Error(`reasoning proof rows missing levels: ${node("quickStartProofReasoningRows").textContent}`);
}
if (!node("quickStartProofAgentRows").textContent.includes("Agent 1")) {
  throw new Error(`agent proof rows missing display aliases: ${node("quickStartProofAgentRows").textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.model_reasoning_availability_matrix_packet !== true ||
  rendered.api_lane_proven !== true ||
  rendered.chatgpt_lane_proven !== false ||
  rendered.combined_full_proven !== false ||
  rendered.partial_api_lane_proven !== true ||
  rendered.combined_status_counts_as_full_success !== false ||
  rendered.api_success_counts_as_combined_success !== false ||
  rendered.native_auth_wall_observed !== true ||
  rendered.native_execution_proven !== false ||
  rendered.reasoning_dispatch_matrix_proven !== true ||
  rendered.provider_declared_reasoning_levels_proven !== true ||
  rendered.provider_reasoning_level_source !== "provider_spec_and_live_call" ||
  rendered.provider_reasoning_level_proof_count !== 3 ||
  rendered.provider_reasoning_level_expected_count !== 3 ||
  rendered.independent_quality_benchmark_proven !== false ||
  rendered.benchmark_required_for_provider_level_proof !== false ||
  rendered.quality_benchmark_status !== "not_required_for_provider_level_proof" ||
  rendered.runtime_readiness_claimed !== false ||
  rendered.file_bridge_acceptance_proven !== true ||
  rendered.agent_alias_route_acceptance_proven !== true ||
  rendered.allowed_api_route_ids_enforced !== true ||
  rendered.forbidden_stale_route_ids_enforced !== true ||
  rendered.bridge_or_file_bridge_used !== true ||
  rendered.command_loop_route_authority_proven !== true ||
  rendered.command_loop_provider_call_count !== 1 ||
  rendered.reasoning_provider_call_count !== 3 ||
  rendered.browser_can_supply_route_authority !== false ||
  rendered.browser_can_supply_reasoning_authority !== false ||
  rendered.browser_model_authority !== false ||
  rendered.intelligence_measured !== false ||
  rendered.secret_value_exposed !== false ||
  rendered.raw_backend_details_exposed !== false ||
  rendered.packet_kind !== "model_reasoning_availability_matrix_truth" ||
  rendered.captured_at_utc !== "2026-01-01T00:00:00Z" ||
  rendered.request_id !== "ui-matrix-test" ||
  rendered.allowed_browser_fields.length !== 5 ||
  rendered.forbidden_fields.length !== 0 ||
  rendered.forbidden_fields_redacted !== true ||
  rendered.forbidden_field_count !== 0 ||
  rendered.forbidden_field_categories.length !== 0 ||
  rendered.matrix_row_count !== 3 ||
  rendered.reasoning_level_rows.length !== 3 ||
  rendered.reasoning_level_row_count !== 3 ||
  rendered.proof_rank !== "api_reasoning_live_only" ||
  rendered.proof_rank_score !== 70 ||
  rendered.proof_rank_status !== "partial" ||
  rendered.proof_rank_counts_as_full_success !== false ||
  rendered.proof_mode_row_count !== 3 ||
  rendered.proof_reasoning_row_count !== 3 ||
  rendered.proof_agent_row_count !== 2 ||
  rendered.display_aliases_are_runtime_aliases !== true ||
  rendered.display_aliases_are_separate_agents !== false
) {
  throw new Error(`matrix flags not preserved: ${node("quickStartRouteResponse").textContent}`);
}
if (!node("quickStartProofReasoningRows").textContent.includes("PROVIDER_DECLARED_REASONING_LEVEL_PROVEN")) {
  throw new Error(`provider reasoning proof level missing: ${node("quickStartProofReasoningRows").textContent}`);
}
if (!rendered.proof_reasoning_rows.every((row) => row.counts_as_provider_level_proof === true)) {
  throw new Error(`provider level proof flags missing: ${node("quickStartRouteResponse").textContent}`);
}
if (!rendered.proof_reasoning_rows.every((row) => row.counts_as_independent_quality_benchmark === false)) {
  throw new Error(`benchmark non-claim flags missing: ${node("quickStartRouteResponse").textContent}`);
}
vm.runInContext(`
renderQuickStartModelReasoningAvailabilityMatrix({
  status: "ok",
  machine_error_code: "OK",
  final_status: "MODEL_REASONING_AVAILABILITY_MATRIX_PROVEN_WITH_LIMITS",
  execution_mode: "chatgpt_plus_api",
  combined_full_proven: true,
  chatgpt_lane_proven: true,
  api_lane_proven: true,
  alias_binding_proven: true,
  combined_status_counts_as_full_success: true,
  api_success_counts_as_combined_success: false,
  native_execution_proven: true,
  reasoning_dispatch_matrix_proven: true,
  provider_declared_reasoning_levels_proven: true,
  provider_reasoning_level_source: "provider_spec_and_live_call",
  provider_reasoning_level_proof_count: 3,
  provider_reasoning_level_expected_count: 3,
  independent_quality_benchmark_proven: true,
  benchmark_required_for_provider_level_proof: false,
  quality_benchmark_status: "not_required_for_provider_level_proof",
  fallback_used: false,
  local_imitation_used: false,
  secret_value_exposed: false,
  raw_backend_details_exposed: false,
  intelligence_measured: false,
  not_intelligence_proof: true,
  next_action: "none"
});
if (!document.getElementById("quickStartRouteChip").className.includes("green")) {
  throw new Error("benchmark-backed packet must not be downgraded by provider-level UI gate");
}
`, sandbox);
vm.runInContext(`
renderQuickStartModelReasoningAvailabilityMatrix({
  status: "blocked",
  machine_error_code: "MODEL_REASONING_MATRIX_REQUIRES_CHATGPT_PLUS_API",
  final_status: "MODEL_REASONING_AVAILABILITY_MATRIX_NOT_PROVEN",
  execution_mode: "api_only",
  chatgpt_lane_proven: false,
  api_lane_proven: false,
  alias_binding_proven: false,
  combined_full_proven: false,
  intelligence_measured: false,
  not_intelligence_proof: true,
  next_action: "select_chatgpt_plus_api"
});
if (document.getElementById("quickStartExecutionModeState").className.includes("green")) {
  throw new Error("wrong mode must not render green execution chip");
}
if (document.getElementById("quickStartExecutionModeState").lastElementChild.textContent !== "select GPT+API") {
  throw new Error("wrong mode label missing");
}
`, sandbox);
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_free_text_result_blocks_background_route_refresh(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.disabled = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}
Node.prototype.setAttribute = function(name, value) {
  this[name] = value;
  if (name === "disabled") {
    this.disabled = true;
  }
};
Node.prototype.removeAttribute = function(name) {
  delete this[name];
  if (name === "disabled") {
    this.disabled = false;
  }
};

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState"
]) {
  node(id);
}
node("quickStartRouteResponse");
node("quickStartRouteRefreshAction");
node("refreshFixture");

const sandbox = {
  console,
  Date,
  document: {
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected while proof result is locked"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
refreshCodexCustomModelsPanel = async () => {
  throw new Error("background refresh must not run while proof result is locked");
};
renderQuickStartNativeFreeTextCommandLoopProof({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH",
  final_status: "CUSTOM_CODEX_NATIVE_FREE_TEXT_COMMAND_LOOP_NOT_PROVEN",
  primary_alias: "Теркистратор",
  coding_alias: "Агент Шмель",
  native_window_observed: false,
  input_capable_ui_observed: false,
  prompt_submitted: false,
  native_launch_attempted: true,
  native_activation_attempted: true,
  native_activation_proven: false,
  native_activation_machine_error_code: "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH",
  native_activation_status: "blocked",
  native_free_text_activation_source: "existing_window_resume_preflight",
  native_auth_usability_state_code: "CUSTOM_NATIVE_AUTH_WALL_OBSERVED",
  native_auth_usability_machine_error_code: "CUSTOM_NATIVE_AUTH_WALL_OBSERVED",
  native_auth_wall_observed: true,
  native_keychain_or_permission_prompt_observed: false,
  native_renderer_no_input_surface_observed: false,
  native_auth_passed_input_ready: false,
  native_resume_after_auth_ready: false,
  native_activation_packet: {
    status: "blocked",
    machine_error_code: "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND"
  },
  native_submit_machine_error_code: "CUSTOM_NATIVE_CDP_PROMPT_SUBMIT_FAILED",
  native_submit_normalized_machine_error_code: "CUSTOM_NATIVE_PROMPT_SUBMIT_FAILED",
  native_agent_proof_machine_error_code: "CUSTOM_NATIVE_AGENT_PROOF_INVALID",
  native_agent_proof_blocking_reasons: ["proof_machine_error_code_not_ok"],
  blocking_reasons: ["CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH"],
  native_agent_proof_file_valid: false,
  native_free_text_command_loop_proven: false,
  native_free_text_tool_bridge_proven: false,
  command_loop_proven: false,
  runtime_context_file_proven: true,
  api_lane_exact_token_matched: false,
  fallback_used: false,
  local_imitation_used: false,
  prompt_text_recorded: false,
  secret_value_exposed: false,
  nested_packets_redacted: true,
  next_action: "stop_and_diagnose_native_free_text_command_loop"
});
`, sandbox);

sandbox.refreshQuickStartRouteStatus().then(() => {
  if (node("quickStartRouteChip").lastElementChild.textContent !== "process missing") {
    throw new Error(`background refresh overwrote native proof result: ${node("quickStartRouteChip").lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
  if (
    rendered.native_free_text_command_loop_packet !== true ||
    rendered.native_free_text_command_loop_proven !== false ||
    rendered.runtime_context_file_proven !== true ||
    rendered.native_launch_attempted !== true ||
    rendered.native_activation_attempted !== true ||
    rendered.native_activation_proven !== false ||
    rendered.native_activation_machine_error_code !== "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH" ||
    rendered.native_activation_status !== "blocked" ||
    rendered.native_free_text_activation_source !== "existing_window_resume_preflight" ||
    rendered.native_auth_usability_state_code !== "CUSTOM_NATIVE_AUTH_WALL_OBSERVED" ||
    rendered.native_auth_usability_machine_error_code !== "CUSTOM_NATIVE_AUTH_WALL_OBSERVED" ||
    rendered.native_auth_wall_observed !== true ||
    rendered.native_keychain_or_permission_prompt_observed !== false ||
    rendered.native_renderer_no_input_surface_observed !== false ||
    rendered.native_auth_passed_input_ready !== false ||
    rendered.native_resume_after_auth_ready !== false ||
    rendered.native_activation_packet.machine_error_code !== "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND" ||
    rendered.native_submit_machine_error_code !== "CUSTOM_NATIVE_CDP_PROMPT_SUBMIT_FAILED" ||
    rendered.native_submit_normalized_machine_error_code !== "CUSTOM_NATIVE_PROMPT_SUBMIT_FAILED" ||
    rendered.native_agent_proof_machine_error_code !== "CUSTOM_NATIVE_AGENT_PROOF_INVALID" ||
    rendered.native_agent_proof_blocking_reasons[0] !== "proof_machine_error_code_not_ok" ||
    rendered.blocking_reasons[0] !== "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH" ||
    rendered.primary_alias !== "Теркистратор" ||
    rendered.coding_alias !== "Агент Шмель" ||
    rendered.nested_packets_redacted !== true
  ) {
    throw new Error(`native proof route response was not preserved: ${node("quickStartRouteResponse").textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_free_text_result_blocks_manual_snapshot_replay(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.disabled = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
  this.value = "";
}
Node.prototype.setAttribute = function(name, value) {
  this[name] = value;
  if (name === "disabled") {
    this.disabled = true;
  }
};
Node.prototype.removeAttribute = function(name) {
  delete this[name];
  if (name === "disabled") {
    this.disabled = false;
  }
};

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartRouteResponse",
  "quickStartExecutionModeSelect",
  "quickStartChatModelSelect",
  "quickStartApiModelSelect",
  "quickStartApiReasoningOptionSelect"
]) {
  node(id);
}
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "provider_declared_disabled";

const sandbox = {
  console,
  Date,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "live", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected while replay guard is tested"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartApiRouteCheckResult(
  {
    execution_mode: "chatgpt_plus_api",
    chatgpt_model_id: "gpt-5.5",
    api_model_id: "wbp-deepseek-chat",
    api_reasoning_option_id: "provider_declared_disabled"
  },
  {
    payload: {
      status: "ok",
      machine_error_code: "OK",
      ui_action: "api_route_check",
      route_id: "wbp-deepseek-chat",
      result: {
        status: "ok",
        machine_error_code: "OK",
        changed_files: []
      }
    },
    refreshState: "complete"
  },
  { remember: true }
);
renderQuickStartNativeFreeTextCommandLoopProof({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH",
  final_status: "CUSTOM_CODEX_NATIVE_FREE_TEXT_COMMAND_LOOP_NOT_PROVEN",
  primary_alias: "Теркистратор",
  coding_alias: "Агент Шмель",
  native_window_observed: false,
  input_capable_ui_observed: false,
  prompt_submitted: false,
  native_agent_proof_file_valid: false,
  native_free_text_command_loop_proven: false,
  native_free_text_tool_bridge_proven: false,
  command_loop_proven: false,
  runtime_context_file_proven: true,
  api_lane_exact_token_matched: false,
  fallback_used: false,
  local_imitation_used: false,
  prompt_text_recorded: false,
  secret_value_exposed: false,
  nested_packets_redacted: true,
  next_action: "stop_and_diagnose_native_free_text_command_loop"
});
replayQuickStartManualCheckSnapshot();
`, sandbox);

if (node("quickStartRouteChip").lastElementChild.textContent !== "process missing") {
  throw new Error(`manual snapshot replay overwrote native proof result: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.native_free_text_command_loop_packet !== true ||
  rendered.runtime_context_file_proven !== true ||
  rendered.primary_alias !== "Теркистратор" ||
  rendered.coding_alias !== "Агент Шмель" ||
  rendered.nested_packets_redacted !== true ||
  rendered.manual_check_replay_active === true
) {
  throw new Error(`native proof response was not preserved over manual replay: ${node("quickStartRouteResponse").textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_free_text_result_survives_model_catalog_render(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState",
  "quickStartRouteResponse",
  "quickStartExecutionModeSelect",
  "quickStartChatModelSelect",
  "quickStartApiModelSelect",
  "quickStartApiReasoningOptionSelect",
  "codexCustomExecutionModeSelect",
  "codexCustomModelSelect",
  "codexCustomApiModelSelect",
  "codexCustomApiReasoningOptionSelect",
  "codexCustomChatLaneCatalog",
  "codexCustomApiLaneCatalog",
  "codexCustomSeedLaneCatalog",
  "codexCustomChatLaneChip",
  "codexCustomApiLaneChip",
  "codexCustomSeedLaneChip",
  "codexCustomModelsSummary",
  "codexCustomRecommendedModel",
  "codexCustomRecommendedApiModel",
  "codexCustomExecutionBoundary",
  "codexCustomApiCompat",
  "codexCustomModelsClaimGate",
  "codexCustomChatModelCount",
  "codexCustomApiModelCount",
  "codexCustomSeedModelCount",
  "codexCustomModelTokenBurn"
]) {
  node(id);
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live", fixtureState: "healthy" };
node("quickStartExecutionModeSelect").value = "chatgpt_plus_api";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "provider_declared_disabled";

const storage = new Map();
const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("model catalog render proof-lock test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartNativeFreeTextCommandLoopProof({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_PROCESS_NOT_FOUND_AFTER_LAUNCH",
  final_status: "CUSTOM_CODEX_NATIVE_FREE_TEXT_COMMAND_LOOP_NOT_PROVEN",
  primary_alias: "Теркистратор",
  coding_alias: "Агент Шмель",
  native_window_observed: false,
  input_capable_ui_observed: false,
  prompt_submitted: false,
  native_agent_proof_file_valid: false,
  native_free_text_command_loop_proven: false,
  native_free_text_tool_bridge_proven: false,
  command_loop_proven: false,
  runtime_context_file_proven: true,
  api_lane_exact_token_matched: false,
  fallback_used: false,
  local_imitation_used: false,
  prompt_text_recorded: false,
  secret_value_exposed: false,
  nested_packets_redacted: true,
  next_action: "stop_and_diagnose_native_free_text_command_loop"
});
`, sandbox);

sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.5",
    models: [
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

if (node("quickStartRouteChip").lastElementChild.textContent !== "process missing") {
  throw new Error(`model catalog render overwrote native proof result: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (
  rendered.native_free_text_command_loop_packet !== true ||
  rendered.runtime_context_file_proven !== true ||
  rendered.primary_alias !== "Теркистратор" ||
  rendered.coding_alias !== "Агент Шмель" ||
  rendered.nested_packets_redacted !== true
) {
  throw new Error(`native proof response changed after model catalog render: ${node("quickStartRouteResponse").textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_native_launch_in_flight_replaces_preflight_ready_state(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "quickStartRouteChip",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartNextActionState"
]) {
  node(id);
}
node("quickStartRouteResponse");

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderQuickStartNativeLaunchInFlight(
  {
    execution_mode: "api_only",
    chatgpt_model_id: "",
    api_model_id: "wbp-openai-gpt-5",
    api_reasoning_option_id: "catalog_default"
  },
  {
    status: "ok",
    machine_error_code: "OK",
    execution_mode: "api_only",
    bridge_required: true,
    bridge_alive: false,
    bridge_status: "down",
    custom_process_observed: false,
    window_status: "not_found",
    config_status: "admitted"
  }
);
`, sandbox);

if (node("quickStartLaunchState").lastElementChild.textContent !== "запускаю") {
  throw new Error(`in-flight launch label is wrong: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "native launch") {
  throw new Error(`route chip should not stay preflight-ready: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").lastElementChild.textContent !== "ожидание") {
  throw new Error(`next action should show packet wait: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.status !== "running" || rendered.machine_error_code !== "CUSTOM_NATIVE_LAUNCH_IN_FLIGHT") {
  throw new Error(`in-flight packet truth missing: ${JSON.stringify(rendered)}`);
}
if (rendered.custom_codex_launch_attempted !== true || rendered.live_call_attempted !== true) {
  throw new Error(`live launch attempt flags missing: ${JSON.stringify(rendered)}`);
}
if (rendered.launch_packet_is_truth_source !== false || rendered.new_launch_started !== false) {
  throw new Error(`in-flight packet must not claim final launch truth: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_custom_launch_render_labels_native_usability_blocker_without_fake_ready(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = { textContent: "" };
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

for (const id of [
  "codexLaunchModesChip",
  "customCodexStatus",
  "customCodexSession",
  "codexLaunchDryRunResponse",
  "quickStartRouteChip",
  "quickStartExecutionModeState",
  "quickStartChatSlotState",
  "quickStartApiSlotState",
  "quickStartOwnerAuthState",
  "quickStartLaunchState",
  "quickStartBridgeState",
  "quickStartWindowState",
  "quickStartConfigState",
  "quickStartHistoryState",
  "quickStartNextActionState",
  "quickStartRouteResponse"
]) {
  node(id);
}

const sandbox = {
  console,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN",
  final_status: "CUSTOM_NATIVE_LAUNCH_BLOCKED_BY_WINDOW_USABILITY",
  execution_mode: "api_only",
  api_model_id: "wbp-openai-gpt-5",
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  bridge_alive: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: true,
  expected_custom_identity_observed: true,
  native_window_observed: true,
  real_codex_app_launched: true,
  native_app_usable: false,
  input_capable_ui_observed: false,
  native_app_usability_blocked_reason_class: "cdp_renderer_input_surface_not_observed",
  renderer_surface_blocked_reason_class: "cdp_renderer_input_surface_not_observed",
  launch_claim_scope: "custom_native_app_window_launch_only",
  next_action: "stop_and_diagnose_custom_window_usability"
});
`, sandbox);

if (!node("codexLaunchModesChip").className.includes("amber")) {
  throw new Error(`native usability blocker must stay amber: ${node("codexLaunchModesChip").className}`);
}
if (node("codexLaunchModesChip").lastElementChild.textContent !== "renderer blocked / input not proven") {
  throw new Error(`wrong launch chip label: ${node("codexLaunchModesChip").lastElementChild.textContent}`);
}
if (node("customCodexSession").textContent !== "window visible; input surface not proven") {
  throw new Error(`wrong session text: ${node("customCodexSession").textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "input не доказан") {
  throw new Error(`quick-start launch state faked readiness: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "renderer blocked") {
  throw new Error(`route chip did not expose renderer blocker: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("quickStartNextActionState").className.includes("green")) {
  throw new Error(`blocked usability next action must not be green: ${node("quickStartNextActionState").className}`);
}
if (!node("quickStartNextActionState").lastElementChild.textContent.startsWith("stop_and_diagnose")) {
  throw new Error(`next action should stay diagnostic: ${node("quickStartNextActionState").lastElementChild.textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.machine_error_code !== "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN") {
  throw new Error(`machine code missing: ${JSON.stringify(rendered)}`);
}
if (rendered.native_app_usable !== false || rendered.native_window_observed !== true) {
  throw new Error(`native window/usability split truth missing: ${JSON.stringify(rendered)}`);
}
if (rendered.native_app_usability_blocked_reason_class !== "cdp_renderer_input_surface_not_observed") {
  throw new Error(`blocked reason missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_model_refresh_ignores_stale_v1_storage_and_prefers_gpt_5_5(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "chatgpt_only";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const storage = new Map();
storage.set("wbp.codex.route-selection.v1", JSON.stringify({
  execution_mode: "api_only",
  chatgpt_model_id: "gpt-5.3-codex",
  api_model_id: "wbp-deepseek-chat",
  api_reasoning_option_id: "catalog_default"
}));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("model refresh storage migration test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.3-codex",
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

const payload = sandbox.quickStartLaunchPayloadFromSelects();
if (payload.execution_mode !== "chatgpt_plus_api") {
  throw new Error(`stale v1 storage reset execution mode: ${JSON.stringify(payload)}`);
}
if (payload.chatgpt_model_id !== "gpt-5.5") {
  throw new Error(`Quick Start did not prefer gpt-5.5: ${JSON.stringify(payload)}`);
}
if (payload.api_model_id !== "wbp-deepseek-chat") {
  throw new Error(`Quick Start did not prefer DeepSeek Chat: ${JSON.stringify(payload)}`);
}
if (payload.api_reasoning_option_id !== "provider_declared_disabled") {
  throw new Error(`Quick Start did not preserve DeepSeek Chat reasoning: ${JSON.stringify(payload)}`);
}
const persisted = JSON.parse(storage.get("wbp.codex.route-selection.v2"));
if (
  persisted.execution_mode !== "chatgpt_plus_api"
  || persisted.chatgpt_model_id !== "gpt-5.5"
  || persisted.api_model_id !== "wbp-deepseek-chat"
  || persisted.api_reasoning_option_id !== "provider_declared_disabled"
) {
  throw new Error(`fresh v2 selection was not persisted: ${JSON.stringify(persisted)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_restores_valid_persisted_mixed_selection(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "chatgpt_only";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const storage = new Map();
storage.set("wbp.codex.route-selection.v2", JSON.stringify({
  execution_mode: "chatgpt_plus_api",
  chatgpt_model_id: "gpt-5.5",
  api_model_id: "wbp-deepseek-chat",
  api_reasoning_option_id: "provider_declared_disabled"
}));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("valid persisted selection restore test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.3-codex",
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

const payload = sandbox.quickStartLaunchPayloadFromSelects();
if (payload.execution_mode !== "chatgpt_plus_api") {
  throw new Error(`valid persisted selection did not restore mixed mode: ${JSON.stringify(payload)}`);
}
if (payload.chatgpt_model_id !== "gpt-5.5") {
  throw new Error(`valid persisted selection did not restore gpt-5.5: ${JSON.stringify(payload)}`);
}
if (payload.api_model_id !== "wbp-deepseek-chat") {
  throw new Error(`valid persisted selection did not restore DeepSeek Chat: ${JSON.stringify(payload)}`);
}
if (payload.api_reasoning_option_id !== "provider_declared_disabled") {
  throw new Error(`valid persisted selection did not restore reasoning: ${JSON.stringify(payload)}`);
}
if (node("codexCustomExecutionModeSelect").value !== "chatgpt_plus_api") {
  throw new Error(`master mode did not mirror persisted Quick Start: ${node("codexCustomExecutionModeSelect").value}`);
}
sandbox.buildCodexCustomLaunchSelectionPayload().then((launchPayload) => {
  if (launchPayload.execution_mode !== "chatgpt_plus_api") {
    throw new Error(`restored launch payload did not stay mixed: ${JSON.stringify(launchPayload)}`);
  }
  if (launchPayload.chatgpt_model_id !== "gpt-5.5") {
    throw new Error(`restored launch payload did not keep gpt-5.5: ${JSON.stringify(launchPayload)}`);
  }
  if (launchPayload.api_model_id !== "wbp-deepseek-chat") {
    throw new Error(`restored launch payload did not keep DeepSeek Chat: ${JSON.stringify(launchPayload)}`);
  }
  if (launchPayload.api_reasoning_option_id !== "provider_declared_disabled") {
    throw new Error(`restored launch payload did not keep API reasoning: ${JSON.stringify(launchPayload)}`);
  }
  const persisted = JSON.parse(storage.get("wbp.codex.route-selection.v2"));
  if (persisted.selection_persistence_schema_version !== 3) {
    throw new Error(`restored mixed selection was not saved with schema v3: ${JSON.stringify(persisted)}`);
  }
  if (
    persisted.execution_mode !== "chatgpt_plus_api"
    || persisted.chatgpt_model_id !== "gpt-5.5"
    || persisted.api_model_id !== "wbp-deepseek-chat"
    || persisted.api_reasoning_option_id !== "provider_declared_disabled"
  ) {
    throw new Error(`restored mixed selection changed while preparing launch: ${JSON.stringify(persisted)}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_replaces_legacy_gpt_53_default_with_server_default(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const storage = new Map();
storage.set("wbp.codex.route-selection.v2", JSON.stringify({
  execution_mode: "api_only",
  chatgpt_model_id: "gpt-5.3-codex",
  api_model_id: "wbp-deepseek-chat",
  api_reasoning_option_id: "provider_declared_disabled"
}));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("legacy default replacement test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.5",
    preferred_default_available: true,
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

if (node("quickStartChatModelSelect").value !== "gpt-5.5") {
  throw new Error(`legacy gpt-5.3 default survived hard reload: ${node("quickStartChatModelSelect").value}`);
}
if (node("codexCustomModelSelect").value !== "gpt-5.5") {
  throw new Error(`master model did not mirror server default: ${node("codexCustomModelSelect").value}`);
}
const persisted = JSON.parse(storage.get("wbp.codex.route-selection.v2"));
if (persisted.chatgpt_model_id !== "gpt-5.5") {
  throw new Error(`legacy persisted model was not upgraded: ${JSON.stringify(persisted)}`);
}
if (persisted.chatgpt_model_selected_by_user === true) {
  throw new Error(`legacy default must not become explicit user selection: ${JSON.stringify(persisted)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_restores_valid_persisted_chatgpt_only_selection(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const storage = new Map();
storage.set("wbp.codex.route-selection.v2", JSON.stringify({
  execution_mode: "chatgpt_only",
  chatgpt_model_id: "gpt-5.5",
  api_model_id: "wbp-deepseek-chat",
  api_reasoning_option_id: "provider_declared_disabled"
}));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("chatgpt-only persisted selection restore test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.3-codex",
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

const payload = sandbox.quickStartLaunchPayloadFromSelects();
if (payload.execution_mode !== "chatgpt_only") {
  throw new Error(`valid persisted selection did not restore ChatGPT-only mode: ${JSON.stringify(payload)}`);
}
if (payload.chatgpt_model_id !== "gpt-5.5") {
  throw new Error(`valid persisted selection did not restore gpt-5.5: ${JSON.stringify(payload)}`);
}
if (payload.api_model_id !== "") {
  throw new Error(`ChatGPT-only restore must clear API model in launch payload: ${JSON.stringify(payload)}`);
}
if (payload.api_reasoning_option_id !== "") {
  throw new Error(`ChatGPT-only restore must clear API reasoning in launch payload: ${JSON.stringify(payload)}`);
}
if (node("quickStartExecutionModeSelect").value !== "chatgpt_only") {
  throw new Error(`Quick Start mode select did not restore ChatGPT-only: ${node("quickStartExecutionModeSelect").value}`);
}
if (node("codexCustomExecutionModeSelect").value !== "chatgpt_only") {
  throw new Error(`master mode did not mirror persisted ChatGPT-only: ${node("codexCustomExecutionModeSelect").value}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_preserves_explicit_user_selected_gpt_53(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const storage = new Map();
storage.set("wbp.codex.route-selection.v2", JSON.stringify({
  execution_mode: "chatgpt_only",
  chatgpt_model_id: "gpt-5.3-codex",
  chatgpt_model_selected_by_user: true
}));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("explicit user selection preservation test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.5",
    preferred_default_available: true,
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      { model_id: "wbp-deepseek-chat", display_name: "WBP DeepSeek Chat", selection_enabled: true }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

if (node("quickStartChatModelSelect").value !== "gpt-5.3-codex") {
  throw new Error(`explicit user gpt-5.3 selection was overwritten: ${node("quickStartChatModelSelect").value}`);
}
const persisted = JSON.parse(storage.get("wbp.codex.route-selection.v2"));
if (persisted.chatgpt_model_selected_by_user !== true) {
  throw new Error(`explicit user selection marker lost: ${JSON.stringify(persisted)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_model_refresh_rejects_invalid_persisted_selection_without_silent_fallback(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this._value = "";
    this.lastElementChild = { textContent: "" };
  }
  get value() { return this._value; }
  set value(next) {
    this._value = String(next ?? "");
    for (const option of this.options || []) {
      option.selected = option.value === this._value;
    }
  }
  get options() {
    return this.children.filter((item) => item.tag === "option");
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
node("quickStartExecutionModeSelect").value = "chatgpt_only";
node("quickStartChatModelSelect").value = "";
node("quickStartApiModelSelect").value = "";
node("quickStartApiReasoningOptionSelect").value = "";
node("codexCustomExecutionModeSelect").value = "";
node("codexCustomModelSelect").value = "";
node("codexCustomApiModelSelect").value = "";
node("codexCustomApiReasoningOptionSelect").value = "";

const invalidSelection = {
  execution_mode: "chatgpt_plus_api",
  chatgpt_model_id: "gpt-5.5",
  api_model_id: "not-server-issued-route",
  api_reasoning_option_id: "provider_declared_disabled"
};
const storage = new Map();
storage.set("wbp.codex.route-selection.v2", JSON.stringify(invalidSelection));

const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); }
    }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch() {
    throw new Error("invalid persisted selection rejection test must not fetch");
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.renderCodexCustomModels({
  status: "ok",
  chatgpt_lane: {
    default_model_id: "gpt-5.3-codex",
    models: [
      { model_id: "gpt-5.3-codex", display_name: "gpt-5.3-codex", selection_enabled: true },
      { model_id: "gpt-5.5", display_name: "gpt-5.5", selection_enabled: true }
    ]
  },
  api_lane: {
    default_model_id: "wbp-deepseek-chat",
    models: [
      {
        model_id: "wbp-deepseek-chat",
        display_name: "WBP DeepSeek Chat",
        selection_enabled: true,
        thinking: { type: "disabled" }
      }
    ]
  },
  seed_only_reference: { models: [] }
}, {
  claim_gate_status: "clear",
  openai_compatible_shape_declared: true,
  configured_wire_api: "openai",
  live_api_checked: false
});

const persisted = JSON.parse(storage.get("wbp.codex.route-selection.v2"));
if (persisted.api_model_id !== "not-server-issued-route") {
  throw new Error(`invalid persisted selection was silently overwritten: ${JSON.stringify(persisted)}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "invalid selection") {
  throw new Error(`invalid selection chip missing: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
const packet = JSON.parse(node("quickStartRouteResponse").textContent);
if (packet.status !== "blocked" || packet.machine_error_code !== "QUICK_START_PERSISTED_SELECTION_INVALID") {
  throw new Error(`invalid selection packet missing: ${node("quickStartRouteResponse").textContent}`);
}
if (packet.silent_fallback_used !== false || packet.fallback_used !== false) {
  throw new Error(`invalid selection must not claim fallback: ${node("quickStartRouteResponse").textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_quick_start_primary_launch_action_preserves_api_only_payload_when_admitted(self) -> None:
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
    this.value = "";
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "api_only";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

const urls = [];
const packets = [];
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
    history: { replaceState() {} },
    localStorage: { setItem() {} }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options.body);
    packets.push(body);
    for (const forbidden of ["route_id", "secret_ref", "api_key", "base_url", "path", "CODEX_HOME"]) {
      if (JSON.stringify(body).includes(forbidden)) {
        throw new Error(`forbidden browser field leaked into launch body: ${forbidden}`);
      }
    }
    if (url === "api/codex/custom/quick-start/config-admission") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
          execution_mode: "api_only",
          chatgpt_model: { status: "not_required", model_id: "" },
          api_model: { status: "admitted", model_id: "wbp-deepseek-chat" },
          api_reasoning: { status: "defaulted", option_id: "catalog_default" },
          api_route: { status: "admitted", route_reference: "server-owned-api-route" },
          launch_admission: "admitted",
          dry_server_truth_only: true,
          custom_codex_launch_attempted: false,
          new_launch_started: false,
          network_calls_made: false,
          live_call_attempted: false,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "native_launch_preflight"
        })
      });
    }
    if (url === "api/codex/custom/native-launch-preflight") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_NATIVE_LAUNCH_PREFLIGHT_ADMITTED",
          execution_mode: "api_only",
          selected_model: "wbp-deepseek-chat",
          owner_authorization_phrase_present: true,
          bridge_required: true,
          bridge_alive: true,
          bridge_status: "running",
          custom_process_observed: false,
          window_status: "not_found",
          config_status: "admitted",
          new_launch_started: false,
          custom_codex_launch_attempted: false,
          live_call_attempted: false,
          provider_called: false,
          next_action: "native_launch"
        })
      });
    }
    if (url === "api/codex/custom/native-launch") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_CODEX_NATIVE_LAUNCH_PROVEN_WITH_LIMITS",
          execution_mode: "api_only",
          selected_model: "wbp-deepseek-chat",
          launch_model_id: "wbp-deepseek-chat",
          route_model_id: "wbp-deepseek-chat",
          chatgpt_model_id: "",
          api_model_id: "wbp-deepseek-chat",
          running_status: true,
          wbp_endpoint_configured: true,
          bridge_alive: true,
          stable_custom_codex_wbp_bridge_final_status: "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS",
          process_started: true,
          native_window_observed: true,
          native_app_usable: true,
          launch_claim_scope: "native_custom_codex_launch_packet_truth",
          selection_packet: {
            execution_mode: "api_only",
            chatgpt_model_id: "",
            api_model_id: "wbp-deepseek-chat",
            primary_model_slot: {
              lane: "api_route_lane",
              model_id: "wbp-deepseek-chat"
            },
            chatgpt_line_used_as_executor: false,
            api_line_used_as_executor: true,
            api_only_calls_chatgpt: false
          },
          route_packet_matches_selection_packet: true,
          quick_start_launch_route_truth_proven_with_limits: true,
          config_status: "matches_last_launch",
          new_launch_started: true,
          live_call_attempted: true,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "continue_in_existing_custom_window"
        })
      });
    }
    throw new Error(`unexpected fetch url ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
  actionMetadata = {
    launch_custom_client_native: {
      available: true,
      disabled_reason_code: "",
      availability_state: "enabled"
    }
  };
  actionMetadataLoaded = true;
`, sandbox);
sandbox.runQuickStartCustomLaunchAction().then(() => {
  const expected = [
    "api/codex/custom/quick-start/config-admission",
    "api/codex/custom/native-launch-preflight",
    "api/codex/custom/native-launch"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`unexpected launch fetches ${JSON.stringify(urls)}`);
  }
  for (const packet of packets) {
    if (packet.execution_mode !== "api_only") {
      throw new Error(`wrong execution mode in payload: ${JSON.stringify(packet)}`);
    }
    if (packet.chatgpt_model_id !== "") {
      throw new Error(`API-only payload must not carry ChatGPT model: ${JSON.stringify(packet)}`);
    }
    if (packet.api_model_id !== "wbp-deepseek-chat") {
      throw new Error(`wrong API model in payload: ${JSON.stringify(packet)}`);
    }
  }
  if (nodes.quickStartChatSlotState.lastElementChild.textContent !== "not required") {
    throw new Error(`ChatGPT slot not rendered as not required: ${nodes.quickStartChatSlotState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartBridgeState.lastElementChild.textContent !== "жив") {
    throw new Error(`bridge chip did not render launch truth: ${nodes.quickStartBridgeState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartWindowState.lastElementChild.textContent !== "найдено") {
    throw new Error(`window chip did not render launch truth: ${nodes.quickStartWindowState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartConfigState.lastElementChild.textContent !== "совпадает") {
    throw new Error(`config chip did not render route truth: ${nodes.quickStartConfigState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartNextActionState.lastElementChild.textContent !== "existing window") {
    throw new Error(`next action chip did not render existing window: ${nodes.quickStartNextActionState.lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (rendered.execution_mode !== "api_only" || rendered.selected_model !== "wbp-deepseek-chat") {
    throw new Error(`API-only launch truth not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
  if (rendered.primary_model_slot_lane !== "api_route_lane" || rendered.api_only_calls_chatgpt !== false) {
    throw new Error(`API-only slot truth not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
  if (rendered.config_status !== "matches_last_launch" || rendered.next_action !== "continue_in_existing_custom_window") {
    throw new Error(`existing-window launch truth not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_custom_launch_render_labels_existing_window_reuse_without_fake_new_launch(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

function makeChip() {
  const chip = new Node();
  chip.lastElementChild = new Node();
  chip.children = [chip.lastElementChild];
  return chip;
}

const nodes = {
  codexLaunchModesChip: makeChip(),
  customCodexStatus: new Node(),
  customCodexSession: new Node(),
  codexLaunchDryRunResponse: new Node(),
  quickStartRouteChip: makeChip(),
  quickStartExecutionModeState: makeChip(),
  quickStartChatSlotState: makeChip(),
  quickStartApiSlotState: makeChip(),
  quickStartOwnerAuthState: makeChip(),
  quickStartLaunchState: makeChip(),
  quickStartBridgeState: makeChip(),
  quickStartWindowState: makeChip(),
  quickStartConfigState: makeChip(),
  quickStartHistoryState: makeChip(),
  quickStartNextActionState: makeChip(),
  quickStartRouteResponse: new Node()
};

const sandbox = {
  console,
  window: { location: { search: "" }, history: { replaceState() {} } },
  document: {
    getElementById(id) { return nodes[id] || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  packet_kind: "custom_native_launch_stability_guard",
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-chat",
  api_model_id: "wbp-deepseek-chat",
  owner_authorization_phrase_present: true,
  running_status: true,
  process_started: true,
  new_launch_started: false,
  native_window_observed: true,
  native_app_usable: true,
  real_codex_app_launched: true,
  expected_custom_identity_observed: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  launch_claim_scope: "custom_codex_launch_stability_and_recovery",
  config_status: "matches_last_launch",
  selection_matches_last_launch: true,
  existing_window_reuse_admissible: true,
  existing_window_relaunch_admissible: false,
  reused_existing_window: true,
  launch_origin: "existing_window",
  fresh_launch_started: false,
  launch_blocked: false,
  launch_packet_is_truth_source: true,
  show_window_attempted: true,
  custom_process_observed: true,
  custom_process_count: 1,
  next_action: "continue_in_existing_custom_window"
});
`, sandbox);

if (!nodes.quickStartLaunchState.className.includes("green")) {
  throw new Error(`reused window should be green as a successful reuse action: ${nodes.quickStartLaunchState.className}`);
}
if (nodes.quickStartLaunchState.lastElementChild.textContent !== "старое окно") {
  throw new Error(`reuse label should not fake a new launch: ${nodes.quickStartLaunchState.lastElementChild.textContent}`);
}
if (nodes.quickStartRouteChip.lastElementChild.textContent !== "reuse ok") {
  throw new Error(`route chip did not show reuse truth: ${nodes.quickStartRouteChip.lastElementChild.textContent}`);
}
const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
if (
  rendered.reused_existing_window !== true ||
  rendered.new_launch_started !== false ||
  rendered.launch_origin !== "existing_window" ||
  rendered.fresh_launch_started !== false ||
  rendered.existing_window_reuse_admissible !== true
) {
  throw new Error(`existing-window reuse truth missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_custom_launch_render_does_not_green_reused_window_without_launch_packet_truth(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

function makeChip() {
  const chip = new Node();
  chip.lastElementChild = new Node();
  chip.children = [chip.lastElementChild];
  return chip;
}

const nodes = {
  codexLaunchModesChip: makeChip(),
  customCodexStatus: new Node(),
  customCodexSession: new Node(),
  codexLaunchDryRunResponse: new Node(),
  quickStartRouteChip: makeChip(),
  quickStartExecutionModeState: makeChip(),
  quickStartChatSlotState: makeChip(),
  quickStartApiSlotState: makeChip(),
  quickStartOwnerAuthState: makeChip(),
  quickStartLaunchState: makeChip(),
  quickStartBridgeState: makeChip(),
  quickStartWindowState: makeChip(),
  quickStartConfigState: makeChip(),
  quickStartHistoryState: makeChip(),
  quickStartNextActionState: makeChip(),
  quickStartRouteResponse: new Node()
};

const sandbox = {
  console,
  window: { location: { search: "" }, history: { replaceState() {} } },
  document: {
    getElementById(id) { return nodes[id] || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  packet_kind: "custom_native_launch_stability_guard",
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-chat",
  api_model_id: "wbp-deepseek-chat",
  owner_authorization_phrase_present: true,
  running_status: false,
  process_started: false,
  new_launch_started: false,
  native_window_observed: true,
  native_app_usable: true,
  real_codex_app_launched: false,
  launch_claim_scope: "custom_codex_launch_stability_and_recovery",
  config_status: "matches_last_launch",
  selection_matches_last_launch: true,
  existing_window_reuse_admissible: true,
  reused_existing_window: true,
  launch_packet_is_truth_source: false,
  show_window_attempted: true,
  custom_process_observed: true,
  custom_process_count: 1,
  next_action: "continue_in_existing_custom_window"
});
`, sandbox);

if (nodes.quickStartLaunchState.className.includes("green")) {
  throw new Error(`stale reuse packet without launch-packet truth must not be green: ${nodes.quickStartLaunchState.className}`);
}
if (nodes.quickStartRouteChip.lastElementChild.textContent === "reuse ok") {
  throw new Error("stale reuse packet must not claim reuse ok");
}
const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
if (rendered.launch_packet_is_truth_source !== false || rendered.reused_existing_window !== true) {
  throw new Error(`stale reuse packet truth fields missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_custom_launch_render_labels_relaunch_success_as_relaunch(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

function makeChip() {
  const chip = new Node();
  chip.lastElementChild = new Node();
  chip.children = [chip.lastElementChild];
  return chip;
}

const nodes = {
  codexLaunchModesChip: makeChip(),
  customCodexStatus: new Node(),
  customCodexSession: new Node(),
  codexLaunchDryRunResponse: new Node(),
  quickStartRouteChip: makeChip(),
  quickStartExecutionModeState: makeChip(),
  quickStartChatSlotState: makeChip(),
  quickStartApiSlotState: makeChip(),
  quickStartOwnerAuthState: makeChip(),
  quickStartLaunchState: makeChip(),
  quickStartBridgeState: makeChip(),
  quickStartWindowState: makeChip(),
  quickStartConfigState: makeChip(),
  quickStartHistoryState: makeChip(),
  quickStartNextActionState: makeChip(),
  quickStartRouteResponse: new Node()
};

const sandbox = {
  console,
  window: { location: { search: "" }, history: { replaceState() {} } },
  document: {
    getElementById(id) { return nodes[id] || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  status: "ok",
  machine_error_code: "OK",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-chat",
  api_model_id: "wbp-deepseek-chat",
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: true,
  expected_custom_identity_observed: true,
  native_window_observed: true,
  native_app_usable: true,
  real_codex_app_launched: true,
  route_packet_matches_selection_packet: true,
  quick_start_launch_route_truth_proven_with_limits: true,
  launch_claim_scope: "native_custom_codex_launch_packet_truth",
  config_status: "changed",
  selection_matches_last_launch: false,
  existing_window_reuse_admissible: false,
  existing_window_relaunch_admissible: true,
  existing_window_relaunch_attempted: true,
  existing_window_relaunch_termination: {
    status: "ok",
    initial_custom_process_count: 1,
    custom_processes_gone: true,
    final_custom_process_count: 0,
    raw_process_lines_exposed: false,
    raw_path_exposed: false
  },
  custom_process_observed_before_relaunch: true,
  custom_process_count_after_relaunch_stop: 0,
  new_launch_started: true,
  reused_existing_window: false,
  launch_packet_is_truth_source: true,
  next_action: "none"
});
`, sandbox);

if (nodes.quickStartLaunchState.lastElementChild.textContent !== "перезапущен") {
  throw new Error(`relaunch success must be labeled as relaunch: ${nodes.quickStartLaunchState.lastElementChild.textContent}`);
}
if (nodes.quickStartRouteChip.lastElementChild.textContent !== "relaunch ok") {
  throw new Error(`route chip did not show relaunch truth: ${nodes.quickStartRouteChip.lastElementChild.textContent}`);
}
const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
if (rendered.existing_window_relaunch_attempted !== true || rendered.new_launch_started !== true || rendered.existing_window_relaunch_termination.status !== "ok") {
  throw new Error(`relaunch truth missing: ${JSON.stringify(rendered)}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_quick_start_primary_launch_action_preserves_chatgpt_only_gpt_5_5_payload_when_admitted(self) -> None:
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
    this.value = "";
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
  setAttribute(name, value) {
    this[name] = value;
    if (name === "disabled") {
      this.disabled = true;
    }
  }
  removeAttribute(name) {
    delete this[name];
    if (name === "disabled") {
      this.disabled = false;
    }
  }
  addEventListener() {}
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node(id);
  }
  return nodes[id];
}
node("quickStartExecutionModeSelect").value = "chatgpt_only";
node("quickStartChatModelSelect").value = "gpt-5.5";
node("quickStartApiModelSelect").value = "wbp-deepseek-chat";
node("quickStartApiReasoningOptionSelect").value = "catalog_default";

const desktop = new Node("desktop");
desktop.dataset = { screen: "quick-start", source: "live" };
const urls = [];
const packets = [];
const sandbox = {
  console,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
    addEventListener() {},
    querySelector(selector) { return selector === ".desktop" ? desktop : null; },
    querySelectorAll() { return []; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=quick-start&source=live" },
    history: { replaceState() {} },
    localStorage: { setItem() {} }
  },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  AbortController,
  fetch(url, options) {
    urls.push(url);
    const body = JSON.parse(options.body);
    packets.push(body);
    if (url === "api/codex/custom/quick-start/config-admission") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS",
          execution_mode: "chatgpt_only",
          chatgpt_model: { status: "admitted", model_id: "gpt-5.5" },
          api_model: { status: "not_required", model_id: "" },
          api_reasoning: { status: "not_required", option_id: "" },
          api_route: { status: "not_required", route_reference: "" },
          launch_admission: "admitted",
          dry_server_truth_only: true,
          custom_codex_launch_attempted: false,
          new_launch_started: false,
          network_calls_made: false,
          live_call_attempted: false,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "native_launch_preflight"
        })
      });
    }
    if (url === "api/codex/custom/native-launch-preflight") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_NATIVE_LAUNCH_PREFLIGHT_ADMITTED",
          execution_mode: "chatgpt_only",
          selected_model: "gpt-5.5",
          owner_authorization_phrase_present: true,
          bridge_required: false,
          bridge_alive: false,
          bridge_status: "not_required",
          custom_process_observed: false,
          window_status: "not_found",
          config_status: "admitted",
          new_launch_started: false,
          custom_codex_launch_attempted: false,
          live_call_attempted: false,
          provider_called: false,
          next_action: "native_launch"
        })
      });
    }
    if (url === "api/codex/custom/native-launch") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: "ok",
          machine_error_code: "OK",
          final_status: "CUSTOM_CODEX_NATIVE_LAUNCH_PROVEN_WITH_LIMITS",
          execution_mode: "chatgpt_only",
          selected_model: "gpt-5.5",
          launch_model_id: "gpt-5.5",
          route_model_id: "gpt-5.5",
          chatgpt_model_id: "gpt-5.5",
          api_model_id: "",
          running_status: true,
          process_started: true,
          native_window_observed: true,
          native_app_usable: true,
          selection_packet: {
            execution_mode: "chatgpt_only",
            chatgpt_model_id: "gpt-5.5",
            api_model_id: "",
            primary_model_slot: {
              lane: "chatgpt_lane",
              model_id: "gpt-5.5"
            },
            chatgpt_line_used_as_executor: true,
            api_line_used_as_executor: false,
            chatgpt_only_calls_api: false
          },
          route_packet_matches_selection_packet: true,
          quick_start_launch_route_truth_proven_with_limits: true,
          config_status: "matches_last_launch",
          new_launch_started: true,
          live_call_attempted: true,
          provider_called: false,
          fallback_used: false,
          silent_fallback_used: false,
          raw_backend_details_exposed: false,
          secret_value_exposed: false,
          raw_path_exposed: false,
          original_codex_touched: false,
          asar_touched: false,
          next_action: "none"
        })
      });
    }
    throw new Error(`unexpected fetch url ${url}`);
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
  actionMetadata = {
    launch_custom_client_native: {
      available: true,
      disabled_reason_code: "",
      availability_state: "enabled"
    }
  };
  actionMetadataLoaded = true;
`, sandbox);
sandbox.runQuickStartCustomLaunchAction().then(() => {
  const expected = [
    "api/codex/custom/quick-start/config-admission",
    "api/codex/custom/native-launch-preflight",
    "api/codex/custom/native-launch"
  ];
  if (JSON.stringify(urls) !== JSON.stringify(expected)) {
    throw new Error(`unexpected launch fetches ${JSON.stringify(urls)}`);
  }
  for (const packet of packets) {
    if (packet.execution_mode !== "chatgpt_only") {
      throw new Error(`wrong execution mode in payload: ${JSON.stringify(packet)}`);
    }
    if (packet.chatgpt_model_id !== "gpt-5.5") {
      throw new Error(`wrong ChatGPT model in payload: ${JSON.stringify(packet)}`);
    }
    if (packet.api_model_id !== "") {
      throw new Error(`ChatGPT-only payload must not carry API model: ${JSON.stringify(packet)}`);
    }
    if (packet.api_reasoning_option_id !== "") {
      throw new Error(`ChatGPT-only payload must not carry API reasoning: ${JSON.stringify(packet)}`);
    }
  }
  if (nodes.quickStartChatSlotState.lastElementChild.textContent !== "admitted") {
    throw new Error(`ChatGPT slot not rendered as admitted: ${nodes.quickStartChatSlotState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartApiSlotState.lastElementChild.textContent !== "not required") {
    throw new Error(`API slot not rendered as not required: ${nodes.quickStartApiSlotState.lastElementChild.textContent}`);
  }
  if (nodes.quickStartBridgeState.lastElementChild.textContent !== "не нужен") {
    throw new Error(`bridge chip did not render ChatGPT-only truth: ${nodes.quickStartBridgeState.lastElementChild.textContent}`);
  }
  const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
  if (rendered.execution_mode !== "chatgpt_only" || rendered.selected_model !== "gpt-5.5") {
    throw new Error(`ChatGPT-only launch truth not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
  if (rendered.api_model_id !== "" || rendered.chatgpt_only_calls_api !== false) {
    throw new Error(`ChatGPT-only slot truth not rendered: ${nodes.quickStartRouteResponse.textContent}`);
  }
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

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
const routeOnlySummary = sandbox.quickStartApiModel({
  status: "ok",
  source: "api_connections_readonly",
  routes: [{
    route_id: "wbp-raw-route-id",
    provider: "openrouter",
    enabled: true,
    role_label: "main route",
    secret_status_label: "available"
  }]
}, "live");
const routeOnlyText = `${routeOnlySummary.provider} ${routeOnlySummary.model}`;
if (routeOnlyText.includes("wbp-raw-route-id")) {
  throw new Error(`quick-start API summary leaked raw route id: ${routeOnlyText}`);
}
if (!routeOnlyText.includes("openrouter")) {
  throw new Error(`quick-start API summary lost safe provider fallback: ${routeOnlyText}`);
}
const selectedRouteSummary = sandbox.quickStartApiModel({
  status: "ok",
  source: "api_connections_readonly",
  routes: [{
    route_id: "wbp-deepseek-chat",
    provider: "deepseek",
    upstream_model: "deepseek-chat",
    enabled: true,
    role_label: "Кандидат",
    secret_status_label: "available",
    secret_visual_state: "green",
    validation_label: "ok",
    validation_visual_state: "green"
  }]
}, "live", "wbp-deepseek-chat");
if (selectedRouteSummary.state !== "ok" || selectedRouteSummary.visual !== "green") {
  throw new Error(`selected route proof not projected: ${JSON.stringify(selectedRouteSummary)}`);
}
if (selectedRouteSummary.selectedRoute !== true || selectedRouteSummary.confirmed !== true) {
  throw new Error(`selected route proof flags missing: ${JSON.stringify(selectedRouteSummary)}`);
}
if (selectedRouteSummary.provider !== "WBP deepseek-chat") {
  throw new Error(`selected route provider summary wrong: ${selectedRouteSummary.provider}`);
}
if (`${selectedRouteSummary.provider} ${selectedRouteSummary.model}`.includes("wbp-deepseek-chat")) {
  throw new Error(`selected route summary leaked raw route id: ${JSON.stringify(selectedRouteSummary)}`);
}
const selectedRouteOverridesFailedPrimary = sandbox.quickStartApiModel({
  status: "ok",
  source: "api_connections_readonly",
  routes: [{
    route_id: "wbp-web-primary-openrouter",
    provider: "openrouter",
    upstream_model: "openai/gpt-5",
    enabled: true,
    role_label: "main route",
    secret_status_label: "available",
    secret_visual_state: "green",
    validation_label: "validate failed",
    validation_visual_state: "red",
    visual_state: "red"
  }, {
    route_id: "wbp-deepseek-v4-pro-max",
    provider: "deepseek",
    display_name: "DeepSeek V4 Pro · Максимум",
    upstream_model: "deepseek-v4-pro",
    enabled: true,
    role_label: "Кандидат",
    secret_status_label: "available",
    secret_visual_state: "green",
    validation_label: "ok",
    validation_visual_state: "green"
  }]
}, "live", "wbp-deepseek-v4-pro-max");
if (selectedRouteOverridesFailedPrimary.state !== "ok" || selectedRouteOverridesFailedPrimary.visual !== "green") {
  throw new Error(`selected route did not override failed registry primary: ${JSON.stringify(selectedRouteOverridesFailedPrimary)}`);
}
if (selectedRouteOverridesFailedPrimary.title !== "Выбранный route подтверждён") {
  throw new Error(`selected route title wrong: ${JSON.stringify(selectedRouteOverridesFailedPrimary)}`);
}
if (selectedRouteOverridesFailedPrimary.provider !== "WBP deepseek-v4-pro") {
  throw new Error(`selected route provider label wrong: ${selectedRouteOverridesFailedPrimary.provider}`);
}
const selectedRouteWithoutProof = sandbox.quickStartApiModel({
  status: "ok",
  source: "api_connections_readonly",
  routes: [{
    route_id: "wbp-deepseek-chat",
    provider: "deepseek",
    upstream_model: "deepseek-chat",
    enabled: true,
    role_label: "Кандидат",
    secret_status_label: "available",
    secret_visual_state: "green",
    validation_label: "not checked",
    validation_visual_state: "neutral"
  }]
}, "live", "wbp-deepseek-chat");
if (selectedRouteWithoutProof.state === "ok" || selectedRouteWithoutProof.visual === "green") {
  throw new Error(`selector-only route should not project green: ${JSON.stringify(selectedRouteWithoutProof)}`);
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
        account_detail_markup = self._overlay_html(html, "accountDetailOverlay", "actionLedgerOverlay")
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
        self.assertNotIn("localStorage", account_detail_markup)
        self.assertNotIn("sessionStorage", account_detail_markup)
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
        self.assertIn('data-api-role-profile-surface="presentation-only"', api_screen)
        self.assertIn('data-api-builder-mode="deferred"', api_screen)
        self.assertIn("Маршруты недоступны", js)
        self.assertIn("Демо-режим. Маршруты показаны как ограниченная сводка", api_screen + js)
        self.assertIn("Live-readonly маршруты недоступны", js)
        self.assertIn("Role / profile metadata", api_screen)
        self.assertIn("presentation only", api_screen)
        self.assertIn("Badge и подписи объясняют admitted metadata", api_screen)
        self.assertIn("не меняют authority, capability или runtime truth", api_screen)
        self.assertIn("Profile packet остаётся support surface", api_screen)
        self.assertIn("support-only", api_screen)
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

    def test_api_route_identity_renders_role_pill_as_metadata_only(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function createElement(tagName) {
  return {
    tagName,
    className: "",
    textContent: "",
    title: "",
    dataset: {},
    children: [],
    append(...nodes) {
      this.children.push(...nodes);
    },
    appendChild(node) {
      this.children.push(node);
    },
    addEventListener() {},
    setAttribute(name, value) {
      this[name] = value;
    }
  };
}

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    createElement,
    getElementById() {
      return { textContent: "", className: "", hidden: false, children: [], append() {}, appendChild() {}, addEventListener() {}, setAttribute() {} };
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { source: "fixture", screen: "api-connections" } }; }
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

function flattenText(node) {
  return [node.textContent || "", ...(node.children || []).flatMap(flattenText)].join(" | ");
}

const mainIdentity = sandbox.routeIdentity({
  route_id: "wbp-main",
  display_name: "OpenAI registry entry",
  role_label: "main route",
  primary: true
});
const reserveIdentity = sandbox.routeIdentity({
  route_id: "wbp-reserve",
  display_name: "Reserve candidate",
  role_label: "Допустим для резерва",
  primary: false
});

const mainText = flattenText(mainIdentity);
const reserveText = flattenText(reserveIdentity);
if (!mainText.includes("Основной маршрут")) {
  throw new Error(`main route pill missing: ${mainText}`);
}
if (mainText.includes("main route")) {
  throw new Error(`raw main route leaked into rendered copy: ${mainText}`);
}
if (!reserveText.includes("Резервный кандидат")) {
  throw new Error(`reserve role pill missing: ${reserveText}`);
}
if (!mainIdentity.children.some((child) => child.className === "api-route-meta")) {
  throw new Error(`route meta container missing: ${JSON.stringify(mainIdentity)}`);
}
const rolePill = sandbox.routeRolePill({ role_label: "main route", primary: true });
if (!rolePill || rolePill.className !== "mini-pill api-route-role-pill blue") {
  throw new Error(`main role pill class mismatch: ${JSON.stringify(rolePill)}`);
}
if (!rolePill.title.includes("admitted metadata")) {
  throw new Error(`role pill title missing metadata boundary: ${rolePill.title}`);
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
        diagnostics_markup = html.split('id="diagnosticsScreen"', 1)[1].split('id="settingsScreen"', 1)[0]
        self.assertIn("renderDiagnosticsAction", js)
        self.assertIn("artifactReference(data.bundle_path)", js)
        self.assertNotIn("Показать журнал", html)
        self.assertNotIn("Открыть auth", html)
        self.assertNotIn("В резерв", html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("readAsText", js)
        self.assertNotIn("localStorage", diagnostics_markup)
        self.assertNotIn("diagnostics export --json", html + js)
        self.assertNotIn("runtime healthy", (html + js).lower())
        self.assertNotIn("pilot", html + js)
        self.assertNotIn("scale proof", html + js)
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
        self.assertIn('data-client-launch-surface="native-proof-preview"', settings_markup)
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
        self.assertIn("selected client · readiness · server-owned native proof", client_markup)
        self.assertIn("Green success требует process, identity и native window proof.", client_markup)
        self.assertIn("Server-owned lane only. Green success требует packet proof и refresh.", client_markup)
        self.assertIn("Native launch lane показывает process/window proof; dispatch-only и workbench-only не считаются запуском клиента.", client_markup)
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
        self.assertIn("review packet preview", settings_markup)
        self.assertIn("supported · local JSON review packet only", settings_markup)
        self.assertIn("exact-text safe apply", settings_markup)
        self.assertIn(
            "supported · one exact text change only, with receipt and recovery",
            settings_markup,
        )
        self.assertIn("import-existing lane", settings_markup)
        self.assertIn(
            "supported · explicit confirm required, narrow lane only",
            settings_markup,
        )
        self.assertIn("DOCX export baseline", settings_markup)
        self.assertIn("Markdown export", settings_markup)
        self.assertIn("Text export", settings_markup)
        self.assertIn("DOCX review import", settings_markup)
        self.assertIn("not supported yet", settings_markup)
        self.assertIn("Word / Google Docs roundtrip", settings_markup)
        self.assertIn("Structural auto-apply", settings_markup)
        self.assertIn("Mass apply", settings_markup)
        self.assertIn("Full sync", settings_markup)
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
            "launch_custom_client_native",
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
        self.assertNotIn("localStorage", settings_markup)
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

    def test_first_useful_release_claim_matrix_is_user_facing_and_narrow(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        readme = (ROOT / "README.md").read_text()
        combined = readme + "\n" + html

        self.assertIn("## First useful release claim matrix", readme)
        self.assertIn(
            "`Review packet preview`: supported; local JSON review packet only",
            readme,
        )
        self.assertIn(
            "`Exact-text safe apply`: supported; one exact text change only, with receipt and recovery",
            readme,
        )
        self.assertIn(
            "`Import-existing lane`: supported; explicit confirm required, narrow lane only",
            readme,
        )
        self.assertIn(
            "`DOCX export baseline`: not claimed in this first useful release",
            readme,
        )
        self.assertIn(
            "`Markdown export`: not claimed in this first useful release",
            readme,
        )
        self.assertIn(
            "`Text export`: not claimed in this first useful release",
            readme,
        )
        self.assertIn("`DOCX review import`: not supported yet", readme)
        self.assertIn("`Word / Google Docs roundtrip`: not claimed", readme)
        self.assertIn("`Structural auto-apply`: not claimed", readme)
        self.assertIn("`Mass apply`: not claimed", readme)
        self.assertIn("`Full sync`: not claimed", readme)

        self.assertIn(
            "supported · local JSON review packet only",
            html,
        )
        self.assertIn(
            "supported · one exact text change only, with receipt and recovery",
            html,
        )
        self.assertIn(
            "supported · explicit confirm required, narrow lane only",
            html,
        )
        self.assertIn("DOCX review import", html)
        self.assertIn("not supported yet", html)
        self.assertIn("Word / Google Docs roundtrip", html)
        self.assertIn("not claimed", html)

        for forbidden in (
            "DOCX review import supported",
            "Word / Google Docs roundtrip supported",
            "structural auto-apply supported",
            "mass apply supported",
            "full sync supported",
            "import-existing lane supported without explicit confirm",
        ):
            self.assertNotIn(forbidden, combined)

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
        self.assertIn('data-client-launch-surface="native-proof-preview"', client_markup)
        self.assertIn("clientLaunchModelFromSnapshot", js)
        self.assertIn("launchPreflightSummary", js)
        self.assertIn("renderClientLaunchSnapshot", js)
        self.assertIn('url.searchParams.set("section", nextSettingsSection)', js)
        self.assertIn("Client status недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Client status устарел. Требуется refresh из bounded packet.", js)
        self.assertIn("Демо-режим. Native Custom launch admitted только через server-owned proof lane.", js)
        self.assertIn("native proof admitted", js)
        self.assertIn("server-owned custom native endpoint", js)

        self.assertIn("Выбранный клиент", client_markup)
        self.assertIn("Launch readiness", client_markup)
        self.assertIn("Запуск клиента", client_markup)
        self.assertIn("Candidate / selection boundary", client_markup)
        self.assertIn("Deferred native actions", client_markup)
        self.assertIn("selected client · readiness · server-owned native proof", client_markup)
        self.assertIn("Client preview не является runtime readiness или доказательством локального файла.", client_markup)
        self.assertIn("Green success требует process, identity и native window proof.", client_markup)
        self.assertIn("Copy preflight", client_markup)
        self.assertIn("Process proof", client_markup)
        self.assertIn("Native launch lane", client_markup)
        self.assertIn("Server-owned lane only. Green success требует packet proof и refresh.", client_markup)
        self.assertIn("dispatch-only и workbench-only не считаются запуском клиента", client_markup)
        self.assertIn("Кандидаты выбираются только из command-owned list.", client_markup)
        self.assertIn("Ручной выбор файла: desktop/native only.", client_markup)
        self.assertIn("Web path payload forbidden.", client_markup)
        self.assertIn("Показать в Finder · human-open not admitted", client_markup)
        self.assertIn("Запустить Custom Codex", client_markup)
        self.assertIn('id="clientActionPreflight"', client_markup)
        self.assertIn('id="clientActionPhase"', client_markup)

        self.assertIn('data-ui-action="launch_custom_client_native"', client_markup)
        self.assertIn('data-ui-action="launch_smoke"', client_markup)
        self.assertEqual(client_markup.count("data-ui-action="), 2)
        self.assertIn('data-screen-link="select-client"', client_markup)
        self.assertIn('data-screen-link="diagnostics"', client_markup)
        self.assertIn("launch_custom_client_native:", js)
        self.assertIn("server-owned custom native endpoint", js)
        self.assertIn("Green success requires process, identity, and native window proof.", js)
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
        self.assertIn('data-ui-action="launch_custom_client_native"', html)
        overview_button = re.search(r'<button id="launchClientAction"[^>]+data-ui-action="([^"]+)"', html)
        self.assertIsNotNone(overview_button)
        self.assertEqual(overview_button.group(1), "launch_custom_client_native")
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
    next_action: "accounts_onboard",
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

    def test_blocked_ui_action_uses_metadata_reason_in_action_panel(self) -> None:
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
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (token) => this.className.split(/\s+/).filter(Boolean).includes(token),
      add: () => {},
      remove: () => {},
      toggle: () => {}
    };
  }
  append(...items) {
    this.children.push(...items);
    if (items.length) {
      this.lastElementChild = items[items.length - 1];
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
  querySelector() { return new Node(); }
  querySelectorAll() { return []; }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    this[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attributes[name];
    delete this[name];
  }
}

const elements = {};
function node(id) {
  if (!elements[id]) {
    elements[id] = new Node(id);
  }
  return elements[id];
}
const desktop = new Node("div");
desktop.dataset = { screen: "quick-start", source: "live", fixtureState: "healthy" };

let fetchCount = 0;
const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) { return new Node(tag); },
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
    fetchCount += 1;
    if (url !== "api/actions") {
      throw new Error(`unexpected fetch ${url}`);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({
        action_phase: "live_readonly",
        actions: {
          api_route_credential_check: {
            ui_action: "api_route_credential_check",
            display_name: "Проверить credential",
            human_meaning: "server-owned credential check",
            action_role: "api_route_probe",
            mutates_runtime: false,
            affects_primary_truth: false,
            confirmation_required: false,
            post_action_refresh_required: false,
            action_claim_scope: "server_packet_only",
            available: false,
            availability_state: "disabled_live_action",
            disabled_reason_code: "RUNTIME_LIVE_ACTION_CHAIN_PARKED",
            disabled_reasons: ["LOCK_HELD", "claim_gate_blocked"],
            unavailable_reason: "Runtime/live-action chain parked by packet metadata."
          }
        }
      })
    });
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  await sandbox.loadActionMetadata();
  sandbox.maybeConfirmAndRun("api_route_credential_check");
  if (fetchCount !== 1) {
    throw new Error(`blocked action must not dispatch another request, got ${fetchCount}`);
  }
  if (elements.actionMachineCode.textContent !== "RUNTIME_LIVE_ACTION_CHAIN_PARKED") {
    throw new Error(`metadata machine code not surfaced: ${elements.actionMachineCode.textContent}`);
  }
  if (elements.actionDisplayState.textContent !== "integration_failure") {
    throw new Error(`blocked display state must stay non-green: ${elements.actionDisplayState.textContent}`);
  }
  if (!elements.actionMessage.textContent.includes("parked")) {
    throw new Error(`metadata unavailable reason missing: ${elements.actionMessage.textContent}`);
  }
  if (elements.actionChangedFiles.textContent !== "0 записей метаданных") {
    throw new Error(`blocked action must not claim changed files: ${elements.actionChangedFiles.textContent}`);
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
  "uiLaneExitForwardPlan",
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
if (!elements.uiLaneExitTruthNote.textContent.includes("must not claim a forward repair route")) {
  throw new Error(`exit summary must avoid forward repair claims: ${elements.uiLaneExitTruthNote.textContent}`);
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
if (elements.uiLaneExitForwardPlan.textContent !== "NO_ACTIVE_REPO_FORWARD_PLAN") {
  throw new Error(`unexpected forward-plan claim: ${elements.uiLaneExitForwardPlan.textContent}`);
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
            "launch_custom_client_native",
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
        overview_button = re.search(r'<button id="launchClientAction"[^>]+data-ui-action="([^"]+)"', html)
        self.assertIsNotNone(overview_button)
        self.assertEqual(overview_button.group(1), "launch_custom_client_native")
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
if (settingsLaunchAvailability.textContent.indexOf("native launch blocked") === -1) {
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

    def test_overview_launch_button_targets_native_custom_action_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        overview_button = re.search(r'<button id="launchClientAction"[^>]+data-ui-action="([^"]+)"', html)
        self.assertIsNotNone(overview_button)
        self.assertEqual(overview_button.group(1), "launch_custom_client_native")
        self.assertNotIn('id="launchClientAction" class="button primary live-action overview-only" type="button" data-ui-action="launch_client_dispatch"', html)
        self.assertIn("launch_custom_client_native:", js)
        self.assertIn('uiAction === "launch_custom_client_native"', js)
        self.assertIn("Запросить native запуск", js)

    def test_custom_launch_render_keeps_workbench_only_packets_non_green(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

node("codexLaunchModesChip").lastElementChild = { textContent: "" };
node("customCodexStatus");
node("customCodexSession");
node("codexLaunchDryRunResponse");

const sandbox = {
  console,
  Node,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "overview" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
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
renderCodexCustomLaunch({
  status: "ok",
  machine_error_code: "OK",
  session_created: true,
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_workdir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: false,
  expected_custom_identity_observed: false,
  native_window_observed: false,
  native_app_usable: false,
  workbench_ready: true,
  launch_claim_scope: "isolated_session_workbench_launch_ready",
  next_action: "prompt"
});
`, sandbox);

if (!node("codexLaunchModesChip").className.includes("amber")) {
  throw new Error(`workbench-only launch must stay amber: ${node("codexLaunchModesChip").className}`);
}
if (node("codexLaunchModesChip").lastElementChild.textContent !== "workbench/session only") {
  throw new Error(`unexpected chip label: ${node("codexLaunchModesChip").lastElementChild.textContent}`);
}
if (node("customCodexSession").textContent !== "workbench/session only") {
  throw new Error(`unexpected session label: ${node("customCodexSession").textContent}`);
}
const rendered = JSON.parse(node("codexLaunchDryRunResponse").textContent);
if (rendered.process_started !== false) {
  throw new Error(`process_started should remain false: ${JSON.stringify(rendered)}`);
}
if (rendered.expected_custom_identity_observed !== false) {
  throw new Error(`identity proof should remain false: ${JSON.stringify(rendered)}`);
}
if (rendered.native_window_observed !== false) {
  throw new Error(`window proof should remain false: ${JSON.stringify(rendered)}`);
}
if (rendered.native_app_usable !== false) {
  throw new Error(`native app usability should remain false: ${JSON.stringify(rendered)}`);
}
if (node("customCodexStatus").textContent !== "ok · isolated_session_workbench_launch_ready") {
  throw new Error(`unexpected status copy: ${node("customCodexStatus").textContent}`);
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

    def test_custom_launch_render_accepts_window_proof_without_usability_greenwash(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

function makeChip() {
  const chip = new Node();
  chip.lastElementChild = new Node();
  chip.children = [chip.lastElementChild];
  return chip;
}

const nodes = {
  codexLaunchModesChip: makeChip(),
  customCodexStatus: new Node(),
  customCodexSession: new Node(),
  codexLaunchDryRunResponse: new Node()
};

const sandbox = {
  console,
  window: { location: { search: "" }, history: { replaceState() {} } },
  document: {
    getElementById(id) { return nodes[id] || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {}
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
renderCodexCustomLaunch({
  status: "ok",
  machine_error_code: "OK",
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: true,
  expected_custom_identity_observed: true,
  native_window_observed: true,
  native_app_usable: false,
  real_codex_app_launched: true,
  launch_claim_scope: "custom_native_app_window_launch_only",
  quick_start_stable_custom_launch_final_status: "QUICK_START_STABLE_CUSTOM_LAUNCH_WITH_PROFILE_REUSE_PROVEN_WITH_LIMITS",
  profile_final_status: "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS",
  session_storage_final_status: "KNOWN_BLOCKER_CUSTOM_CODEX_SESSION_STORAGE_NOT_OBSERVED",
  profile_persistence_proven: true,
  persistent_profile_reused: true,
  codex_home_reused: true,
  electron_user_data_reused: true,
  profile_path_stable: true,
  persistent_profile_root_is_tmp: false,
  persistent_codex_home_is_tmp: false,
  persistent_user_data_dir_is_tmp: false,
  profile_relaunch_required_for_strong_history_claim: true,
  custom_codex_window_deepseek_smoke_final_status: "CUSTOM_CODEX_WINDOW_DEEPSEEK_LAUNCH_PROVEN_PROMPT_SMOKE_BLOCKED_WITH_LIMITS",
  custom_codex_window_deepseek_launch_proven_with_limits: true,
  manual_prompt_smoke_attempted: false,
  manual_prompt_smoke_proven: false,
  manual_prompt_smoke_counts_as_model_truth: false,
  manual_prompt_smoke_blocked_reason: "manual_native_window_prompt_not_automated",
  model_self_report_counts_as_runtime_truth: false,
  deepseek_window_prompt_runtime_truth_proven: false,
  history_persistence_claimed: false,
  visible_thread_history_restored_claimed: false,
  next_action: "none"
});
`, sandbox);

if (!nodes.codexLaunchModesChip.className.includes("amber")) {
  throw new Error(`window-only proof should stay amber: ${nodes.codexLaunchModesChip.className}`);
}
if (nodes.codexLaunchModesChip.className.includes("green")) {
  throw new Error(`window-only proof must not turn chip green: ${nodes.codexLaunchModesChip.className}`);
}
if (nodes.codexLaunchModesChip.lastElementChild.textContent !== "window visible / proof incomplete") {
  throw new Error(`unexpected chip label: ${nodes.codexLaunchModesChip.lastElementChild.textContent}`);
}
if (nodes.customCodexSession.textContent !== "window visible; native proof incomplete") {
  throw new Error(`unexpected session label: ${nodes.customCodexSession.textContent}`);
}
const rendered = JSON.parse(nodes.codexLaunchDryRunResponse.textContent);
if (rendered.native_app_usable !== false) {
  throw new Error(`native_app_usable should stay false when only window proof passed: ${JSON.stringify(rendered)}`);
}
if (rendered.real_codex_app_launched !== true) {
  throw new Error(`real_codex_app_launched should be true: ${JSON.stringify(rendered)}`);
}
if (rendered.custom_codex_window_deepseek_smoke_final_status !== "CUSTOM_CODEX_WINDOW_DEEPSEEK_LAUNCH_PROVEN_PROMPT_SMOKE_BLOCKED_WITH_LIMITS") {
  throw new Error(`window smoke status should render: ${JSON.stringify(rendered)}`);
}
if (rendered.quick_start_stable_custom_launch_final_status !== "QUICK_START_STABLE_CUSTOM_LAUNCH_WITH_PROFILE_REUSE_PROVEN_WITH_LIMITS") {
  throw new Error(`stable launch final status should render: ${JSON.stringify(rendered)}`);
}
if (rendered.profile_final_status !== "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS" || rendered.profile_persistence_proven !== true) {
  throw new Error(`profile persistence should render separately: ${JSON.stringify(rendered)}`);
}
if (rendered.persistent_profile_root_is_tmp !== false || rendered.persistent_user_data_dir_is_tmp !== false) {
  throw new Error(`persistent profile paths must not be tmp for normal launch: ${JSON.stringify(rendered)}`);
}
if (rendered.custom_codex_window_deepseek_launch_proven_with_limits !== true) {
  throw new Error(`window launch proof should render true: ${JSON.stringify(rendered)}`);
}
if (rendered.manual_prompt_smoke_attempted !== false || rendered.manual_prompt_smoke_proven !== false) {
  throw new Error(`manual prompt smoke must stay unproven: ${JSON.stringify(rendered)}`);
}
if (rendered.model_self_report_counts_as_runtime_truth !== false) {
  throw new Error(`model self-report must not count as truth: ${JSON.stringify(rendered)}`);
}
if (rendered.history_persistence_claimed !== false || rendered.visible_thread_history_restored_claimed !== false) {
  throw new Error(`history must not be claimed by window smoke: ${JSON.stringify(rendered)}`);
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

    def test_custom_launch_render_shows_limited_window_launch_without_green_claim(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
  }
  return nodes[id];
}

node("codexLaunchModesChip").lastElementChild = { textContent: "" };
node("quickStartLaunchState").lastElementChild = { textContent: "" };
node("quickStartRouteChip").lastElementChild = { textContent: "" };
node("customCodexStatus");
node("customCodexSession");
node("codexLaunchDryRunResponse");
node("quickStartRouteResponse");

const sandbox = {
  console,
  Node,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "overview" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return node(id); }
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
renderCodexCustomLaunch({
  status: "blocked",
  machine_error_code: "CUSTOM_NATIVE_WINDOW_NOT_PROVEN",
  session_created: false,
  running_status: true,
  isolated_home: true,
  isolated_codex_home: true,
  isolated_profile_dir: true,
  server_issued_model_list: true,
  wbp_endpoint_configured: true,
  browser_route_injection: false,
  browser_backend_injection: false,
  current_codex_touched: false,
  process_started: true,
  expected_custom_identity_observed: true,
  native_window_observed: true,
  native_app_usable: false,
  real_codex_app_launched: false,
  launch_claim_scope: "custom_native_app_window_launch_only",
  next_action: "stop_and_diagnose_native_launch"
});
`, sandbox);

if (!node("codexLaunchModesChip").className.includes("amber")) {
  throw new Error(`limited native window launch must stay amber: ${node("codexLaunchModesChip").className}`);
}
if (node("codexLaunchModesChip").className.includes("green")) {
  throw new Error(`limited native window launch must not be green: ${node("codexLaunchModesChip").className}`);
}
if (node("codexLaunchModesChip").lastElementChild.textContent !== "window visible / proof incomplete") {
  throw new Error(`unexpected chip label: ${node("codexLaunchModesChip").lastElementChild.textContent}`);
}
if (node("quickStartLaunchState").lastElementChild.textContent !== "окно открыто") {
  throw new Error(`quick-start launch state did not show opened window: ${node("quickStartLaunchState").lastElementChild.textContent}`);
}
if (node("quickStartRouteChip").lastElementChild.textContent !== "proof incomplete") {
  throw new Error(`route chip did not show limited proof: ${node("quickStartRouteChip").lastElementChild.textContent}`);
}
if (node("customCodexSession").textContent !== "window visible; native proof incomplete") {
  throw new Error(`unexpected session label: ${node("customCodexSession").textContent}`);
}
const rendered = JSON.parse(node("quickStartRouteResponse").textContent);
if (rendered.status !== "blocked" || rendered.native_window_observed !== true || rendered.real_codex_app_launched !== false) {
  throw new Error(`limited native launch truth not preserved: ${JSON.stringify(rendered)}`);
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

    def test_deepseek_code_edit_proof_does_not_green_window_without_usability(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function Node() {
  this.textContent = "";
  this.className = "";
  this.hidden = false;
  this.dataset = {};
  this.children = [];
  this.lastElementChild = null;
}

function makeChip() {
  const chip = new Node();
  chip.lastElementChild = new Node();
  chip.children = [chip.lastElementChild];
  return chip;
}

const nodes = {
  quickStartRouteChip: makeChip(),
  quickStartExecutionModeState: makeChip(),
  quickStartLaunchState: makeChip(),
  quickStartRouteResponse: new Node()
};

const sandbox = {
  console,
  Node,
  document: {
    addEventListener() {},
    querySelector() { return { dataset: { source: "fixture", screen: "quick-start" } }; },
    querySelectorAll() { return []; },
    getElementById(id) { return nodes[id] || null; }
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
renderQuickStartDeepSeekCodeEditProof({
  status: "blocked",
  machine_error_code: "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_NOT_PROVEN",
  final_status: "KNOWN_BLOCKER_CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCTION_FAILED",
  execution_mode: "api_only",
  selected_model: "wbp-deepseek-v4-pro-max",
  api_model_id: "wbp-deepseek-v4-pro-max",
  native_app_usable: false,
  window_launch_proven_with_limits: true
});
`, sandbox);

if (nodes.quickStartLaunchState.className.includes("green")) {
  throw new Error(`legacy window proof must not turn launch state green: ${nodes.quickStartLaunchState.className}`);
}
if (!nodes.quickStartLaunchState.className.includes("amber")) {
  throw new Error(`legacy window proof should stay amber: ${nodes.quickStartLaunchState.className}`);
}
if (nodes.quickStartLaunchState.lastElementChild.textContent !== "окно не доказано") {
  throw new Error(`unexpected launch label: ${nodes.quickStartLaunchState.lastElementChild.textContent}`);
}
const rendered = JSON.parse(nodes.quickStartRouteResponse.textContent);
if (rendered.window_launch_proven_with_limits !== true || rendered.native_app_usable !== false) {
  throw new Error(`rendered packet lost the split truth: ${JSON.stringify(rendered)}`);
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
        try:
            from PIL import Image
        except ModuleNotFoundError as exc:
            self.skipTest(f"PIL unavailable: {exc}")

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

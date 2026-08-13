# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R64 static contracts for the registry-bound workflow product screen."""

from __future__ import annotations

import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "wild_boar_proxy" / "web_design_ui"


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])


class WebWorkflowUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (UI / "index.html").read_text(encoding="utf-8")
        cls.js = (UI / "scripts" / "overview.js").read_text(encoding="utf-8")
        cls.css = (UI / "styles" / "overview.css").read_text(encoding="utf-8")

    def test_workflow_screen_has_navigation_composer_progress_and_history(self) -> None:
        parser = _IdCollector()
        parser.feed(self.html)
        required = {
            "workflowsNav",
            "workflowsScreen",
            "workflowActorList",
            "workflowStepList",
            "workflowModeControlled",
            "workflowModeLive",
            "workflowAddStep",
            "workflowRun",
            "workflowProgress",
            "workflowHistoryBody",
        }
        self.assertTrue(required.issubset(parser.ids), required - parser.ids)
        self.assertIn('data-screen-link="workflows"', self.html)
        self.assertIn('aria-live="polite"', self.html)

    def test_browser_payload_contains_intent_only(self) -> None:
        payload_source = self.js.split("function workflowRunPayload()", 1)[1].split(
            "function validateWorkflowDraft()", 1
        )[0]
        for allowed in (
            "step_request_id",
            "alias",
            "prompt",
            "role_instruction",
            "context_policy",
            "fork_from",
            "repo_touching",
        ):
            self.assertIn(allowed, payload_source)
        for forbidden in (
            "provider_id",
            "route_id",
            "slot_id",
            "binding_revision",
            "assignment_revision",
            "credential_ref",
        ):
            self.assertNotIn(forbidden, payload_source)

    def test_post_uses_shared_web_auth_headers_and_live_is_server_gated(self) -> None:
        run_source = self.js.split("async function runWorkflowControl()", 1)[1].split(
            "function operatorSetText", 1
        )[0]
        self.assertIn('fetch("api/workflow/run"', run_source)
        self.assertIn('webPostHeaders({ "Content-Type": "application/json" })', run_source)
        self.assertIn('liveInput.disabled = !liveAdmitted || source !== "live"', self.js)
        self.assertIn('workflowExecutionAdmitted = source === "live"', self.js)
        self.assertIn('run.disabled = !workflowExecutionAdmitted', self.js)

    def test_keyboard_and_mobile_contracts_are_present(self) -> None:
        self.assertIn('event.metaKey || event.ctrlKey', self.js)
        self.assertIn('@media (max-width: 560px)', self.css)
        self.assertIn('.workflow-control-layout', self.css)
        self.assertIn('font-size: 16px;', self.css)

    def test_javascript_is_syntactically_valid(self) -> None:
        node = Path(
            "/Users/kirillponomarev/.cache/codex-runtimes/"
            "codex-primary-runtime/dependencies/node/bin/node"
        )
        completed = subprocess.run(
            [str(node), "--check", str(UI / "scripts" / "overview.js")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()

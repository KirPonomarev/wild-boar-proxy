#!/usr/bin/env python3
import asyncio
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path.cwd()
UI_DIR = REPO / "wild_boar_proxy" / "web_design_ui"
OUT_DIR = REPO / "audit_results" / "ui_web_action_ledger_canonical_panel_pass_2026-05-14"
SCREENSHOTS_DIR = OUT_DIR / "screenshots" / "after"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


ACTION_METADATA = {
    "sync_runtime": {
        "available": True,
        "display_name": "Сверка",
        "human_meaning": "Запросить bounded sync.",
        "action_role": "runtime_sync",
        "mutates_runtime": True,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "runtime_state",
    },
    "validate_account": {
        "available": True,
        "display_name": "Проверить аккаунт",
        "human_meaning": "Запросить проверку аккаунта.",
        "action_role": "account_verification",
        "mutates_runtime": True,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account_lifecycle",
    },
    "onboard_account": {
        "available": True,
        "display_name": "Добавить в резерв",
        "human_meaning": "Запустить reserve-first onboarding.",
        "action_role": "account_onboarding",
        "mutates_runtime": True,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account_lifecycle",
    },
    "export_diagnostics": {
        "available": True,
        "display_name": "Экспорт",
        "human_meaning": "Создать support artifact.",
        "action_role": "support_artifact",
        "mutates_runtime": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "support_artifact",
    },
}

BASE_FIXTURE = {
    "schema_version": 1,
    "status": "ok",
    "state_id": "healthy",
    "source": "fixture",
    "has_warnings": False,
    "runtime": {
        "visual_state": "healthy",
        "status_label": "Работает",
        "desired_mode": "managed",
        "effective_mode": "managed",
        "endpoint": "127.0.0.1:8320",
        "machine_error_code": "OK",
        "human_message": "Capture fixture",
        "last_error": "",
        "observed_at_utc": "capture",
    },
    "pool_summary": {
        "active": 10,
        "reserve": 15,
        "hold": 1,
        "problem": 2,
        "active_note": "capture",
        "reserve_note": "capture",
        "hold_note": "capture",
        "problem_note": "capture",
    },
    "events": [],
}


def action_payload(kind):
    if kind == "empty":
        return None, "none"
    if kind == "running":
        return {
            "ui_action": "validate_account",
            "action_role": "account_verification",
            "account_id": "acc-021",
            "post_action_refresh_required": False,
            "result": {
                "status": "running",
                "machine_error_code": "RUNNING",
                "human_message": "Действие выполняется.",
                "next_action": "wait",
                "changed_files": [],
            },
        }, "none"
    if kind in {"success_refresh_complete", "success_refresh_pending", "refresh_failed"}:
        refresh = {
            "success_refresh_complete": "complete",
            "success_refresh_pending": "none",
            "refresh_failed": "failed",
        }[kind]
        return {
            "status": "ok",
            "ui_action": "sync_runtime",
            "action_role": "runtime_sync",
            "post_action_refresh_required": True,
            "result": {
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "Сверка выполнена, требуется подтверждение refresh.",
                "next_action": "refresh_runtime",
                "changed_files": ["/private/tmp/runtime-a.json"],
            },
        }, refresh
    if kind == "command_error":
        return {
            "status": "command_error",
            "ui_action": "sync_runtime",
            "action_role": "runtime_sync",
            "post_action_refresh_required": False,
            "result": {
                "status": "command_error",
                "machine_error_code": "COMMAND_FAILED",
                "human_message": "Команда не выполнена.",
                "next_action": "retry",
                "changed_files": [],
            },
        }, "none"
    if kind in {"invalid_json", "timeout"}:
        status = "invalid_json" if kind == "invalid_json" else "timeout"
        machine = "UI_ACTION_INVALID_JSON" if kind == "invalid_json" else "UI_ACTION_TIMEOUT"
        return {
            "ui_action": "validate_account",
            "action_role": "integration_failure",
            "account_id": "acc-021",
            "post_action_refresh_required": False,
            "result": {
                "status": status,
                "machine_error_code": machine,
                "human_message": "Endpoint не вернул admitted response.",
                "next_action": "retry",
                "changed_files": [],
            },
        }, "none"
    if kind == "duplicate_blocked":
        return {
            "status": "duplicate_blocked",
            "ui_action": "validate_account",
            "action_role": "ui_session_guard",
            "account_id": "acc-021",
            "post_action_refresh_required": False,
            "result": {
                "status": "duplicate_blocked",
                "machine_error_code": "UI_DUPLICATE_SUBMIT_BLOCKED",
                "human_message": "Повторная отправка заблокирована в текущей UI-сессии.",
                "next_action": "wait",
                "changed_files": [],
            },
        }, "none"
    if kind == "onboarding_ambiguous":
        return {
            "status": "ok",
            "ui_action": "onboard_account",
            "action_role": "account_onboarding",
            "post_action_refresh_required": True,
            "result": {
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "Onboarding требует выбора оператора.",
                "next_action": "operator_action",
                "changed_files": [],
                "onboarding": {
                    "ui_state": "needs_user_action",
                    "final_outcome": "ambiguous_new_auth_detection",
                    "selected_backend_id": "hidden",
                    "reserve_first_proven": False,
                    "selection_status": "ambiguous",
                },
            },
        }, "none"
    if kind == "diagnostics_export_result":
        return {
            "status": "ok",
            "ui_action": "export_diagnostics",
            "action_role": "support_artifact",
            "post_action_refresh_required": False,
            "result": {
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "Диагностический пакет поддержки экспортирован.",
                "exit_code": 0,
                "next_action": "none",
                "changed_files": ["/private/tmp/wbp-diagnostics-secret"],
                "data": {
                    "bundle_path": "/private/tmp/wbp-diagnostics-secret",
                    "redaction_status": "enforced",
                },
            },
        }, "none"
    raise ValueError(kind)


SCENARIOS = [
    "empty",
    "running",
    "success_refresh_complete",
    "success_refresh_pending",
    "refresh_failed",
    "command_error",
    "invalid_json",
    "timeout",
    "duplicate_blocked",
    "onboarding_ambiguous",
    "diagnostics_export_result",
]


def injected_html(name):
    payload, refresh = action_payload(name)
    base = (UI_DIR / "index.html").read_text()
    pre_script = f"""
<script>
window.__captureActions = {json.dumps(ACTION_METADATA, ensure_ascii=False)};
window.__captureOverviewFixture = {json.dumps(BASE_FIXTURE, ensure_ascii=False)};
const __captureOriginalFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {{
  const url = String(input);
  if (url === "api/actions" || url.endsWith("/api/actions")) {{
    return new Response(JSON.stringify({{ actions: window.__captureActions }}), {{ status: 200, headers: {{ "Content-Type": "application/json" }} }});
  }}
  if (url.startsWith("fixtures/") || url.includes("/fixtures/")) {{
    return new Response(JSON.stringify(window.__captureOverviewFixture), {{ status: 200, headers: {{ "Content-Type": "application/json" }} }});
  }}
  return __captureOriginalFetch(input, init);
}};
</script>"""
    post_script = f"""
<script>
window.__captureScenario = {json.dumps({"name": name, "payload": payload, "refresh": refresh}, ensure_ascii=False)};
function __captureCollect() {{
  const panel = document.getElementById("actionLedgerPanel");
  const card = document.getElementById("actionPanel");
  const root = document.documentElement;
  const panelRect = panel.getBoundingClientRect();
  const cardRect = card.getBoundingClientRect();
  const ledgerTextFull = document.getElementById("actionLedgerList").textContent;
  const clipped = Array.from(document.querySelectorAll("#actionLedgerPanel button, #actionLedgerPanel .chip, #actionLedgerPanel .action-ledger-row, #actionPanel button, #actionPanel .chip")).filter((node) => {{
    const style = getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return false;
    return node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 2;
  }}).slice(0, 12).map((node) => ({{
    tag: node.tagName,
    id: node.id || "",
    className: node.className || "",
    text: node.textContent.trim().slice(0, 80),
    scrollWidth: node.scrollWidth,
    clientWidth: node.clientWidth,
    scrollHeight: node.scrollHeight,
    clientHeight: node.clientHeight
  }}));
  return {{
    scenario: window.__captureScenario.name,
    displayState: document.getElementById("actionDisplayState").textContent.trim(),
    cardClass: card.className,
    ledgerHidden: document.getElementById("actionLedgerOverlay").hidden,
    ledgerRows: document.querySelectorAll("#actionLedgerList .action-ledger-row").length,
    emptyRows: document.querySelectorAll("#actionLedgerList .action-ledger-empty").length,
    summaryTitle: document.getElementById("actionSummaryTitle").textContent.trim(),
    summaryRefresh: document.getElementById("actionSummaryRefresh").textContent.trim(),
    ledgerText: ledgerTextFull.trim().slice(0, 600),
    viewport: {{ width: window.innerWidth, height: window.innerHeight }},
    document: {{ scrollWidth: root.scrollWidth, scrollHeight: root.scrollHeight }},
    panelRect: {{
      left: panelRect.left,
      right: panelRect.right,
      top: panelRect.top,
      bottom: panelRect.bottom,
      width: panelRect.width,
      height: panelRect.height,
      scrollWidth: panel.scrollWidth,
      clientWidth: panel.clientWidth
    }},
    compactCardRect: {{
      left: cardRect.left,
      right: cardRect.right,
      top: cardRect.top,
      bottom: cardRect.bottom,
      width: cardRect.width,
      height: cardRect.height
    }},
    visibleSvgIcons: Array.from(document.querySelectorAll("#actionLedgerPanel svg, #actionPanel svg")).filter((node) => node.getBoundingClientRect().width > 0).length,
    visibleImgIcons: Array.from(document.querySelectorAll("#actionLedgerPanel img, #actionPanel img")).filter((node) => node.getBoundingClientRect().width > 0).length,
    fileInputs: document.querySelectorAll("input[type=file]").length,
    rawPathVisible: ledgerTextFull.includes("/private/tmp/") || ledgerTextFull.includes("/tmp/runtime"),
    rawArgvVisible: /argv|command_id/i.test(ledgerTextFull),
    clipped
  }};
}}
function __captureRun() {{
  setScreen("overview", false);
  renderSnapshot(window.__captureOverviewFixture);
  if (window.__captureScenario.payload) {{
    setActionPanel(window.__captureScenario.payload, window.__captureScenario.refresh || "none");
    if (window.__captureScenario.name === "onboarding_ambiguous") {{
      document.getElementById("actionPanel").classList.remove("onboarding-result-expanded");
      document.getElementById("onboardingResultFlow").hidden = true;
    }}
  }}
  openActionLedgerPanel();
  const pre = document.createElement("pre");
  pre.id = "captureMetrics";
  pre.textContent = JSON.stringify(__captureCollect());
  pre.hidden = true;
  document.body.append(pre);
  document.documentElement.dataset.captureReady = "true";
}}
window.addEventListener("load", () => window.setTimeout(__captureRun, 250));
</script>"""
    return (
        base.replace("<head>", f'<head>\n  <base href="file://{UI_DIR}/">')
        .replace(
            '<script src="scripts/overview.js"></script>',
            f'{pre_script}\n  <script src="scripts/overview.js"></script>\n  {post_script}',
        )
    )


class RawWebSocket:
    def __init__(self, port, path):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=6)
        self.sock.settimeout(6)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: http://127.0.0.1\r\n"
            "\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")

    def send_json(self, packet):
        data = json.dumps(packet).encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_json(self):
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 1:
                return json.loads(payload.decode("utf-8"))
            if opcode == 8:
                raise RuntimeError("WebSocket closed")
            if opcode == 9:
                self._send_pong(payload)

    def _recv_exact(self, length):
        chunks = []
        remaining = length
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket stream ended")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame(self):
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = int.from_bytes(self._recv_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._recv_exact(8), "big")
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _send_pong(self, payload):
        header = bytearray([0x8A, len(payload)])
        self.sock.sendall(bytes(header) + payload)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def cdp_send(ws, method, params=None, session_id=None, message_id=[0]):
    message_id[0] += 1
    packet = {"id": message_id[0], "method": method, "params": params or {}}
    if session_id:
        packet["sessionId"] = session_id
    ws.send_json(packet)
    while True:
        msg = ws.recv_json()
        if msg.get("id") == message_id[0]:
            return msg


def wait_for_debug_endpoint(profile):
    active_port = profile / "DevToolsActivePort"
    deadline = time.time() + 8
    while time.time() < deadline:
        if active_port.exists():
            lines = active_port.read_text().splitlines()
            if len(lines) >= 2:
                return int(lines[0]), lines[1]
        time.sleep(0.05)
    raise RuntimeError("DevToolsActivePort was not created")


def capture_one(name, html_path, screenshot_path):
    profile = Path(tempfile.mkdtemp(prefix=f"wbp-ledger-profile-{name}-"))
    proc = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--no-default-browser-check",
            "--no-first-run",
            "--allow-file-access-from-files",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            "--window-size=1600,1000",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        port, browser_path = wait_for_debug_endpoint(profile)
        ws = RawWebSocket(port, browser_path)
        try:
            created = cdp_send(ws, "Target.createTarget", {"url": "about:blank"})
            target_id = created["result"]["targetId"]
            attached = cdp_send(ws, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
            session_id = attached["result"]["sessionId"]
            cdp_send(ws, "Page.enable", session_id=session_id)
            cdp_send(ws, "Runtime.enable", session_id=session_id)
            cdp_send(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1600,
                "height": 1000,
                "deviceScaleFactor": 1,
                "mobile": False,
            }, session_id=session_id)
            cdp_send(ws, "Page.navigate", {"url": f"file://{html_path}"}, session_id=session_id)
            deadline = time.time() + 6
            while time.time() < deadline:
                ready = cdp_send(ws, "Runtime.evaluate", {
                    "expression": "document.documentElement.dataset.captureReady === 'true'",
                    "returnByValue": True,
                }, session_id=session_id)
                if ready.get("result", {}).get("result", {}).get("value") is True:
                    break
                time.sleep(0.1)
            metrics_result = cdp_send(ws, "Runtime.evaluate", {
                "expression": "document.getElementById('captureMetrics')?.textContent || ''",
                "returnByValue": True,
            }, session_id=session_id)
            metrics_text = metrics_result["result"]["result"].get("value", "")
            if not metrics_text:
                raise RuntimeError(f"capture metrics missing for {name}")
            shot = cdp_send(ws, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session_id=session_id)
            screenshot_path.write_bytes(base64.b64decode(shot["result"]["data"]))
            return json.loads(metrics_text)
        finally:
            ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wbp-ledger-capture-html-"))
    metrics = []
    try:
        for name in SCENARIOS:
            html_path = tmp / f"{name}.html"
            screenshot_path = SCREENSHOTS_DIR / f"{name}.png"
            html_path.write_text(injected_html(name))
            parsed = capture_one(name, html_path, screenshot_path)
            parsed["screenshot"] = str(Path("screenshots") / "after" / screenshot_path.name)
            metrics.append(parsed)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    (OUT_DIR / "after_metrics.json").write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": metrics,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Submit a bounded prompt into the real Custom Codex UI over CDP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.custom_codex_physical_observer import (  # noqa: E402
    ObserverMode,
    observe_visible_output,
)


DEFAULT_CDP_URL = "http://127.0.0.1:9223"
DEFAULT_NODE_BIN = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
)
DEFAULT_NODE_MODULES = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
)
DEFAULT_PROFILE_DIR = (
    Path.home()
    / "Library/Application Support/WildBoarProxy/CodexProfiles/wbp-custom-main"
)
DEFAULT_USER_DATA_DIR = DEFAULT_PROFILE_DIR / "electron-user-data"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_tail(value: str, limit: int = 4000) -> str:
    text = str(value or "")
    return text[-limit:]


def blocked_packet(
    *,
    machine_error_code: str,
    prompt: str,
    expected_text: str,
    mode: ObserverMode,
    evidence_dir: Path,
    cdp_url: str,
    blocking_reasons: list[str],
    owner_proof: dict[str, Any] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_version": 1,
        "packet_kind": "custom_codex_physical_smoke",
        "captured_at_utc": utc_now(),
        "status": "blocked",
        "machine_error_code": machine_error_code,
        "prompt_sha256": sha256_text(prompt),
        "prompt_text_recorded": False,
        "expected_text": expected_text,
        "expected_text_sha256": sha256_text(expected_text),
        "mode": mode,
        "cdp_url_recorded": False,
        "cdp_url_sha256": sha256_text(cdp_url),
        "evidence_dir": str(evidence_dir),
        "raw_text_recorded": False,
        "prompt_submitted": False,
        "blocking_reasons": blocking_reasons,
    }
    if owner_proof is not None:
        packet["cdp_owner_proof"] = owner_proof
    if extras:
        packet.update(extras)
    return packet


def _cdp_port(cdp_url: str) -> tuple[int | None, str]:
    parsed = urlparse(cdp_url)
    if parsed.scheme not in {"http", "https"}:
        return None, "cdp_url_scheme_not_http"
    hostname = parsed.hostname or ""
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None, "cdp_url_not_loopback"
    if parsed.port is None:
        return None, "cdp_url_port_missing"
    return int(parsed.port), "ok"


def _listening_pids_for_port(port: int) -> list[int]:
    if not shutil.which("lsof"):
        return []
    proc = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"],
        text=True,
        capture_output=True,
        check=False,
    )
    pids: list[int] = []
    for line in proc.stdout.splitlines():
        if not line.startswith("p"):
            continue
        try:
            pids.append(int(line[1:]))
        except ValueError:
            continue
    return sorted(set(pids))


def _process_command(pid: int) -> str:
    proc = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip()


def prove_cdp_owner(
    *,
    cdp_url: str,
    profile_dir: Path,
    user_data_dir: Path,
    allow_unbound_cdp: bool,
) -> dict[str, Any]:
    port, reason = _cdp_port(cdp_url)
    proof: dict[str, Any] = {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": "CUSTOM_PHYSICAL_CDP_OWNER_NOT_PROVEN",
        "cdp_owner_proven": False,
        "cdp_port": port,
        "profile_dir_recorded": False,
        "profile_dir_sha256": sha256_text(str(profile_dir.resolve(strict=False))),
        "user_data_dir_recorded": False,
        "user_data_dir_sha256": sha256_text(str(user_data_dir.resolve(strict=False))),
        "owner_process_command_recorded": False,
    }
    if allow_unbound_cdp:
        proof.update(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "cdp_owner_proven": False,
                "owner_proof_bypassed": True,
            }
        )
        return proof
    if port is None:
        proof["owner_block_reason"] = reason
        return proof
    pids = _listening_pids_for_port(port)
    proof["candidate_pid_count"] = len(pids)
    proof["candidate_pid_sha256"] = sha256_text(",".join(str(pid) for pid in pids))
    expected_user_data_arg = f"--user-data-dir={user_data_dir.resolve(strict=False)}"
    required_markers = (
        "Codex WBP Clean.app/Contents/MacOS/Codex",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        expected_user_data_arg,
    )
    owner_candidates: list[tuple[int, str]] = []
    for pid in pids:
        command = _process_command(pid)
        if all(marker in command for marker in required_markers):
            owner_candidates.append((pid, command))
    proof["owner_candidate_pid_count"] = len(owner_candidates)
    proof["owner_candidate_pid_sha256"] = sha256_text(
        ",".join(str(pid) for pid, _command in owner_candidates)
    )
    if len(owner_candidates) != 1:
        proof["owner_block_reason"] = "cdp_owner_process_not_unique"
        return proof
    pid, command = owner_candidates[0]
    proof["cdp_owner_pid"] = pid
    proof["owner_process_command_sha256"] = sha256_text(command)
    missing = [marker for marker in required_markers if marker not in command]
    if missing:
        proof["owner_block_reason"] = "cdp_listener_command_mismatch"
        proof["missing_marker_count"] = len(missing)
        proof["missing_marker_sha256"] = sha256_text(json.dumps(missing, sort_keys=True))
        return proof
    proof.update(
        {
            "status": "ok",
            "machine_error_code": "OK",
            "cdp_owner_proven": True,
            "owner_block_reason": "",
        }
    )
    return proof


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return str(args.prompt or "")


def discover_node_bin(value: str | None) -> str:
    if value:
        return value
    env_value = os.environ.get("WBP_NODE_BIN")
    if env_value:
        return env_value
    if DEFAULT_NODE_BIN.exists():
        return str(DEFAULT_NODE_BIN)
    found = shutil.which("node")
    return found or "node"


def discover_node_modules(value: str | None) -> str:
    if value:
        return value
    env_value = os.environ.get("WBP_NODE_MODULE_DIR")
    if env_value:
        return env_value
    return str(DEFAULT_NODE_MODULES)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_router_proof(
    *,
    proof_file: Path | None,
    expected_text: str,
    started_after_ns: int | None,
) -> dict[str, Any]:
    if proof_file is None:
        return {
            "router_proof_required": False,
            "router_proof_proven": False,
            "router_proof_machine_error_code": "",
            "router_proof_blocking_reasons": [],
        }

    proof_path = proof_file.expanduser()
    result: dict[str, Any] = {
        "router_proof_required": True,
        "router_proof_proven": False,
        "router_proof_file_path_recorded": False,
        "router_proof_file_sha256": sha256_text(str(proof_path.resolve(strict=False))),
        "router_proof_packet_sha256": "",
        "router_proof_machine_error_code": "CUSTOM_PHYSICAL_ROUTER_PROOF_NOT_PROVEN",
        "router_proof_blocking_reasons": [],
        "router_proof_output_text_sha256": "",
        "router_proof_output_text_recorded": False,
    }
    if not proof_path.is_file():
        result["router_proof_machine_error_code"] = "CUSTOM_PHYSICAL_ROUTER_PROOF_FILE_MISSING"
        result["router_proof_blocking_reasons"] = ["router_proof_file_missing"]
        return result

    stat = proof_path.stat()
    if started_after_ns is not None and stat.st_mtime_ns < started_after_ns:
        result["router_proof_machine_error_code"] = "CUSTOM_PHYSICAL_ROUTER_PROOF_FILE_STALE"
        result["router_proof_blocking_reasons"] = ["router_proof_file_stale"]
        return result

    try:
        packet = json.loads(proof_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result["router_proof_machine_error_code"] = "CUSTOM_PHYSICAL_ROUTER_PROOF_INVALID_JSON"
        result["router_proof_blocking_reasons"] = ["router_proof_invalid_json"]
        return result
    if not isinstance(packet, dict):
        result["router_proof_machine_error_code"] = "CUSTOM_PHYSICAL_ROUTER_PROOF_NOT_OBJECT"
        result["router_proof_blocking_reasons"] = ["router_proof_not_object"]
        return result

    result["router_proof_packet_sha256"] = sha256_file(proof_path)
    output_text = str(packet.get("output_text") or "")
    result["router_proof_output_text_sha256"] = sha256_text(output_text)
    visible_output_allowed = bool(
        packet.get("exact_plain_reply_matched") is True
        or packet.get("output_passthrough_required") is True
        or packet.get("repo_bridge_evidence_response_proven") is True
    )
    failures: list[str] = []
    expected_fields = {
        "packet_kind": "wbp_api_agent_auto_router",
        "status": "ok",
        "machine_error_code": "OK",
    }
    for key, expected_value in expected_fields.items():
        if packet.get(key) != expected_value:
            failures.append(f"router_proof_{key}_not_expected")
    for key in (
        "auto_router_proven",
        "direct_reply_proven",
        "api_route_selected",
        "direct_reply_selected",
    ):
        if packet.get(key) is not True:
            failures.append(f"router_proof_{key}_not_true")
    for key in (
        "fallback_used",
        "local_imitation_used",
        "tools_wbp_dip_invoked",
        "dip_run_invoked",
        "codex_exec_invoked",
        "native_codex_subagent_used_as_dip",
        "secret_value_exposed",
    ):
        if packet.get(key) is not False:
            failures.append(f"router_proof_{key}_not_false")
    if output_text != expected_text:
        failures.append("router_proof_output_text_not_expected")
    if not visible_output_allowed:
        failures.append("router_proof_visible_output_not_allowed")

    if failures:
        result["router_proof_blocking_reasons"] = failures
        return result

    result.update(
        {
            "router_proof_proven": True,
            "router_proof_machine_error_code": "OK",
            "router_proof_blocking_reasons": [],
        }
    )
    return result


NODE_RUNNER = r"""
const fs = require("fs");
const { chromium } = require("playwright");

function bodyText() {
  return document.body ? (document.body.innerText || "") : "";
}

function runActive() {
  return Array.from(document.querySelectorAll("button")).some((button) => {
    const text = (button.innerText || "").trim();
    const aria = button.getAttribute("aria-label") || "";
    return text === "Остановить" || aria === "Остановить";
  });
}

async function writePacket(path, packet) {
  fs.writeFileSync(path, JSON.stringify(packet, null, 2));
}

(async () => {
  const args = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const startedAt = Date.now();
  let browser;
  try {
    browser = await chromium.connectOverCDP(args.cdp_url);
    const pages = browser.contexts().flatMap((context) => context.pages());
    if (pages.length !== 1) {
      throw new Error(`expected_one_cdp_page_got_${pages.length}`);
    }
    const page = pages[0];
    await page.bringToFront();
    const beforeText = await page.evaluate(bodyText);
    const activeBefore = await page.evaluate(runActive);
    if (activeBefore && !args.allow_while_active) {
      await writePacket(args.output_path, {
        status: "blocked",
        machine_error_code: "CUSTOM_PHYSICAL_RUN_ALREADY_ACTIVE",
        before_text: beforeText,
        after_text: beforeText,
        run_active: true,
        prompt_submitted: false,
        elapsed_ms: Date.now() - startedAt
      });
      return;
    }

    const editor = page.locator('[contenteditable="true"]').last();
    await editor.click({ timeout: 10000 });
    await page.keyboard.press("Meta+A");

    let insertionStrategyUsed = "";
    let insertionError = "";
    if (args.send_strategy === "paste") {
      try {
        await page.evaluate(async (prompt) => {
          await navigator.clipboard.writeText(prompt);
        }, args.prompt);
        await page.keyboard.press("Meta+V");
        insertionStrategyUsed = "paste";
      } catch (error) {
        insertionError = String(error && error.message ? error.message : error);
      }
    }
    if (!insertionStrategyUsed && args.send_strategy !== "insertText") {
      try {
        await editor.fill(args.prompt, { timeout: 10000 });
        insertionStrategyUsed = "fill";
      } catch (error) {
        insertionError = String(error && error.message ? error.message : error);
      }
    }
    if (!insertionStrategyUsed) {
      await page.keyboard.insertText(args.prompt);
      insertionStrategyUsed = "insertText";
    }

    await page.keyboard.press("Enter");

    let afterText = beforeText;
    let active = false;
    const deadline = startedAt + args.timeout_ms;
    while (Date.now() < deadline) {
      await page.waitForTimeout(1000);
      afterText = await page.evaluate(bodyText);
      active = await page.evaluate(runActive);
      if (!active && afterText !== beforeText && Date.now() - startedAt >= args.min_wait_ms) {
        break;
      }
    }
    if (args.screenshot_path) {
      try {
        await page.screenshot({ path: args.screenshot_path, fullPage: false });
      } catch (_) {
        // Screenshot is optional secondary evidence only.
      }
    }
    await writePacket(args.output_path, {
      status: "ok",
      machine_error_code: "OK",
      before_text: beforeText,
      after_text: afterText,
      run_active: active,
      prompt_submitted: true,
      input_text_insert_succeeded: true,
      insertion_strategy_used: insertionStrategyUsed,
      insertion_error: insertionError,
      elapsed_ms: Date.now() - startedAt
    });
  } catch (error) {
    await writePacket(process.argv[3], {
      status: "blocked",
      machine_error_code: "CUSTOM_PHYSICAL_CDP_PROMPT_SUBMIT_FAILED",
      exception_class: error && error.name ? error.name : "Error",
      error_message: String(error && error.message ? error.message : error),
      prompt_submitted: false,
      elapsed_ms: Date.now() - startedAt
    });
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
})();
"""


def run_node_submitter(
    *,
    node_bin: str,
    node_modules: str,
    evidence_dir: Path,
    prompt: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    runner_path = evidence_dir / "custom-cdp-runner.cjs"
    screenshot_path = (
        evidence_dir / "custom-cdp-screenshot.png"
        if args.record_screenshot
        else Path("")
    )
    runner_path.write_text(NODE_RUNNER, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="wbp-custom-cdp-") as raw_dir_name:
        raw_dir = Path(raw_dir_name)
        input_path = raw_dir / "custom-cdp-input.json"
        output_path = raw_dir / "custom-cdp-output.json"
        write_json(
            input_path,
            {
                "cdp_url": args.cdp_url,
                "prompt": prompt,
                "timeout_ms": int(args.timeout_seconds * 1000),
                "min_wait_ms": int(args.min_wait_seconds * 1000),
                "send_strategy": args.send_strategy,
                "allow_while_active": args.allow_while_active,
                "output_path": str(output_path),
                "screenshot_path": str(screenshot_path) if args.record_screenshot else "",
            },
        )
        env = dict(os.environ)
        env["NODE_PATH"] = node_modules
        proc = subprocess.run(
            [node_bin, str(runner_path), str(input_path), str(output_path)],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=max(5.0, args.timeout_seconds + 20.0),
            check=False,
        )
        if not output_path.is_file():
            return {
                "status": "blocked",
                "machine_error_code": "CUSTOM_PHYSICAL_CDP_RUNNER_NO_OUTPUT",
                "node_exit_code": proc.returncode,
                "node_stdout_tail": bounded_tail(proc.stdout, 1000),
                "node_stderr_tail": bounded_tail(proc.stderr, 1000),
            }
        raw = json.loads(output_path.read_text(encoding="utf-8"))
        raw["node_exit_code"] = proc.returncode
        raw["node_stdout_tail"] = bounded_tail(proc.stdout, 1000)
        raw["node_stderr_tail"] = bounded_tail(proc.stderr, 1000)
        raw["screenshot_path"] = (
            str(screenshot_path)
            if args.record_screenshot and screenshot_path.is_file()
            else ""
        )
        return raw


def build_packet(
    *,
    raw: dict[str, Any],
    prompt: str,
    expected_text: str,
    mode: ObserverMode,
    evidence_dir: Path,
    cdp_url: str,
    owner_proof: dict[str, Any],
    router_proof_file: Path | None = None,
    router_proof_started_after_ns: int | None = None,
) -> dict[str, Any]:
    before_text = str(raw.get("before_text") or "")
    after_text = str(raw.get("after_text") or "")
    if raw.get("status") != "ok":
        return blocked_packet(
            machine_error_code=str(
                raw.get("machine_error_code") or "CUSTOM_PHYSICAL_CDP_FAILED"
            ),
            prompt=prompt,
            expected_text=expected_text,
            mode=mode,
            evidence_dir=evidence_dir,
            cdp_url=cdp_url,
            owner_proof=owner_proof,
            blocking_reasons=["cdp_submit_failed"],
            extras={
                "node_exit_code": raw.get("node_exit_code"),
                "node_stdout_tail": raw.get("node_stdout_tail", ""),
                "node_stderr_tail": raw.get("node_stderr_tail", ""),
                "prompt_submitted": raw.get("prompt_submitted") is True,
            },
        )
    observation = observe_visible_output(
        before_text=before_text,
        after_text=after_text,
        prompt=prompt,
        expected_text=expected_text,
        mode=mode,
        run_active=raw.get("run_active") is True,
    ).as_packet()
    router_proof = validate_router_proof(
        proof_file=router_proof_file,
        expected_text=expected_text,
        started_after_ns=router_proof_started_after_ns,
    )
    router_proof_required = router_proof["router_proof_required"] is True
    router_proof_ok = (
        not router_proof_required or router_proof["router_proof_proven"] is True
    )
    ok = observation["status"] == "ok" and router_proof_ok
    machine_error_code = str(observation["machine_error_code"])
    if observation["status"] == "ok" and not router_proof_ok:
        machine_error_code = str(router_proof["router_proof_machine_error_code"])
    blocking_reasons: list[str] = []
    if observation["status"] != "ok":
        blocking_reasons.append(str(observation["machine_error_code"]))
    if router_proof_required and not router_proof_ok:
        blocking_reasons.extend(
            str(reason)
            for reason in router_proof.get("router_proof_blocking_reasons", [])
        )
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_physical_smoke",
        "captured_at_utc": utc_now(),
        "status": "ok" if ok else "blocked",
        "machine_error_code": machine_error_code,
        "prompt_sha256": sha256_text(prompt),
        "prompt_text_recorded": False,
        "expected_text": expected_text,
        "expected_text_sha256": sha256_text(expected_text),
        "mode": mode,
        "cdp_url_recorded": False,
        "cdp_url_sha256": sha256_text(cdp_url),
        "evidence_dir": str(evidence_dir),
        "raw_text_recorded": False,
        "screenshot_recorded": bool(raw.get("screenshot_path")),
        "cdp_owner_proof": owner_proof,
        "before_text_sha256": sha256_text(before_text),
        "after_text_sha256": sha256_text(after_text),
        "prompt_submitted": raw.get("prompt_submitted") is True,
        "input_text_insert_succeeded": raw.get("input_text_insert_succeeded") is True,
        "insertion_strategy_used": raw.get("insertion_strategy_used", ""),
        "elapsed_ms": raw.get("elapsed_ms"),
        "screenshot_path": raw.get("screenshot_path", ""),
        "observer": observation,
        "router_proof": router_proof,
        "custom_response_exact_token_observed": observation["expected_text_observed"],
        "custom_response_bound_to_request": bool(
            observation["custom_response_bound_to_request"] and router_proof_ok
        ),
        "false_green_blocked": observation["machine_error_code"]
        in {
            "CUSTOM_PHYSICAL_PROMPT_ECHO_ONLY",
            "CUSTOM_PHYSICAL_COMMAND_ECHO_ONLY",
            "CUSTOM_PHYSICAL_PROMPT_SPLIT_INTO_RECOMMENDATIONS",
        }
        or bool(router_proof_required and not router_proof_ok),
        "blocking_reasons": [] if ok else blocking_reasons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--expected", required=True)
    parser.add_argument(
        "--mode",
        choices=["native", "api", "fail_closed", "auto"],
        default="auto",
    )
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--min-wait-seconds", type=float, default=1.0)
    parser.add_argument("--record-screenshot", action="store_true")
    parser.add_argument(
        "--send-strategy",
        choices=["fill", "paste", "insertText"],
        default="insertText",
    )
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--node-bin", default="")
    parser.add_argument("--node-modules", default="")
    parser.add_argument("--allow-while-active", action="store_true")
    parser.add_argument(
        "--required-router-proof-file",
        default="",
        help="Require a fresh auto-route-output proof packet written by this UI turn.",
    )
    parser.add_argument(
        "--profile-dir",
        default=os.environ.get("WBP_PROFILE_DIR", str(DEFAULT_PROFILE_DIR)),
    )
    parser.add_argument("--user-data-dir", default="")
    parser.add_argument(
        "--allow-unbound-cdp",
        action="store_true",
        help="Skip CDP owner proof. Intended only for diagnosing non-WBP test fixtures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = read_prompt(args)
    if not prompt.strip():
        print("prompt is required", file=sys.stderr)
        return 2
    evidence_dir = (
        Path(args.evidence_dir)
        if args.evidence_dir
        else Path(tempfile.gettempdir())
        / "wbp-manual-custom-evidence"
        / f"custom-physical-smoke-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    node_bin = discover_node_bin(args.node_bin)
    node_modules = discover_node_modules(args.node_modules)
    profile_dir = Path(args.profile_dir).expanduser()
    user_data_dir = (
        Path(args.user_data_dir).expanduser()
        if args.user_data_dir
        else profile_dir / "electron-user-data"
    )
    owner_proof = prove_cdp_owner(
        cdp_url=args.cdp_url,
        profile_dir=profile_dir,
        user_data_dir=user_data_dir,
        allow_unbound_cdp=bool(args.allow_unbound_cdp),
    )
    if owner_proof.get("status") != "ok":
        packet = blocked_packet(
            machine_error_code=str(
                owner_proof.get("machine_error_code")
                or "CUSTOM_PHYSICAL_CDP_OWNER_NOT_PROVEN"
            ),
            prompt=prompt,
            expected_text=args.expected,
            mode=args.mode,
            evidence_dir=evidence_dir,
            cdp_url=args.cdp_url,
            owner_proof=owner_proof,
            blocking_reasons=["cdp_owner_not_proven"],
        )
        write_json(evidence_dir / "packet.json", packet)
        print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    router_proof_file = (
        Path(args.required_router_proof_file).expanduser()
        if args.required_router_proof_file
        else None
    )
    router_proof_started_after_ns = time.time_ns() if router_proof_file else None
    raw = run_node_submitter(
        node_bin=node_bin,
        node_modules=node_modules,
        evidence_dir=evidence_dir,
        prompt=prompt,
        args=args,
    )
    packet = build_packet(
        raw=raw,
        prompt=prompt,
        expected_text=args.expected,
        mode=args.mode,
        evidence_dir=evidence_dir,
        cdp_url=args.cdp_url,
        owner_proof=owner_proof,
        router_proof_file=router_proof_file,
        router_proof_started_after_ns=router_proof_started_after_ns,
    )
    write_json(evidence_dir / "packet.json", packet)
    print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

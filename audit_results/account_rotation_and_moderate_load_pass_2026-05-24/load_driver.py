#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audit-only bounded load driver for Codex Custom web sessions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import statistics
import sys
import threading
import time
from typing import Any
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.web_design_live_server import (
    OWNER_STANDING_AUTHORIZATION_PHRASE,
    build_handler,
)


ARTIFACT_DIR = Path(__file__).resolve().parent
PREFERRED_MODEL = "gpt-5.3-codex"
CANARY_REQUESTS = 3
MODERATE_REQUESTS = 20
MODERATE_CONCURRENCY = 2
PROMPT = "Reply with exactly LOAD_OK."


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path: str) -> dict[str, Any]:
        with self.opener.open(f"{self.base_url}{path}", timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))


def choose_model(client: Client) -> tuple[str, dict[str, Any]]:
    packet = client.get("/api/codex/custom/models")
    model_ids = [
        str(entry.get("model_id"))
        for entry in packet.get("available_models", [])
        if isinstance(entry, dict) and entry.get("model_id")
    ]
    if PREFERRED_MODEL in model_ids:
        return PREFERRED_MODEL, packet
    if not model_ids:
        raise RuntimeError("no server-issued models available")
    return model_ids[0], packet


def summarize_prompt_packet(index: int, phase: str, packet: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    trace_packet = packet.get("trace_observer_packet")
    trace_safe = {
        key: trace_packet.get(key)
        for key in (
            "request_observed",
            "response_observed",
            "forwarded_to_wbp",
            "method",
            "path",
            "upstream_status",
            "machine_error_code",
            "observer_closed",
        )
        if isinstance(trace_packet, dict) and key in trace_packet
    }
    return {
        "index": index,
        "phase": phase,
        "captured_at_utc": utc_now(),
        "status": packet.get("status"),
        "machine_error_code": packet.get("machine_error_code"),
        "session_id_prefix": str(packet.get("session_id", ""))[:4],
        "model_id": packet.get("model_id"),
        "model_server_issued": packet.get("model_server_issued") is True,
        "selected_source_class": packet.get("selected_source_class"),
        "selected_source_provenance": packet.get("selected_source_provenance"),
        "source_provenance_proven": packet.get("source_provenance_proven") is True,
        "selected_backend_server_issued": packet.get("selected_backend_server_issued") is True,
        "selected_backend_digest_present": bool(packet.get("selected_backend_digest")),
        "selected_route_server_issued": packet.get("selected_route_server_issued") is True,
        "route_provenance_required": packet.get("route_provenance_required") is True,
        "route_provenance_proven": packet.get("route_provenance_proven") is True,
        "live_prompt_admitted": packet.get("live_prompt_admitted") is True,
        "live_prompt_executed": packet.get("live_prompt_executed") is True,
        "live_prompt_full_success": packet.get("live_prompt_full_success") is True,
        "model_response_present": packet.get("model_response_present") is True,
        "inference_proven": packet.get("inference_proven") is True,
        "prompt_sha256": packet.get("prompt_sha256"),
        "prompt_preview_redacted": packet.get("prompt_preview_redacted"),
        "response_digest": packet.get("response_digest"),
        "response_preview_bounded": str(packet.get("response_preview_bounded") or "")[:80],
        "token_usage_present": packet.get("token_usage_present") is True,
        "token_burn": packet.get("token_burn"),
        "latency_ms": packet.get("latency_ms") if isinstance(packet.get("latency_ms"), int) else elapsed_ms,
        "wall_latency_ms": elapsed_ms,
        "error_class": packet.get("error_class", ""),
        "wbp_path_proven": packet.get("wbp_path_proven") is True,
        "cli_proxy_api_path_proven": packet.get("cli_proxy_api_path_proven") is True,
        "independent_wbp_trace_observed": packet.get("independent_wbp_trace_observed") is True,
        "trace_path": packet.get("trace_path"),
        "upstream_status": packet.get("upstream_status"),
        "forwarded_to_wbp": packet.get("forwarded_to_wbp") is True,
        "trace_observer_packet": trace_safe,
        "isolated_engine_home_proven": packet.get("isolated_engine_home_proven") is True,
        "current_codex_touched": packet.get("current_codex_touched") is True,
        "fallback_attempted": packet.get("fallback_attempted") is True,
        "raw_backend_id_exposed": packet.get("raw_backend_id_exposed") is True,
        "raw_auth_ref_exposed": packet.get("raw_auth_ref_exposed") is True,
        "secret_value_recorded": packet.get("secret_value_recorded") is True,
        "next_action": packet.get("next_action"),
    }


def one_request(client: Client, *, index: int, phase: str, model_id: str) -> dict[str, Any]:
    cleanup_packet: dict[str, Any] | None = None
    started = time.time()
    created = client.post("/api/codex/custom/sessions", {"model_id": model_id})
    if created.get("status") != "ok" or created.get("session_created") is not True:
        return {
            "index": index,
            "phase": phase,
            "status": created.get("status"),
            "machine_error_code": created.get("machine_error_code"),
            "session_created": False,
            "elapsed_ms": int((time.time() - started) * 1000),
            "next_action": created.get("next_action"),
        }
    session = created.get("session") if isinstance(created.get("session"), dict) else {}
    session_id = str(session.get("session_id") or "")
    try:
        prompt_packet = client.post(
            f"/api/codex/custom/sessions/{session_id}/prompt",
            {"prompt": PROMPT},
        )
        elapsed_ms = int((time.time() - started) * 1000)
        summary = summarize_prompt_packet(index, phase, prompt_packet, elapsed_ms)
        summary["session_created"] = True
        summary["create_selection_proven"] = created.get("selection_packet", {}).get("selection_proven") is True
        summary["create_selected_source_class"] = created.get("selection_packet", {}).get("selected_source_class")
        summary["create_selected_backend_digest_present"] = bool(
            created.get("selection_packet", {}).get("selected_backend_digest")
        )
        return summary
    finally:
        if session_id:
            cleanup_packet = client.post(f"/api/codex/custom/sessions/{session_id}/cleanup", {})
            (ARTIFACT_DIR / f"{phase}_cleanup_{index:03d}.json").write_text(
                json.dumps(
                    {
                        "index": index,
                        "phase": phase,
                        "status": cleanup_packet.get("status"),
                        "machine_error_code": cleanup_packet.get("machine_error_code"),
                        "cleanup_performed": cleanup_packet.get("cleanup_performed") is True,
                        "owned_session_root_only": cleanup_packet.get("owned_session_root_only") is True,
                        "current_codex_home_touched": cleanup_packet.get("current_codex_home_touched") is True,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )


def run_serial(client: Client, *, phase: str, count: int, model_id: str) -> list[dict[str, Any]]:
    results = []
    for index in range(1, count + 1):
        result = one_request(client, index=index, phase=phase, model_id=model_id)
        results.append(result)
        if should_stop(results):
            break
    return results


def run_concurrent(client: Client, *, phase: str, count: int, concurrency: int, model_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        next_index = 1
        futures = set()
        while next_index <= count and len(futures) < concurrency:
            futures.add(executor.submit(one_request, client, index=next_index, phase=phase, model_id=model_id))
            next_index += 1
        while futures:
            for future in as_completed(futures):
                futures.remove(future)
                break
            result = future.result()
            results.append(result)
            if should_stop(results):
                for pending in futures:
                    pending.cancel()
                break
            if next_index <= count:
                futures.add(executor.submit(one_request, client, index=next_index, phase=phase, model_id=model_id))
                next_index += 1
    return sorted(results, key=lambda item: int(item.get("index") or 0))


def should_stop(results: list[dict[str, Any]]) -> bool:
    codes: dict[str, int] = {}
    for result in results:
        code = str(result.get("machine_error_code") or "UNKNOWN")
        if code == "OK":
            continue
        codes[code] = codes.get(code, 0) + 1
        if codes[code] >= 2:
            return True
    for result in results:
        if result.get("current_codex_touched") is True:
            return True
        if result.get("secret_value_recorded") is True:
            return True
        if result.get("raw_backend_id_exposed") is True or result.get("raw_auth_ref_exposed") is True:
            return True
        if result.get("live_prompt_full_success") is True and result.get("independent_wbp_trace_observed") is not True:
            return True
    return False


def summarize(canary: list[dict[str, Any]], moderate: list[dict[str, Any]]) -> dict[str, Any]:
    all_results = canary + moderate
    failures = [item for item in all_results if item.get("machine_error_code") != "OK"]
    latencies = [
        int(item.get("wall_latency_ms") or item.get("latency_ms") or 0)
        for item in all_results
        if isinstance(item.get("wall_latency_ms") or item.get("latency_ms"), int)
    ]
    failure_classes: dict[str, int] = {}
    for item in failures:
        code = str(item.get("machine_error_code") or "UNKNOWN")
        failure_classes[code] = failure_classes.get(code, 0) + 1
    success_count = sum(1 for item in all_results if item.get("machine_error_code") == "OK")
    return {
        "captured_at_utc": utc_now(),
        "prompt_sha256": digest(PROMPT),
        "raw_prompt_stored_in_results": False,
        "canary_requests_attempted": len(canary),
        "moderate_requests_attempted": len(moderate),
        "total_requests": len(all_results),
        "moderate_concurrency": MODERATE_CONCURRENCY,
        "success_count": success_count,
        "failure_count": len(failures),
        "failure_classes": failure_classes,
        "latency_min_ms": min(latencies) if latencies else None,
        "latency_p50_ms": int(statistics.median(latencies)) if latencies else None,
        "latency_p95_ms": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "lock_held_count": failure_classes.get("LOCK_HELD", 0),
        "upstream_401_count": failure_classes.get("TRACE_UPSTREAM_HTTP_401", 0),
        "upstream_403_count": failure_classes.get("TRACE_UPSTREAM_HTTP_403", 0),
        "upstream_429_count": failure_classes.get("TRACE_UPSTREAM_HTTP_429", 0),
        "current_codex_touch_count": sum(1 for item in all_results if item.get("current_codex_touched") is True),
        "secret_leak_count": sum(1 for item in all_results if item.get("secret_value_recorded") is True),
        "raw_backend_or_auth_leak_count": sum(
            1
            for item in all_results
            if item.get("raw_backend_id_exposed") is True or item.get("raw_auth_ref_exposed") is True
        ),
        "all_successes_have_trace": all(
            item.get("independent_wbp_trace_observed") is True
            for item in all_results
            if item.get("machine_error_code") == "OK"
        ),
        "all_successes_isolated": all(
            item.get("isolated_engine_home_proven") is True
            and item.get("current_codex_touched") is False
            for item in all_results
            if item.get("machine_error_code") == "OK"
        ),
        "stop_condition_triggered": should_stop(all_results),
        "bounded_proof_ready": (
            len(canary) == CANARY_REQUESTS
            and len(moderate) == MODERATE_REQUESTS
            and len(failures) == 0
            and success_count == CANARY_REQUESTS + MODERATE_REQUESTS
            and all(item.get("independent_wbp_trace_observed") is True for item in all_results)
            and all(item.get("current_codex_touched") is False for item in all_results)
            and all(item.get("secret_value_recorded") is False for item in all_results)
            and all(item.get("raw_backend_id_exposed") is False for item in all_results)
            and all(item.get("raw_auth_ref_exposed") is False for item in all_results)
        ),
    }


def main() -> int:
    handler = build_handler(owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    client = Client(base_url)
    try:
        model_id, model_packet = choose_model(client)
        (ARTIFACT_DIR / "load_model_packet.json").write_text(
            json.dumps(
                {
                    "captured_at_utc": utc_now(),
                    "status": model_packet.get("status"),
                    "machine_error_code": model_packet.get("machine_error_code"),
                    "selected_model": model_id,
                    "model_count": model_packet.get("model_count"),
                    "server_issued": model_packet.get("server_issued") is True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        canary = run_serial(client, phase="canary", count=CANARY_REQUESTS, model_id=model_id)
        (ARTIFACT_DIR / "canary_results.json").write_text(
            json.dumps({"captured_at_utc": utc_now(), "results": canary}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        moderate: list[dict[str, Any]] = []
        if not should_stop(canary) and all(item.get("machine_error_code") == "OK" for item in canary):
            moderate = run_concurrent(
                client,
                phase="moderate",
                count=MODERATE_REQUESTS,
                concurrency=MODERATE_CONCURRENCY,
                model_id=model_id,
            )
        (ARTIFACT_DIR / "moderate_load_results.json").write_text(
            json.dumps({"captured_at_utc": utc_now(), "results": moderate}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        summary = summarize(canary, moderate)
        summary["server_base_url"] = "http://127.0.0.1:<ephemeral>"
        summary["selected_model"] = model_id
        (ARTIFACT_DIR / "load_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0 if summary["bounded_proof_ready"] else 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

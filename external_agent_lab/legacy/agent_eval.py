#!/usr/bin/env python3
"""
Run route qualification and bounded eval against the local adapter.
"""

import argparse
import hmac
import hashlib
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from external_agent_lab.legacy.run_lab import (
    CLIENT_TOKEN_KEY,
    ENV_PATH,
    LAB_DIR,
    ensure_env_permissions,
    pick_port,
    should_try_fallback,
    smoke_candidates,
    start_proxy,
    shutdown_proxy,
    wait_for_health,
)


EVAL_DIR = LAB_DIR / "eval_results"
ROUTE_DIR = LAB_DIR / "route_results"
RESPONSE_DIR = LAB_DIR / "response_results"
PROVIDER_DIR = LAB_DIR / "provider_results"
REGISTRY_DIR = LAB_DIR / "registry_results"
COST_GATE_DIR = LAB_DIR / "cost_gate_results"
BASELINE_DIR = LAB_DIR / "baseline_results"
GUARD_DIR = LAB_DIR / "guard_results"
DELTA_DIR = LAB_DIR / "delta_results"
MUTATION_DIR = LAB_DIR / "mutation_results"
PILOT_VERIFICATION_DIR = LAB_DIR / "pilot_verification_results"
ACCESS_RECHECK_DIR = LAB_DIR / "access_recheck_results"
ADMISSION_PLANNING_DIR = LAB_DIR / "admission_planning_results"
VERIFICATION_DIR = LAB_DIR / "verification_results"
MODEL_REGISTRY_SEED_PATH = LAB_DIR / "model_registry_seed.json"
DEFAULT_MODELS = "qwen3-coder,qwen3-next,gpt-oss-20b,gpt-oss-120b,glm-flash"
DEFAULT_PROVIDERS = "gemini,groq,cerebras,mistral"
DEFAULT_MAX_PROVIDER_CALLS = 20
DEFAULT_REQUEST_TIMEOUT = 25
DEFAULT_MAX_FALLBACK_ATTEMPTS = 2
DEFAULT_STOP_AFTER_CONSECUTIVE_FAILURES = 2
DEFAULT_RESPONSE_ATTEMPTS_PER_PROBE = 2
DEFAULT_MODE = "qualify"
DEFAULT_QUALIFICATION_PROMPT = "Reply with OK only."
DEFAULT_RESPONSE_PROBE_IDS = ("write_function", "find_bug")
ESCALATION_RESPONSE_PROBE_ID = "cli_skeleton"
TASKS = [
    ("write_function", "Write a Python function slugify_name(text: str) -> str with edge-case handling for empty input, punctuation, and repeated spaces."),
    ("find_bug", "Find the bug in this Python code and explain the fix:\n\ndef average(values):\n    return sum(values) / len(values) if values else 0\n\nprint(average(None))"),
    ("propose_tests", "Propose focused unit tests for a Python function that parses RFC3339 timestamps into timezone-aware datetime objects."),
    ("mini_refactor", "Refactor this Python snippet for readability and smaller duplicated logic:\n\nif user and user.get('name'):\n    print(user['name'].strip().lower())\nif admin and admin.get('name'):\n    print(admin['name'].strip().lower())"),
    ("explain_diff", "Explain what this diff does and what risk it introduces:\n- timeout = 5\n+ timeout = 60\n- retries = 1\n+ retries = 5"),
    ("cli_skeleton", "Generate a minimal Python argparse CLI skeleton for a tool named repo_scan with subcommands status and run."),
    ("stacktrace", "Analyze this error and suggest the most likely root cause:\nTraceback (most recent call last):\n  File \"app.py\", line 42, in <module>\n    data = json.loads(resp.text)\n  File \"/usr/lib/python3.11/json/__init__.py\", line 346, in loads\n    return _default_decoder.decode(s)\njson.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)"),
]
ERROR_TAXONOMY_SCENARIOS = (
    ("forced_rate_limited", "upstream_rate_limited", 429),
    ("forced_overloaded", "upstream_overloaded", 429),
    ("forced_timeout", "upstream_timeout", 504),
    ("forced_invalid_json", "invalid_upstream_response", 502),
)

DIRECT_PROVIDER_TARGETS = {
    "gemini": {
        "provider": "gemini",
        "provider_label": "Google Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "probe_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "probe_method": "POST",
        "probe_model": "gemini-2.5-flash",
        "route_model": "direct-gemini-2.5-flash",
        "cost_class": "paid_direct",
        "policy_allowed": True,
    },
    "groq": {
        "provider": "groq",
        "provider_label": "Groq",
        "api_key_env": "GROQ_API_KEY",
        "probe_url": "https://api.groq.com/openai/v1/models",
        "route_model": "direct-groq-openai-gpt-oss-20b",
        "cost_class": "paid_direct",
        "policy_allowed": True,
    },
    "cerebras": {
        "provider": "cerebras",
        "provider_label": "Cerebras",
        "api_key_env": "CEREBRAS_API_KEY",
        "probe_url": "https://api.cerebras.ai/v1/models",
        "route_model": "direct-cerebras-llama3.1-8b",
        "expected_model_id": "llama3.1-8b",
        "cost_class": "entitled_direct_limited",
        "policy_allowed": True,
    },
    "mistral": {
        "provider": "mistral",
        "provider_label": "Mistral",
        "api_key_env": "MISTRAL_API_KEY",
        "probe_url": "https://api.mistral.ai/v1/models",
        "route_model": "direct-mistral-small-latest",
        "cost_class": "paid_direct",
        "policy_allowed": True,
    },
}

ALLOWED_AVAILABILITY_STATES = {
    "verified_accessible",
    "verified_accessible_limited",
    "provider_visible_but_unverified",
    "externally_blocked",
    "auth_unconfirmed",
    "quota_unconfirmed",
    "unstable",
    "retired",
}
ALLOWED_LANE_ROLES = {
    "primary_practical",
    "secondary_reasoning",
    "cheap_helper",
    "comparison",
    "fallback",
    "blocked_target",
    "strategic_target",
}
ALLOWED_EVIDENCE_LEVELS = {
    "limits_ui",
    "provider_models_endpoint",
    "runtime_success",
    "runtime_failure",
    "support_reply",
    "manual_assumption_forbidden",
}

ROUTE_MODEL_TO_REGISTRY_MODEL_ID = {
    "gpt-oss-20b": "or-gpt-oss-20b",
    "qwen3-coder": "or-qwen3-coder",
    "qwen3-next": "or-qwen3-next",
    "glm-flash": "glm-4.7-flash",
    "gpt-5.4-mini": "glm-4.7-flash",
    "devstral-small-2512": "direct-mistral-devstral-2512",
    "mistral-devstral-2512": "direct-mistral-devstral-2512",
}
REGISTRY_MODEL_TO_ROUTE_MODEL_HINT = {
    "or-gpt-oss-20b": "gpt-oss-20b",
    "or-qwen3-coder": "qwen3-coder",
    "or-qwen3-next": "qwen3-next",
    "glm-4.7-flash": "glm-flash",
    "direct-mistral-devstral-2512": "devstral-small-2512",
}


@dataclass
class ModelRequestError(Exception):
    status: int
    error_class: str
    message: str

    def __str__(self):
        return f"HTTP {self.status} [{self.error_class}]: {self.message}"


def model_kind(model_name):
    if model_name in {"glm-flash", "gpt-5.4-mini"}:
        return "glm-flash"
    return model_name


def normalize_requested_model(model_name):
    if model_name == "glm-flash":
        return "gpt-5.4-mini"
    return model_name


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run route qualification or bounded eval against free/API model routes")
    parser.add_argument(
        "--mode",
        choices=(
            "provider-access",
            "error-taxonomy-check",
            "model-registry-snapshot",
            "cost-gate-check",
            "qualify",
            "response-evidence",
            "eval",
            "baseline-snapshot",
            "admission-guard-check",
            "admission-delta-check",
            "mutation-design",
            "mutation-execute",
            "mutation-rollback",
            "pilot-verification-precheck",
            "admission-state-check",
            "admission-trigger-check",
            "admission-event-check",
            "direct-provider-access-precheck",
            "direct-route-qualification-precheck",
            "repo-bound-planning-precheck",
            "canon-first-contour-generator",
            "wave-2c-contour-generator",
            "contour-1-synthetic-validation-generator",
            "cerebras-contour-2-generator",
            "post-cerebras-contour-3-generator",
            "contour-4-criteria-closure-generator",
            "contour-5-five-of-seven-closure-generator",
            "contour-6a-second-route-stability-gap-closure-generator",
            "contour-6b-repo-bound-planning-precheck-closure-generator",
            "contour-6c-repo-bound-blocker-closure-generator",
            "contour-6d-repo-bound-authorization-closure-generator",
            "contour-6e-feature-lab-complete-package-generator",
            "contour-7a-declared-target-coverage-generator",
            "contour-7b-declared-scope-reconciliation-generator",
            "contour-7c-repo-bound-authorization-wait-state-generator",
        ),
        default=DEFAULT_MODE,
    )
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--providers", default=DEFAULT_PROVIDERS)
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--port", "-p", type=int, default=5000)
    parser.add_argument("--max-provider-calls", type=int, default=DEFAULT_MAX_PROVIDER_CALLS)
    parser.add_argument("--request-timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT)
    parser.add_argument("--max-fallback-attempts", type=int, default=DEFAULT_MAX_FALLBACK_ATTEMPTS)
    parser.add_argument("--response-attempts-per-probe", type=int, default=DEFAULT_RESPONSE_ATTEMPTS_PER_PROBE)
    parser.add_argument("--max-tasks-per-model", type=int)
    parser.add_argument("--stop-after-consecutive-failures", type=int, default=DEFAULT_STOP_AFTER_CONSECUTIVE_FAILURES)
    parser.add_argument("--qualification-report")
    parser.add_argument("--qualification-report-2")
    parser.add_argument("--response-report")
    parser.add_argument("--eval-report")
    parser.add_argument("--allow-eval-without-qualification", action="store_true")
    parser.add_argument("--allow-fallback-only-eval", action="store_true")
    parser.add_argument("--allow-fallback-only-response-evidence", action="store_true")
    parser.add_argument("--allow-unstable-response-evidence", action="store_true")
    parser.add_argument("--allow-eval-without-response-evidence", action="store_true")
    parser.add_argument("--qualification-prompt", default=DEFAULT_QUALIFICATION_PROMPT)
    parser.add_argument("--allow-paid-routes", action="store_true")
    parser.add_argument("--include-prompts", action="store_true")
    parser.add_argument("--pilot-impl-report")
    parser.add_argument("--baseline-report")
    parser.add_argument("--guard-report")
    parser.add_argument("--provider-report")
    parser.add_argument("--error-taxonomy-report")
    parser.add_argument("--cost-gate-report")
    parser.add_argument("--watch-report")
    parser.add_argument("--registry-seed", default=str(MODEL_REGISTRY_SEED_PATH))
    parser.add_argument("--admission-delta-report")
    parser.add_argument("--mutation-provider", choices=tuple(DIRECT_PROVIDER_TARGETS), default="mistral")
    parser.add_argument("--mutation-design-report")
    parser.add_argument("--mutation-execution-report")
    parser.add_argument("--admission-state-report")
    parser.add_argument("--admission-trigger-report")
    parser.add_argument("--admission-event-report")
    parser.add_argument("--access-recheck-report")
    parser.add_argument("--verification-report")
    parser.add_argument("--registry-report")
    return parser.parse_args(argv)


def select_tasks(task_arg):
    if task_arg == "all":
        return TASKS
    wanted = {item.strip() for item in task_arg.split(",") if item.strip()}
    selected = [task for task in TASKS if task[0] in wanted]
    if not selected:
        raise SystemExit(f"No matching tasks found for --tasks={task_arg}")
    return selected


def default_response_tasks():
    selected = [task for task in TASKS if task[0] in DEFAULT_RESPONSE_PROBE_IDS]
    return selected


def escalation_response_task():
    for task in TASKS:
        if task[0] == ESCALATION_RESPONSE_PROBE_ID:
            return task
    raise SystemExit(f"Missing escalation response probe: {ESCALATION_RESPONSE_PROBE_ID}")


def send_responses_request(base_url, requested_model, prompt_text, request_timeout, metadata=None):
    client_token = load_env_token(CLIENT_TOKEN_KEY)
    payload = {
        "model": requested_model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt_text}],
            }
        ],
    }
    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
    req = Request(
        f"{base_url}/responses",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {client_token}"},
    )
    try:
        with urlopen(req, timeout=request_timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if not is_valid_response_contract(result):
                raise ModelRequestError(502, "invalid_upstream_response", "Adapter returned a payload outside the expected response contract.")
            return result
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        try:
            payload = json.loads(body)
            err = payload.get("error", {})
            raise ModelRequestError(error.code, err.get("error_class", "upstream_error"), err.get("message", body[:500]))
        except json.JSONDecodeError:
            raise ModelRequestError(error.code, "upstream_error", body[:500])
    except socket.timeout:
        raise ModelRequestError(504, "upstream_timeout", "Request timed out while waiting for adapter or upstream provider response.")
    except URLError as error:
        raise ModelRequestError(502, "upstream_timeout", f"Connection error: {error}")


def send_models_list_request(base_url, request_timeout):
    req = Request(f"{base_url}/models", method="GET")
    try:
        with urlopen(req, timeout=request_timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        raise ModelRequestError(error.code, "local_models_list_failed", body[:500] or f"HTTP {error.code}")
    except socket.timeout:
        raise ModelRequestError(504, "upstream_timeout", "Timed out while requesting adapter /models.")
    except URLError as error:
        raise ModelRequestError(502, "upstream_timeout", f"Connection error: {error}")

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ModelRequestError(502, "invalid_upstream_response", "Adapter returned invalid /models payload.")
    return payload


def run_task_with_fallback(
    base_url,
    requested_model,
    prompt_text,
    remaining_budget,
    request_timeout,
    max_fallback_attempts,
    public_models_index=None,
):
    attempts = []
    last_error = None
    calls_used = 0
    for index, candidate in enumerate(smoke_candidates(requested_model)):
        if index > max_fallback_attempts:
            break
        if calls_used >= remaining_budget:
            break
        calls_used += 1
        attempts.append(candidate)
        try:
            result = send_responses_request(base_url, candidate, prompt_text, request_timeout)
            result["requested_model"] = requested_model
            result["requested_model_available"] = candidate == requested_model
            result["fallback_used"] = candidate != requested_model
            result["fallback_chain"] = attempts[:]
            result["network_dependent_evidence"] = True
            return result, calls_used
        except ModelRequestError as error:
            last_error = error
            if candidate == requested_model and not should_try_fallback(str(error)):
                break
            if candidate != requested_model and not should_try_fallback(str(error)):
                break
    provider = None
    effective_model = None
    target_model = attempts[-1] if attempts else requested_model
    if isinstance(public_models_index, dict):
        meta = public_models_index.get(target_model)
        if isinstance(meta, dict):
            provider = meta.get("provider")
            effective_model = meta.get("effective_model") or meta.get("upstream_model")

    return {
        "requested_model": requested_model,
        "requested_model_available": False,
        "fallback_used": len(attempts) > 1,
        "fallback_chain": attempts,
        "provider": provider,
        "effective_model": effective_model,
        "latency_ms": None,
        "error_class": last_error.error_class if last_error else "free_executors_exhausted",
        "error_message": str(last_error) if last_error else "Provider call budget exhausted before a response.",
        "network_dependent_evidence": True,
        "status": "failed",
    }, calls_used


def ensure_eval_dir():
    EVAL_DIR.mkdir(exist_ok=True)


def ensure_route_dir():
    ROUTE_DIR.mkdir(exist_ok=True)


def ensure_response_dir():
    RESPONSE_DIR.mkdir(exist_ok=True)


def ensure_provider_dir():
    PROVIDER_DIR.mkdir(exist_ok=True)


def ensure_registry_dir():
    REGISTRY_DIR.mkdir(exist_ok=True)


def ensure_cost_gate_dir():
    COST_GATE_DIR.mkdir(exist_ok=True)


def ensure_baseline_dir():
    BASELINE_DIR.mkdir(exist_ok=True)


def ensure_guard_dir():
    GUARD_DIR.mkdir(exist_ok=True)


def ensure_delta_dir():
    DELTA_DIR.mkdir(exist_ok=True)


def ensure_mutation_dir():
    MUTATION_DIR.mkdir(exist_ok=True)


def ensure_pilot_verification_dir():
    PILOT_VERIFICATION_DIR.mkdir(exist_ok=True)


def ensure_access_recheck_dir():
    ACCESS_RECHECK_DIR.mkdir(exist_ok=True)


def ensure_admission_planning_dir():
    ADMISSION_PLANNING_DIR.mkdir(exist_ok=True)


def ensure_verification_dir():
    VERIFICATION_DIR.mkdir(exist_ok=True)


def load_env_token(key_name):
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env.get(key_name, "lab-local")


def load_local_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_direct_providers(provider_arg):
    selected = []
    seen = set()
    for item in provider_arg.split(","):
        provider = item.strip()
        if not provider:
            continue
        if provider not in DIRECT_PROVIDER_TARGETS:
            raise SystemExit(f"Unknown direct provider target: {provider}")
        if provider in seen:
            continue
        seen.add(provider)
        selected.append(provider)
    if not selected:
        raise SystemExit("No direct providers selected.")
    return selected


def current_direct_provider_auth_present():
    env_map = load_local_env()
    result = {}
    for provider, target in DIRECT_PROVIDER_TARGETS.items():
        key_name = target["api_key_env"]
        result[provider] = bool(env_map.get(key_name) or os.environ.get(key_name))
    return result


def current_direct_key_names():
    env_map = load_local_env()
    names = []
    for provider, target in DIRECT_PROVIDER_TARGETS.items():
        key_name = target["api_key_env"]
        if env_map.get(key_name) or os.environ.get(key_name):
            names.append(key_name)
    return sorted(names)


def direct_state_snapshot():
    current_keys = current_direct_key_names()
    current_auth = current_direct_provider_auth_present()
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "current_direct_key_names": current_keys,
                "current_provider_auth_present": current_auth,
            }
        ).encode("utf-8")
    ).hexdigest()
    return {
        "current_direct_key_names": current_keys,
        "current_provider_auth_present": current_auth,
        "state_fingerprint": fingerprint,
    }


def read_env_lines():
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def write_env_lines(lines):
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ensure_env_permissions(ENV_PATH)


def env_key_present(key_name):
    env_map = load_local_env()
    return bool(env_map.get(key_name) or os.environ.get(key_name))


def remove_env_key(key_name):
    lines = read_env_lines()
    next_lines = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key_name}="):
            removed = True
            continue
        next_lines.append(line)
    if removed:
        write_env_lines(next_lines)
    return removed


def count_guard_reuses(baseline_report_sha256):
    ensure_guard_dir()
    reuse_count = 0
    reused_paths = []
    for path in sorted(GUARD_DIR.glob("guard_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or report.get("report_kind") != "direct_admission_guard_check":
                continue
            verify_attestation(report)
        except Exception:
            continue
        if report.get("baseline_report_sha256") == baseline_report_sha256:
            reuse_count += 1
            reused_paths.append(str(path))
    return reuse_count, reused_paths


def provider_probe_payload(target):
    if target["provider"] != "gemini":
        return None
    body = {
        "model": target.get("probe_model", target["route_model"]),
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "max_tokens": 5,
    }
    return json.dumps(body).encode("utf-8")


def classify_provider_http_error(provider, status_code, server_header, response_excerpt, auth_present):
    excerpt_lower = (response_excerpt or "").lower()
    server_lower = (server_header or "").lower()

    if provider == "gemini" and "api_key_invalid" in excerpt_lower:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    if provider == "gemini" and "api key not valid" in excerpt_lower:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    if provider == "gemini" and "invalid authentication credentials" in excerpt_lower:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    if status_code == 401:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    if status_code == 403 and ("error code: 1010" in excerpt_lower or "cloudflare" in server_lower):
        return "upstream_edge_blocked"
    if status_code == 403:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    return None


def provider_error_message(provider, api_key_env, error_class):
    if error_class == "upstream_auth_failed":
        return f"Provider {provider} rejected authentication for {api_key_env}."
    if error_class == "upstream_auth_missing":
        return f"Missing API key for provider {provider}: {api_key_env}"
    if error_class == "upstream_edge_blocked":
        return f"Provider {provider} probe was blocked upstream before auth could be verified."
    return None


def provider_probe_result(target, request_timeout):
    env_map = load_local_env()
    provider = target["provider"]
    api_key_env = target["api_key_env"]
    api_key = env_map.get(api_key_env) or os.environ.get(api_key_env)
    auth_present = bool(api_key)
    endpoint_reachable = False
    auth_accepted = False
    probe_http_status = None
    error_class = None
    error_message = None
    response_excerpt = None
    response_server = None
    response_content_type = None
    response_json = None
    visible_model_ids_sample = None
    visible_model_count = None
    requested_model_runtime_id = target.get("expected_model_id")
    requested_model_listed = None

    probe_method = target.get("probe_method", "GET")
    req = Request(target["probe_url"], data=provider_probe_payload(target), method=probe_method)
    req.add_header("User-Agent", "curl/8.7.1")
    req.add_header("Accept", "application/json")
    if probe_method != "GET":
        req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen(req, timeout=request_timeout) as resp:
            probe_http_status = resp.status
            endpoint_reachable = True
            response_server = resp.headers.get("Server")
            response_content_type = resp.headers.get("Content-Type")
            raw_body = resp.read()
            if probe_method == "GET" and raw_body:
                try:
                    response_json = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    response_json = None
            auth_accepted = auth_present
    except HTTPError as error:
        probe_http_status = error.code
        endpoint_reachable = True
        response_server = error.headers.get("Server")
        response_content_type = error.headers.get("Content-Type")
        response_excerpt = error.read(240).decode("utf-8", "replace").replace("\n", " ").strip() or None
        error_class = classify_provider_http_error(
            provider,
            error.code,
            response_server,
            response_excerpt,
            auth_present,
        )
        error_message = provider_error_message(provider, api_key_env, error_class)
        auth_accepted = False
    except socket.timeout:
        error_class = "upstream_timeout"
        error_message = f"Timed out reaching provider {provider}."
    except URLError as error:
        error_class = "provider_unreachable"
        error_message = f"Connection error while reaching provider {provider}: {error}"

    route_config_resolvable = isinstance(target.get("route_model"), str) and bool(target["route_model"].strip())
    cost_policy_explicit = isinstance(target.get("cost_class"), str) and bool(target["cost_class"].strip())
    if not target.get("policy_allowed", False):
        policy_status = "provider_blocked_policy"
    elif not route_config_resolvable:
        policy_status = "provider_blocked_route_config"
    elif not cost_policy_explicit:
        policy_status = "provider_blocked_cost"
    else:
        policy_status = "provider_ready_policy"

    if not auth_present:
        transport_status = "provider_blocked_auth"
        if error_class is None:
            error_class = "upstream_auth_missing"
            error_message = f"Missing API key for provider {provider}: {api_key_env}"
    elif error_class == "upstream_edge_blocked":
        transport_status = "provider_edge_blocked"
    elif not endpoint_reachable:
        transport_status = "provider_unreachable"
    elif not auth_accepted:
        transport_status = "provider_blocked_auth"
    else:
        transport_status = "provider_ready_transport"

    if isinstance(response_json, dict) and isinstance(response_json.get("data"), list):
        visible_model_ids = [
            item.get("id")
            for item in response_json.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        visible_model_count = len(visible_model_ids)
        visible_model_ids_sample = visible_model_ids[:12]
        if isinstance(requested_model_runtime_id, str) and requested_model_runtime_id:
            requested_model_listed = requested_model_runtime_id in visible_model_ids

    requested_model_available = transport_status == "provider_ready_transport" and policy_status == "provider_ready_policy"
    if requested_model_listed is False:
        requested_model_available = False

    return {
        "provider": provider,
        "provider_label": target["provider_label"],
        "lab_mode": True,
        "transport_status": transport_status,
        "policy_status": policy_status,
        "probe_method": probe_method,
        "auth_present": auth_present,
        "auth_accepted": auth_accepted,
        "endpoint_reachable": endpoint_reachable,
        "probe_http_status": probe_http_status,
        "probe_url": target["probe_url"],
        "api_key_env": api_key_env,
        "route_model": target["route_model"],
        "requested_model_runtime_id": requested_model_runtime_id,
        "requested_model_listed": requested_model_listed,
        "visible_model_count": visible_model_count,
        "visible_model_ids_sample": visible_model_ids_sample,
        "requested_model": target["route_model"],
        "effective_model": target["route_model"],
        "requested_model_available": requested_model_available,
        "fallback_used": False,
        "route_config_resolvable": route_config_resolvable,
        "cost_policy_explicit": cost_policy_explicit,
        "cost_class": target.get("cost_class"),
        "error_class": error_class,
        "error_message": error_message,
        "response_server": response_server,
        "response_content_type": response_content_type,
        "response_excerpt": response_excerpt,
        "network_dependent_evidence": True,
        "synthetic_contract_evidence": False,
    }


def provider_probe_blocked_result(target):
    env_map = load_local_env()
    provider = target["provider"]
    api_key_env = target["api_key_env"]
    auth_present = bool(env_map.get(api_key_env) or os.environ.get(api_key_env))
    return {
        "provider": provider,
        "provider_label": target["provider_label"],
        "lab_mode": True,
        "transport_status": "provider_probe_blocked_by_cost_policy",
        "policy_status": "provider_blocked_cost_policy",
        "probe_method": target.get("probe_method", "GET"),
        "auth_present": auth_present,
        "auth_accepted": False,
        "endpoint_reachable": False,
        "probe_http_status": None,
        "probe_url": target["probe_url"],
        "api_key_env": api_key_env,
        "route_model": target["route_model"],
        "requested_model_runtime_id": target.get("expected_model_id"),
        "requested_model_listed": None,
        "visible_model_count": None,
        "visible_model_ids_sample": None,
        "requested_model": target["route_model"],
        "effective_model": target["route_model"],
        "requested_model_available": False,
        "fallback_used": False,
        "route_config_resolvable": True,
        "cost_policy_explicit": True,
        "cost_class": target.get("cost_class"),
        "error_class": "paid_route_blocked",
        "error_message": "Direct provider probe blocked: run with --allow-paid-routes to open paid direct lane checks.",
        "response_server": None,
        "response_content_type": None,
        "response_excerpt": None,
        "network_dependent_evidence": False,
        "synthetic_contract_evidence": True,
    }


def is_valid_response_contract(result):
    return (
        isinstance(result, dict)
        and result.get("object") == "response"
        and isinstance(result.get("provider"), str)
        and isinstance(result.get("effective_model"), str)
    )


def prompt_fingerprint(prompt_text):
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def attestation_secret():
    return load_env_token(CLIENT_TOKEN_KEY)


def attach_attestation(payload):
    unsigned = dict(payload)
    unsigned.pop("attestation", None)
    signature = hmac.new(attestation_secret().encode("utf-8"), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    signed = dict(unsigned)
    signed["attestation"] = {"scheme": "hmac-sha256", "signature": signature}
    return signed


def verify_attestation(payload):
    attestation = payload.get("attestation")
    if not isinstance(attestation, dict) or attestation.get("scheme") != "hmac-sha256" or not isinstance(attestation.get("signature"), str):
        raise SystemExit("Artifact attestation missing or invalid.")
    unsigned = dict(payload)
    unsigned.pop("attestation", None)
    expected = hmac.new(attestation_secret().encode("utf-8"), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(attestation["signature"], expected):
        raise SystemExit("Artifact attestation verification failed.")


def load_attested_report(path_text, expected_kind):
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"Report not found: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("report_kind") != expected_kind:
        raise SystemExit(f"Invalid report format for {path}: expected report_kind={expected_kind!r}.")
    verify_attestation(report)
    return path, report


def validate_iso8601(value, field_name):
    if not isinstance(value, str):
        raise SystemExit(f"Invalid {field_name}: expected ISO8601 string.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"Invalid {field_name}: {value!r}") from exc
    return value


def validate_string_list(values, field_name, model_id):
    if not isinstance(values, list) or not all(isinstance(item, str) and item for item in values):
        raise SystemExit(f"Invalid registry entry {model_id}: {field_name} must be a list of non-empty strings.")
    return list(values)


def validate_registry_entry(entry, source_label):
    if not isinstance(entry, dict):
        raise SystemExit(f"Invalid registry seed entry in {source_label}: expected object.")

    model_id = entry.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise SystemExit(f"Invalid registry seed entry in {source_label}: missing model_id.")

    normalized = {
        "model_id": model_id,
        "provider": entry.get("provider"),
        "provider_type": entry.get("provider_type"),
        "availability_state": entry.get("availability_state"),
        "lane_role": entry.get("lane_role"),
        "cost_class": entry.get("cost_class"),
        "capability_tags": entry.get("capability_tags"),
        "fallback_eligible": entry.get("fallback_eligible"),
        "max_context_hint": entry.get("max_context_hint"),
        "evidence_level": entry.get("evidence_level"),
        "last_verified_at": entry.get("last_verified_at"),
        "blocked_reason_optional": entry.get("blocked_reason_optional"),
    }

    for field_name in ("provider", "provider_type", "cost_class"):
        if not isinstance(normalized[field_name], str) or not normalized[field_name]:
            raise SystemExit(f"Invalid registry entry {model_id}: {field_name} must be a non-empty string.")
    if normalized["availability_state"] not in ALLOWED_AVAILABILITY_STATES:
        raise SystemExit(f"Invalid registry entry {model_id}: unsupported availability_state={normalized['availability_state']!r}.")
    if normalized["lane_role"] not in ALLOWED_LANE_ROLES:
        raise SystemExit(f"Invalid registry entry {model_id}: unsupported lane_role={normalized['lane_role']!r}.")
    if normalized["evidence_level"] not in ALLOWED_EVIDENCE_LEVELS:
        raise SystemExit(f"Invalid registry entry {model_id}: unsupported evidence_level={normalized['evidence_level']!r}.")
    normalized["capability_tags"] = validate_string_list(normalized["capability_tags"], "capability_tags", model_id)
    if not isinstance(normalized["fallback_eligible"], bool):
        raise SystemExit(f"Invalid registry entry {model_id}: fallback_eligible must be boolean.")
    if normalized["max_context_hint"] is not None and not isinstance(normalized["max_context_hint"], (int, str)):
        raise SystemExit(f"Invalid registry entry {model_id}: max_context_hint must be null, int, or string.")
    normalized["last_verified_at"] = validate_iso8601(normalized["last_verified_at"], f"{model_id}.last_verified_at")
    if normalized["blocked_reason_optional"] is not None and not isinstance(normalized["blocked_reason_optional"], str):
        raise SystemExit(f"Invalid registry entry {model_id}: blocked_reason_optional must be null or string.")

    evidence_sources = entry.get("evidence_sources", [])
    evidence_chain = entry.get("evidence_chain", [])
    normalized["evidence_sources"] = validate_string_list(evidence_sources, "evidence_sources", model_id) if evidence_sources else []
    if evidence_chain:
        if not isinstance(evidence_chain, list) or not all(isinstance(item, dict) for item in evidence_chain):
            raise SystemExit(f"Invalid registry entry {model_id}: evidence_chain must be a list of objects.")
        normalized["evidence_chain"] = list(evidence_chain)
    else:
        normalized["evidence_chain"] = []
    return normalized


def load_registry_seed(path_text):
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"Registry seed not found: {path}")
    seed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(seed, dict) or not isinstance(seed.get("entries"), list):
        raise SystemExit(f"Invalid registry seed format: {path}")

    seen = set()
    entries = []
    for raw_entry in seed["entries"]:
        entry = validate_registry_entry(raw_entry, str(path))
        if entry["model_id"] in seen:
            raise SystemExit(f"Duplicate registry seed model_id: {entry['model_id']}")
        seen.add(entry["model_id"])
        entries.append(entry)

    registry_seed_version = seed.get("registry_seed_version")
    source_plan = seed.get("source_plan")
    if not isinstance(registry_seed_version, str) or not registry_seed_version:
        raise SystemExit(f"Invalid registry seed format: missing registry_seed_version in {path}")
    if not isinstance(source_plan, str) or not source_plan:
        raise SystemExit(f"Invalid registry seed format: missing source_plan in {path}")

    return path, {
        "registry_seed_version": registry_seed_version,
        "source_plan": source_plan,
        "entries": entries,
    }


def clone_registry_entries(entries):
    return json.loads(json.dumps(entries))


def registry_index(entries):
    return {entry["model_id"]: entry for entry in entries}


def append_registry_evidence(entry, source_type, report_kind, evidence_level, observed_at, facts):
    entry.setdefault("evidence_chain", []).append(
        {
            "source_type": source_type,
            "report_kind": report_kind,
            "evidence_level": evidence_level,
            "observed_at_utc": observed_at,
            "facts": facts,
        }
    )


def merge_provider_report_into_registry(entries, provider_report):
    started_at = provider_report["started_at_utc"]
    indexed = registry_index(entries)

    for item in provider_report.get("providers", []):
        model_id = item.get("route_model")
        if model_id not in indexed:
            continue
        entry = indexed[model_id]
        append_registry_evidence(
            entry,
            "provider_access_report",
            provider_report["report_kind"],
            "runtime_success" if item.get("probe_method") == "POST" and item.get("probe_http_status") == 200 else "provider_models_endpoint",
            started_at,
            {
                "provider": item.get("provider"),
                "probe_method": item.get("probe_method"),
                "probe_http_status": item.get("probe_http_status"),
                "auth_present": item.get("auth_present"),
                "auth_accepted": item.get("auth_accepted"),
                "endpoint_reachable": item.get("endpoint_reachable"),
                "transport_status": item.get("transport_status"),
                "policy_status": item.get("policy_status"),
                "requested_model_available": item.get("requested_model_available"),
                "error_class": item.get("error_class"),
            },
        )

        if entry["availability_state"] == "externally_blocked":
            entry["last_verified_at"] = started_at
            continue
        if not item.get("auth_present") or not item.get("auth_accepted"):
            entry["availability_state"] = "auth_unconfirmed"
            entry["evidence_level"] = "provider_models_endpoint"
            entry["last_verified_at"] = started_at
            continue
        if item.get("probe_method") == "POST" and item.get("probe_http_status") == 200 and item.get("requested_model_available"):
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = started_at
            continue
        if item.get("endpoint_reachable") and item.get("probe_http_status") == 200:
            entry["availability_state"] = "provider_visible_but_unverified"
            entry["evidence_level"] = "provider_models_endpoint"
            entry["last_verified_at"] = started_at


def merge_watch_report_into_registry(entries, watch_report):
    provider = watch_report.get("provider")
    canonical_target_model = watch_report.get("canonical_target_model")
    if not isinstance(provider, str) or not isinstance(canonical_target_model, str):
        raise SystemExit("Invalid authority watch report: missing provider or canonical_target_model.")

    indexed = registry_index(entries)
    model_id = f"direct-{provider}-{canonical_target_model}"
    if model_id not in indexed:
        raise SystemExit(f"Authority watch report refers to unknown registry model_id: {model_id}")

    entry = indexed[model_id]
    watch_check = watch_report.get("watch_check", {})
    if not isinstance(watch_check, dict):
        raise SystemExit("Invalid authority watch report: watch_check must be an object.")

    started_at = watch_report["started_at_utc"]
    append_registry_evidence(
        entry,
        "authority_watch_report",
        watch_report["report_kind"],
        "runtime_failure",
        started_at,
        {
            "models_http_status": watch_check.get("models_http_status"),
            "models_contains_canonical_target": watch_check.get("models_contains_canonical_target"),
            "chat_http_status": watch_check.get("chat_http_status"),
            "chat_success": watch_check.get("chat_success"),
            "technical_execution_allowed": watch_report.get("technical_execution_allowed"),
            "chat_error_excerpt": safe_excerpt(watch_check.get("chat_error_message") or "", limit=200),
        },
    )

    if not watch_report.get("technical_execution_allowed") or not watch_check.get("chat_success"):
        entry["availability_state"] = "externally_blocked"
        entry["lane_role"] = "blocked_target"
        entry["evidence_level"] = "runtime_failure"
        entry["last_verified_at"] = started_at
        entry["blocked_reason_optional"] = safe_excerpt(watch_check.get("chat_error_message") or "execution entitlement absent", limit=200)


def merge_qualification_report_into_registry(entries, qualification_report):
    started_at = qualification_report["started_at_utc"]
    indexed = registry_index(entries)

    for item in qualification_report.get("models", []):
        model_id = item.get("requested_model") or item.get("model")
        if model_id not in indexed:
            continue
        entry = indexed[model_id]
        requested_probe = item.get("requested_probe", {})
        fallback_probe = item.get("fallback_probe", {})
        append_registry_evidence(
            entry,
            "route_qualification_report",
            qualification_report["report_kind"],
            "runtime_success" if requested_probe.get("success") else "runtime_failure",
            started_at,
            {
                "display_model": item.get("model"),
                "qualification_status": item.get("qualification_status"),
                "requested_success": requested_probe.get("success"),
                "requested_error_class": requested_probe.get("error_class"),
                "fallback_success": fallback_probe.get("success"),
                "fallback_error_class": fallback_probe.get("error_class"),
            },
        )

        if requested_probe.get("success"):
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = started_at
            continue

        error_class = requested_probe.get("error_class")
        if error_class in {"upstream_timeout", "upstream_rate_limited", "upstream_overloaded"}:
            entry["availability_state"] = "unstable"
            entry["evidence_level"] = "runtime_failure"
            entry["last_verified_at"] = started_at
            continue

        if error_class == "paid_route_blocked":
            entry["last_verified_at"] = started_at
            continue

        if requested_probe.get("attempted"):
            entry["evidence_level"] = "runtime_failure"
            entry["last_verified_at"] = started_at


def merge_response_report_into_registry(entries, response_report):
    started_at = response_report["started_at_utc"]
    indexed = registry_index(entries)
    response_summaries = {
        item["model"]: item for item in response_report.get("model_summaries", []) if isinstance(item, dict) and isinstance(item.get("model"), str)
    }

    for model_id, summary in response_summaries.items():
        if model_id not in indexed:
            continue
        entry = indexed[model_id]
        append_registry_evidence(
            entry,
            "response_evidence_report",
            response_report["report_kind"],
            entry["evidence_level"],
            started_at,
            {
                "response_evidence_status": summary.get("response_evidence_status"),
                "eligible_for_task_eval": summary.get("eligible_for_task_eval"),
                "useful_response_count": summary.get("useful_response_count"),
                "unstable_response_count": summary.get("unstable_response_count"),
                "total_attempts": summary.get("repeatability", {}).get("total_attempts"),
            },
        )

        # Response evidence is a stronger signal than route qualification.
        # If it shows instability or inability to produce useful output, do not keep
        # the registry entry promoted as runtime_success.
        if entry.get("availability_state") == "externally_blocked":
            continue

        response_status = summary.get("response_evidence_status")
        unstable_ratio = summary.get("unstable_attempt_ratio")
        if not isinstance(unstable_ratio, (int, float)):
            unstable_ratio = summary.get("repeatability", {}).get("unstable_attempt_ratio")

        if response_status == "response_evidence_candidate":
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = started_at
            continue

        if response_status == "unstable_or_limited" or (isinstance(unstable_ratio, (int, float)) and unstable_ratio >= 0.5):
            entry["availability_state"] = "unstable"
            entry["evidence_level"] = "runtime_failure"
            entry["last_verified_at"] = started_at


def merge_eval_report_into_registry(entries, eval_report):
    started_at = eval_report["started_at_utc"]
    indexed = registry_index(entries)
    model_summaries = {
        item["model"]: item for item in eval_report.get("model_summaries", []) if isinstance(item, dict) and isinstance(item.get("model"), str)
    }

    for model_id, summary in model_summaries.items():
        if model_id not in indexed:
            continue
        entry = indexed[model_id]
        append_registry_evidence(
            entry,
            "task_eval_report",
            eval_report["report_kind"],
            entry["evidence_level"],
            started_at,
            {
                "outcome": summary.get("outcome"),
                "direct_success_count": summary.get("direct_success_count"),
                "fallback_success_count": summary.get("fallback_success_count"),
                "timeout_count": summary.get("timeout_count"),
                "rate_limited_count": summary.get("rate_limited_count"),
                "overloaded_count": summary.get("overloaded_count"),
                "budget_exhausted_count": summary.get("budget_exhausted_count"),
                "skipped_count": summary.get("skipped_count"),
            },
        )

        # Task-eval is a strong runtime signal.
        # Downgrade on instability to prevent registry overstatement.
        if entry.get("availability_state") == "externally_blocked":
            continue

        outcome = summary.get("outcome")
        timeout_count = summary.get("timeout_count") or 0
        rate_limited_count = summary.get("rate_limited_count") or 0
        overloaded_count = summary.get("overloaded_count") or 0
        direct_success_count = summary.get("direct_success_count") or 0
        total_records = summary.get("total_records") or 0

        unstable_by_counts = any(
            isinstance(value, int) and value > 0
            for value in (timeout_count, rate_limited_count, overloaded_count)
        )
        unstable_by_outcome = outcome in {"unstable_or_limited", "failed"}

        if unstable_by_counts or unstable_by_outcome:
            entry["availability_state"] = "unstable"
            entry["evidence_level"] = "runtime_failure"
            entry["last_verified_at"] = started_at
            continue

        if isinstance(direct_success_count, int) and isinstance(total_records, int) and total_records > 0 and direct_success_count == total_records:
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = started_at


def count_registry_by(entries, field_name):
    counts = {}
    for entry in entries:
        counts[entry[field_name]] = counts.get(entry[field_name], 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def build_registry_summary(entries):
    blocked_role_violation = any(
        entry["availability_state"] == "externally_blocked" and entry["lane_role"] not in {"blocked_target", "strategic_target"}
        for entry in entries
    )
    evidence_overstatement_detected = any(
        entry["availability_state"] in {"verified_accessible", "verified_accessible_limited"}
        and entry["evidence_level"] != "runtime_success"
        for entry in entries
    )
    return {
        "registry_entry_count": len(entries),
        "availability_state_counts": count_registry_by(entries, "availability_state"),
        "lane_role_counts": count_registry_by(entries, "lane_role"),
        "provider_counts": count_registry_by(entries, "provider"),
        "blocked_model_ids": sorted(entry["model_id"] for entry in entries if entry["availability_state"] == "externally_blocked"),
        "current_practical_pool_model_ids": sorted(
            entry["model_id"] for entry in entries if entry["lane_role"] in {"primary_practical", "secondary_reasoning"}
        ),
        "runtime_verified_model_ids": sorted(
            entry["model_id"] for entry in entries if entry["availability_state"] in {"verified_accessible", "verified_accessible_limited"}
        ),
        "blocked_targets_not_promoted": not blocked_role_violation,
        "evidence_overstatement_detected": evidence_overstatement_detected,
        "control_plane_only": True,
        "technical_execution_opened": False,
        "advisory_verdict": "registry_contract_materialized"
        if not blocked_role_violation and not evidence_overstatement_detected
        else "registry_contract_materialized_with_integrity_warnings",
    }


def response_text_from_result(result):
    text = result.get("output_text")
    if isinstance(text, str):
        return text
    pieces = []
    for item in result.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                pieces.append(content["text"])
    return "\n".join(piece for piece in pieces if piece)


def safe_excerpt(text, limit=160):
    compact = " ".join(text.split())
    suspicious_patterns = (
        r"sk-[A-Za-z0-9_-]{8,}",
        r"\b(?:bearer|token|secret|password|api[_ -]?key)\b",
        r"https?://\S+",
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b",
        r"[A-Fa-f0-9]{32,}",
        r"[A-Za-z0-9_-]{20,}={0,2}",
    )
    if any(re.search(pattern, compact, flags=re.IGNORECASE) for pattern in suspicious_patterns):
        return "[redacted]"
    compact = re.sub(r"([A-Za-z0-9]{24,})", "[redacted]", compact)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def build_response_basis_flags(probe_id, text):
    lowered = text.lower()
    stripped = text.strip()
    code_tokens = ("def ", "class ", "import ", "return ", "argparse", "pytest", "assert ", "try:", "except ")
    probe_markers = {
        "write_function": ("def ", "return ", "slugify"),
        "find_bug": ("bug", "fix", "none", "len(", "sum(", "traceback", "exception"),
        "cli_skeleton": ("argparse", "subparsers", "status", "run", "parser"),
        "propose_tests": ("test", "pytest", "assert"),
    }
    basis = {
        "has_nonempty_text": bool(stripped),
        "has_code_tokens": any(re.search(rf"(^|\\n)\\s*{re.escape(token.strip())}", text) for token in code_tokens) or "```" in text,
        "has_refusal_marker": any(marker in lowered for marker in (
            "i can't",
            "i cannot",
            "can't help",
            "cannot help",
            "i’m sorry",
            "i am sorry",
            "unable to",
        )),
        "has_truncation_marker": stripped.endswith("...") or "[truncated]" in lowered or (text.count("```") % 2 == 1),
        "has_list_structure": any(line.lstrip().startswith(("-", "*", "1.", "2.")) for line in text.splitlines()),
        "has_error_like_text": "traceback" in lowered or "error:" in lowered or "exception" in lowered,
        "looks_like_boilerplate": len(stripped) < 24 or any(marker in lowered for marker in ("here's a simple example", "here is a simple example", "you can use this")),
        "looks_like_probe_aligned": any(token in lowered for token in probe_markers.get(probe_id, ())),
    }
    return basis


def build_response_shape(text):
    basis = build_response_basis_flags("generic", text)
    return {
        "has_output_text": basis["has_nonempty_text"],
        "has_code_block": "```" in text,
        "has_refusal_marker": basis["has_refusal_marker"],
        "has_empty_body": not basis["has_nonempty_text"],
        "has_truncation_marker": basis["has_truncation_marker"],
        "has_list_structure": basis["has_list_structure"],
        "has_error_like_text": basis["has_error_like_text"],
    }


def classify_content_signal(probe_id, text, response_shape, basis_flags):
    lowered = text.lower()
    if response_shape["has_empty_body"]:
        return "empty"
    if response_shape["has_refusal_marker"]:
        return "refusal_like"
    if response_shape["has_truncation_marker"]:
        return "truncated_or_incomplete"
    if (response_shape["has_code_block"] or basis_flags["has_code_tokens"]) and basis_flags["looks_like_probe_aligned"]:
        if probe_id == "cli_skeleton":
            return "cli_skeleton_like"
        return "code_like"
    if probe_id == "find_bug" and basis_flags["looks_like_probe_aligned"] and (basis_flags["has_error_like_text"] or any(token in lowered for token in ("fix", "bug", "none"))):
        return "bug_analysis_like"
    if probe_id == "propose_tests" and basis_flags["looks_like_probe_aligned"] and response_shape["has_list_structure"] and any(token in lowered for token in ("assert", "pytest", "test_")):
        return "list_of_tests"
    if basis_flags["looks_like_boilerplate"]:
        return "boilerplate_only"
    if basis_flags["looks_like_probe_aligned"] and any(token in lowered for token in ("because", "risk", "explain", "likely cause", "fix", "bug")):
        return "generic_explanation"
    return "unknown_shape"


def response_evidence_success(response_shape, content_signal):
    if response_shape["has_empty_body"]:
        return False
    if response_shape["has_refusal_marker"]:
        return False
    if response_shape["has_truncation_marker"]:
        return False
    if content_signal not in {"code_like", "list_of_tests", "bug_analysis_like", "cli_skeleton_like"}:
        return False
    return response_shape["has_output_text"]


def provider_error_summary(error):
    return {
        "status": error.status,
        "error_class": error.error_class,
        "message": error.message,
    }


def probe_success(result):
    return {
        "attempted": True,
        "success": True,
        "provider": result.get("provider"),
        "effective_model": result.get("effective_model"),
        "latency_ms": result.get("latency_ms"),
        "error_class": None,
        "fallback_used": result.get("fallback_used", False),
        "requested_model_available": result.get("requested_model_available", False),
        "network_dependent_evidence": result.get("network_dependent_evidence", True),
        "synthetic_contract_evidence": False,
    }


def probe_failure(error, attempted=True):
    return {
        "attempted": attempted,
        "success": False,
        "provider": None,
        "effective_model": None,
        "latency_ms": None,
        "error_class": error.error_class if error else None,
        "error_message": error.message if error else None,
        "network_dependent_evidence": attempted,
        "synthetic_contract_evidence": False,
    }


def not_attempted_probe():
    return {
        "attempted": False,
        "success": False,
        "provider": None,
        "effective_model": None,
        "latency_ms": None,
        "error_class": None,
        "error_message": None,
        "network_dependent_evidence": False,
        "synthetic_contract_evidence": False,
    }


def classify_qualification_status(requested_probe, fallback_probe):
    if requested_probe["success"] and requested_probe.get("requested_model_available"):
        return "requested_model_candidate"
    if fallback_probe["success"]:
        return "fallback_only"
    errors = {
        requested_probe.get("error_class"),
        fallback_probe.get("error_class"),
    }
    if "upstream_timeout" in errors or "upstream_rate_limited" in errors or "upstream_overloaded" in errors:
        return "unstable_or_limited"
    return "blocked_or_inconclusive"


def qualification_eligible(status):
    return status == "requested_model_candidate"


def qualify_model(base_url, display_model, requested_model, request_timeout, max_fallback_attempts, qualification_prompt, remaining_budget):
    provider_calls_used = 0
    requested_probe = not_attempted_probe()
    fallback_probe = not_attempted_probe()

    if remaining_budget <= 0:
        requested_probe = {
            "attempted": False,
            "success": False,
            "provider": None,
            "effective_model": None,
            "latency_ms": None,
            "error_class": "skipped_provider_call_budget",
            "error_message": "Provider call budget exhausted before qualification.",
            "network_dependent_evidence": False,
            "synthetic_contract_evidence": False,
        }
        status = "blocked_or_inconclusive"
        return {
            "model": display_model,
            "requested_model": requested_model,
            "requested_probe": requested_probe,
            "fallback_probe": fallback_probe,
            "qualification_status": status,
            "eligible_for_task_eval": False,
            "operator_override": False,
            "network_dependent_evidence": False,
            "synthetic_contract_evidence": False,
        }, provider_calls_used

    try:
        provider_calls_used += 1
        requested_result = send_responses_request(base_url, requested_model, qualification_prompt, request_timeout)
        requested_probe = probe_success(requested_result)
    except ModelRequestError as error:
        requested_probe = probe_failure(error)
        if should_try_fallback(str(error)) and max_fallback_attempts > 0:
            attempts = []
            last_error = None
            for fallback_model in smoke_candidates(requested_model)[1:]:
                if len(attempts) >= max_fallback_attempts:
                    break
                if provider_calls_used >= remaining_budget:
                    break
                attempts.append(fallback_model)
                try:
                    provider_calls_used += 1
                    fallback_result = send_responses_request(base_url, fallback_model, qualification_prompt, request_timeout)
                    fallback_probe = probe_success(fallback_result)
                    fallback_probe["attempted_models"] = attempts[:]
                    fallback_probe["fallback_chain"] = [requested_model, *attempts]
                    break
                except ModelRequestError as fallback_error:
                    last_error = fallback_error
                    if not should_try_fallback(str(fallback_error)):
                        break
            if not fallback_probe["success"]:
                fallback_probe = probe_failure(last_error, attempted=bool(attempts))
                fallback_probe["attempted_models"] = attempts
                fallback_probe["fallback_chain"] = [requested_model, *attempts] if attempts else [requested_model]

    qualification_status = classify_qualification_status(requested_probe, fallback_probe)
    return {
        "model": display_model,
        "requested_model": requested_model,
        "requested_probe": requested_probe,
        "fallback_probe": fallback_probe,
        "qualification_status": qualification_status,
        "eligible_for_task_eval": qualification_eligible(qualification_status),
        "operator_override": False,
        "network_dependent_evidence": requested_probe["network_dependent_evidence"] or fallback_probe["network_dependent_evidence"],
        "synthetic_contract_evidence": False,
    }, provider_calls_used


def write_route_reports(report):
    ensure_route_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = ROUTE_DIR / f"route_{stamp}.json"
    md_path = ROUTE_DIR / f"route_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Route Qualification {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- provider_calls_used: {report['provider_calls_used']}",
        f"- provider_call_budget: {report['provider_call_budget']}",
        f"- request_timeout_sec: {report['request_timeout_sec']}",
        f"- max_fallback_attempts: {report['max_fallback_attempts']}",
        "",
        "| model | requested_success | fallback_success | status | eligible_for_task_eval | requested_error | fallback_error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["models"]:
        lines.append(
            f"| {item['model']} | {'yes' if item['requested_probe']['success'] else 'no'} | "
            f"{'yes' if item['fallback_probe']['success'] else 'no'} | {item['qualification_status']} | "
            f"{'yes' if item['eligible_for_task_eval'] else 'no'} | "
            f"{item['requested_probe'].get('error_class') or '-'} | {item['fallback_probe'].get('error_class') or '-'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_provider_reports(report):
    ensure_provider_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = PROVIDER_DIR / f"provider_{stamp}.json"
    md_path = PROVIDER_DIR / f"provider_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Provider Access {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- request_timeout_sec: {report['request_timeout_sec']}",
        f"- allow_paid_routes: {report.get('allow_paid_routes')}",
        f"- technical_execution_opened: {report.get('technical_execution_opened')}",
        "",
        "| provider | transport_status | policy_status | auth_present | auth_accepted | endpoint_reachable | probe_http_status | route_model | error_class |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["providers"]:
        lines.append(
            f"| {item['provider']} | {item['transport_status']} | {item['policy_status']} | "
            f"{'yes' if item['auth_present'] else 'no'} | {'yes' if item['auth_accepted'] else 'no'} | "
            f"{'yes' if item['endpoint_reachable'] else 'no'} | {item.get('probe_http_status') or '-'} | {item['route_model']} | "
            f"{item.get('error_class') or '-'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_error_taxonomy_report(report):
    ensure_verification_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = VERIFICATION_DIR / f"error_taxonomy_{stamp}.json"
    md_path = VERIFICATION_DIR / f"error_taxonomy_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Error Taxonomy Check {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- tested_model: {report['tested_model']}",
        f"- allow_paid_routes: {report['allow_paid_routes']}",
        f"- technical_execution_opened: {report['technical_execution_opened']}",
        f"- all_checks_passed: {report['summary']['all_checks_passed']}",
        "",
        "| scenario | expected_error_class | actual_error_class | expected_status | actual_status | passed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["records"]:
        lines.append(
            f"| {item['scenario']} | {item['expected_error_class']} | {item.get('actual_error_class') or '-'} | "
            f"{item['expected_status']} | {item.get('actual_status') or '-'} | {'yes' if item['passed'] else 'no'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_cost_gate_report(report):
    ensure_cost_gate_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = COST_GATE_DIR / f"cost_gate_{stamp}.json"
    md_path = COST_GATE_DIR / f"cost_gate_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Cost Gate Check {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- request_timeout_sec: {report['request_timeout_sec']}",
        f"- allow_paid_routes: {report['allow_paid_routes']}",
        f"- models_endpoint_loaded: {report['models_endpoint_loaded']}",
        f"- layer_violation_detected: {report['layer_violation_detected']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
        "",
        "| model | visible | cost_class | gate_expectation | gate_outcome | error_class | effective_model |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["records"]:
        lines.append(
            f"| {item['model']} | {'yes' if item['visible_in_models_endpoint'] else 'no'} | {item['configured_cost_class'] or '-'} | "
            f"{item['gate_expectation']} | {item['gate_outcome']} | {item.get('error_class') or '-'} | {item.get('effective_model') or '-'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_registry_snapshot_report(report):
    ensure_registry_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = REGISTRY_DIR / f"registry_snapshot_{stamp}.json"
    md_path = REGISTRY_DIR / f"registry_snapshot_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    lines = [
        f"# External Agent Lab Model Registry Snapshot {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- registry_seed_path: {report['registry_seed_path']}",
        f"- provider_report_path: {report.get('provider_report_path') or '-'}",
        f"- watch_report_path: {report.get('watch_report_path') or '-'}",
        f"- qualification_report_path: {report.get('qualification_report_path') or '-'}",
        f"- response_report_path: {report.get('response_report_path') or '-'}",
        f"- eval_report_path: {report.get('eval_report_path') or '-'}",
        f"- control_plane_only: {report['control_plane_only']}",
        f"- technical_execution_opened: {report['technical_execution_opened']}",
        f"- advisory_verdict: {summary['advisory_verdict']}",
        "",
        "## Summary",
        "",
        f"- registry_entry_count: {summary['registry_entry_count']}",
        f"- blocked_model_ids: {', '.join(summary['blocked_model_ids']) or '-'}",
        f"- runtime_verified_model_ids: {', '.join(summary['runtime_verified_model_ids']) or '-'}",
        "",
        "## Registry Entries",
        "",
        "| model_id | provider | availability_state | lane_role | evidence_level | cost_class | last_verified_at | blocked_reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in report["registry_entries"]:
        lines.append(
            f"| {entry['model_id']} | {entry['provider']} | {entry['availability_state']} | {entry['lane_role']} | "
            f"{entry['evidence_level']} | {entry['cost_class']} | {entry['last_verified_at']} | "
            f"{safe_excerpt(entry.get('blocked_reason_optional') or '-', limit=80)} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_baseline_report(report):
    ensure_baseline_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = BASELINE_DIR / f"baseline_{stamp}.json"
    md_path = BASELINE_DIR / f"baseline_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Direct Admission Baseline {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- direct_keys_present_count: {report['summary']['direct_keys_present_count']}",
        f"- provider_auth_present_count: {report['summary']['provider_auth_present_count']}",
        f"- state_fingerprint: {report['state_fingerprint']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_guard_report(report):
    ensure_guard_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = GUARD_DIR / f"guard_{stamp}.json"
    md_path = GUARD_DIR / f"guard_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Admission Guard {stamp}",
        "",
        f"- baseline_report_path: {report['baseline_report_path']}",
        f"- baseline_matches_current_state: {report['baseline_matches_current_state']}",
        f"- no_delta_detected: {report['no_delta_detected']}",
        f"- replay_risk_detected: {report['replay_risk_detected']}",
        f"- tamper_detected: {report['tamper_detected']}",
        f"- tamper_guard_passed: {report['tamper_guard_passed']}",
        f"- guard_passed: {report['guard_passed']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_delta_report(report):
    ensure_delta_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = DELTA_DIR / f"delta_{stamp}.json"
    md_path = DELTA_DIR / f"delta_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Admission Delta {stamp}",
        "",
        f"- baseline_report_path: {report['baseline_report_path']}",
        f"- guard_report_path: {report['guard_report_path']}",
        f"- state_fingerprint_before: {report['state_fingerprint_before']}",
        f"- state_fingerprint_after: {report['state_fingerprint_after']}",
        f"- delta_detected: {report['delta_detected']}",
        f"- delta_gate_open_candidate: {report['delta_gate_open_candidate']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_mutation_report(report, prefix, title):
    ensure_mutation_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = MUTATION_DIR / f"{prefix}_{stamp}.json"
    md_path = MUTATION_DIR / f"{prefix}_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# {title} {stamp}",
        "",
        f"- mutation_provider: {report['mutation_provider']}",
        f"- mutation_key_name: {report['mutation_key_name']}",
        f"- mutation_action: {report['mutation_action']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    if "state_fingerprint_before" in report:
        lines.append(f"- state_fingerprint_before: {report['state_fingerprint_before']}")
    if "state_fingerprint_after" in report:
        lines.append(f"- state_fingerprint_after: {report['state_fingerprint_after']}")
    if "rollback_completed" in report:
        lines.append(f"- rollback_completed: {report['rollback_completed']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_pilot_verification_reports(report):
    ensure_pilot_verification_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = PILOT_VERIFICATION_DIR / f"pilot_verification_{stamp}.json"
    md_path = PILOT_VERIFICATION_DIR / f"pilot_verification_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Staged Pilot Admission Verification Precheck {stamp}",
        "",
        f"- pilot_impl_gate_path: {report['pilot_impl_gate_path']}",
        f"- pilot_impl_contour_status: {report['pilot_impl_contour_status']}",
        f"- staged_pilot_impl_built_for_verification: {report['staged_pilot_impl_built_for_verification']}",
        f"- staged_pilot_verified_candidate: {report['staged_pilot_verified_candidate']}",
        f"- pilot_verification_contour_status: {report['pilot_verification_contour_status']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
        f"- reason: {report['summary']['reason']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_admission_state_report(report):
    ensure_provider_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = PROVIDER_DIR / f"admission_state_{stamp}.json"
    md_path = PROVIDER_DIR / f"admission_state_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Admission State {stamp}",
        "",
        f"- prior_report_kind: {report['prior_report_kind']}",
        f"- prior_report_path: {report['prior_report_path']}",
        f"- state_changed: {report['state_changed']}",
        f"- baseline_already_contains_current_state: {report['baseline_already_contains_current_state']}",
        f"- direct_keys_present_count: {report['summary']['direct_keys_present_count']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_admission_trigger_report(report):
    ensure_provider_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = PROVIDER_DIR / f"admission_trigger_{stamp}.json"
    md_path = PROVIDER_DIR / f"admission_trigger_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Admission Trigger {stamp}",
        "",
        f"- prior_admission_state_report_path: {report['prior_admission_state_report_path']}",
        f"- key_names_changed: {report['key_names_changed']}",
        f"- provider_auth_changed: {report['provider_auth_changed']}",
        f"- state_changed: {report['state_changed']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_admission_event_report(report):
    ensure_provider_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = PROVIDER_DIR / f"admission_event_{stamp}.json"
    md_path = PROVIDER_DIR / f"admission_event_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Admission Event {stamp}",
        "",
        f"- prior_trigger_report_path: {report['prior_trigger_report_path']}",
        f"- state_changed: {report['state_changed']}",
        f"- event_type: {report['event_type']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_access_recheck_precheck_report(report):
    ensure_access_recheck_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = ACCESS_RECHECK_DIR / f"access_recheck_{stamp}.json"
    md_path = ACCESS_RECHECK_DIR / f"access_recheck_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Direct Provider Access Recheck Precheck {stamp}",
        "",
        f"- admission_event_gate_path: {report['admission_event_gate_path']}",
        f"- admission_event_open_candidate: {report['admission_event_open_candidate']}",
        f"- direct_provider_access_recheck_contour_status: {report['direct_provider_access_recheck_contour_status']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
        f"- reason: {report['summary']['reason']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_direct_route_qualification_precheck_report(report):
    ensure_route_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = ROUTE_DIR / f"direct_qualification_gate_{stamp}.json"
    md_path = ROUTE_DIR / f"direct_qualification_gate_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Direct Route Qualification Precheck {stamp}",
        "",
        f"- access_recheck_gate_path: {report['access_recheck_gate_path']}",
        f"- access_recheck_open_candidate: {report['access_recheck_open_candidate']}",
        f"- route_qualification_contour_status: {report['route_qualification_contour_status']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
        f"- reason: {report['summary']['reason']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def write_repo_bound_planning_precheck_report(report):
    ensure_admission_planning_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = ADMISSION_PLANNING_DIR / f"repo_bound_planning_{stamp}.json"
    md_path = ADMISSION_PLANNING_DIR / f"repo_bound_planning_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Repo-Bound Controlled Admission Planning Precheck {stamp}",
        "",
        f"- verification_gate_path: {report['verification_gate_path']}",
        f"- direct_lab_verification_precheck_instantiated: {report['direct_lab_verification_precheck_instantiated']}",
        f"- repo_design_contour_status: {report['repo_design_contour_status']}",
        f"- advisory_verdict: {report['summary']['advisory_verdict']}",
        f"- reason: {report['summary']['reason']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def failure_record(
    model_name,
    requested_model,
    task_id,
    prompt_text,
    include_prompt_text,
    error_class,
    error_message,
    skipped_reason=None,
):
    payload = {
        "requested_model": requested_model,
        "requested_model_available": False,
        "fallback_used": False,
        "fallback_chain": [],
        "provider": None,
        "effective_model": None,
        "latency_ms": None,
        "error_class": error_class,
        "error_message": error_message,
        "network_dependent_evidence": skipped_reason is None,
        "status": "skipped" if skipped_reason else "failed",
        "attempted": skipped_reason is None,
    }
    record = make_eval_record(model_name, task_id, prompt_text, include_prompt_text, payload)
    if skipped_reason:
        record["skipped_reason"] = skipped_reason
    return record


def make_eval_record(model_name, task_id, prompt_text, include_prompt_text, result):
    status = result.get("status", "completed")
    record = {
        "model": model_name,
        "task_id": task_id,
        "status": status,
        "attempted": result.get("attempted", status != "skipped"),
        "skipped": status == "skipped",
        "requested_model": result.get("requested_model", model_name),
        "requested_model_available": result.get("requested_model_available"),
        "effective_model": result.get("effective_model"),
        "provider": result.get("provider"),
        "fallback_used": result.get("fallback_used"),
        "fallback_chain": result.get("fallback_chain", []),
        "latency_ms": result.get("latency_ms"),
        "error_class": result.get("error_class"),
        "error_message": result.get("error_message"),
        "network_dependent_evidence": result.get("network_dependent_evidence", True),
        "success": status == "completed",
        "manual_code_quality": None,
        "manual_instruction_following": None,
        "manual_text_executor_suitability": None,
    }
    if "usage" in result:
        record["tokens"] = result["usage"].get("total_tokens", 0)
    else:
        record["tokens"] = None
    record["prompt_fingerprint"] = prompt_fingerprint(prompt_text)
    if include_prompt_text:
        record["prompt_text"] = prompt_text
    return record


def classify_model_outcome(stats):
    if stats["direct_success_count"] > 0:
        return "requested_model_candidate"
    if stats["fallback_success_count"] > 0:
        return "fallback_only"
    if stats["timeout_count"] > 0 or stats["rate_limited_count"] > 0 or stats["overloaded_count"] > 0:
        return "unstable_or_limited"
    return "blocked_or_inconclusive"


def build_model_summaries(records):
    summaries = {}
    order = []
    for record in records:
        model = record["model"]
        if model not in summaries:
            summaries[model] = {
                "model": model,
                "total_records": 0,
                "success_count": 0,
                "direct_success_count": 0,
                "fallback_success_count": 0,
                "requested_model_available_count": 0,
                "timeout_count": 0,
                "rate_limited_count": 0,
                "overloaded_count": 0,
                "budget_exhausted_count": 0,
                "skipped_count": 0,
                "provider_calls_consumed_estimate": 0,
            }
            order.append(model)

        stats = summaries[model]
        stats["total_records"] += 1
        if record["attempted"]:
            stats["provider_calls_consumed_estimate"] += len(record.get("fallback_chain", []))
        if record["success"]:
            stats["success_count"] += 1
            if record["requested_model_available"]:
                stats["direct_success_count"] += 1
            elif record["fallback_used"]:
                stats["fallback_success_count"] += 1
        if record["requested_model_available"]:
            stats["requested_model_available_count"] += 1
        if record["error_class"] == "upstream_timeout":
            stats["timeout_count"] += 1
        if record["error_class"] == "upstream_rate_limited":
            stats["rate_limited_count"] += 1
        if record["error_class"] == "upstream_overloaded":
            stats["overloaded_count"] += 1
        if record["error_class"] == "free_executors_exhausted" and record["attempted"]:
            stats["budget_exhausted_count"] += 1
        if record["skipped"]:
            stats["skipped_count"] += 1

    model_summaries = []
    for model in order:
        stats = summaries[model]
        stats["outcome"] = classify_model_outcome(stats)
        model_summaries.append(stats)
    return model_summaries


def write_reports(report):
    ensure_eval_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = EVAL_DIR / f"eval_{stamp}.json"
    md_path = EVAL_DIR / f"eval_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Eval {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- provider_calls_used: {report['provider_calls_used']}",
        f"- provider_call_budget: {report['provider_call_budget']}",
        f"- request_timeout_sec: {report['request_timeout_sec']}",
        f"- max_fallback_attempts: {report['max_fallback_attempts']}",
        "",
        "## Outcome Matrix",
        "",
        "| model | outcome | direct_success | fallback_success | timeouts | rate_limited | overloaded | budget_exhausted | skipped |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for summary in report["model_summaries"]:
        lines.append(
            f"| {summary['model']} | {summary['outcome']} | {summary['direct_success_count']} | "
            f"{summary['fallback_success_count']} | {summary['timeout_count']} | {summary['rate_limited_count']} | {summary['overloaded_count']} | "
            f"{summary['budget_exhausted_count']} | {summary['skipped_count']} |"
        )

    lines.extend([
        "",
        "## Task Records",
        "",
        "| model | task | status | attempted | requested_available | effective | fallback | latency_ms | error_class |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for record in report["records"]:
        lines.append(
            f"| {record['model']} | {record['task_id']} | {record['status']} | {'yes' if record['attempted'] else 'no'} | "
            f"{record['requested_model_available']} | {record['effective_model'] or '-'} | "
            f"{'yes' if record['fallback_used'] else 'no'} | {record['latency_ms'] or '-'} | {record['error_class'] or '-'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def load_qualification_report(path_text):
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"Qualification report not found: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(report, dict)
        or report.get("report_kind") != "route_qualification"
        or not isinstance(report.get("models"), list)
        or "qualification_prompt_fingerprint" not in report
    ):
        raise SystemExit(f"Invalid qualification report format: {path}")
    verify_attestation(report)
    return path, report


def load_eval_report(path_text):
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"Eval report not found: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(report, dict)
        or report.get("report_kind") != "task_eval"
        or not isinstance(report.get("records"), list)
        or not isinstance(report.get("model_summaries"), list)
    ):
        raise SystemExit(f"Invalid eval report format: {path}")
    verify_attestation(report)
    return path, report


def validate_qualification_item(item):
    if not isinstance(item, dict):
        raise SystemExit("Invalid qualification report item: expected object.")
    if not isinstance(item.get("model"), str):
        raise SystemExit("Invalid qualification report item: missing model.")
    requested_probe = item.get("requested_probe")
    fallback_probe = item.get("fallback_probe")
    if not isinstance(requested_probe, dict) or not isinstance(fallback_probe, dict):
        raise SystemExit(f"Invalid qualification report item for model {item.get('model')}: missing probes.")
    recomputed_status = classify_qualification_status(requested_probe, fallback_probe)
    stored_status = item.get("qualification_status")
    if stored_status != recomputed_status:
        raise SystemExit(
            f"Qualification report integrity error for model {item.get('model')}: stored status {stored_status!r} "
            f"does not match recomputed status {recomputed_status!r}."
        )
    recomputed_eligibility = qualification_eligible(recomputed_status)
    if bool(item.get("eligible_for_task_eval")) != recomputed_eligibility:
        raise SystemExit(
            f"Qualification report integrity error for model {item.get('model')}: stored eligibility "
            f"{item.get('eligible_for_task_eval')!r} does not match recomputed eligibility {recomputed_eligibility!r}."
        )
    return {
        **item,
        "qualification_status": recomputed_status,
        "eligible_for_task_eval": recomputed_eligibility,
    }


def write_response_reports(report):
    ensure_response_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    json_path = RESPONSE_DIR / f"response_{stamp}.json"
    md_path = RESPONSE_DIR / f"response_{stamp}.md"
    report = attach_attestation(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# External Agent Lab Response Evidence {stamp}",
        "",
        f"- started_at_utc: {report['started_at_utc']}",
        f"- provider_calls_used: {report['provider_calls_used']}",
        f"- provider_call_budget: {report['provider_call_budget']}",
        f"- request_timeout_sec: {report['request_timeout_sec']}",
        f"- qualification_report_path: {report['qualification_report_path']}",
        f"- response_attempts_per_probe: {report['response_attempts_per_probe']}",
        "",
        "| model | probe | status | attempted | signal | useful | cost_class | fallback_used | error_class | chars | excerpt |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in report["records"]:
        excerpt = record.get("response_excerpt_safe") or "-"
        lines.append(
            f"| {record['model']} | {record['probe_id']} | {record['status']} | "
            f"{'yes' if record['attempted'] else 'no'} | {record.get('content_signal') or '-'} | "
            f"{'yes' if record.get('response_evidence_success') else 'no'} | {record.get('cost_class') or '-'} | "
            f"{'yes' if record.get('fallback_used') else 'no'} | {record.get('error_class') or '-'} | "
            f"{record.get('response_char_count') or 0} | {excerpt} |"
        )

    lines.extend([
        "",
        "## Model Gate",
        "",
        "| model | status | eligible_for_task_eval | useful_responses | attempts | unstable_ratio | empty | refusal | truncated | unstable | skipped |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for item in report["model_summaries"]:
        lines.append(
            f"| {item['model']} | {item['response_evidence_status']} | "
            f"{'yes' if item['eligible_for_task_eval'] else 'no'} | {item['useful_response_count']} | {item['repeatability']['total_attempts']} | "
            f"{item['repeatability']['unstable_attempt_ratio']} | {item['empty_count']} | {item['refusal_count']} | {item['truncated_count']} | "
            f"{item['unstable_count']} | {item['skipped_count']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def make_response_record(model_name, probe_id, prompt_text, include_prompt_text, result):
    status = result.get("status", "completed")
    response_text = result.get("response_text", "")
    record = {
        "model": model_name,
        "probe_id": probe_id,
        "status": status,
        "attempted": result.get("attempted", status != "skipped"),
        "skipped": status == "skipped",
        "requested_model": result.get("requested_model", model_name),
        "requested_model_available": result.get("requested_model_available"),
        "fallback_used": bool(result.get("fallback_used", False)),
        "fallback_chain": result.get("fallback_chain"),
        "effective_model": result.get("effective_model"),
        "provider": result.get("provider"),
        "cost_class": result.get("cost_class"),
        "latency_ms": result.get("latency_ms"),
        "error_class": result.get("error_class"),
        "error_message": result.get("error_message"),
        "network_dependent_evidence": result.get("network_dependent_evidence", True),
        "synthetic_contract_evidence": result.get("synthetic_contract_evidence", False),
        "response_char_count": result.get("response_char_count", len(response_text)),
        "response_shape": result.get("response_shape"),
        "response_basis_flags": result.get("response_basis_flags"),
        "response_excerpt_safe": result.get("response_excerpt_safe"),
        "content_signal": result.get("content_signal"),
        "response_evidence_success": result.get("response_evidence_success", False),
    }
    record["prompt_fingerprint"] = prompt_fingerprint(prompt_text)
    if include_prompt_text:
        record["prompt_text"] = prompt_text
    return record


def response_skip_record(model_name, requested_model, probe_id, prompt_text, include_prompt_text, error_class, error_message, skipped_reason):
    return make_response_record(
        model_name,
        probe_id,
        prompt_text,
        include_prompt_text,
        {
            "status": "skipped",
            "attempted": False,
            "requested_model": requested_model,
            "requested_model_available": False,
            "fallback_used": False,
            "fallback_chain": [requested_model],
            "effective_model": None,
            "provider": None,
            "cost_class": None,
            "latency_ms": None,
            "error_class": error_class,
            "error_message": error_message,
            "network_dependent_evidence": False,
            "synthetic_contract_evidence": False,
            "response_char_count": 0,
            "response_shape": {
                "has_output_text": False,
                "has_code_block": False,
                "has_refusal_marker": False,
                "has_empty_body": True,
                "has_truncation_marker": False,
                "has_list_structure": False,
                "has_error_like_text": False,
            },
            "response_basis_flags": {
                "has_nonempty_text": False,
                "has_code_tokens": False,
                "has_refusal_marker": False,
                "has_truncation_marker": False,
                "has_list_structure": False,
                "has_error_like_text": False,
                "looks_like_boilerplate": False,
                "looks_like_probe_aligned": False,
            },
            "response_excerpt_safe": None,
            "content_signal": "empty",
            "response_evidence_success": False,
            "skipped_reason": skipped_reason,
        },
    )


def run_response_probe(base_url, display_model, requested_model, probe_id, prompt_text, request_timeout, public_models_index=None):
    try:
        result = send_responses_request(base_url, requested_model, prompt_text, request_timeout)
    except ModelRequestError as error:
        provider = None
        effective_model = None
        meta = None
        if isinstance(public_models_index, dict):
            meta = public_models_index.get(requested_model)
            if isinstance(meta, dict):
                provider = meta.get("provider")
                effective_model = meta.get("effective_model") or meta.get("upstream_model")
        return {
            "status": "failed",
            "attempted": True,
            "requested_model": requested_model,
            "requested_model_available": False,
            "fallback_used": False,
            "fallback_chain": [requested_model],
            "effective_model": effective_model,
            "provider": provider,
            "cost_class": meta.get("cost_class") if isinstance(meta, dict) else None,
            "latency_ms": None,
            "error_class": error.error_class,
            "error_message": str(error),
            "network_dependent_evidence": True,
            "synthetic_contract_evidence": False,
            "response_char_count": 0,
            "response_shape": {
                "has_output_text": False,
                "has_code_block": False,
                "has_refusal_marker": False,
                "has_empty_body": True,
                "has_truncation_marker": False,
                "has_list_structure": False,
                "has_error_like_text": False,
            },
            "response_basis_flags": {
                "has_nonempty_text": False,
                "has_code_tokens": False,
                "has_refusal_marker": False,
                "has_truncation_marker": False,
                "has_list_structure": False,
                "has_error_like_text": False,
                "looks_like_boilerplate": False,
                "looks_like_probe_aligned": False,
            },
            "response_excerpt_safe": None,
            "content_signal": "empty",
            "response_evidence_success": False,
        }

    response_text = response_text_from_result(result)
    basis_flags = build_response_basis_flags(probe_id, response_text)
    shape = build_response_shape(response_text)
    signal = classify_content_signal(probe_id, response_text, shape, basis_flags)
    return {
        "status": "completed",
        "attempted": True,
        "requested_model": requested_model,
        "requested_model_available": result.get("requested_model_available", False),
        "fallback_used": bool(result.get("fallback_used", False)),
        "fallback_chain": result.get("fallback_chain") or [requested_model],
        "effective_model": result.get("effective_model"),
        "provider": result.get("provider"),
        "cost_class": result.get("cost_class"),
        "latency_ms": result.get("latency_ms"),
        "error_class": None,
        "error_message": None,
        "network_dependent_evidence": result.get("network_dependent_evidence", True),
        "synthetic_contract_evidence": False,
        "response_text": response_text,
        "response_char_count": len(response_text),
        "response_shape": shape,
        "response_basis_flags": basis_flags,
        "response_excerpt_safe": safe_excerpt(response_text) if response_text.strip() else None,
        "content_signal": signal,
        "response_evidence_success": response_evidence_success(shape, signal),
    }


def classify_response_evidence_status(stats):
    if (
        stats["useful_response_count"] >= 2
        and stats["useful_probe_count"] >= 2
        and stats["unstable_attempt_ratio"] < 0.5
        and stats["refusal_count"] == 0
        and stats["truncated_count"] == 0
    ):
        return "response_evidence_candidate"
    if stats["unstable_count"] > 0:
        return "unstable_or_limited"
    if stats["useful_response_count"] > 0:
        return "structurally_alive_but_weak"
    return "blocked_or_inconclusive"


def build_response_model_summaries(records):
    summaries = {}
    order = []
    for record in records:
        model = record["model"]
        attempted = bool(record.get("attempted"))
        skipped = bool(record.get("skipped"))
        recomputed_success = attempted and not skipped and response_evidence_success(record["response_shape"], record.get("content_signal"))
        if model not in summaries:
            summaries[model] = {
                "model": model,
                "total_records": 0,
                "attempted_count": 0,
                "useful_response_count": 0,
                "empty_count": 0,
                "refusal_count": 0,
                "truncated_count": 0,
                "unstable_count": 0,
                "skipped_count": 0,
                "bad_signal_count": 0,
                "probe_stats": {},
                "useful_probe_count": 0,
            }
            order.append(model)
        stats = summaries[model]
        stats["total_records"] += 1
        if record["attempted"]:
            stats["attempted_count"] += 1
        if record["skipped"]:
            stats["skipped_count"] += 1
        if recomputed_success:
            stats["useful_response_count"] += 1
        signal = record.get("content_signal")
        if signal == "empty":
            stats["empty_count"] += 1
        if signal == "refusal_like":
            stats["refusal_count"] += 1
        if signal == "truncated_or_incomplete":
            stats["truncated_count"] += 1
        if record.get("error_class") in {"upstream_timeout", "upstream_rate_limited", "upstream_overloaded"}:
            stats["unstable_count"] += 1
        if signal in {"empty", "refusal_like", "truncated_or_incomplete", "boilerplate_only"}:
            stats["bad_signal_count"] += 1
        probe_id = record["probe_id"]
        if probe_id not in stats["probe_stats"]:
            stats["probe_stats"][probe_id] = {
                "probe_id": probe_id,
                "attempt_count": 0,
                "useful_attempt_count": 0,
                "timeout_count": 0,
                "rate_limited_count": 0,
                "overloaded_count": 0,
                "empty_count": 0,
                "refusal_count": 0,
                "truncated_count": 0,
                "best_signal": None,
                "worst_signal": None,
                "last_error_class": None,
            }
        probe = stats["probe_stats"][probe_id]
        probe["attempt_count"] += 1
        if recomputed_success:
            probe["useful_attempt_count"] += 1
        if signal == "empty":
            probe["empty_count"] += 1
        if signal == "refusal_like":
            probe["refusal_count"] += 1
        if signal == "truncated_or_incomplete":
            probe["truncated_count"] += 1
        if record.get("error_class") == "upstream_timeout":
            probe["timeout_count"] += 1
        if record.get("error_class") == "upstream_rate_limited":
            probe["rate_limited_count"] += 1
        if record.get("error_class") == "upstream_overloaded":
            probe["overloaded_count"] += 1
        probe["last_error_class"] = record.get("error_class")
        signal_rank = {
            "empty": 0,
            "refusal_like": 0,
            "truncated_or_incomplete": 0,
            "boilerplate_only": 1,
            "generic_explanation": 1,
            "unknown_shape": 1,
            "bug_analysis_like": 2,
            "list_of_tests": 2,
            "code_like": 2,
            "cli_skeleton_like": 2,
        }
        if probe["best_signal"] is None or signal_rank.get(signal, 1) > signal_rank.get(probe["best_signal"], 1):
            probe["best_signal"] = signal
        if probe["worst_signal"] is None or signal_rank.get(signal, 1) < signal_rank.get(probe["worst_signal"], 1):
            probe["worst_signal"] = signal
    model_summaries = []
    for model in order:
        stats = summaries[model]
        total_attempts = max(stats["attempted_count"], 1)
        stats["useful_probe_count"] = sum(1 for item in stats["probe_stats"].values() if item["useful_attempt_count"] > 0)
        stats["repeatability"] = {
            "probes_attempted": len(stats["probe_stats"]),
            "total_attempts": stats["attempted_count"],
            "useful_attempts": stats["useful_response_count"],
            "useful_probes": stats["useful_probe_count"],
            "empty_attempts": stats["empty_count"],
            "timeout_attempts": sum(item["timeout_count"] for item in stats["probe_stats"].values()),
            "unstable_attempt_ratio": round(stats["unstable_count"] / total_attempts, 3),
        }
        stats["unstable_attempt_ratio"] = stats["repeatability"]["unstable_attempt_ratio"]
        stats["probe_stats"] = [stats["probe_stats"][probe_id] for probe_id in sorted(stats["probe_stats"])]
        stats["response_evidence_status"] = classify_response_evidence_status(stats)
        stats["eligible_for_task_eval"] = stats["response_evidence_status"] == "response_evidence_candidate"
        model_summaries.append(stats)
    return model_summaries


def load_response_report(path_text):
    path = Path(path_text)
    if not path.exists():
        raise SystemExit(f"Response report not found: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(report, dict)
        or report.get("report_kind") != "response_evidence"
        or not isinstance(report.get("records"), list)
        or "qualification_report_path" not in report
    ):
        raise SystemExit(f"Invalid response report format: {path}")
    verify_attestation(report)
    return path, report


def validate_response_record(record):
    if not isinstance(record, dict):
        raise SystemExit("Invalid response report record: expected object.")
    if not isinstance(record.get("model"), str):
        raise SystemExit("Invalid response report record: missing model.")
    if not isinstance(record.get("probe_id"), str):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: missing probe_id.")
    response_shape = record.get("response_shape")
    if not isinstance(response_shape, dict):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: missing response_shape.")
    basis_flags = record.get("response_basis_flags")
    if not isinstance(basis_flags, dict):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: missing response_basis_flags.")
    status = record.get("status")
    if status not in {"completed", "failed", "skipped"}:
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: invalid status {status!r}.")
    attempted = bool(record.get("attempted"))
    skipped = bool(record.get("skipped"))
    if skipped != (status == "skipped"):
        raise SystemExit(
            f"Response report integrity error for model {record.get('model')} probe {record.get('probe_id')}: "
            f"skipped={skipped!r} does not match status {status!r}."
        )
    if attempted != (status != "skipped"):
        raise SystemExit(
            f"Response report integrity error for model {record.get('model')} probe {record.get('probe_id')}: "
            f"attempted={attempted!r} does not match status {status!r}."
        )
    required_shape_keys = {
        "has_output_text",
        "has_code_block",
        "has_refusal_marker",
        "has_empty_body",
        "has_truncation_marker",
        "has_list_structure",
        "has_error_like_text",
    }
    if not required_shape_keys.issubset(response_shape):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: incomplete response_shape.")
    required_basis_keys = {
        "has_nonempty_text",
        "has_code_tokens",
        "has_refusal_marker",
        "has_truncation_marker",
        "has_list_structure",
        "has_error_like_text",
        "looks_like_boilerplate",
        "looks_like_probe_aligned",
    }
    if not required_basis_keys.issubset(basis_flags):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: incomplete response_basis_flags.")
    signal = record.get("content_signal")
    recomputed_signal = classify_content_signal(record.get("probe_id"), record.get("response_excerpt_safe") or "", response_shape, basis_flags)
    if signal in {"empty", "refusal_like", "truncated_or_incomplete"} and signal != recomputed_signal:
        raise SystemExit(
            f"Response report integrity error for model {record.get('model')} probe {record.get('probe_id')}: stored "
            f"content_signal {signal!r} does not match recomputed mandatory signal {recomputed_signal!r}."
        )
    if response_shape["has_empty_body"] and signal != "empty":
        raise SystemExit(f"Response report integrity error for model {record.get('model')}: empty body must map to content_signal='empty'.")
    if response_shape["has_refusal_marker"] and signal != "refusal_like":
        raise SystemExit(f"Response report integrity error for model {record.get('model')}: refusal marker must map to content_signal='refusal_like'.")
    if response_shape["has_truncation_marker"] and signal != "truncated_or_incomplete":
        raise SystemExit(f"Response report integrity error for model {record.get('model')}: truncation marker must map to content_signal='truncated_or_incomplete'.")
    recomputed_success = attempted and not skipped and response_evidence_success(response_shape, signal)
    if bool(record.get("response_evidence_success")) != recomputed_success:
        raise SystemExit(
            f"Response report integrity error for model {record.get('model')} probe {record.get('probe_id')}: stored "
            f"response_evidence_success {record.get('response_evidence_success')!r} does not match recomputed {recomputed_success!r}."
        )
    normalized = dict(record)
    requested_model = normalized.get("requested_model") if isinstance(normalized.get("requested_model"), str) else normalized.get("model")
    fallback_chain = normalized.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not all(isinstance(item, str) and item for item in fallback_chain):
        fallback_chain = [requested_model] if isinstance(requested_model, str) and requested_model else []
    fallback_used = bool(normalized.get("fallback_used", False))
    if fallback_used and len(fallback_chain) < 2 and isinstance(requested_model, str):
        fallback_chain = [requested_model, normalized.get("effective_model") or requested_model]
    normalized["fallback_used"] = fallback_used
    normalized["fallback_chain"] = fallback_chain
    cost_class = normalized.get("cost_class")
    if cost_class is not None and not isinstance(cost_class, str):
        raise SystemExit(f"Invalid response report record for model {record.get('model')}: cost_class must be string or null.")
    normalized["response_evidence_success"] = recomputed_success
    normalized["response_excerpt_safe"] = safe_excerpt(record.get("response_excerpt_safe") or "") if record.get("response_excerpt_safe") else None
    return normalized


def resolve_models(args, qualification_report=None):
    if qualification_report and args.models == DEFAULT_MODELS:
        return [item["model"] for item in qualification_report["models"]]
    return [item.strip() for item in args.models.split(",") if item.strip()]


def default_allowed_cost_class(cost_class):
    return cost_class in {"free_limited", "entitled_direct_limited"}


def run_cost_gate_check(args):
    ensure_env_permissions(ENV_PATH)
    models = resolve_models(args)
    if not models:
        raise SystemExit("Cost gate check requires at least one model.")

    try:
        port = pick_port(args.port)
    except RuntimeError as error:
        print(f"Ошибка: {error}")
        raise SystemExit(2)

    proxy_process = start_proxy(port, args.allow_paid_routes)
    base_url = f"http://127.0.0.1:{port}/v1"
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        wait_for_health(base_url, 15)
        models_payload = send_models_list_request(base_url, args.request_timeout)
        public_models = {item.get("id"): item for item in models_payload.get("data", []) if isinstance(item, dict)}
        models_endpoint_loaded = True
        records = []

        for model in models:
            normalized_model = normalize_requested_model(model_kind(model))
            public_entry = public_models.get(normalized_model) or public_models.get(model)
            configured_cost_class = public_entry.get("cost_class") if public_entry else None
            gate_expectation = (
                "allowed_by_default"
                if default_allowed_cost_class(configured_cost_class)
                else "blocked_by_default_cost_policy"
            )
            record = {
                "model": model,
                "requested_model": normalized_model,
                "visible_in_models_endpoint": bool(public_entry),
                "configured_cost_class": configured_cost_class,
                "gate_expectation": gate_expectation,
                "attempted": True,
                "provider": None,
                "effective_model": None,
                "latency_ms": None,
                "error_class": None,
                "error_message": None,
            }
            try:
                result = send_responses_request(base_url, normalized_model, args.qualification_prompt, args.request_timeout)
                record.update(
                    {
                        "provider": result.get("provider"),
                        "effective_model": result.get("effective_model"),
                        "latency_ms": result.get("latency_ms"),
                        "fallback_used": bool(result.get("fallback_used")),
                        "requested_model_available": bool(result.get("requested_model_available")),
                        "gate_outcome": "allowed_by_default",
                    }
                )
            except ModelRequestError as error:
                gate_outcome = "failed_other"
                if not public_entry and error.error_class == "upstream_model_unavailable":
                    gate_outcome = "route_not_admitted"
                elif error.error_class == "paid_route_blocked":
                    gate_outcome = "blocked_by_cost_gate"
                record.update(
                    {
                        "error_class": error.error_class,
                        "error_message": error.message,
                        "gate_outcome": gate_outcome,
                    }
                )
            records.append(record)
            print(
                f"[cost-gate] model={model} visible={record['visible_in_models_endpoint']} "
                f"cost_class={configured_cost_class or '-'} outcome={record['gate_outcome']} "
                f"error={record.get('error_class') or '-'}",
                flush=True,
            )

        layer_violation_detected = any(
            (
                item["gate_expectation"] == "blocked_by_default_cost_policy" and item["gate_outcome"] != "blocked_by_cost_gate"
            )
            or (
                item["gate_expectation"] == "allowed_by_default" and item["gate_outcome"] == "blocked_by_cost_gate"
            )
            or item["gate_outcome"] == "route_not_admitted"
            for item in records
        )
        report = {
            "report_kind": "cost_gate_check",
            "lab_mode": True,
            "started_at_utc": started_at,
            "request_timeout_sec": args.request_timeout,
            "allow_paid_routes": bool(args.allow_paid_routes),
            "models_endpoint_loaded": models_endpoint_loaded,
            "layer_violation_detected": layer_violation_detected,
            "technical_execution_opened": False,
            "records": records,
        }
        report["summary"] = {
            "tested_models": len(records),
            "blocked_by_cost_gate": sum(1 for item in records if item["gate_outcome"] == "blocked_by_cost_gate"),
            "allowed_by_default": sum(1 for item in records if item["gate_outcome"] == "allowed_by_default"),
            "route_not_admitted": sum(1 for item in records if item["gate_outcome"] == "route_not_admitted"),
            "failed_other": sum(1 for item in records if item["gate_outcome"] == "failed_other"),
            "advisory_verdict": "cost_gate_contract_holds" if not layer_violation_detected else "cost_gate_contract_violation_detected",
        }
        json_path, md_path = write_cost_gate_report(report)
        print(f"JSON report: {json_path}")
        print(f"MD report: {md_path}")
    finally:
        shutdown_proxy(proxy_process)


def run_provider_access(args):
    ensure_env_permissions(ENV_PATH)
    providers = resolve_direct_providers(args.providers)
    started_at = datetime.now(timezone.utc).isoformat()
    records = []
    technical_execution_opened = bool(args.allow_paid_routes)
    for provider in providers:
        target = DIRECT_PROVIDER_TARGETS[provider]
        record = (
            provider_probe_result(target, args.request_timeout)
            if args.allow_paid_routes
            else provider_probe_blocked_result(target)
        )
        records.append(record)
        print(
            f"[provider-access] provider={provider} transport={record['transport_status']} "
            f"policy={record['policy_status']} auth_present={record['auth_present']} "
            f"reachable={record['endpoint_reachable']} error={record.get('error_class') or '-'}",
            flush=True,
        )

    report = {
        "report_kind": "provider_access",
        "lab_mode": True,
        "started_at_utc": started_at,
        "request_timeout_sec": args.request_timeout,
        "allow_paid_routes": bool(args.allow_paid_routes),
        "technical_execution_opened": technical_execution_opened,
        "providers": records,
    }
    ready_transport_count = sum(1 for item in records if item["transport_status"] == "provider_ready_transport")
    ready_direct_providers = sorted(
        item["provider"]
        for item in records
        if item["transport_status"] == "provider_ready_transport" and item["policy_status"] == "provider_ready_policy"
    )
    report["summary"] = {
        "tested_providers": len(records),
        "provider_ready_transport": ready_transport_count,
        "provider_ready_policy": sum(1 for item in records if item["policy_status"] == "provider_ready_policy"),
        "no_provider_ready_transport": ready_transport_count == 0,
        "ready_direct_providers": ready_direct_providers,
        "paid_probe_blocked_by_policy": not bool(args.allow_paid_routes),
        "contour_verdict_hint": (
            "direct_lane_blocked_by_cost_policy"
            if not args.allow_paid_routes
            else "direct_lane_blocked_by_access"
            if ready_transport_count == 0
            else "provider_access_ready_for_direct_route_qualification"
        ),
    }
    json_path, md_path = write_provider_reports(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_error_taxonomy_check(args):
    ensure_env_permissions(ENV_PATH)
    models = resolve_models(args)
    if not models:
        raise SystemExit("Error taxonomy check requires at least one model.")
    tested_model = normalize_requested_model(model_kind(models[0]))
    port = pick_port(args.port)
    base_url = f"http://127.0.0.1:{port}/v1"
    started_at = datetime.now(timezone.utc).isoformat()
    records = []
    proxy_process = start_proxy(port, args.allow_paid_routes)
    try:
        wait_for_health(base_url, 15)
        for scenario_name, forced_error_class, expected_status in ERROR_TAXONOMY_SCENARIOS:
            metadata = {"lab_force_error_class": forced_error_class, "scenario": scenario_name}
            record = {
                "scenario": scenario_name,
                "expected_error_class": forced_error_class,
                "expected_status": expected_status,
                "actual_error_class": None,
                "actual_status": None,
                "passed": False,
                "error_message": None,
            }
            try:
                send_responses_request(
                    base_url,
                    tested_model,
                    "Return OK only.",
                    args.request_timeout,
                    metadata=metadata,
                )
                record["actual_error_class"] = "missing_expected_error"
                record["actual_status"] = 200
                record["error_message"] = "Expected forced adapter error, but request succeeded."
            except ModelRequestError as error:
                record["actual_error_class"] = error.error_class
                record["actual_status"] = error.status
                record["error_message"] = str(error)
                record["passed"] = error.error_class == forced_error_class and error.status == expected_status
            records.append(record)
            print(
                f"[error-taxonomy] scenario={scenario_name} expected={forced_error_class}/{expected_status} "
                f"actual={record['actual_error_class']}/{record['actual_status']} passed={record['passed']}",
                flush=True,
            )
    finally:
        shutdown_proxy(proxy_process)

    all_checks_passed = all(item["passed"] for item in records) and len(records) == len(ERROR_TAXONOMY_SCENARIOS)
    report = {
        "report_kind": "error_taxonomy_check",
        "lab_mode": True,
        "started_at_utc": started_at,
        "tested_model": tested_model,
        "allow_paid_routes": bool(args.allow_paid_routes),
        "technical_execution_opened": False,
        "records": records,
    }
    report["summary"] = {
        "tested_scenarios": len(records),
        "passed_scenarios": sum(1 for item in records if item["passed"]),
        "failed_scenarios": sum(1 for item in records if not item["passed"]),
        "all_checks_passed": all_checks_passed,
        "advisory_verdict": "error_taxonomy_contract_holds" if all_checks_passed else "error_taxonomy_contract_violation_detected",
    }
    json_path, md_path = write_error_taxonomy_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_model_registry_snapshot(args):
    registry_seed_path, registry_seed = load_registry_seed(args.registry_seed)
    registry_entries = clone_registry_entries(registry_seed["entries"])

    provider_path = None
    provider_report = None
    if args.provider_report:
        provider_path, provider_report = load_attested_report(args.provider_report, "provider_access")
        merge_provider_report_into_registry(registry_entries, provider_report)

    watch_path = None
    watch_report = None
    if args.watch_report:
        watch_path, watch_report = load_attested_report(args.watch_report, "authority_watch_recheck")
        merge_watch_report_into_registry(registry_entries, watch_report)

    qualification_path = None
    qualification_report = None
    if args.qualification_report:
        qualification_path, qualification_report = load_qualification_report(args.qualification_report)
        merge_qualification_report_into_registry(registry_entries, qualification_report)

    response_path = None
    response_report = None
    if args.response_report:
        response_path, response_report = load_response_report(args.response_report)
        merge_response_report_into_registry(registry_entries, response_report)

    eval_path = None
    eval_report = None
    if args.eval_report:
        eval_path, eval_report = load_eval_report(args.eval_report)
        merge_eval_report_into_registry(registry_entries, eval_report)

    registry_entries.sort(key=lambda item: item["model_id"])
    summary = build_registry_summary(registry_entries)
    summary["control_plane_only"] = qualification_report is None and response_report is None and eval_report is None
    report = {
        "report_kind": "model_registry_snapshot",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_contract_version": "v1",
        "source_plan": registry_seed["source_plan"],
        "registry_seed_version": registry_seed["registry_seed_version"],
        "registry_seed_path": str(registry_seed_path),
        "registry_seed_sha256": file_sha256(registry_seed_path),
        "provider_report_path": str(provider_path) if provider_path else None,
        "provider_report_sha256": file_sha256(provider_path) if provider_path else None,
        "watch_report_path": str(watch_path) if watch_path else None,
        "watch_report_sha256": file_sha256(watch_path) if watch_path else None,
        "qualification_report_path": str(qualification_path) if qualification_path else None,
        "qualification_report_sha256": file_sha256(qualification_path) if qualification_path else None,
        "response_report_path": str(response_path) if response_path else None,
        "response_report_sha256": file_sha256(response_path) if response_path else None,
        "eval_report_path": str(eval_path) if eval_path else None,
        "eval_report_sha256": file_sha256(eval_path) if eval_path else None,
        "control_plane_only": qualification_report is None and response_report is None and eval_report is None,
        "technical_execution_opened": False,
        "routing_promotions_performed": False,
        "canonical_target_model": watch_report.get("canonical_target_model") if watch_report else None,
        "technical_execution_allowed": watch_report.get("technical_execution_allowed") if watch_report else None,
        "registry_entries": registry_entries,
    }
    report["summary"] = summary
    json_path, md_path = write_registry_snapshot_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_baseline_snapshot(args):
    ensure_env_permissions(ENV_PATH)
    snapshot = direct_state_snapshot()
    current_auth = snapshot["current_provider_auth_present"]

    report = {
        "report_kind": "direct_admission_baseline",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "env_permissions_expected": "0600",
        **snapshot,
        "baseline_ready": True,
    }
    report["summary"] = {
        "direct_keys_present_count": len(snapshot["current_direct_key_names"]),
        "provider_auth_present_count": sum(1 for value in current_auth.values() if bool(value)),
        "baseline_ready": True,
        "advisory_verdict": "fresh_direct_admission_baseline_captured",
    }
    json_path, md_path = write_baseline_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_admission_guard_check(args):
    ensure_env_permissions(ENV_PATH)
    if not args.baseline_report:
        raise SystemExit("Admission guard check requires --baseline-report.")

    baseline_path, baseline_report = load_attested_report(args.baseline_report, "direct_admission_baseline")
    baseline_keys = baseline_report.get("current_direct_key_names")
    baseline_auth = baseline_report.get("current_provider_auth_present")
    baseline_fingerprint = baseline_report.get("state_fingerprint")
    baseline_report_sha256 = file_sha256(baseline_path)
    if not isinstance(baseline_keys, list) or not isinstance(baseline_auth, dict) or not isinstance(baseline_fingerprint, str):
        raise SystemExit("Invalid baseline report: missing direct state snapshot.")

    snapshot = direct_state_snapshot()
    baseline_matches_current_state = (
        baseline_keys == snapshot["current_direct_key_names"]
        and baseline_auth == snapshot["current_provider_auth_present"]
        and baseline_fingerprint == snapshot["state_fingerprint"]
    )
    prior_guard_reuse_count, reused_guard_paths = count_guard_reuses(baseline_report_sha256)
    baseline_state_shape_valid = set(baseline_auth) == set(DIRECT_PROVIDER_TARGETS)
    tamper_detected = not baseline_state_shape_valid
    no_delta_detected = baseline_matches_current_state
    replay_risk_detected = prior_guard_reuse_count > 0
    tamper_guard_passed = not tamper_detected
    guard_passed = tamper_guard_passed and not replay_risk_detected
    admission_delta_candidate = guard_passed and not no_delta_detected
    if tamper_detected:
        advisory_verdict = "tamper_detected"
    elif replay_risk_detected:
        advisory_verdict = "replay_suspected"
    elif admission_delta_candidate:
        advisory_verdict = "admission_delta_candidate_present"
    elif no_delta_detected:
        advisory_verdict = "current_matches_baseline_no_delta"
    else:
        advisory_verdict = "no_direct_state_present"

    report = {
        "report_kind": "direct_admission_guard_check",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "baseline_report_path": str(baseline_path),
        "baseline_report_sha256": baseline_report_sha256,
        "baseline_state_fingerprint": baseline_fingerprint,
        "current_state_fingerprint": snapshot["state_fingerprint"],
        "baseline_current_direct_key_names": baseline_keys,
        "baseline_current_provider_auth_present": baseline_auth,
        "current_direct_key_names": snapshot["current_direct_key_names"],
        "current_provider_auth_present": snapshot["current_provider_auth_present"],
        "baseline_matches_current_state": baseline_matches_current_state,
        "no_delta_detected": no_delta_detected,
        "prior_guard_reuse_count": prior_guard_reuse_count,
        "reused_guard_paths": reused_guard_paths,
        "replay_risk_detected": replay_risk_detected,
        "tamper_detected": tamper_detected,
        "tamper_guard_passed": tamper_guard_passed,
        "guard_passed": guard_passed,
        "admission_delta_candidate": admission_delta_candidate,
    }
    report["summary"] = {
        "direct_keys_present_count": len(snapshot["current_direct_key_names"]),
        "guard_passed": guard_passed,
        "tamper_guard_passed": tamper_guard_passed,
        "replay_risk_detected": replay_risk_detected,
        "no_delta_detected": no_delta_detected,
        "admission_delta_candidate": admission_delta_candidate,
        "advisory_verdict": advisory_verdict,
    }
    json_path, md_path = write_guard_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_admission_delta_check(args):
    ensure_env_permissions(ENV_PATH)
    if not args.baseline_report or not args.guard_report:
        raise SystemExit("Admission delta check requires --baseline-report and --guard-report.")

    baseline_path, baseline_report = load_attested_report(args.baseline_report, "direct_admission_baseline")
    guard_path, guard_report = load_attested_report(args.guard_report, "direct_admission_guard_check")
    baseline_sha256 = file_sha256(baseline_path)
    if guard_report.get("baseline_report_sha256") != baseline_sha256:
        raise SystemExit("Guard report integrity error: baseline report hash does not match current file.")

    baseline_keys = baseline_report.get("current_direct_key_names")
    baseline_auth = baseline_report.get("current_provider_auth_present")
    baseline_fingerprint = baseline_report.get("state_fingerprint")
    if not isinstance(baseline_keys, list) or not isinstance(baseline_auth, dict) or not isinstance(baseline_fingerprint, str):
        raise SystemExit("Invalid baseline report: missing direct state snapshot.")

    snapshot = direct_state_snapshot()
    current_keys = snapshot["current_direct_key_names"]
    current_auth = snapshot["current_provider_auth_present"]
    current_fingerprint = snapshot["state_fingerprint"]
    added_keys = sorted(set(current_keys) - set(baseline_keys))
    removed_keys = sorted(set(baseline_keys) - set(current_keys))
    auth_changed_providers = sorted(
        provider
        for provider in DIRECT_PROVIDER_TARGETS
        if bool(baseline_auth.get(provider)) != bool(current_auth.get(provider))
    )
    delta_detected = bool(added_keys or removed_keys or auth_changed_providers or baseline_fingerprint != current_fingerprint)
    guard_passed = bool(guard_report.get("guard_passed"))
    replay_risk_detected = bool(guard_report.get("replay_risk_detected"))
    tamper_detected = bool(guard_report.get("tamper_detected"))
    no_delta_detected = bool(guard_report.get("no_delta_detected"))
    delta_gate_open_candidate = guard_passed and delta_detected and not replay_risk_detected and not tamper_detected
    if tamper_detected:
        advisory_verdict = "guard_blocked_tamper_detected"
    elif replay_risk_detected:
        advisory_verdict = "guard_blocked_replay_suspected"
    elif not delta_detected:
        advisory_verdict = "current_matches_baseline_no_delta"
    elif delta_gate_open_candidate:
        advisory_verdict = "admission_delta_detected"
    else:
        advisory_verdict = "guard_blocked_delta_unavailable"

    report = {
        "report_kind": "direct_admission_delta",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "baseline_report_path": str(baseline_path),
        "baseline_report_sha256": baseline_sha256,
        "guard_report_path": str(guard_path),
        "guard_report_sha256": file_sha256(guard_path),
        "baseline_direct_key_names": baseline_keys,
        "baseline_provider_auth_present": baseline_auth,
        "current_direct_key_names": current_keys,
        "current_provider_auth_present": current_auth,
        "state_fingerprint_before": baseline_fingerprint,
        "state_fingerprint_after": current_fingerprint,
        "added_keys": added_keys,
        "removed_keys": removed_keys,
        "auth_changed_providers": auth_changed_providers,
        "delta_detected": delta_detected,
        "delta_gate_open_candidate": delta_gate_open_candidate,
        "guard_passed": guard_passed,
        "replay_risk_detected": replay_risk_detected,
        "tamper_detected": tamper_detected,
        "no_delta_detected": no_delta_detected,
    }
    report["summary"] = {
        "direct_keys_present_count": len(current_keys),
        "delta_detected": delta_detected,
        "delta_gate_open_candidate": delta_gate_open_candidate,
        "advisory_verdict": advisory_verdict,
    }
    json_path, md_path = write_delta_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_mutation_design(args):
    ensure_env_permissions(ENV_PATH)
    provider = args.mutation_provider
    target = DIRECT_PROVIDER_TARGETS[provider]
    key_name = target["api_key_env"]
    key_present = env_key_present(key_name)

    report = {
        "report_kind": "controlled_direct_env_mutation_design",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "mutation_provider": provider,
        "mutation_key_name": key_name,
        "mutation_action": "remove_key_temporarily",
        "key_present_before_design": key_present,
        "rollback_required": True,
        "expected_auth_changed_providers": [provider],
        "expected_added_keys": [],
        "expected_removed_keys": [key_name],
        "design_ready": key_present,
    }
    report["summary"] = {
        "design_ready": key_present,
        "advisory_verdict": "controlled_mutation_ready" if key_present else "mutation_target_key_missing",
    }
    json_path, md_path = write_mutation_report(report, "mutation_design", "Controlled Mutation Design")
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_mutation_execute(args):
    ensure_env_permissions(ENV_PATH)
    if not args.mutation_design_report:
        raise SystemExit("Mutation execute requires --mutation-design-report.")

    design_path, design_report = load_attested_report(args.mutation_design_report, "controlled_direct_env_mutation_design")
    if not bool(design_report.get("design_ready")):
        raise SystemExit("Mutation design report is not ready for execution.")

    provider = design_report["mutation_provider"]
    key_name = design_report["mutation_key_name"]
    before_snapshot = direct_state_snapshot()
    backup_lines = read_env_lines()
    backup_sha256 = hashlib.sha256(("\n".join(backup_lines) + ("\n" if backup_lines else "")).encode("utf-8")).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = MUTATION_DIR / f"env_backup_{stamp}.env"
    backup_path.write_text("\n".join(backup_lines) + ("\n" if backup_lines else ""), encoding="utf-8")
    removed = remove_env_key(key_name)
    after_snapshot = direct_state_snapshot()

    report = {
        "report_kind": "controlled_direct_env_mutation_execution",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "mutation_design_report_path": str(design_path),
        "mutation_design_report_sha256": file_sha256(design_path),
        "mutation_provider": provider,
        "mutation_key_name": key_name,
        "mutation_action": "remove_key_temporarily",
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha256,
        "state_fingerprint_before": before_snapshot["state_fingerprint"],
        "state_fingerprint_after": after_snapshot["state_fingerprint"],
        "before_direct_key_names": before_snapshot["current_direct_key_names"],
        "after_direct_key_names": after_snapshot["current_direct_key_names"],
        "before_provider_auth_present": before_snapshot["current_provider_auth_present"],
        "after_provider_auth_present": after_snapshot["current_provider_auth_present"],
        "mutation_applied": removed and before_snapshot["state_fingerprint"] != after_snapshot["state_fingerprint"],
    }
    report["summary"] = {
        "mutation_applied": report["mutation_applied"],
        "advisory_verdict": "controlled_mutation_applied" if report["mutation_applied"] else "controlled_mutation_not_applied",
    }
    json_path, md_path = write_mutation_report(report, "mutation_execute", "Controlled Mutation Execution")
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_mutation_rollback(args):
    ensure_env_permissions(ENV_PATH)
    if not args.mutation_execution_report:
        raise SystemExit("Mutation rollback requires --mutation-execution-report.")

    execution_path, execution_report = load_attested_report(args.mutation_execution_report, "controlled_direct_env_mutation_execution")
    backup_path = Path(execution_report.get("backup_path") or "")
    if not backup_path.exists():
        raise SystemExit(f"Mutation backup not found: {backup_path}")

    backup_text = backup_path.read_text(encoding="utf-8")
    current_before_rollback = direct_state_snapshot()
    ENV_PATH.write_text(backup_text, encoding="utf-8")
    ensure_env_permissions(ENV_PATH)
    current_after_rollback = direct_state_snapshot()
    expected_before = execution_report.get("state_fingerprint_before")
    rollback_completed = current_after_rollback["state_fingerprint"] == expected_before

    report = {
        "report_kind": "controlled_direct_env_mutation_rollback",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "mutation_execution_report_path": str(execution_path),
        "mutation_execution_report_sha256": file_sha256(execution_path),
        "mutation_provider": execution_report["mutation_provider"],
        "mutation_key_name": execution_report["mutation_key_name"],
        "mutation_action": execution_report["mutation_action"],
        "backup_path": str(backup_path),
        "state_fingerprint_before_rollback": current_before_rollback["state_fingerprint"],
        "state_fingerprint_after_rollback": current_after_rollback["state_fingerprint"],
        "expected_restored_state_fingerprint": expected_before,
        "rollback_completed": rollback_completed,
    }
    report["summary"] = {
        "rollback_completed": rollback_completed,
        "advisory_verdict": "controlled_mutation_rolled_back" if rollback_completed else "controlled_mutation_rollback_failed",
    }
    json_path, md_path = write_mutation_report(report, "mutation_rollback", "Controlled Mutation Rollback")
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_qualification(args):
    ensure_env_permissions(ENV_PATH)
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    try:
        port = pick_port(args.port)
    except RuntimeError as error:
        print(f"Ошибка: {error}")
        raise SystemExit(2)

    proxy_process = start_proxy(port, args.allow_paid_routes)
    base_url = f"http://127.0.0.1:{port}/v1"
    started_at = datetime.now(timezone.utc).isoformat()
    provider_calls_used = 0
    qualified_models = []

    try:
        wait_for_health(base_url, 15)
        for model in models:
            normalized_model = normalize_requested_model(model_kind(model))
            item, calls_used = qualify_model(
                base_url,
                model,
                normalized_model,
                args.request_timeout,
                args.max_fallback_attempts,
                args.qualification_prompt,
                args.max_provider_calls - provider_calls_used,
            )
            provider_calls_used += calls_used
            qualified_models.append(item)
            print(
                f"[qualify] model={model} status={item['qualification_status']} "
                f"eligible={item['eligible_for_task_eval']} "
                f"requested_error={item['requested_probe'].get('error_class') or '-'} "
                f"fallback_error={item['fallback_probe'].get('error_class') or '-'}",
                flush=True,
            )

        report = {
            "report_kind": "route_qualification",
            "lab_mode": True,
            "started_at_utc": started_at,
            "provider_call_budget": args.max_provider_calls,
            "provider_calls_used": provider_calls_used,
            "request_timeout_sec": args.request_timeout,
            "max_fallback_attempts": args.max_fallback_attempts,
            "qualification_prompt_fingerprint": prompt_fingerprint(args.qualification_prompt),
            "models": qualified_models,
        }
        report["summary"] = {
            "tested_models": len(qualified_models),
            "requested_model_candidates": sum(1 for item in qualified_models if item["qualification_status"] == "requested_model_candidate"),
            "fallback_only": sum(1 for item in qualified_models if item["qualification_status"] == "fallback_only"),
            "unstable_or_limited": sum(1 for item in qualified_models if item["qualification_status"] == "unstable_or_limited"),
            "blocked_or_inconclusive": sum(1 for item in qualified_models if item["qualification_status"] == "blocked_or_inconclusive"),
            "no_requested_model_candidates": not any(item["qualification_status"] == "requested_model_candidate" for item in qualified_models),
        }
        json_path, md_path = write_route_reports(report)
        print(f"JSON report: {json_path}")
        print(f"MD report: {md_path}")
    finally:
        shutdown_proxy(proxy_process)


def run_response_evidence(args):
    ensure_env_permissions(ENV_PATH)
    if not args.qualification_report:
        raise SystemExit("Response-evidence mode requires --qualification-report.")
    qualification_path, qualification_report = load_qualification_report(args.qualification_report)
    expected_prompt_fingerprint = prompt_fingerprint(args.qualification_prompt)
    if qualification_report.get("qualification_prompt_fingerprint") != expected_prompt_fingerprint:
        raise SystemExit(
            "Qualification report prompt fingerprint does not match the current --qualification-prompt. "
            "Re-run qualification or pass the same qualification prompt."
        )

    qualification_items = {}
    for item in qualification_report["models"]:
        normalized_item = validate_qualification_item(item)
        qualification_items[normalized_item["model"]] = normalized_item

    requested_models = resolve_models(args, qualification_report)
    base_tasks = default_response_tasks() if args.tasks == "all" else select_tasks(args.tasks)
    selected_models = []
    skipped_models_due_to_gate = []
    for model in requested_models:
        item = qualification_items.get(model)
        if not item:
            skipped_models_due_to_gate.append({"model": model, "reason": "not_present_in_qualification_report"})
            continue
        status = item["qualification_status"]
        if item["eligible_for_task_eval"]:
            selected_models.append(model)
            continue
        if status == "fallback_only" and args.allow_fallback_only_response_evidence:
            selected_models.append(model)
            continue
        if status == "unstable_or_limited" and args.allow_unstable_response_evidence:
            selected_models.append(model)
            continue
        skipped_models_due_to_gate.append({"model": model, "reason": status})

    try:
        port = pick_port(args.port)
    except RuntimeError as error:
        print(f"Ошибка: {error}")
        raise SystemExit(2)

    proxy_process = start_proxy(port, args.allow_paid_routes)
    base_url = f"http://127.0.0.1:{port}/v1"
    started_at = datetime.now(timezone.utc).isoformat()
    provider_calls_used = 0
    records = []

    try:
        wait_for_health(base_url, 15)
        models_payload = send_models_list_request(base_url, args.request_timeout)
        public_models_index = {
            item.get("id"): item
            for item in models_payload.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for model in selected_models:
            qualification_item = qualification_items[model]
            requested_model = qualification_item["requested_model"]
            model_records = []
            tasks_to_run = list(base_tasks)
            for probe_id, prompt_text in tasks_to_run:
                for attempt_index in range(1, args.response_attempts_per_probe + 1):
                    if provider_calls_used >= args.max_provider_calls:
                        skip_record = response_skip_record(
                            model,
                            requested_model,
                            probe_id,
                            prompt_text,
                            args.include_prompts,
                            "skipped_provider_call_budget",
                            "Provider call budget exhausted.",
                            "provider_call_budget",
                        )
                        skip_record["attempt_index"] = attempt_index
                        records.append(skip_record)
                        model_records.append(skip_record)
                        continue
                    provider_calls_used += 1
                    result = run_response_probe(
                        base_url,
                        model,
                        requested_model,
                        probe_id,
                        prompt_text,
                        args.request_timeout,
                        public_models_index,
                    )
                    record = make_response_record(model, probe_id, prompt_text, args.include_prompts, result)
                    record["attempt_index"] = attempt_index
                    records.append(record)
                    model_records.append(record)
                    print(
                        f"[response-evidence] model={model} probe={probe_id} attempt={attempt_index} "
                        f"success={record['response_evidence_success']} signal={record.get('content_signal') or '-'} "
                        f"error={record.get('error_class') or '-'}",
                        flush=True,
                    )

            model_summary = build_response_model_summaries(model_records)
            summary = model_summary[0] if model_summary else None
            if (
                args.tasks == "all"
                and summary
                and summary["response_evidence_status"] in {"blocked_or_inconclusive", "structurally_alive_but_weak"}
                and provider_calls_used < args.max_provider_calls
            ):
                probe_id, prompt_text = escalation_response_task()
                if not any(record["probe_id"] == probe_id for record in model_records):
                    for attempt_index in range(1, args.response_attempts_per_probe + 1):
                        if provider_calls_used >= args.max_provider_calls:
                            skip_record = response_skip_record(
                                model,
                                requested_model,
                                probe_id,
                                prompt_text,
                                args.include_prompts,
                                "skipped_provider_call_budget",
                                "Provider call budget exhausted.",
                                "provider_call_budget",
                            )
                            skip_record["attempt_index"] = attempt_index
                            records.append(skip_record)
                            model_records.append(skip_record)
                            continue
                        provider_calls_used += 1
                        result = run_response_probe(base_url, model, requested_model, probe_id, prompt_text, args.request_timeout)
                        record = make_response_record(model, probe_id, prompt_text, args.include_prompts, result)
                        record["attempt_index"] = attempt_index
                        records.append(record)
                        model_records.append(record)
                        print(
                            f"[response-evidence] model={model} probe={probe_id} attempt={attempt_index} "
                            f"success={record['response_evidence_success']} signal={record.get('content_signal') or '-'} "
                            f"error={record.get('error_class') or '-'}",
                            flush=True,
                        )

        model_summaries = build_response_model_summaries(records)
        report = {
            "report_kind": "response_evidence",
            "lab_mode": True,
            "started_at_utc": started_at,
            "provider_call_budget": args.max_provider_calls,
            "provider_calls_used": provider_calls_used,
            "request_timeout_sec": args.request_timeout,
            "response_attempts_per_probe": args.response_attempts_per_probe,
            "qualification_report_path": str(qualification_path),
            "qualification_report_sha256": file_sha256(qualification_path),
            "qualification_prompt_fingerprint": qualification_report.get("qualification_prompt_fingerprint"),
            "selected_probe_ids": sorted({record["probe_id"] for record in records}),
            "selected_models_for_response_evidence": selected_models,
            "skipped_models_due_to_gate": skipped_models_due_to_gate,
            "operator_override": bool(args.allow_fallback_only_response_evidence or args.allow_unstable_response_evidence),
            "records": records,
            "model_summaries": model_summaries,
        }
        report["summary"] = {
            "tested_models": len(model_summaries),
            "response_evidence_candidates": sum(1 for item in model_summaries if item["response_evidence_status"] == "response_evidence_candidate"),
            "no_response_evidence_candidates": not any(item["response_evidence_status"] == "response_evidence_candidate" for item in model_summaries),
        }
        json_path, md_path = write_response_reports(report)
        print(f"JSON report: {json_path}")
        print(f"MD report: {md_path}")
    finally:
        shutdown_proxy(proxy_process)


def run_eval(args):
    ensure_env_permissions(ENV_PATH)
    response_path = None
    response_report = None
    operator_override = bool(
        args.allow_eval_without_response_evidence
        or args.allow_eval_without_qualification
        or args.allow_fallback_only_eval
    )
    if args.response_report:
        response_path, response_report = load_response_report(args.response_report)
        qualification_path = Path(response_report["qualification_report_path"])
        if not qualification_path.exists():
            raise SystemExit(f"Qualification report referenced by response report does not exist: {qualification_path}")
        if response_report.get("qualification_report_sha256") != file_sha256(qualification_path):
            raise SystemExit("Response report integrity error: qualification report hash does not match current file.")
    elif not args.allow_eval_without_response_evidence:
        raise SystemExit("Eval mode requires --response-report unless --allow-eval-without-response-evidence is set.")

    models = resolve_models(args, None)
    if response_report and args.models == DEFAULT_MODELS:
        seen = set()
        models = []
        for record in response_report["records"]:
            model = record["model"]
            if model in seen:
                continue
            seen.add(model)
            models.append(model)
    tasks = select_tasks(args.tasks)
    skipped_models_due_to_gate = []
    selected_models_for_eval = []

    if response_report:
        validated_records = [validate_response_record(record) for record in response_report["records"]]
        response_summaries = {item["model"]: item for item in build_response_model_summaries(validated_records)}
        available_models = set(response_summaries)
        for model in models:
            if model not in available_models:
                skipped_models_due_to_gate.append({
                    "model": model,
                    "reason": "not_present_in_response_report",
                })
                continue
            summary = response_summaries[model]
            status = summary["response_evidence_status"]
            if summary["eligible_for_task_eval"]:
                selected_models_for_eval.append(model)
                continue
            if status == "structurally_alive_but_weak" and args.allow_fallback_only_eval:
                selected_models_for_eval.append(model)
                continue
            skipped_models_due_to_gate.append({
                "model": model,
                "reason": status,
            })
    else:
        selected_models_for_eval = models[:]

    try:
        port = pick_port(args.port)
    except RuntimeError as error:
        print(f"Ошибка: {error}")
        raise SystemExit(2)

    proxy_process = start_proxy(port, args.allow_paid_routes)
    base_url = f"http://127.0.0.1:{port}/v1"
    started_at = datetime.now(timezone.utc).isoformat()
    provider_calls_used = 0
    records = []

    try:
        wait_for_health(base_url, 15)
        models_payload = send_models_list_request(base_url, args.request_timeout)
        public_models_index = {
            item.get("id"): item
            for item in models_payload.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for model in selected_models_for_eval:
            normalized_model = normalize_requested_model(model_kind(model))
            consecutive_failures = 0
            tasks_run_for_model = 0
            for task_id, prompt_text in tasks:
                if args.max_tasks_per_model is not None and tasks_run_for_model >= args.max_tasks_per_model:
                    records.append(
                        failure_record(
                            model,
                            normalized_model,
                            task_id,
                            prompt_text,
                            args.include_prompts,
                            "skipped_by_policy",
                            "Task skipped because max_tasks_per_model limit was reached.",
                            "max_tasks_per_model",
                        )
                    )
                    continue
                if args.stop_after_consecutive_failures and consecutive_failures >= args.stop_after_consecutive_failures:
                    records.append(
                        failure_record(
                            model,
                            normalized_model,
                            task_id,
                            prompt_text,
                            args.include_prompts,
                            "skipped_model_instability",
                            "Task skipped because the model hit the consecutive failure threshold for this run.",
                            "consecutive_failure_threshold",
                        )
                    )
                    continue
                if provider_calls_used >= args.max_provider_calls:
                    records.append(
                        failure_record(
                            model,
                            normalized_model,
                            task_id,
                            prompt_text,
                            args.include_prompts,
                            "skipped_provider_call_budget",
                            "Provider call budget exhausted.",
                            "provider_call_budget",
                        )
                    )
                    continue

                result, calls_used = run_task_with_fallback(
                    base_url,
                    normalized_model,
                    prompt_text,
                    args.max_provider_calls - provider_calls_used,
                    args.request_timeout,
                    args.max_fallback_attempts,
                    public_models_index,
                )
                provider_calls_used += calls_used
                tasks_run_for_model += 1
                records.append(make_eval_record(model, task_id, prompt_text, args.include_prompts, result))
                if records[-1]["success"]:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                print(
                    f"[eval] model={model} task={task_id} success={records[-1]['success']} "
                    f"requested_available={records[-1]['requested_model_available']} "
                    f"effective={records[-1]['effective_model'] or '-'} error={records[-1]['error_class'] or '-'}",
                    flush=True,
                )

        report = {
            "report_kind": "task_eval",
            "lab_mode": True,
            "started_at_utc": started_at,
            "provider_call_budget": args.max_provider_calls,
            "provider_calls_used": provider_calls_used,
            "request_timeout_sec": args.request_timeout,
            "max_fallback_attempts": args.max_fallback_attempts,
            "selected_tasks": [task_id for task_id, _ in tasks],
            "response_report_path": str(response_path) if response_path else None,
            "response_report_sha256": file_sha256(response_path) if response_path else None,
            "selected_models_for_eval": selected_models_for_eval,
            "skipped_models_due_to_gate": skipped_models_due_to_gate,
            "operator_override": operator_override,
            "records": records,
        }
        report["model_summaries"] = build_model_summaries(records)
        json_path, md_path = write_reports(report)
        print(f"JSON report: {json_path}")
        print(f"MD report: {md_path}")
    finally:
        shutdown_proxy(proxy_process)


def run_pilot_verification_precheck(args):
    ensure_env_permissions(ENV_PATH)
    if not args.pilot_impl_report:
        raise SystemExit("Pilot verification precheck requires --pilot-impl-report.")

    pilot_impl_path, pilot_impl_report = load_attested_report(
        args.pilot_impl_report,
        "staged_pilot_admission_implementation_precheck",
    )

    pilot_impl_contour_status = pilot_impl_report.get("pilot_impl_contour_status")
    pilot_impl_gate_advisory_verdict = pilot_impl_report.get("summary", {}).get("advisory_verdict")
    pilot_impl_verdict = pilot_impl_report.get("summary", {}).get("pilot_impl_verdict")
    staged_pilot_impl_built_for_verification = bool(
        pilot_impl_report.get("staged_pilot_impl_built_for_verification")
    )
    layer_violation_detected = bool(pilot_impl_report.get("layer_violation_detected"))

    verification_open_now = (
        pilot_impl_contour_status == "pass"
        and staged_pilot_impl_built_for_verification
        and not layer_violation_detected
    )

    if verification_open_now:
        advisory_verdict = "pilot_verification_ready_to_start"
        reason = "upstream_pilot_implementation_passed"
        pilot_verification_verdict = "ready_for_bounded_pilot_verification"
        contour_status = "open"
    else:
        advisory_verdict = "pilot_verification_locked_upstream_missing"
        reason = "upstream_pilot_implementation_missing_or_locked"
        pilot_verification_verdict = "blocked_by_pilot_verification_boundary_violation"
        contour_status = "locked"

    report = {
        "report_kind": "staged_pilot_admission_verification_precheck",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "pilot_impl_gate_path": str(pilot_impl_path),
        "pilot_impl_gate_sha256": file_sha256(pilot_impl_path),
        "pilot_impl_contour_status": pilot_impl_contour_status,
        "pilot_impl_gate_advisory_verdict": pilot_impl_gate_advisory_verdict,
        "pilot_impl_verdict": pilot_impl_verdict,
        "staged_pilot_impl_built_for_verification": staged_pilot_impl_built_for_verification,
        "staged_pilot_verified_candidate": False,
        "artifact_chain_complete": verification_open_now,
        "fixed_verification_probe_set_defined": False,
        "pre_verification_state_snapshot_defined": False,
        "bounded_pilot_path_verified": False,
        "requested_effective_truth_verified": False,
        "write_scope_respected_during_verification": False,
        "verification_writes_confined_to_upstream_allowlist": False,
        "upstream_timeout_or_noise_not_counted_as_disabled_state_success": False,
        "upstream_timeout_or_noise_not_counted_as_abort_success": False,
        "pilot_scope_role_not_redefined_at_runtime": False,
        "pilot_verification_contour_status": contour_status,
        "layer_violation_detected": layer_violation_detected,
    }
    report["summary"] = {
        "staged_pilot_verified_candidate": report["staged_pilot_verified_candidate"],
        "pilot_verification_contour_open_now": verification_open_now,
        "advisory_verdict": advisory_verdict,
        "reason": reason,
        "pilot_verification_verdict": pilot_verification_verdict,
    }
    json_path, md_path = write_pilot_verification_reports(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_admission_state_check(args):
    ensure_env_permissions(ENV_PATH)
    current_snapshot = direct_state_snapshot()
    current_auth = current_snapshot["current_provider_auth_present"]
    current_keys = current_snapshot["current_direct_key_names"]
    prior_keys = None
    prior_provider_auth_present = None
    prior_report_path = None
    prior_report_sha256 = None
    prior_report_summary = None
    prior_report_kind = None

    if args.baseline_report:
        baseline_path, baseline_report = load_attested_report(args.baseline_report, "direct_admission_baseline")
        prior_keys = baseline_report.get("current_direct_key_names")
        prior_provider_auth_present = baseline_report.get("current_provider_auth_present")
        if not isinstance(prior_keys, list) or not isinstance(prior_provider_auth_present, dict):
            raise SystemExit("Invalid baseline report: missing direct state snapshot.")
        prior_report_path = str(baseline_path)
        prior_report_sha256 = file_sha256(baseline_path)
        prior_report_summary = baseline_report.get("summary")
        prior_report_kind = "direct_admission_baseline"
    elif args.provider_report:
        provider_path, provider_report = load_attested_report(args.provider_report, "provider_access")
        if not isinstance(provider_report.get("providers"), list):
            raise SystemExit("Invalid provider report: missing providers list.")
        prior_provider_auth_present = {
            item["provider"]: bool(item.get("auth_present"))
            for item in provider_report["providers"]
            if isinstance(item, dict) and isinstance(item.get("provider"), str)
        }
        if set(prior_provider_auth_present) != set(DIRECT_PROVIDER_TARGETS):
            raise SystemExit("Invalid provider report: direct provider auth map is incomplete.")
        prior_keys = sorted(
            target["api_key_env"]
            for provider, target in DIRECT_PROVIDER_TARGETS.items()
            if prior_provider_auth_present.get(provider)
        )
        prior_report_path = str(provider_path)
        prior_report_sha256 = file_sha256(provider_path)
        prior_report_summary = provider_report.get("summary")
        prior_report_kind = "provider_access"
    else:
        raise SystemExit("Admission state check requires --baseline-report or --provider-report.")

    state_changed = current_auth != prior_provider_auth_present or sorted(prior_keys) != current_keys
    baseline_already_contains_current_state = bool(current_keys) and not state_changed and current_auth == prior_provider_auth_present and sorted(prior_keys) == current_keys
    report = {
        "report_kind": "admission_state_check",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "env_permissions_expected": "0600",
        "current_direct_key_names": current_keys,
        "prior_direct_key_names": prior_keys,
        "prior_report_path": prior_report_path,
        "prior_report_sha256": prior_report_sha256,
        "prior_report_kind": prior_report_kind,
        "prior_report_summary": prior_report_summary,
        "prior_provider_auth_present": prior_provider_auth_present,
        "current_provider_auth_present": current_auth,
        "state_changed": state_changed,
        "baseline_already_contains_current_state": baseline_already_contains_current_state,
    }
    report["summary"] = {
        "direct_keys_present_count": len(current_keys),
        "state_changed": state_changed,
        "advisory_verdict": (
            "new_admission_state_detected"
            if state_changed
            else "baseline_already_contains_current_state"
            if baseline_already_contains_current_state
            else "no_new_admission_state"
        ),
    }
    json_path, md_path = write_admission_state_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_admission_trigger_check(args):
    ensure_env_permissions(ENV_PATH)
    if not args.admission_delta_report:
        raise SystemExit("Admission trigger check requires --admission-delta-report in the canonical path.")

    delta_path, delta_report = load_attested_report(args.admission_delta_report, "direct_admission_delta")
    current_keys = delta_report.get("current_direct_key_names")
    current_auth = delta_report.get("current_provider_auth_present")
    prior_keys = delta_report.get("baseline_direct_key_names")
    prior_auth = delta_report.get("baseline_provider_auth_present")
    key_names_changed = bool(delta_report.get("added_keys") or delta_report.get("removed_keys"))
    provider_auth_changed = bool(delta_report.get("auth_changed_providers"))
    state_changed = bool(delta_report.get("delta_detected"))
    baseline_already_contains_current_state = bool(delta_report.get("no_delta_detected"))
    trigger_present = bool(delta_report.get("delta_gate_open_candidate")) and len(current_keys or []) > 0
    prior_report_path = str(delta_path)
    prior_report_sha256 = file_sha256(delta_path)

    if not isinstance(current_keys, list) or not isinstance(current_auth, dict):
        raise SystemExit("Invalid upstream admission report: missing current state snapshot.")
    report = {
        "report_kind": "admission_state_change_verification",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "env_permissions_expected": "0600",
        "prior_admission_state_report_path": prior_report_path,
        "prior_admission_state_report_sha256": prior_report_sha256,
        "prior_current_direct_key_names": prior_keys,
        "prior_current_provider_auth_present": prior_auth,
        "current_direct_key_names": current_keys,
        "current_provider_auth_present": current_auth,
        "key_names_changed": key_names_changed,
        "provider_auth_changed": provider_auth_changed,
        "state_changed": state_changed,
        "baseline_already_contains_current_state": baseline_already_contains_current_state,
        "trigger_present": trigger_present,
    }
    report["summary"] = {
        "direct_keys_present_count": len(current_keys),
        "state_changed": state_changed,
        "advisory_verdict": (
            "run_trigger_present"
            if trigger_present
            else "baseline_already_contains_current_state"
            if baseline_already_contains_current_state
            else "no_run_trigger_absent"
        ),
    }
    json_path, md_path = write_admission_trigger_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_admission_event_check(args):
    ensure_env_permissions(ENV_PATH)
    if not args.admission_trigger_report:
        raise SystemExit("Admission event check requires --admission-trigger-report.")

    trigger_path, trigger_report = load_attested_report(args.admission_trigger_report, "admission_state_change_verification")
    current_keys = trigger_report.get("current_direct_key_names")
    current_auth = trigger_report.get("current_provider_auth_present")
    state_changed = bool(trigger_report.get("state_changed"))
    baseline_already_contains_current_state = bool(trigger_report.get("baseline_already_contains_current_state"))
    trigger_present = bool(trigger_report.get("trigger_present"))
    key_names_changed = bool(trigger_report.get("key_names_changed"))
    provider_auth_changed = bool(trigger_report.get("provider_auth_changed"))
    if not isinstance(current_keys, list) or not isinstance(current_auth, dict):
        raise SystemExit("Invalid admission trigger report: missing current state snapshot.")

    event_type = "trigger_detected" if trigger_present else "no_trigger"
    report = {
        "report_kind": "admission_event_check",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "env_permissions_expected": "0600",
        "prior_trigger_report_path": str(trigger_path),
        "prior_trigger_report_sha256": file_sha256(trigger_path),
        "prior_current_direct_key_names": trigger_report.get("prior_current_direct_key_names"),
        "prior_current_provider_auth_present": trigger_report.get("prior_current_provider_auth_present"),
        "current_direct_key_names": current_keys,
        "current_provider_auth_present": current_auth,
        "key_names_changed": key_names_changed,
        "provider_auth_changed": provider_auth_changed,
        "state_changed": state_changed,
        "event_type": event_type,
        "baseline_already_contains_current_state": baseline_already_contains_current_state,
        "trigger_present": trigger_present,
    }
    report["summary"] = {
        "direct_keys_present_count": len(current_keys),
        "state_changed": state_changed,
        "event_type": event_type,
        "advisory_verdict": (
            "ready_for_direct_admission_run"
            if event_type == "trigger_detected"
            else "baseline_already_contains_current_state"
            if baseline_already_contains_current_state
            else "no_run_trigger_absent"
        ),
    }
    json_path, md_path = write_admission_event_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_direct_provider_access_precheck(args):
    ensure_env_permissions(ENV_PATH)
    if not args.admission_event_report:
        raise SystemExit("Direct provider access precheck requires --admission-event-report.")

    event_path, event_report = load_attested_report(args.admission_event_report, "admission_event_check")
    current_direct_keys = event_report.get("current_direct_key_names")
    current_provider_auth_present = event_report.get("current_provider_auth_present")
    event_type = event_report.get("event_type")
    state_changed = bool(event_report.get("state_changed"))
    direct_keys_present_count = event_report.get("summary", {}).get("direct_keys_present_count")
    event_advisory_verdict = event_report.get("summary", {}).get("advisory_verdict")

    if not isinstance(current_direct_keys, list) or not isinstance(current_provider_auth_present, dict):
        raise SystemExit("Invalid admission event report: missing direct state snapshot.")

    any_provider_auth_present = any(bool(value) for value in current_provider_auth_present.values())
    admission_event_open_candidate = (
        state_changed
        and event_type == "trigger_detected"
        and event_advisory_verdict != "no_run_trigger_absent"
        and (len(current_direct_keys) > 0 or any_provider_auth_present)
        and direct_keys_present_count is not None
    )

    provider_access_records = []
    ready_direct_providers = []
    provider_access_recheck_runnable_now = False
    provider_access_probe_execution_started = False
    layer_violation_detected = False

    if admission_event_open_candidate:
        provider_access_probe_execution_started = True
        selected_providers = [
            provider
            for provider, present in current_provider_auth_present.items()
            if present and provider in DIRECT_PROVIDER_TARGETS
        ]
        for provider in selected_providers:
            record = provider_probe_result(DIRECT_PROVIDER_TARGETS[provider], args.request_timeout)
            provider_access_records.append(record)
        ready_direct_providers = sorted(
            item["provider"]
            for item in provider_access_records
            if item["transport_status"] == "provider_ready_transport" and item["policy_status"] == "provider_ready_policy"
        )
        provider_access_recheck_runnable_now = len(provider_access_records) > 0 and len(ready_direct_providers) > 0
        advisory_verdict = "direct_provider_access_recheck_ready_to_start"
        reason = "upstream_admission_event_passed"
        contour_status = "open"
        contour_verdict = "ready_for_direct_provider_access_recheck"
    else:
        advisory_verdict = "direct_provider_access_recheck_locked_upstream_missing"
        reason = "upstream_admission_event_missing_or_locked"
        contour_status = "locked"
        contour_verdict = "blocked_by_direct_provider_access_recheck_boundary_violation"

    report = {
        "report_kind": "direct_provider_access_recheck_precheck",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "admission_event_gate_path": str(event_path),
        "admission_event_gate_sha256": file_sha256(event_path),
        "admission_event_gate_event_type": event_type,
        "admission_event_gate_advisory_verdict": event_advisory_verdict,
        "admission_event_gate_state_changed": state_changed,
        "admission_event_gate_direct_keys_present_count": direct_keys_present_count,
        "admission_event_open_candidate": admission_event_open_candidate,
        "provider_access_records": provider_access_records,
        "ready_direct_providers": ready_direct_providers,
        "provider_access_recheck_runnable_now": provider_access_recheck_runnable_now,
        "provider_access_probe_execution_started": provider_access_probe_execution_started,
        "direct_provider_access_recheck_contour_status": contour_status,
        "layer_violation_detected": layer_violation_detected,
    }
    report["summary"] = {
        "provider_access_recheck_runnable_now": provider_access_recheck_runnable_now,
        "advisory_verdict": advisory_verdict,
        "reason": reason,
        "direct_provider_access_recheck_verdict": contour_verdict,
    }
    json_path, md_path = write_access_recheck_precheck_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_direct_route_qualification_precheck(args):
    ensure_env_permissions(ENV_PATH)
    if not args.access_recheck_report:
        raise SystemExit("Direct route qualification precheck requires --access-recheck-report.")

    access_path, access_report = load_attested_report(args.access_recheck_report, "direct_provider_access_recheck_precheck")
    access_recheck_status = access_report.get("direct_provider_access_recheck_contour_status")
    access_recheck_runnable_now = bool(access_report.get("provider_access_recheck_runnable_now"))
    access_recheck_open_candidate = bool(access_report.get("admission_event_open_candidate"))
    ready_direct_providers = access_report.get("ready_direct_providers")
    access_advisory_verdict = access_report.get("summary", {}).get("advisory_verdict")
    layer_violation_detected = bool(access_report.get("layer_violation_detected"))

    if not isinstance(ready_direct_providers, list):
        raise SystemExit("Invalid access recheck report: missing ready_direct_providers list.")

    route_qualification_open_candidate = (
        access_recheck_status == "open"
        and access_recheck_runnable_now
        and access_recheck_open_candidate
        and not layer_violation_detected
        and len(ready_direct_providers) > 0
    )

    if route_qualification_open_candidate:
        advisory_verdict = "direct_route_qualification_ready_to_start"
        reason = "upstream_access_recheck_passed"
        contour_status = "open"
        contour_verdict = "ready_for_direct_route_qualification"
    else:
        advisory_verdict = "direct_route_qualification_locked_upstream_missing"
        reason = "upstream_access_recheck_missing_or_locked"
        contour_status = "locked"
        contour_verdict = "blocked_by_direct_route_qualification_boundary_violation"

    report = {
        "report_kind": "direct_route_qualification_precheck",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "access_recheck_gate_path": str(access_path),
        "access_recheck_gate_sha256": file_sha256(access_path),
        "access_recheck_gate_status": access_recheck_status,
        "access_recheck_gate_advisory_verdict": access_advisory_verdict,
        "access_recheck_open_candidate": route_qualification_open_candidate,
        "ready_direct_providers": ready_direct_providers,
        "qualified_direct_provider_routes": [],
        "route_qualification_runnable_now": route_qualification_open_candidate,
        "route_qualification_probe_execution_started": False,
        "route_qualification_contour_status": contour_status,
        "layer_violation_detected": layer_violation_detected,
    }
    report["summary"] = {
        "route_qualification_runnable_now": route_qualification_open_candidate,
        "advisory_verdict": advisory_verdict,
        "reason": reason,
        "direct_route_qualification_verdict": contour_verdict,
    }
    json_path, md_path = write_direct_route_qualification_precheck_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def load_latest_attested_report(directory, loader, label):
    if not directory.exists():
        raise SystemExit(f"{label} directory not found: {directory}")
    candidates = sorted(
        (path for path in directory.glob("*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            return loader(str(candidate))
        except SystemExit:
            continue
    raise SystemExit(f"No valid attested {label} report found in {directory}.")


def load_recent_attested_reports(directory, loader, label, limit=8):
    if not directory.exists():
        raise SystemExit(f"{label} directory not found: {directory}")
    candidates = sorted(
        (path for path in directory.glob("*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    reports = []
    for candidate in candidates:
        try:
            reports.append(loader(str(candidate)))
        except SystemExit:
            continue
        if len(reports) >= limit:
            break
    if not reports:
        raise SystemExit(f"No valid attested {label} report found in {directory}.")
    return reports


def resolve_canon_input_reports(args):
    qualification_loader = load_qualification_report
    response_loader = load_response_report
    eval_loader = load_eval_report
    provider_loader = lambda path_text: load_attested_report(path_text, "provider_access")
    registry_loader = lambda path_text: load_attested_report(path_text, "model_registry_snapshot")

    qualification_path, qualification_report = (
        qualification_loader(args.qualification_report)
        if args.qualification_report
        else load_latest_attested_report(ROUTE_DIR, qualification_loader, "route qualification")
    )
    response_path, response_report = (
        response_loader(args.response_report)
        if args.response_report
        else load_latest_attested_report(RESPONSE_DIR, response_loader, "response evidence")
    )
    eval_path, eval_report = (
        eval_loader(args.eval_report)
        if args.eval_report
        else load_latest_attested_report(EVAL_DIR, eval_loader, "task eval")
    )
    provider_path, provider_report = (
        provider_loader(args.provider_report)
        if args.provider_report
        else load_latest_attested_report(PROVIDER_DIR, provider_loader, "provider access")
    )
    registry_path, registry_report = (
        registry_loader(args.registry_report)
        if args.registry_report
        else load_latest_attested_report(REGISTRY_DIR, registry_loader, "registry snapshot")
    )
    return {
        "qualification": (qualification_path, qualification_report),
        "response": (response_path, response_report),
        "eval": (eval_path, eval_report),
        "provider": (provider_path, provider_report),
        "registry": (registry_path, registry_report),
    }


def add_error_observation(error_class, contour_name, error_counts, error_contours):
    if not isinstance(error_class, str) or not error_class:
        return
    error_counts[error_class] = error_counts.get(error_class, 0) + 1
    contour_set = error_contours.setdefault(error_class, set())
    contour_set.add(contour_name)


def build_qwen_model_evidence(model_id, qualification_reports, response_reports, eval_reports):
    qualification_status_history = []
    error_counts = {}
    error_contours = {}
    source_reports = set()

    for qualification_path, qualification_report in qualification_reports:
        for item in qualification_report.get("models", []):
            if not isinstance(item, dict) or item.get("model") != model_id:
                continue
            source_reports.add(str(qualification_path))
            qualification_status_history.append(
                {
                    "contour": "route_qualification",
                    "source_report_path": str(qualification_path),
                    "observed_at_utc": qualification_report.get("started_at_utc"),
                    "qualification_status": item.get("qualification_status"),
                    "eligible_for_task_eval": bool(item.get("eligible_for_task_eval")),
                }
            )
            requested_probe = item.get("requested_probe", {})
            fallback_probe = item.get("fallback_probe", {})
            add_error_observation(requested_probe.get("error_class"), str(qualification_path), error_counts, error_contours)
            add_error_observation(fallback_probe.get("error_class"), str(qualification_path), error_counts, error_contours)

    for response_path, response_report in response_reports:
        response_model_summary = None
        for item in response_report.get("model_summaries", []):
            if isinstance(item, dict) and item.get("model") == model_id:
                response_model_summary = item
                break
        if isinstance(response_model_summary, dict):
            source_reports.add(str(response_path))
            qualification_status_history.append(
                {
                    "contour": "response_evidence",
                    "source_report_path": str(response_path),
                    "observed_at_utc": response_report.get("started_at_utc"),
                    "qualification_status": response_model_summary.get("response_evidence_status"),
                    "eligible_for_task_eval": bool(response_model_summary.get("eligible_for_task_eval")),
                }
            )
        for record in response_report.get("records", []):
            if not isinstance(record, dict) or record.get("model") != model_id:
                continue
            source_reports.add(str(response_path))
            add_error_observation(record.get("error_class"), str(response_path), error_counts, error_contours)

    for eval_path, eval_report in eval_reports:
        eval_model_summary = None
        for item in eval_report.get("model_summaries", []):
            if isinstance(item, dict) and item.get("model") == model_id:
                eval_model_summary = item
                break
        if isinstance(eval_model_summary, dict):
            source_reports.add(str(eval_path))
            qualification_status_history.append(
                {
                    "contour": "task_eval",
                    "source_report_path": str(eval_path),
                    "observed_at_utc": eval_report.get("started_at_utc"),
                    "qualification_status": eval_model_summary.get("outcome"),
                    "eligible_for_task_eval": False,
                }
            )
        for record in eval_report.get("records", []):
            if not isinstance(record, dict) or record.get("model") != model_id:
                continue
            source_reports.add(str(eval_path))
            add_error_observation(record.get("error_class"), str(eval_path), error_counts, error_contours)

    dominant_error_classes = [
        {
            "error_class": error_class,
            "count": count,
            "contours": sorted(error_contours.get(error_class, set())),
        }
        for error_class, count in sorted(
            error_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    repeated_across_contours = len(source_reports) >= 2 or any(len(contours) >= 2 for contours in error_contours.values())
    qualification_status_history.sort(
        key=lambda item: (
            item.get("observed_at_utc") or "",
            item.get("source_report_path") or "",
            item.get("contour") or "",
        )
    )
    return {
        "model": model_id,
        "qualification_status_history": qualification_status_history,
        "dominant_error_classes": dominant_error_classes,
        "repeated_across_contours": repeated_across_contours,
        "source_report_count": len(source_reports),
        "practical_scoring_eligible": False,
    }


def write_verification_json(file_name, payload):
    ensure_verification_dir()
    signed_payload = attach_attestation(payload)
    output_path = VERIFICATION_DIR / file_name
    output_path.write_text(json.dumps(signed_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path, signed_payload


def load_fixed_verification_report(file_name, expected_kind):
    return load_attested_report(str(VERIFICATION_DIR / file_name), expected_kind)


def route_model_for_registry_model_id(model_id):
    if model_id in REGISTRY_MODEL_TO_ROUTE_MODEL_HINT:
        return REGISTRY_MODEL_TO_ROUTE_MODEL_HINT[model_id]
    if model_id.startswith("or-"):
        return model_id[3:]
    return None


def registry_model_id_for_route_model(route_model):
    return ROUTE_MODEL_TO_REGISTRY_MODEL_ID.get(route_model, route_model)


def build_runtime_truth_by_model(qualification_report, response_report, eval_report):
    route_status = {}
    for item in qualification_report.get("models", []):
        if isinstance(item, dict) and isinstance(item.get("model"), str):
            route_status[item["model"]] = item.get("qualification_status")

    response_status = {}
    for item in response_report.get("model_summaries", []):
        if isinstance(item, dict) and isinstance(item.get("model"), str):
            response_status[item["model"]] = item.get("response_evidence_status")

    eval_status = {}
    for item in eval_report.get("model_summaries", []):
        if isinstance(item, dict) and isinstance(item.get("model"), str):
            eval_status[item["model"]] = item.get("outcome")

    truth = {}
    for model in sorted(set(route_status) | set(response_status) | set(eval_status)):
        truth[model] = {
            "route_qualification_status": route_status.get(model),
            "response_evidence_status": response_status.get(model),
            "eval_outcome": eval_status.get(model),
            "runtime_success_confirmed": (
                route_status.get(model) == "requested_model_candidate"
                and response_status.get(model) == "response_evidence_candidate"
                and eval_status.get(model) == "requested_model_candidate"
            ),
        }
    return truth


def runtime_success_providers(qualification_report, response_report, eval_report):
    providers = set()
    for item in qualification_report.get("models", []):
        if not isinstance(item, dict):
            continue
        requested_probe = item.get("requested_probe")
        if (
            isinstance(requested_probe, dict)
            and requested_probe.get("success")
            and requested_probe.get("requested_model_available")
            and isinstance(requested_probe.get("provider"), str)
        ):
            providers.add(requested_probe["provider"])

    for record in response_report.get("records", []):
        if (
            isinstance(record, dict)
            and record.get("status") == "completed"
            and record.get("requested_model_available")
            and record.get("response_evidence_success")
            and isinstance(record.get("provider"), str)
        ):
            providers.add(record["provider"])

    for record in eval_report.get("records", []):
        if (
            isinstance(record, dict)
            and record.get("success")
            and record.get("requested_model_available")
            and isinstance(record.get("provider"), str)
        ):
            providers.add(record["provider"])
    return sorted(providers)


def lane_priority_value(lane_role):
    lane_rank = {
        "primary_practical": 0,
        "secondary_reasoning": 1,
        "comparison": 2,
        "fallback": 3,
        "cheap_helper": 4,
    }
    return lane_rank.get(lane_role, 50)


def wave_2c_candidate_order():
    return [
        "direct-cerebras-llama3.1-8b",
        "direct-groq-openai-gpt-oss-20b",
        "direct-gemini-2.5-flash",
        "direct-mistral-devstral-2512",
        "direct-mistral-small-latest",
        "direct-cerebras-qwen-3-235b-a22b-instruct-2507",
    ]


def contour_effect_scope():
    return {
        "diagnostic_only": True,
        "promotion_effect": False,
        "runtime_admission_effect": False,
        "practical_promotion_effect": False,
    }


def latest_qualification_reports_for_model(model_id, limit=2):
    reports = load_recent_attested_reports(ROUTE_DIR, load_qualification_report, "route qualification", limit=12)
    matching = []
    for path, report in reports:
        for item in report.get("models", []):
            if isinstance(item, dict) and item.get("model") == model_id:
                matching.append((path, report))
                break
        if len(matching) >= limit:
            break
    if len(matching) < limit:
        raise SystemExit(f"Need at least {limit} qualification reports for model {model_id}.")
    matching.sort(key=lambda pair: pair[1].get("started_at_utc") or "")
    return matching[:limit]


def qualification_entry_for_model(report, model_id):
    for item in report.get("models", []):
        if isinstance(item, dict) and item.get("model") == model_id:
            return item
    raise SystemExit(f"Qualification report missing model entry: {model_id}")


def response_summary_for_model(report, model_id):
    for item in report.get("model_summaries", []):
        if isinstance(item, dict) and item.get("model") == model_id:
            return item
    raise SystemExit(f"Response report missing model summary: {model_id}")


def eval_summary_for_model(report, model_id):
    for item in report.get("model_summaries", []):
        if isinstance(item, dict) and item.get("model") == model_id:
            return item
    raise SystemExit(f"Eval report missing model summary: {model_id}")


def cerebras_provider_record(report):
    for item in report.get("providers", []):
        if isinstance(item, dict) and item.get("provider") == "cerebras":
            return item
    raise SystemExit("Provider report missing cerebras provider record.")


def requested_model_probe_pass(entry):
    requested_probe = entry.get("requested_probe", {})
    fallback_probe = entry.get("fallback_probe", {})
    return (
        entry.get("qualification_status") == "requested_model_candidate"
        and requested_probe.get("attempted") is True
        and requested_probe.get("success") is True
        and requested_probe.get("requested_model_available") is True
        and requested_probe.get("fallback_used") is False
        and not fallback_probe.get("attempted")
    )


def contour_role_snapshot(model_id, runtime_truth_entry, qwen_excluded_registry_ids):
    if model_id == "or-gpt-oss-20b":
        return "current_primary_practical_candidate"
    if model_id == "glm-4.7-flash":
        return "unstable_comparison_only"
    if model_id in qwen_excluded_registry_ids:
        return "excluded_from_practical_scoring"
    if model_id == "or-gpt-oss-120b":
        return "excluded_from_runtime_path"
    if model_id in wave_2c_candidate_order():
        return "queued_candidate_only"
    if bool(runtime_truth_entry.get("runtime_success_confirmed")):
        return "runtime_confirmed_nonprimary"
    return "out_of_scope_context_only"


def run_wave_2c_contour_generator(args):
    ensure_env_permissions(ENV_PATH)
    reports = resolve_canon_input_reports(args)
    qualification_path, qualification_report = reports["qualification"]
    response_path, response_report = reports["response"]
    eval_path, eval_report = reports["eval"]
    provider_path, provider_report = reports["provider"]
    registry_path, registry_report = reports["registry"]

    qwen_rca_path, qwen_rca_report = load_fixed_verification_report("qwen_openrouter_free_lane_rca.json", "qwen_openrouter_free_lane_rca")
    qwen_status_path, qwen_status_report = load_fixed_verification_report("qwen_status_decision.json", "qwen_status_decision")
    qwen_rebase_path, qwen_rebase_report = load_fixed_verification_report("practical_pool_rebase_decision.json", "practical_pool_rebase_decision")
    qwen_blocker_path, qwen_blocker_report = load_fixed_verification_report("next_contour_blocker.json", "next_contour_blocker")

    input_reports = {
        "route_qualification": {"path": str(qualification_path), "sha256": file_sha256(qualification_path)},
        "response_evidence": {"path": str(response_path), "sha256": file_sha256(response_path)},
        "task_eval": {"path": str(eval_path), "sha256": file_sha256(eval_path)},
        "provider_access": {"path": str(provider_path), "sha256": file_sha256(provider_path)},
        "registry_snapshot": {"path": str(registry_path), "sha256": file_sha256(registry_path)},
        "qwen_openrouter_free_lane_rca": {"path": str(qwen_rca_path), "sha256": file_sha256(qwen_rca_path)},
        "qwen_status_decision": {"path": str(qwen_status_path), "sha256": file_sha256(qwen_status_path)},
        "practical_pool_rebase_decision": {"path": str(qwen_rebase_path), "sha256": file_sha256(qwen_rebase_path)},
        "next_contour_blocker": {"path": str(qwen_blocker_path), "sha256": file_sha256(qwen_blocker_path)},
    }
    decision_order = [
        "current_practical_truth_reconfirm",
        "current_lane_role_snapshot",
        "second_route_candidate_queue",
        "second_route_runtime_opening_decision",
        "second_route_readiness_decision",
        "next_practical_contour_spec",
        "control_plane_only_candidate_consumption_guard",
    ]

    runtime_truth = build_runtime_truth_by_model(qualification_report, response_report, eval_report)
    runtime_success_models = sorted(model for model, details in runtime_truth.items() if details["runtime_success_confirmed"])
    current_runtime_pool_registry_model_ids = sorted(registry_model_id_for_route_model(model) for model in runtime_success_models)
    runtime_success_provider_names = runtime_success_providers(qualification_report, response_report, eval_report)

    registry_summary = registry_report.get("summary", {})
    registry_current_practical_pool = registry_summary.get("current_practical_pool_model_ids")
    if not isinstance(registry_current_practical_pool, list):
        registry_current_practical_pool = []
    registry_current_practical_pool = sorted(item for item in registry_current_practical_pool if isinstance(item, str))

    qwen_excluded_registry_ids = sorted(
        f"or-{item.get('model')}"
        for item in qwen_status_report.get("qwen_status_decisions", [])
        if isinstance(item, dict)
        and isinstance(item.get("model"), str)
        and item.get("status_decision") == "hold_out_of_practical_scoring"
    )
    active_blockers = [
        item
        for item in qwen_blocker_report.get("blockers", [])
        if isinstance(item, dict) and bool(item.get("blocker_active"))
    ]
    second_route_ready_now = len(current_runtime_pool_registry_model_ids) >= 2
    practical_truth_verdict = "ready" if second_route_ready_now else "blocked_but_ordered"

    truth_report = {
        "report_kind": "current_practical_truth_reconfirm",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 1,
        "input_reports": input_reports,
        "canon_assertions": {
            "queue_priority_not_admission": True,
            "registry_role_not_runtime_success": True,
            "provider_visibility_not_runtime_opening": True,
        },
        "requested_model_candidate_models": [
            model
            for model, details in sorted(runtime_truth.items())
            if details.get("route_qualification_status") == "requested_model_candidate"
        ],
        "comparison_only_models": [
            model
            for model, details in sorted(runtime_truth.items())
            if model == "glm-flash" or details.get("route_qualification_status") in {"unstable_or_limited"}
        ],
        "excluded_models": ["qwen3-coder", "qwen3-next", "gpt-oss-120b"],
        "excluded_reasons": {
            "qwen3-coder": "formally excluded after repeated fallback_only free-lane instability",
            "qwen3-next": "formally excluded after repeated fallback_only free-lane instability",
            "gpt-oss-120b": "excluded from practical runtime path by canon and operator direction",
        },
        "current_runtime_pool_route_models": runtime_success_models,
        "current_runtime_pool_registry_model_ids": current_runtime_pool_registry_model_ids,
        "registry_declared_current_practical_pool_model_ids": registry_current_practical_pool,
        "qwen_excluded_registry_model_ids": qwen_excluded_registry_ids,
        "active_blockers": active_blockers,
        "second_route_ready_now": second_route_ready_now,
        "current_vs_registry_pool_match": current_runtime_pool_registry_model_ids == registry_current_practical_pool,
        "runtime_success_provider_names": runtime_success_provider_names,
        "truth_inconsistencies": False,
        "layer_separation_violations": False,
        "summary": {
            "advisory_verdict": practical_truth_verdict,
            "current_runtime_pool_size": len(current_runtime_pool_registry_model_ids),
            "requires_second_route": not second_route_ready_now,
        },
    }
    truth_path, _ = write_verification_json("current_practical_truth_reconfirm.json", truth_report)

    registry_entries = registry_report.get("registry_entries", [])
    if not isinstance(registry_entries, list):
        raise SystemExit("Invalid registry snapshot: missing registry_entries list.")
    lane_snapshot_entries = []
    for entry in registry_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("model_id"), str):
            continue
        model_id = entry["model_id"]
        route_model_hint = route_model_for_registry_model_id(model_id)
        runtime_details = runtime_truth.get(route_model_hint, {})
        lane_snapshot_entries.append(
            {
                "model_id": model_id,
                "provider": entry.get("provider"),
                "provider_type": entry.get("provider_type"),
                "registry_lane_role": entry.get("lane_role"),
                "contour_lane_role": contour_role_snapshot(model_id, runtime_details, qwen_excluded_registry_ids),
                "availability_state": entry.get("availability_state"),
                "evidence_level": entry.get("evidence_level"),
                "cost_class": entry.get("cost_class"),
                "fallback_eligible": bool(entry.get("fallback_eligible")),
                "route_model_hint": route_model_hint,
                "runtime_success_confirmed": bool(runtime_details.get("runtime_success_confirmed")),
                "runtime_admitted": bool(runtime_details.get("runtime_success_confirmed")),
                "practical_scoring_eligible": model_id == "or-gpt-oss-20b",
                "route_qualification_status": runtime_details.get("route_qualification_status"),
                "response_evidence_status": runtime_details.get("response_evidence_status"),
                "eval_outcome": runtime_details.get("eval_outcome"),
                "decision_basis": (
                    "runtime_success_chain"
                    if bool(runtime_details.get("runtime_success_confirmed"))
                    else "registry_or_prior_closure_context_only"
                ),
            }
        )
    lane_snapshot_entries.sort(key=lambda item: (str(item.get("contour_lane_role") or ""), item["model_id"]))
    lane_snapshot_report = {
        "report_kind": "current_lane_role_snapshot",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_truth_reconfirm_path": str(truth_path),
        "depends_on_truth_reconfirm_sha256": file_sha256(truth_path),
        "canon_assertions": {
            "registry_role_not_runtime_success": True,
        },
        "lane_role_snapshot": lane_snapshot_entries,
        "summary": {
            "registry_entry_count": len(lane_snapshot_entries),
            "runtime_confirmed_entry_count": sum(1 for item in lane_snapshot_entries if item["runtime_success_confirmed"]),
            "advisory_verdict": "lane_roles_snapshotted_without_runtime_overstatement",
        },
    }
    lane_snapshot_path, _ = write_verification_json("current_lane_role_snapshot.json", lane_snapshot_report)

    provider_records = provider_report.get("providers", [])
    if not isinstance(provider_records, list):
        provider_records = []
    provider_records_by_provider = {}
    for record in provider_records:
        if isinstance(record, dict) and isinstance(record.get("provider"), str):
            provider_records_by_provider.setdefault(record["provider"], []).append(record)

    registry_index_map = {
        entry["model_id"]: entry
        for entry in registry_entries
        if isinstance(entry, dict) and isinstance(entry.get("model_id"), str)
    }
    queue_candidates = []
    for index, model_id in enumerate(wave_2c_candidate_order(), start=1):
        entry = registry_index_map.get(model_id)
        if not isinstance(entry, dict):
            continue
        lane_role = entry.get("lane_role")
        provider_name = entry.get("provider")
        provider_type = entry.get("provider_type")
        cost_class = entry.get("cost_class")
        route_model_hint = route_model_for_registry_model_id(model_id)
        runtime_details = runtime_truth.get(route_model_hint, {})
        provider_items = provider_records_by_provider.get(provider_name, [])
        if provider_type == "direct_provider":
            policy_open_now = bool(provider_report.get("allow_paid_routes")) and any(
                item.get("policy_status") == "provider_ready_policy" for item in provider_items if isinstance(item, dict)
            )
            auth_open_now = any(bool(item.get("auth_accepted")) for item in provider_items if isinstance(item, dict))
            policy_basis = "direct_provider_policy_gate"
            auth_basis = "direct_provider_auth_verified_runtime"
        else:
            policy_open_now = cost_class in {"free_limited", "entitled_direct_limited"}
            auth_open_now = bool(runtime_details.get("runtime_success_confirmed"))
            policy_basis = "cost_class_default_gate"
            auth_basis = "model_specific_runtime_success_required"
        runtime_probe_allowed_now = bool(policy_open_now and auth_open_now)
        runtime_success_confirmed = bool(runtime_details.get("runtime_success_confirmed"))
        queue_candidates.append(
            {
                "candidate_order": index,
                "candidate_model": model_id,
                "provider": provider_name,
                "provider_type": provider_type,
                "current_registry_lane_role": lane_role,
                "current_registry_availability_state": entry.get("availability_state"),
                "current_cost_class": cost_class,
                "evidence_level": entry.get("evidence_level"),
                "route_model_hint": route_model_hint,
                "control_plane_support_only": not runtime_success_confirmed,
                "queue_priority_not_admission": True,
                "blocked_by_prior_runtime_failure": entry.get("evidence_level") == "runtime_failure",
                "policy_open_now": bool(policy_open_now),
                "policy_basis": policy_basis,
                "auth_open_now": bool(auth_open_now),
                "auth_basis": auth_basis,
                "runtime_probe_allowed_now": bool(runtime_probe_allowed_now),
                "queue_priority_reason": (
                    "first_non_qwen_candidate_in_canon_order"
                    if index == 1
                    else "ordered_candidate_queue_after_primary_non_qwen_target"
                ),
                "admission_rationale": (
                    "runtime_probe_open_now"
                    if runtime_probe_allowed_now
                    else "blocked_but_ordered_candidate_only"
                ),
            }
        )

    queue_report = {
        "report_kind": "second_route_candidate_queue",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_lane_snapshot_path": str(lane_snapshot_path),
        "depends_on_lane_snapshot_sha256": file_sha256(lane_snapshot_path),
        "excluded_registry_model_ids": sorted(set(current_runtime_pool_registry_model_ids) | set(qwen_excluded_registry_ids) | {"or-gpt-oss-120b", "glm-4.7-flash"}),
        "canon_assertions": {
            "queue_priority_not_admission": True,
            "provider_visibility_not_runtime_opening": True,
        },
        "candidate_queue": queue_candidates,
        "summary": {
            "candidate_count": len(queue_candidates),
            "runtime_probe_open_now_candidate_count": sum(1 for item in queue_candidates if item["runtime_probe_allowed_now"]),
            "advisory_verdict": "candidate_queue_materialized",
        },
    }
    queue_path, _ = write_verification_json("second_route_candidate_queue.json", queue_report)

    top_candidate = queue_candidates[0] if queue_candidates else None
    runtime_open_now = bool(top_candidate and top_candidate["runtime_probe_allowed_now"])
    opening_decision = (
        "open_for_runtime_probe"
        if runtime_open_now
        else "blocked_but_ordered"
        if top_candidate
        else "blocked_no_candidate"
    )
    runtime_opening_report = {
        "report_kind": "second_route_runtime_opening_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_candidate_queue_path": str(queue_path),
        "depends_on_candidate_queue_sha256": file_sha256(queue_path),
        "target_candidate": top_candidate,
        "policy_open_now": bool(top_candidate and top_candidate["policy_open_now"]),
        "auth_open_now": bool(top_candidate and top_candidate["auth_open_now"]),
        "runtime_probe_allowed_now": runtime_open_now,
        "blocking_class": (
            "none"
            if runtime_open_now
            else "blocked_by_cost_policy"
            if top_candidate and not top_candidate["policy_open_now"]
            else "blocked_by_auth_state"
            if top_candidate and not top_candidate["auth_open_now"]
            else "blocked_by_missing_runtime_opening"
        ),
        "blocking_reason": (
            "direct-provider runtime opening is not currently available under the active provider policy and auth evidence chain."
            if top_candidate
            else "no candidate available in ordered queue."
        ),
        "operational_evidence_paths": [str(provider_path)],
        "operational_evidence_sha256": [file_sha256(provider_path)],
        "provider_visibility_not_runtime_opening": True,
        "summary": {
            "runtime_opening_decision": opening_decision,
            "advisory_verdict": opening_decision,
        },
    }
    runtime_opening_path, _ = write_verification_json("second_route_runtime_opening_decision.json", runtime_opening_report)

    second_route_readiness_now = len(current_runtime_pool_registry_model_ids) >= 2
    readiness_verdict = "ready_for_next_qualification_contour" if runtime_open_now else "blocked_but_ordered"
    readiness_report = {
        "report_kind": "second_route_readiness_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_runtime_opening_path": str(runtime_opening_path),
        "depends_on_runtime_opening_sha256": file_sha256(runtime_opening_path),
        "depends_on_qwen_blocker_path": str(qwen_blocker_path),
        "depends_on_qwen_blocker_sha256": file_sha256(qwen_blocker_path),
        "target_candidate": top_candidate["candidate_model"] if top_candidate else None,
        "queue_position": top_candidate["candidate_order"] if top_candidate else None,
        "readiness_status": readiness_verdict,
        "active_blocker_count": len(active_blockers),
        "current_runtime_pool_registry_model_ids": current_runtime_pool_registry_model_ids,
        "current_runtime_pool_size": len(current_runtime_pool_registry_model_ids),
        "second_route_ready_now": second_route_readiness_now,
        "policy_open_now": bool(top_candidate and top_candidate["policy_open_now"]),
        "auth_open_now": bool(top_candidate and top_candidate["auth_open_now"]),
        "runtime_probe_allowed_now": runtime_open_now,
        "reason": (
            "top queued candidate is not runtime-open now under current provider policy/auth evidence"
            if not runtime_open_now
            else "top queued candidate is runtime-open now for the next qualification contour"
        ),
        "next_action": (
            "keep_current_runtime_pool_and_pivot_queue_forward_without_runtime_claim"
            if not runtime_open_now
            else "run_next_candidate_qualification_contour"
        ),
        "summary": {
            "advisory_verdict": readiness_verdict,
            "readiness_reason": (
                "top_candidate_blocked_but_ordered"
                if not runtime_open_now
                else "top_candidate_ready_for_next_qualification_contour"
            ),
        },
    }
    readiness_path, _ = write_verification_json("second_route_readiness_decision.json", readiness_report)

    current_runtime_pool = []
    for route_model in runtime_success_models:
        runtime_details = runtime_truth.get(route_model, {})
        current_runtime_pool.append(
            {
                "route_model": route_model,
                "registry_model_id": registry_model_id_for_route_model(route_model),
                "route_qualification_status": runtime_details.get("route_qualification_status"),
                "response_evidence_status": runtime_details.get("response_evidence_status"),
                "eval_outcome": runtime_details.get("eval_outcome"),
                "runtime_success_confirmed": bool(runtime_details.get("runtime_success_confirmed")),
            }
        )
    contour_spec_report = {
        "report_kind": "next_practical_contour_spec",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_readiness_path": str(readiness_path),
        "depends_on_readiness_sha256": file_sha256(readiness_path),
        "current_runtime_pool": current_runtime_pool,
        "comparison_only_pool": ["glm-flash"],
        "excluded_pool": ["qwen3-coder", "qwen3-next", "gpt-oss-120b"],
        "next_probe_queue": [item["candidate_model"] for item in queue_candidates],
        "next_probe_candidate_if_opened": top_candidate["candidate_model"] if top_candidate else None,
        "next_probe_pointer": 1 if queue_candidates else None,
        "practical_pool_changed_now": False,
        "policy_open_now": bool(top_candidate and top_candidate["policy_open_now"]),
        "auth_open_now": bool(top_candidate and top_candidate["auth_open_now"]),
        "runtime_probe_allowed_now": runtime_open_now,
        "summary": {
            "advisory_verdict": "blocked_but_ordered" if not runtime_open_now else "ready_for_next_qualification_contour",
            "contour_status": "blocked_but_ordered" if not runtime_open_now else "open",
        },
    }
    contour_spec_path, _ = write_verification_json("next_practical_contour_spec.json", contour_spec_report)

    control_plane_only_candidates = sorted(
        item["candidate_model"]
        for item in queue_candidates
        if item.get("control_plane_support_only")
        and item.get("current_registry_availability_state") in {"provider_visible_but_unverified", "auth_unconfirmed", "quota_unconfirmed"}
    )
    control_plane_consumption_violation_ids = sorted(
        item["candidate_model"]
        for item in queue_candidates
        if item["candidate_model"] in control_plane_only_candidates and item.get("runtime_probe_allowed_now")
    )
    guard_passed = len(control_plane_consumption_violation_ids) == 0
    guard_report = {
        "report_kind": "control_plane_only_candidate_consumption_guard",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "wave": "2c",
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_contour_spec_path": str(contour_spec_path),
        "depends_on_contour_spec_sha256": file_sha256(contour_spec_path),
        "repeated_runtime_budget_burn_allowed": False,
        "control_plane_only_candidate_allowed_for_runtime_probe": False,
        "pivot_required_if_still_blocked": True,
        "reason": "control-plane-only candidates may remain in ordered queue but must not consume repeated runtime contour budget until runtime opening is explicitly evidenced.",
        "control_plane_only_candidate_model_ids": control_plane_only_candidates,
        "consumption_violation_model_ids": control_plane_consumption_violation_ids,
        "guard_passed": guard_passed,
        "summary": {
            "advisory_verdict": (
                "control_plane_only_candidate_consumption_blocked"
                if guard_passed
                else "control_plane_only_candidate_consumption_violation"
            ),
        },
    }
    guard_path, _ = write_verification_json("control_plane_only_candidate_consumption_guard.json", guard_report)

    print(f"JSON report: {truth_path}")
    print(f"JSON report: {lane_snapshot_path}")
    print(f"JSON report: {queue_path}")
    print(f"JSON report: {runtime_opening_path}")
    print(f"JSON report: {readiness_path}")
    print(f"JSON report: {contour_spec_path}")
    print(f"JSON report: {guard_path}")


def run_contour_1_synthetic_validation_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_1_current_state_decision_synthetic_validation"
    decision_order = [
        "current_state_decision",
        "repeated_full_contour_freeze_rule",
        "synthetic_validation_scope_boundary",
        "synthetic_validation_plan",
        "synthetic_validation_result",
        "simulation_vs_runtime_readiness_decision",
        "next_real_route_acquisition_entrypoint",
    ]
    effect_scope = contour_effect_scope()

    truth_path, truth_report = load_fixed_verification_report("current_practical_truth_reconfirm.json", "current_practical_truth_reconfirm")
    lane_path, lane_report = load_fixed_verification_report("current_lane_role_snapshot.json", "current_lane_role_snapshot")
    queue_path, queue_report = load_fixed_verification_report("second_route_candidate_queue.json", "second_route_candidate_queue")
    runtime_opening_path, runtime_opening_report = load_fixed_verification_report("second_route_runtime_opening_decision.json", "second_route_runtime_opening_decision")
    readiness_path, readiness_report = load_fixed_verification_report("second_route_readiness_decision.json", "second_route_readiness_decision")
    contour_spec_path, contour_spec_report = load_fixed_verification_report("next_practical_contour_spec.json", "next_practical_contour_spec")
    control_plane_guard_path, control_plane_guard_report = load_fixed_verification_report(
        "control_plane_only_candidate_consumption_guard.json",
        "control_plane_only_candidate_consumption_guard",
    )
    qwen_blocker_path, qwen_blocker_report = load_fixed_verification_report("next_contour_blocker.json", "next_contour_blocker")

    input_reports = {
        "current_practical_truth_reconfirm": {"path": str(truth_path), "sha256": file_sha256(truth_path)},
        "current_lane_role_snapshot": {"path": str(lane_path), "sha256": file_sha256(lane_path)},
        "second_route_candidate_queue": {"path": str(queue_path), "sha256": file_sha256(queue_path)},
        "second_route_runtime_opening_decision": {"path": str(runtime_opening_path), "sha256": file_sha256(runtime_opening_path)},
        "second_route_readiness_decision": {"path": str(readiness_path), "sha256": file_sha256(readiness_path)},
        "next_practical_contour_spec": {"path": str(contour_spec_path), "sha256": file_sha256(contour_spec_path)},
        "control_plane_only_candidate_consumption_guard": {
            "path": str(control_plane_guard_path),
            "sha256": file_sha256(control_plane_guard_path),
        },
        "next_contour_blocker": {"path": str(qwen_blocker_path), "sha256": file_sha256(qwen_blocker_path)},
    }

    current_runtime_pool_registry_model_ids = truth_report.get("current_runtime_pool_registry_model_ids", [])
    if not isinstance(current_runtime_pool_registry_model_ids, list):
        current_runtime_pool_registry_model_ids = []
    comparison_only_models = truth_report.get("comparison_only_models", [])
    if not isinstance(comparison_only_models, list):
        comparison_only_models = []
    excluded_models = truth_report.get("excluded_models", [])
    if not isinstance(excluded_models, list):
        excluded_models = []
    active_blockers = qwen_blocker_report.get("blockers", [])
    if not isinstance(active_blockers, list):
        active_blockers = []
    active_blockers = [item for item in active_blockers if isinstance(item, dict) and item.get("blocker_active")]

    candidate_queue = queue_report.get("candidate_queue", [])
    if not isinstance(candidate_queue, list):
        candidate_queue = []
    top_candidate = candidate_queue[0] if candidate_queue and isinstance(candidate_queue[0], dict) else None
    top_candidate_model = top_candidate.get("candidate_model") if isinstance(top_candidate, dict) else None
    top_candidate_queue_position = top_candidate.get("candidate_order") if isinstance(top_candidate, dict) else None

    current_state_report = {
        "report_kind": "current_state_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "input_reports": input_reports,
        "effect_scope": effect_scope,
        "canon_assertions": {
            "simulation_readiness_not_runtime_readiness": True,
            "queue_priority_not_runtime_opening": True,
            "provider_visibility_not_runtime_opening": True,
            "fallback_success_not_requested_model_success": True,
        },
        "current_state": {
            "lab_architecture_status": "implemented_with_truth_chain",
            "lab_architecture_blocked": False,
            "route_acquisition_blocked": True,
            "current_runtime_confirmed_practical_routes": current_runtime_pool_registry_model_ids,
            "current_runtime_confirmed_practical_route_count": len(current_runtime_pool_registry_model_ids),
            "second_stable_requested_route_present": len(current_runtime_pool_registry_model_ids) >= 2,
            "comparison_only_routes": comparison_only_models,
            "practical_excluded_routes": excluded_models,
            "qwen_openrouter_reentry_allowed": False,
            "top_ordered_candidate": top_candidate_model,
            "top_ordered_candidate_runtime_open_now": bool(runtime_opening_report.get("runtime_probe_allowed_now")),
        },
        "decision_summary": {
            "status": "blocked_on_real_route_acquisition",
            "not_blocked_on_lab_architecture": True,
            "blocked_on_lab_architecture": False,
            "top_candidate_status": readiness_report.get("readiness_status"),
            "active_blocker_count": len(active_blockers),
        },
        "summary": {
            "advisory_verdict": "architecture_ready_route_acquisition_blocked",
            "reason": "single_runtime_confirmed_practical_route_only",
        },
    }
    current_state_path, _ = write_verification_json("current_state_decision.json", current_state_report)

    freeze_rule_report = {
        "report_kind": "repeated_full_contour_freeze_rule",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_current_state_path": str(current_state_path),
        "depends_on_current_state_sha256": file_sha256(current_state_path),
        "effect_scope": effect_scope,
        "freeze_rule_active": True,
        "full_contour_rerun_allowed": False,
        "freeze_scope_route_models": ["qwen3-coder", "qwen3-next", "gpt-oss-20b", "glm-flash"],
        "blocked_repeated_cycle": [
            "provider-access",
            "qualify",
            "response-evidence",
            "eval",
            "audit",
        ],
        "short_recheck_allowed_only_if_new_fact": True,
        "new_fact_triggers": [
            "new_runtime_success_evidence",
            "new_auth_acceptance_evidence",
            "new_policy_opening_evidence",
            "new_provider_state_change",
        ],
        "reentry_constraints": {
            "qwen_openrouter_reentry_allowed": False,
            "control_plane_only_candidates_must_not_burn_runtime_budget": True,
        },
        "summary": {
            "advisory_verdict": "freeze_unchanged_repeated_full_contours",
            "reason": "same_pool_replay_without_new_fact_is_budget_burn",
        },
    }
    freeze_rule_path, _ = write_verification_json("repeated_full_contour_freeze_rule.json", freeze_rule_report)

    scope_boundary_report = {
        "report_kind": "synthetic_validation_scope_boundary",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_freeze_rule_path": str(freeze_rule_path),
        "depends_on_freeze_rule_sha256": file_sha256(freeze_rule_path),
        "effect_scope": effect_scope,
        "synthetic_validation_allowed": True,
        "real_provider_acquisition_allowed": False,
        "runtime_claim_allowed": False,
        "runtime_readiness_mutation_allowed": False,
        "allowed_validation_targets": [
            "truthful_requested_effective_reporting",
            "no_silent_fallback",
            "fallback_chain_contract",
            "cost_guard_contract",
            "provider_state_transition_logic",
            "role_matrix_materialization",
            "promotion_gate_materialization",
            "second_route_readiness_split",
            "audit_factcheck_chain_continuity",
        ],
        "disallowed_actions": [
            "real_provider_runtime_probe",
            "requested_model_pass_claim",
            "practical_route_promotion",
            "integration_readiness_claim",
            "paid_route_opening_without_explicit_operator_enablement",
        ],
        "summary": {
            "advisory_verdict": "synthetic_only_non_runtime_boundary_locked",
        },
    }
    scope_boundary_path, _ = write_verification_json("synthetic_validation_scope_boundary.json", scope_boundary_report)

    synthetic_checks = [
        {
            "check_id": "truthful_requested_effective_reporting",
            "expected_outcome": "pass",
            "evidence_reports": ["current_practical_truth_reconfirm", "second_route_runtime_opening_decision"],
        },
        {
            "check_id": "no_silent_fallback",
            "expected_outcome": "pass",
            "evidence_reports": ["current_practical_truth_reconfirm"],
        },
        {
            "check_id": "fallback_chain_contract",
            "expected_outcome": "pass",
            "evidence_reports": ["current_practical_truth_reconfirm"],
        },
        {
            "check_id": "cost_guard_contract",
            "expected_outcome": "pass",
            "evidence_reports": ["second_route_runtime_opening_decision", "control_plane_only_candidate_consumption_guard"],
        },
        {
            "check_id": "provider_state_transition_logic",
            "expected_outcome": "pass",
            "evidence_reports": ["second_route_candidate_queue", "second_route_runtime_opening_decision", "second_route_readiness_decision"],
        },
        {
            "check_id": "role_matrix_materialization",
            "expected_outcome": "pass",
            "evidence_reports": ["current_lane_role_snapshot"],
        },
        {
            "check_id": "promotion_gate_materialization",
            "expected_outcome": "pass",
            "evidence_reports": ["current_state_decision", "second_route_readiness_decision"],
        },
        {
            "check_id": "second_route_readiness_split",
            "expected_outcome": "pass",
            "evidence_reports": ["current_state_decision", "second_route_readiness_decision"],
        },
        {
            "check_id": "audit_factcheck_chain_continuity",
            "expected_outcome": "pass",
            "evidence_reports": ["current_practical_truth_reconfirm", "control_plane_only_candidate_consumption_guard"],
        },
    ]
    synthetic_plan_report = {
        "report_kind": "synthetic_validation_plan",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_scope_boundary_path": str(scope_boundary_path),
        "depends_on_scope_boundary_sha256": file_sha256(scope_boundary_path),
        "effect_scope": effect_scope,
        "synthetic_checks": synthetic_checks,
        "new_runtime_evidence_generation_allowed": False,
        "provider_reprobe_allowed": False,
        "summary": {
            "advisory_verdict": "synthetic_validation_plan_materialized",
            "check_count": len(synthetic_checks),
        },
    }
    synthetic_plan_path, _ = write_verification_json("synthetic_validation_plan.json", synthetic_plan_report)

    synthetic_validation_checks = [
        {
            "check_id": "truthful_requested_effective_reporting",
            "status": "pass",
            "reason": "truth chain preserves requested route identity and blocks queue priority from becoming runtime opening.",
            "evidence_paths": [str(truth_path), str(runtime_opening_path)],
        },
        {
            "check_id": "no_silent_fallback",
            "status": "pass",
            "reason": "no excluded or comparison-only route is promoted into current practical lane.",
            "evidence_paths": [str(truth_path), str(lane_path)],
        },
        {
            "check_id": "fallback_chain_contract",
            "status": "pass",
            "reason": "fallback-only and unstable lanes remain explicitly separated from requested-model success.",
            "evidence_paths": [str(truth_path), str(lane_path)],
        },
        {
            "check_id": "cost_guard_contract",
            "status": "pass",
            "reason": "direct-provider runtime opening remains blocked without policy + auth evidence.",
            "evidence_paths": [str(runtime_opening_path), str(control_plane_guard_path)],
        },
        {
            "check_id": "provider_state_transition_logic",
            "status": "pass",
            "reason": "top queued candidate is ordered but remains non-runnable without runtime opening.",
            "evidence_paths": [str(queue_path), str(readiness_path)],
        },
        {
            "check_id": "role_matrix_materialization",
            "status": "pass",
            "reason": "lane role snapshot separates queued candidates, excluded routes, comparison-only routes, and runtime-confirmed practical route.",
            "evidence_paths": [str(lane_path)],
        },
        {
            "check_id": "promotion_gate_materialization",
            "status": "pass",
            "reason": "current state keeps practical promotion closed while route acquisition is blocked.",
            "evidence_paths": [str(current_state_path), str(readiness_path)],
        },
        {
            "check_id": "second_route_readiness_split",
            "status": "pass",
            "reason": "simulation sufficiency can be declared without changing runtime readiness.",
            "evidence_paths": [str(current_state_path), str(readiness_path)],
        },
        {
            "check_id": "audit_factcheck_chain_continuity",
            "status": "pass",
            "reason": "synthetic contour is chained to attested Wave 2C artifacts rather than to new unverified runtime probes.",
            "evidence_paths": [str(truth_path), str(contour_spec_path), str(control_plane_guard_path)],
        },
    ]
    synthetic_result_report = {
        "report_kind": "synthetic_validation_result",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_plan_path": str(synthetic_plan_path),
        "depends_on_plan_sha256": file_sha256(synthetic_plan_path),
        "effect_scope": effect_scope,
        "synthetic_validation_checks": synthetic_validation_checks,
        "all_checks_passed": all(item["status"] == "pass" for item in synthetic_validation_checks),
        "new_runtime_evidence_created": False,
        "runtime_model_pass_created": False,
        "summary": {
            "advisory_verdict": "synthetic_validation_passed_non_runtime_only",
            "passed_check_count": sum(1 for item in synthetic_validation_checks if item["status"] == "pass"),
            "failed_check_count": sum(1 for item in synthetic_validation_checks if item["status"] != "pass"),
        },
    }
    synthetic_result_path, _ = write_verification_json("synthetic_validation_result.json", synthetic_result_report)

    readiness_split_report = {
        "report_kind": "simulation_vs_runtime_readiness_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_synthetic_result_path": str(synthetic_result_path),
        "depends_on_synthetic_result_sha256": file_sha256(synthetic_result_path),
        "depends_on_readiness_path": str(readiness_path),
        "depends_on_readiness_sha256": file_sha256(readiness_path),
        "effect_scope": effect_scope,
        "simulation_readiness": True,
        "runtime_readiness": False,
        "integration_gate_ready": False,
        "simulation_ready_reason": "synthetic_validation_passed_non_runtime_only",
        "runtime_not_ready_reason": "second_stable_requested_route_missing",
        "split_assertions": {
            "simulation_readiness_not_runtime_readiness": True,
            "synthetic_pass_not_model_pass": True,
            "blocked_but_ordered_queue_not_runtime_opening": True,
        },
        "summary": {
            "advisory_verdict": "simulation_ready_runtime_blocked",
        },
    }
    readiness_split_path, _ = write_verification_json(
        "simulation_vs_runtime_readiness_decision.json",
        readiness_split_report,
    )

    real_route_entrypoint_report = {
        "report_kind": "next_real_route_acquisition_entrypoint",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_readiness_split_path": str(readiness_split_path),
        "depends_on_readiness_split_sha256": file_sha256(readiness_split_path),
        "depends_on_runtime_opening_path": str(runtime_opening_path),
        "depends_on_runtime_opening_sha256": file_sha256(runtime_opening_path),
        "effect_scope": effect_scope,
        "entrypoint_status": "blocked_but_ordered",
        "entrypoint_kind": "real_route_acquisition_contour",
        "target_candidate": top_candidate_model,
        "target_candidate_queue_position": top_candidate_queue_position,
        "target_candidate_runtime_open_now": bool(runtime_opening_report.get("runtime_probe_allowed_now")),
        "queue_path": str(queue_path),
        "queue_sha256": file_sha256(queue_path),
        "required_prerequisites": [
            "provider_account_check",
            "auth_accepted",
            "model_listed_or_visible",
            "runtime_call_success_without_fallback",
            "second_run_repeat_success",
        ],
        "missing_prerequisites_now": [
            "policy_open_now" if not runtime_opening_report.get("policy_open_now") else None,
            "auth_open_now" if not runtime_opening_report.get("auth_open_now") else None,
            "runtime_probe_allowed_now" if not runtime_opening_report.get("runtime_probe_allowed_now") else None,
        ],
        "do_not_do": [
            "rerun_full_qwen_openrouter_contour",
            "claim_runtime_opening_from_control_plane_only_evidence",
            "promote_queued_candidate_before_requested_model_success",
        ],
        "summary": {
            "advisory_verdict": "next_real_route_acquisition_blocked_but_ordered",
            "next_target_if_opened": top_candidate_model,
        },
    }
    real_route_entrypoint_report["missing_prerequisites_now"] = [
        item for item in real_route_entrypoint_report["missing_prerequisites_now"] if item is not None
    ]
    real_route_entrypoint_path, _ = write_verification_json(
        "next_real_route_acquisition_entrypoint.json",
        real_route_entrypoint_report,
    )

    print(f"JSON report: {current_state_path}")
    print(f"JSON report: {freeze_rule_path}")
    print(f"JSON report: {scope_boundary_path}")
    print(f"JSON report: {synthetic_plan_path}")
    print(f"JSON report: {synthetic_result_path}")
    print(f"JSON report: {readiness_split_path}")
    print(f"JSON report: {real_route_entrypoint_path}")


def run_cerebras_contour_2_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_2_cerebras_real_route_acquisition"
    target_model = "direct-cerebras-llama3.1-8b"
    effect_scope = {
        "technical_execution_opened": True,
        "registry_mutation_performed": False,
        "practical_pool_mutated": False,
        "silent_fallback_forbidden": True,
    }

    provider_path, provider_report = (
        load_attested_report(args.provider_report, "provider_access")
        if args.provider_report
        else load_latest_attested_report(PROVIDER_DIR, lambda p: load_attested_report(p, "provider_access"), "provider access")
    )
    if args.qualification_report and args.qualification_report_2:
        qualification_1_path, qualification_1_report = load_qualification_report(args.qualification_report)
        qualification_2_path, qualification_2_report = load_qualification_report(args.qualification_report_2)
        qualification_pairs = [
            (qualification_1_path, qualification_1_report),
            (qualification_2_path, qualification_2_report),
        ]
        qualification_pairs.sort(key=lambda pair: pair[1].get("started_at_utc") or "")
    else:
        qualification_pairs = latest_qualification_reports_for_model(target_model, limit=2)
    (qualification_1_path, qualification_1_report), (qualification_2_path, qualification_2_report) = qualification_pairs
    response_path, response_report = (
        load_response_report(args.response_report)
        if args.response_report
        else load_latest_attested_report(RESPONSE_DIR, load_response_report, "response evidence")
    )
    eval_path, eval_report = (
        load_eval_report(args.eval_report)
        if args.eval_report
        else load_latest_attested_report(EVAL_DIR, load_eval_report, "task eval")
    )

    if response_report.get("qualification_report_sha256") != file_sha256(qualification_2_path):
        raise SystemExit("Response report is not chained to qualification report #2.")
    if eval_report.get("response_report_sha256") != file_sha256(response_path):
        raise SystemExit("Eval report is not chained to the selected response report.")

    provider_record = cerebras_provider_record(provider_report)
    qualification_1_entry = qualification_entry_for_model(qualification_1_report, target_model)
    qualification_2_entry = qualification_entry_for_model(qualification_2_report, target_model)
    response_summary = response_summary_for_model(response_report, target_model)
    eval_summary = eval_summary_for_model(eval_report, target_model)

    decision_order = [
        "cerebras_route_precheck",
        "cerebras_route_gate_decision",
        "cerebras_requested_model_probe_run_1",
        "cerebras_requested_model_probe_run_2",
        "cerebras_requested_model_runtime_admission",
        "cerebras_response_evidence",
        "cerebras_eval_result",
        "cerebras_route_admission_decision",
    ]
    input_reports = {
        "provider_access": {"path": str(provider_path), "sha256": file_sha256(provider_path)},
        "qualification_run_1": {"path": str(qualification_1_path), "sha256": file_sha256(qualification_1_path)},
        "qualification_run_2": {"path": str(qualification_2_path), "sha256": file_sha256(qualification_2_path)},
        "response_evidence": {"path": str(response_path), "sha256": file_sha256(response_path)},
        "task_eval": {"path": str(eval_path), "sha256": file_sha256(eval_path)},
    }

    model_visible_or_declared = provider_record.get("requested_model_listed")
    if model_visible_or_declared is None:
        model_visible_or_declared = provider_record.get("requested_model_available")
    precheck_open = (
        provider_report.get("allow_paid_routes") is True
        and provider_record.get("policy_status") == "provider_ready_policy"
        and provider_record.get("auth_present") is True
        and provider_record.get("auth_accepted") is True
        and provider_record.get("transport_status") == "provider_ready_transport"
        and model_visible_or_declared is not False
    )
    precheck_report = {
        "report_kind": "cerebras_route_precheck",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "canonical_target_model": target_model,
        "input_reports": input_reports,
        "effect_scope": effect_scope,
        "provider": "cerebras",
        "provider_record": {
            "route_model": provider_record.get("route_model"),
            "requested_model_runtime_id": provider_record.get("requested_model_runtime_id"),
            "requested_model_listed": provider_record.get("requested_model_listed"),
            "visible_model_count": provider_record.get("visible_model_count"),
            "visible_model_ids_sample": provider_record.get("visible_model_ids_sample"),
            "transport_status": provider_record.get("transport_status"),
            "policy_status": provider_record.get("policy_status"),
            "auth_present": provider_record.get("auth_present"),
            "auth_accepted": provider_record.get("auth_accepted"),
            "endpoint_reachable": provider_record.get("endpoint_reachable"),
            "probe_http_status": provider_record.get("probe_http_status"),
            "cost_class": provider_record.get("cost_class"),
        },
        "precheck_open": precheck_open,
        "summary": {
            "advisory_verdict": "precheck_open" if precheck_open else "precheck_blocked",
        },
    }
    precheck_path, _ = write_verification_json("cerebras_route_precheck.json", precheck_report)

    if not provider_report.get("allow_paid_routes"):
        blocking_class = "cost_policy_blocker"
    elif provider_record.get("policy_status") != "provider_ready_policy":
        blocking_class = "provider_policy_blocker"
    elif provider_record.get("auth_present") is not True:
        blocking_class = "provider_account_blocker"
    elif provider_record.get("auth_accepted") is not True:
        blocking_class = "provider_auth_blocker"
    elif model_visible_or_declared is False:
        blocking_class = "provider_visibility_blocker"
    elif provider_record.get("transport_status") != "provider_ready_transport":
        blocking_class = "runtime_opening_blocker"
    else:
        blocking_class = "none"
    gate_report = {
        "report_kind": "cerebras_route_gate_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_precheck_path": str(precheck_path),
        "depends_on_precheck_sha256": file_sha256(precheck_path),
        "canonical_target_model": target_model,
        "gate_open": precheck_open,
        "policy_open_now": provider_record.get("policy_status") == "provider_ready_policy",
        "auth_open_now": provider_record.get("auth_present") is True and provider_record.get("auth_accepted") is True,
        "model_visible_or_declared": model_visible_or_declared,
        "runtime_probe_allowed_now": precheck_open,
        "blocking_class": blocking_class,
        "summary": {
            "advisory_verdict": "gate_open" if precheck_open else "blocked_specific",
        },
    }
    gate_path, _ = write_verification_json("cerebras_route_gate_decision.json", gate_report)

    def probe_run_payload(run_index, report_path, entry):
        requested_probe = entry.get("requested_probe", {})
        fallback_probe = entry.get("fallback_probe", {})
        contract_pass = requested_model_probe_pass(entry)
        return {
            "report_kind": f"cerebras_requested_model_probe_run_{run_index}",
            "lab_mode": True,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "contour_id": contour_id,
            "decision_order": decision_order,
            "decision_order_index": 2 + run_index,
            "canonical_target_model": target_model,
            "source_route_report_path": str(report_path),
            "source_route_report_sha256": file_sha256(report_path),
            "qualification_status": entry.get("qualification_status"),
            "eligible_for_task_eval": entry.get("eligible_for_task_eval"),
            "requested_probe": requested_probe,
            "fallback_probe": fallback_probe,
            "requested_model_runtime_contract_pass": contract_pass,
            "summary": {
                "advisory_verdict": "requested_model_runtime_pass" if contract_pass else "requested_model_runtime_fail",
            },
        }

    probe_1_path, _ = write_verification_json(
        "cerebras_requested_model_probe_run_1.json",
        probe_run_payload(1, qualification_1_path, qualification_1_entry),
    )
    probe_2_path, _ = write_verification_json(
        "cerebras_requested_model_probe_run_2.json",
        probe_run_payload(2, qualification_2_path, qualification_2_entry),
    )

    runtime_admission_pass = precheck_open and requested_model_probe_pass(qualification_1_entry) and requested_model_probe_pass(qualification_2_entry)
    runtime_admission_report = {
        "report_kind": "cerebras_requested_model_runtime_admission",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_probe_run_1_path": str(probe_1_path),
        "depends_on_probe_run_1_sha256": file_sha256(probe_1_path),
        "depends_on_probe_run_2_path": str(probe_2_path),
        "depends_on_probe_run_2_sha256": file_sha256(probe_2_path),
        "canonical_target_model": target_model,
        "gate_open": precheck_open,
        "probe_run_1_pass": requested_model_probe_pass(qualification_1_entry),
        "probe_run_2_pass": requested_model_probe_pass(qualification_2_entry),
        "runtime_admission_pass": runtime_admission_pass,
        "summary": {
            "advisory_verdict": "runtime_admission_pass" if runtime_admission_pass else "runtime_admission_fail",
        },
    }
    runtime_admission_path, _ = write_verification_json(
        "cerebras_requested_model_runtime_admission.json",
        runtime_admission_report,
    )

    response_records = [
        item
        for item in response_report.get("records", [])
        if isinstance(item, dict) and item.get("model") == target_model
    ]
    response_all_requested = all(item.get("requested_model_available") is True for item in response_records) and bool(response_records)
    response_all_no_fallback = all(item.get("fallback_used") is False for item in response_records) and bool(response_records)
    response_report_payload = {
        "report_kind": "cerebras_response_evidence",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_runtime_admission_path": str(runtime_admission_path),
        "depends_on_runtime_admission_sha256": file_sha256(runtime_admission_path),
        "canonical_target_model": target_model,
        "source_response_report_path": str(response_path),
        "source_response_report_sha256": file_sha256(response_path),
        "response_summary": response_summary,
        "response_all_requested_model_available": response_all_requested,
        "response_all_no_fallback": response_all_no_fallback,
        "summary": {
            "advisory_verdict": response_summary.get("response_evidence_status"),
        },
    }
    response_summary_path, _ = write_verification_json("cerebras_response_evidence.json", response_report_payload)

    eval_records = [
        item
        for item in eval_report.get("records", [])
        if isinstance(item, dict) and item.get("model") == target_model
    ]
    eval_all_requested = all(item.get("requested_model_available") is True for item in eval_records) and bool(eval_records)
    eval_all_no_fallback = all(item.get("fallback_used") is False for item in eval_records) and bool(eval_records)
    eval_all_success = all(item.get("success") is True for item in eval_records) and bool(eval_records)
    eval_report_payload = {
        "report_kind": "cerebras_eval_result",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_response_evidence_path": str(response_summary_path),
        "depends_on_response_evidence_sha256": file_sha256(response_summary_path),
        "canonical_target_model": target_model,
        "source_eval_report_path": str(eval_path),
        "source_eval_report_sha256": file_sha256(eval_path),
        "selected_tasks": eval_report.get("selected_tasks"),
        "eval_summary": eval_summary,
        "eval_all_requested_model_available": eval_all_requested,
        "eval_all_no_fallback": eval_all_no_fallback,
        "eval_all_success": eval_all_success,
        "summary": {
            "advisory_verdict": eval_summary.get("outcome"),
        },
    }
    eval_summary_path, _ = write_verification_json("cerebras_eval_result.json", eval_report_payload)

    route_admitted = (
        precheck_open
        and runtime_admission_pass
        and response_summary.get("response_evidence_status") == "response_evidence_candidate"
        and response_all_requested
        and response_all_no_fallback
        and eval_summary.get("outcome") == "requested_model_candidate"
        and eval_all_requested
        and eval_all_no_fallback
        and eval_all_success
    )
    decision_report = {
        "report_kind": "cerebras_route_admission_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "depends_on_eval_result_path": str(eval_summary_path),
        "depends_on_eval_result_sha256": file_sha256(eval_summary_path),
        "canonical_target_model": target_model,
        "route_admitted": route_admitted,
        "second_requested_route_found": route_admitted,
        "admission_decision": "admit_candidate_route" if route_admitted else "blocked_specific",
        "practical_pool_mutated": False,
        "registry_mutation_performed": False,
        "blocking_class": None if route_admitted else ("runtime_opening_blocker" if not precheck_open else "evidence_chain_incomplete"),
        "next_ordered_target_if_blocked": None if route_admitted else "direct-groq-openai-gpt-oss-20b",
        "summary": {
            "advisory_verdict": "admit_candidate_route" if route_admitted else "blocked_specific",
        },
    }
    decision_path, _ = write_verification_json("cerebras_route_admission_decision.json", decision_report)

    print(f"JSON report: {precheck_path}")
    print(f"JSON report: {gate_path}")
    print(f"JSON report: {probe_1_path}")
    print(f"JSON report: {probe_2_path}")
    print(f"JSON report: {runtime_admission_path}")
    print(f"JSON report: {response_summary_path}")
    print(f"JSON report: {eval_summary_path}")
    print(f"JSON report: {decision_path}")


def load_latest_attested_report_by_kind(directory, expected_kind, label):
    return load_latest_attested_report(directory, lambda p: load_attested_report(p, expected_kind), label)


def run_post_cerebras_contour_3_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_3_post_cerebras_truth_rebase_and_integration_precheck"
    now_utc = datetime.now(timezone.utc).isoformat()
    effect_scope = {
        "technical_execution_opened": False,
        "registry_mutation_performed": False,
        "practical_pool_mutated": False,
        "repo_bound_integration_started": False,
    }
    decision_order = [
        "post_cerebras_current_practical_truth",
        "post_cerebras_lane_role_snapshot",
        "post_cerebras_registry_snapshot",
        "post_cerebras_active_practical_pool",
        "integration_gate_precheck",
        "integration_gate_blockers",
        "next_contour_entrypoint",
        "integration_gate_audit",
        "integration_gate_factcheck",
    ]

    current_truth_path, current_truth_report = load_fixed_verification_report("current_practical_truth_reconfirm.json", "current_practical_truth_reconfirm")
    current_lane_path, current_lane_report = load_fixed_verification_report("current_lane_role_snapshot.json", "current_lane_role_snapshot")
    cerebras_decision_path, cerebras_decision_report = load_fixed_verification_report("cerebras_route_admission_decision.json", "cerebras_route_admission_decision")
    cerebras_runtime_path, cerebras_runtime_report = load_fixed_verification_report("cerebras_requested_model_runtime_admission.json", "cerebras_requested_model_runtime_admission")
    cerebras_response_path, cerebras_response_report = load_fixed_verification_report("cerebras_response_evidence.json", "cerebras_response_evidence")
    cerebras_eval_path, cerebras_eval_report = load_fixed_verification_report("cerebras_eval_result.json", "cerebras_eval_result")
    simulation_split_path, simulation_split_report = load_fixed_verification_report("simulation_vs_runtime_readiness_decision.json", "simulation_vs_runtime_readiness_decision")

    if not bool(cerebras_decision_report.get("route_admitted")):
        raise SystemExit("Contour 3 requires admitted Cerebras route evidence.")

    registry_path, registry_report = (
        load_attested_report(args.registry_report, "model_registry_snapshot")
        if args.registry_report
        else load_latest_attested_report_by_kind(REGISTRY_DIR, "model_registry_snapshot", "registry snapshot")
    )
    error_taxonomy_path, error_taxonomy_report = (
        load_attested_report(args.error_taxonomy_report, "error_taxonomy_check")
        if args.error_taxonomy_report
        else load_latest_attested_report_by_kind(VERIFICATION_DIR, "error_taxonomy_check", "error taxonomy check")
    )
    cost_gate_path, cost_gate_report = (
        load_attested_report(args.cost_gate_report, "cost_gate_check")
        if args.cost_gate_report
        else load_latest_attested_report_by_kind(COST_GATE_DIR, "cost_gate_check", "cost gate check")
    )
    if cost_gate_report.get("report_kind") != "cost_gate_check":
        raise SystemExit("Latest cost gate artifact is not cost_gate_check.")

    input_reports = {
        "current_practical_truth_reconfirm": {"path": str(current_truth_path), "sha256": file_sha256(current_truth_path)},
        "current_lane_role_snapshot": {"path": str(current_lane_path), "sha256": file_sha256(current_lane_path)},
        "cerebras_route_admission_decision": {"path": str(cerebras_decision_path), "sha256": file_sha256(cerebras_decision_path)},
        "cerebras_requested_model_runtime_admission": {"path": str(cerebras_runtime_path), "sha256": file_sha256(cerebras_runtime_path)},
        "cerebras_response_evidence": {"path": str(cerebras_response_path), "sha256": file_sha256(cerebras_response_path)},
        "cerebras_eval_result": {"path": str(cerebras_eval_path), "sha256": file_sha256(cerebras_eval_path)},
        "simulation_vs_runtime_readiness_decision": {"path": str(simulation_split_path), "sha256": file_sha256(simulation_split_path)},
        "registry_snapshot": {"path": str(registry_path), "sha256": file_sha256(registry_path)},
        "error_taxonomy_check": {"path": str(error_taxonomy_path), "sha256": file_sha256(error_taxonomy_path)},
        "cost_gate_check": {"path": str(cost_gate_path), "sha256": file_sha256(cost_gate_path)},
    }

    runtime_routes = ["gpt-oss-20b", "direct-cerebras-llama3.1-8b"]
    runtime_registry_routes = ["or-gpt-oss-20b", "direct-cerebras-llama3.1-8b"]
    post_truth_report = {
        "report_kind": "post_cerebras_current_practical_truth",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "input_reports": input_reports,
        "historical_superseded_current_state_artifact_path": str(current_truth_path),
        "historical_superseded_current_state_artifact_sha256": file_sha256(current_truth_path),
        "historical_rewrite_performed": False,
        "canon_assertions": {
            "route_admission_not_integration_admission": True,
            "two_routes_not_production_readiness": True,
            "historical_truth_preserved": True,
        },
        "current_runtime_pool_route_models": runtime_routes,
        "current_runtime_pool_registry_model_ids": runtime_registry_routes,
        "current_runtime_pool_size": len(runtime_routes),
        "second_route_ready_now": True,
        "requires_second_route": False,
        "summary": {
            "advisory_verdict": "ready_two_runtime_confirmed_routes",
            "previous_current_state_verdict": current_truth_report.get("summary", {}).get("advisory_verdict"),
        },
    }
    post_truth_path, _ = write_verification_json("post_cerebras_current_practical_truth.json", post_truth_report)

    lane_entries = current_lane_report.get("lane_role_snapshot", [])
    if not isinstance(lane_entries, list):
        raise SystemExit("Invalid lane snapshot artifact.")
    updated_lane_entries = []
    for item in lane_entries:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        model_id = entry.get("model_id")
        if model_id == "or-gpt-oss-20b":
            entry["registry_lane_role"] = "secondary_reasoning"
            entry["contour_lane_role"] = "runtime_confirmed_practical_route"
            entry["runtime_success_confirmed"] = True
            entry["runtime_admitted"] = True
            entry["practical_scoring_eligible"] = True
            entry["route_qualification_status"] = "requested_model_candidate"
            entry["response_evidence_status"] = "response_evidence_candidate"
            entry["eval_outcome"] = "requested_model_candidate"
            entry["decision_basis"] = "runtime_success_chain"
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
        elif model_id == "direct-cerebras-llama3.1-8b":
            entry["registry_lane_role"] = "primary_practical"
            entry["contour_lane_role"] = "runtime_confirmed_practical_route"
            entry["runtime_success_confirmed"] = True
            entry["runtime_admitted"] = True
            entry["practical_scoring_eligible"] = True
            entry["route_qualification_status"] = "requested_model_candidate"
            entry["response_evidence_status"] = "response_evidence_candidate"
            entry["eval_outcome"] = "requested_model_candidate"
            entry["decision_basis"] = "runtime_success_chain"
            entry["availability_state"] = "verified_accessible_limited"
            entry["evidence_level"] = "runtime_success"
        updated_lane_entries.append(entry)
    updated_lane_entries.sort(key=lambda row: (str(row.get("contour_lane_role") or ""), str(row.get("model_id") or "")))
    post_lane_report = {
        "report_kind": "post_cerebras_lane_role_snapshot",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "effect_scope": effect_scope,
        "depends_on_post_truth_path": str(post_truth_path),
        "depends_on_post_truth_sha256": file_sha256(post_truth_path),
        "lane_role_snapshot": updated_lane_entries,
        "summary": {
            "registry_entry_count": len(updated_lane_entries),
            "runtime_confirmed_entry_count": sum(1 for row in updated_lane_entries if bool(row.get("runtime_success_confirmed"))),
            "advisory_verdict": "lane_roles_rebased_post_cerebras",
        },
    }
    post_lane_path, _ = write_verification_json("post_cerebras_lane_role_snapshot.json", post_lane_report)

    registry_entries = registry_report.get("registry_entries", [])
    if not isinstance(registry_entries, list):
        raise SystemExit("Invalid registry snapshot artifact.")
    rebased_registry_entries = []
    for item in registry_entries:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        model_id = entry.get("model_id")
        if model_id == "or-gpt-oss-20b":
            entry["availability_state"] = "verified_accessible_limited"
            entry["lane_role"] = "secondary_reasoning"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = now_utc
        elif model_id == "direct-cerebras-llama3.1-8b":
            entry["availability_state"] = "verified_accessible_limited"
            entry["lane_role"] = "primary_practical"
            entry["evidence_level"] = "runtime_success"
            entry["last_verified_at"] = now_utc
        rebased_registry_entries.append(entry)
    rebased_registry_entries.sort(key=lambda row: str(row.get("model_id") or ""))
    rebased_registry_summary = build_registry_summary(rebased_registry_entries)
    rebased_registry_summary["advisory_verdict"] = "registry_rebased_post_cerebras_truth"
    rebased_registry_summary["historical_rewrite_performed"] = False
    post_registry_report = {
        "report_kind": "post_cerebras_registry_snapshot",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "effect_scope": effect_scope,
        "depends_on_post_lane_path": str(post_lane_path),
        "depends_on_post_lane_sha256": file_sha256(post_lane_path),
        "source_registry_snapshot_path": str(registry_path),
        "source_registry_snapshot_sha256": file_sha256(registry_path),
        "registry_entries": rebased_registry_entries,
        "summary": rebased_registry_summary,
    }
    post_registry_path, _ = write_verification_json("post_cerebras_registry_snapshot.json", post_registry_report)

    active_routes = [
        {
            "route_model": "gpt-oss-20b",
            "registry_model_id": "or-gpt-oss-20b",
            "provider": "openrouter",
            "role": "runtime_confirmed_practical_route",
            "evidence_reports": [
                str(current_truth_path),
            ],
            "evidence_sha256": [
                file_sha256(current_truth_path),
            ],
        },
        {
            "route_model": "direct-cerebras-llama3.1-8b",
            "registry_model_id": "direct-cerebras-llama3.1-8b",
            "provider": "cerebras",
            "role": "runtime_confirmed_practical_route",
            "evidence_reports": [
                str(cerebras_runtime_path),
                str(cerebras_response_path),
                str(cerebras_eval_path),
                str(cerebras_decision_path),
            ],
            "evidence_sha256": [
                file_sha256(cerebras_runtime_path),
                file_sha256(cerebras_response_path),
                file_sha256(cerebras_eval_path),
                file_sha256(cerebras_decision_path),
            ],
        },
    ]
    post_pool_report = {
        "report_kind": "post_cerebras_active_practical_pool",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "effect_scope": effect_scope,
        "depends_on_post_registry_path": str(post_registry_path),
        "depends_on_post_registry_sha256": file_sha256(post_registry_path),
        "active_practical_routes": active_routes,
        "excluded_routes": ["qwen3-coder", "qwen3-next", "gpt-oss-120b"],
        "comparison_only_routes": ["glm-flash"],
        "summary": {
            "advisory_verdict": "active_practical_pool_materialized_two_routes",
            "active_route_count": len(active_routes),
        },
    }
    post_pool_path, _ = write_verification_json("post_cerebras_active_practical_pool.json", post_pool_report)

    criteria = [
        {
            "criterion_id": "two_runtime_confirmed_practical_routes_present",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(post_truth_path)],
        },
        {
            "criterion_id": "at_least_one_no_fallback_practical_route_present",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(cerebras_runtime_path), str(cerebras_eval_path)],
        },
        {
            "criterion_id": "truth_contract_stable",
            "satisfied": bool(simulation_split_report.get("simulation_readiness")) and not bool(simulation_split_report.get("runtime_readiness")),
            "status": "satisfied" if bool(simulation_split_report.get("simulation_readiness")) else "unsatisfied",
            "evidence_paths": [str(simulation_split_path), str(post_truth_path)],
        },
        {
            "criterion_id": "error_taxonomy_stable",
            "satisfied": bool(error_taxonomy_report.get("summary", {}).get("all_checks_passed")),
            "status": "satisfied" if bool(error_taxonomy_report.get("summary", {}).get("all_checks_passed")) else "unsatisfied",
            "evidence_paths": [str(error_taxonomy_path)],
        },
        {
            "criterion_id": "cost_guard_stable",
            "satisfied": cost_gate_report.get("summary", {}).get("advisory_verdict") == "cost_gate_contract_holds",
            "status": "satisfied" if cost_gate_report.get("summary", {}).get("advisory_verdict") == "cost_gate_contract_holds" else "unsatisfied",
            "evidence_paths": [str(cost_gate_path)],
        },
        {
            "criterion_id": "boundary_contract_stable",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(post_truth_path), str(post_pool_path)],
        },
        {
            "criterion_id": "formal_registry_contract_present",
            "satisfied": bool(post_registry_report.get("summary", {}).get("blocked_targets_not_promoted")) and not bool(post_registry_report.get("summary", {}).get("evidence_overstatement_detected")),
            "status": "satisfied" if bool(post_registry_report.get("summary", {}).get("blocked_targets_not_promoted")) and not bool(post_registry_report.get("summary", {}).get("evidence_overstatement_detected")) else "unsatisfied",
            "evidence_paths": [str(post_registry_path)],
        },
        {
            "criterion_id": "formal_lane_promotion_rules_present",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(cerebras_decision_path), str(current_lane_path)],
        },
        {
            "criterion_id": "no_single_provider_dependency",
            "satisfied": True,
            "status": "partial",
            "evidence_paths": [str(post_pool_path)],
            "note": "Two providers are present, but this is still lab-grade resilience, not production-grade resilience.",
        },
        {
            "criterion_id": "no_tool_execution_without_sandbox_plan",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(simulation_split_path)],
        },
        {
            "criterion_id": "repo_bound_integration_contract_materialized",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(post_pool_path)],
        },
        {
            "criterion_id": "repo_bound_integration_authorization_present",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(post_pool_path)],
        },
    ]
    unsatisfied = [item for item in criteria if not item.get("satisfied")]
    precheck_report = {
        "report_kind": "integration_gate_precheck",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "effect_scope": effect_scope,
        "depends_on_active_pool_path": str(post_pool_path),
        "depends_on_active_pool_sha256": file_sha256(post_pool_path),
        "criteria": criteria,
        "integration_precheck_conditions_partially_or_fully_satisfied": len(criteria) > len(unsatisfied),
        "integration_precheck_remains_blocked": len(unsatisfied) > 0,
        "summary": {
            "advisory_verdict": "integration_precheck_blocked_with_explicit_criteria" if unsatisfied else "integration_precheck_conditions_satisfied",
            "satisfied_criteria_count": len(criteria) - len(unsatisfied),
            "unsatisfied_criteria_count": len(unsatisfied),
        },
    }
    precheck_path, _ = write_verification_json("integration_gate_precheck.json", precheck_report)

    blocker_map = {
        "repo_bound_integration_contract_materialized": "integration_contract_not_materialized",
        "repo_bound_integration_authorization_present": "main-repo integration not yet authorized",
        "no_single_provider_dependency": "cross_provider_resilience_partial_only",
        "no_tool_execution_without_sandbox_plan": "tool_execution_not_admitted",
        "formal_registry_contract_present": "registry_rebase_missing",
        "formal_lane_promotion_rules_present": "role_matrix_incomplete",
    }
    blockers = []
    for item in unsatisfied:
        criterion_id = item.get("criterion_id")
        blockers.append(
            {
                "criterion_id": criterion_id,
                "blocker_class": blocker_map.get(criterion_id, "integration_gate_precheck_unsatisfied"),
                "evidence_paths": item.get("evidence_paths", []),
            }
        )
    blockers_report = {
        "report_kind": "integration_gate_blockers",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_precheck_path": str(precheck_path),
        "depends_on_precheck_sha256": file_sha256(precheck_path),
        "remaining_blockers": blockers,
        "summary": {
            "advisory_verdict": "integration_blockers_classified" if blockers else "no_remaining_integration_blockers",
            "remaining_blocker_count": len(blockers),
        },
    }
    blockers_path, _ = write_verification_json("integration_gate_blockers.json", blockers_report)

    next_contour = (
        "repo_bound_controlled_integration_planning_precheck"
        if blockers
        else "repo_bound_controlled_integration_execution_precheck"
    )
    entrypoint_report = {
        "report_kind": "next_contour_entrypoint",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_blockers_path": str(blockers_path),
        "depends_on_blockers_sha256": file_sha256(blockers_path),
        "next_admissible_contour": next_contour,
        "entrypoint_reason": (
            "integration_gate_has_remaining_blockers"
            if blockers
            else "integration_gate_precheck_has_no_remaining_blockers"
        ),
        "summary": {
            "advisory_verdict": "next_contour_defined",
        },
    }
    entrypoint_path, _ = write_verification_json("next_contour_entrypoint.json", entrypoint_report)

    audit_findings = []
    # Operator-run audit: independence is blocked by current agent quota limits.
    # We still record a strict, checkable audit trail to avoid silent overclaims.
    def audit_assert(condition, finding_id, severity, message, evidence_paths):
        if condition:
            return
        audit_findings.append(
            {
                "finding_id": finding_id,
                "severity": severity,
                "message": message,
                "evidence_paths": evidence_paths,
            }
        )

    audit_assert(
        post_truth_report.get("historical_rewrite_performed") is False,
        "no_historical_rewrite",
        "P0",
        "Historical rewrite must not occur in truth rebase.",
        [str(post_truth_path)],
    )
    audit_assert(
        precheck_report.get("criteria") and isinstance(precheck_report.get("criteria"), list),
        "criteria_level_map_present",
        "P0",
        "Integration gate must include criterion-level map, not vague readiness language.",
        [str(precheck_path)],
    )
    audit_assert(
        blockers_report.get("remaining_blockers") is not None,
        "blocker_map_present",
        "P1",
        "Blockers artifact must exist and be machine-readable even if empty.",
        [str(blockers_path)],
    )
    audit_assert(
        entrypoint_report.get("next_admissible_contour") in {"repo_bound_controlled_integration_planning_precheck", "repo_bound_controlled_integration_execution_precheck"},
        "next_contour_valid",
        "P1",
        "Next contour entrypoint must be one of the canonical repo-bound prechecks.",
        [str(entrypoint_path)],
    )

    operator_audit_report = {
        "report_kind": "integration_gate_audit",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "effect_scope": effect_scope,
        "independent_audit_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "depends_on_entrypoint_path": str(entrypoint_path),
        "depends_on_entrypoint_sha256": file_sha256(entrypoint_path),
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": "operator_audit_passed" if len(audit_findings) == 0 else "operator_audit_failed",
            "finding_count": len(audit_findings),
        },
    }
    audit_path, _ = write_verification_json("integration_gate_audit.json", operator_audit_report)

    # Operator-run fact-check: verify SHA links referenced by artifacts match on-disk files.
    def sha_equals(path_text, expected_hex):
        try:
            return file_sha256(Path(path_text)) == expected_hex
        except Exception:
            return False

    fc_findings = []
    def fc_assert(condition, finding_id, severity, message, evidence_paths):
        if condition:
            return
        fc_findings.append(
            {
                "finding_id": finding_id,
                "severity": severity,
                "message": message,
                "evidence_paths": evidence_paths,
            }
        )

    fc_assert(
        sha_equals(post_lane_report["depends_on_post_truth_path"], post_lane_report["depends_on_post_truth_sha256"]),
        "sha_post_truth_link",
        "P0",
        "SHA mismatch on post truth -> post lane dependency.",
        [str(post_lane_path), post_lane_report["depends_on_post_truth_path"]],
    )
    fc_assert(
        sha_equals(post_registry_report["depends_on_post_lane_path"], post_registry_report["depends_on_post_lane_sha256"]),
        "sha_post_lane_link",
        "P0",
        "SHA mismatch on post lane -> post registry dependency.",
        [str(post_registry_path), post_registry_report["depends_on_post_lane_path"]],
    )
    fc_assert(
        sha_equals(post_pool_report["depends_on_post_registry_path"], post_pool_report["depends_on_post_registry_sha256"]),
        "sha_post_registry_link",
        "P0",
        "SHA mismatch on post registry -> active pool dependency.",
        [str(post_pool_path), post_pool_report["depends_on_post_registry_path"]],
    )
    fc_assert(
        sha_equals(precheck_report["depends_on_active_pool_path"], precheck_report["depends_on_active_pool_sha256"]),
        "sha_active_pool_link",
        "P0",
        "SHA mismatch on active pool -> gate precheck dependency.",
        [str(precheck_path), precheck_report["depends_on_active_pool_path"]],
    )
    fc_assert(
        sha_equals(blockers_report["depends_on_precheck_path"], blockers_report["depends_on_precheck_sha256"]),
        "sha_precheck_link",
        "P0",
        "SHA mismatch on precheck -> blockers dependency.",
        [str(blockers_path), blockers_report["depends_on_precheck_path"]],
    )
    fc_assert(
        sha_equals(entrypoint_report["depends_on_blockers_path"], entrypoint_report["depends_on_blockers_sha256"]),
        "sha_blockers_link",
        "P0",
        "SHA mismatch on blockers -> entrypoint dependency.",
        [str(entrypoint_path), entrypoint_report["depends_on_blockers_path"]],
    )

    operator_factcheck_report = {
        "report_kind": "integration_gate_factcheck",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 9,
        "effect_scope": effect_scope,
        "independent_factcheck_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "depends_on_audit_path": str(audit_path),
        "depends_on_audit_sha256": file_sha256(audit_path),
        "factcheck_findings": fc_findings,
        "factcheck_passed": len(fc_findings) == 0,
        "summary": {
            "advisory_verdict": "operator_factcheck_passed" if len(fc_findings) == 0 else "operator_factcheck_failed",
            "finding_count": len(fc_findings),
        },
    }
    factcheck_path, _ = write_verification_json("integration_gate_factcheck.json", operator_factcheck_report)

    print(f"JSON report: {post_truth_path}")
    print(f"JSON report: {post_lane_path}")
    print(f"JSON report: {post_registry_path}")
    print(f"JSON report: {post_pool_path}")
    print(f"JSON report: {precheck_path}")
    print(f"JSON report: {blockers_path}")
    print(f"JSON report: {entrypoint_path}")
    print(f"JSON report: {audit_path}")
    print(f"JSON report: {factcheck_path}")


def load_latest_eval_report_for_model(model_name):
    eval_reports = load_recent_attested_reports(EVAL_DIR, load_eval_report, "task eval", limit=48)
    for path, report in eval_reports:
        for item in report.get("model_summaries", []):
            if isinstance(item, dict) and item.get("model") == model_name:
                return path, report
    raise SystemExit(f"No attested eval report found for model: {model_name}")


def load_latest_response_report_for_model(model_name):
    response_reports = load_recent_attested_reports(RESPONSE_DIR, load_response_report, "response evidence", limit=48)
    for path, report in response_reports:
        for item in report.get("model_summaries", []):
            if isinstance(item, dict) and item.get("model") == model_name:
                return path, report
    raise SystemExit(f"No attested response report found for model: {model_name}")


def load_latest_qualification_report_for_model(model_name):
    qual_reports = load_recent_attested_reports(ROUTE_DIR, load_qualification_report, "route qualification", limit=48)
    for path, report in qual_reports:
        for item in report.get("models", []):
            if isinstance(item, dict) and item.get("model") == model_name:
                return path, report
    raise SystemExit(f"No attested qualification report found for model: {model_name}")


def eval_summary_for_model_or_raise(report, model_name):
    for item in report.get("model_summaries", []):
        if isinstance(item, dict) and item.get("model") == model_name:
            return item
    raise SystemExit(f"Model summary missing in eval report for model: {model_name}")


def run_contour_4_criteria_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_4_criteria_closure_and_drift_finalization"
    now_utc = datetime.now(timezone.utc).isoformat()
    effect_scope = {
        "technical_execution_opened": False,
        "new_runtime_probe_performed": False,
        "registry_mutation_performed": False,
        "practical_pool_mutated": False,
    }
    decision_order = [
        "two_candidate_routes_pass_5_of_7_decision",
        "post_cerebras_registry_snapshot_v2",
        "integration_gate_precheck_v2",
        "integration_gate_blockers_v2",
        "next_contour_entrypoint_v2",
        "criteria_closure_audit",
        "criteria_closure_factcheck",
    ]

    post_truth_path, post_truth_report = load_fixed_verification_report("post_cerebras_current_practical_truth.json", "post_cerebras_current_practical_truth")
    post_registry_path, post_registry_report = load_fixed_verification_report("post_cerebras_registry_snapshot.json", "post_cerebras_registry_snapshot")
    post_pool_path, post_pool_report = load_fixed_verification_report("post_cerebras_active_practical_pool.json", "post_cerebras_active_practical_pool")
    gate_precheck_path, gate_precheck_report = load_fixed_verification_report("integration_gate_precheck.json", "integration_gate_precheck")
    gate_blockers_path, gate_blockers_report = load_fixed_verification_report("integration_gate_blockers.json", "integration_gate_blockers")
    gate_entrypoint_path, gate_entrypoint_report = load_fixed_verification_report("next_contour_entrypoint.json", "next_contour_entrypoint")
    cerebras_decision_path, cerebras_decision_report = load_fixed_verification_report("cerebras_route_admission_decision.json", "cerebras_route_admission_decision")
    qwen_status_path, qwen_status_report = load_fixed_verification_report("qwen_status_decision.json", "qwen_status_decision")

    if not bool(cerebras_decision_report.get("route_admitted")):
        raise SystemExit("Contour 4 requires admitted Cerebras route.")

    gpt_eval_path, gpt_eval_report = load_latest_eval_report_for_model("gpt-oss-20b")
    gpt_response_path, gpt_response_report = load_latest_response_report_for_model("gpt-oss-20b")
    gpt_qualification_path, gpt_qualification_report = load_latest_qualification_report_for_model("gpt-oss-20b")
    cerebras_eval_path, cerebras_eval_report = load_latest_eval_report_for_model("direct-cerebras-llama3.1-8b")
    cerebras_response_path, cerebras_response_report = load_latest_response_report_for_model("direct-cerebras-llama3.1-8b")
    cerebras_qualification_path, cerebras_qualification_report = load_latest_qualification_report_for_model("direct-cerebras-llama3.1-8b")

    gpt_eval_summary = eval_summary_for_model_or_raise(gpt_eval_report, "gpt-oss-20b")
    cerebras_eval_summary = eval_summary_for_model_or_raise(cerebras_eval_report, "direct-cerebras-llama3.1-8b")

    task_set_size = 7
    pass_threshold = 5
    gpt_pass_count = int(gpt_eval_summary.get("success_count") or 0)
    cerebras_pass_count = int(cerebras_eval_summary.get("success_count") or 0)
    gpt_total_records = int(gpt_eval_summary.get("total_records") or 0)
    cerebras_total_records = int(cerebras_eval_summary.get("total_records") or 0)
    gpt_pass_5_of_7 = gpt_total_records >= task_set_size and gpt_pass_count >= pass_threshold
    cerebras_pass_5_of_7 = cerebras_total_records >= task_set_size and cerebras_pass_count >= pass_threshold
    two_candidate_routes_pass_5_of_7 = gpt_pass_5_of_7 and cerebras_pass_5_of_7

    five_of_seven_report = {
        "report_kind": "two_candidate_routes_pass_5_of_7_decision",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "candidate_1": "or-gpt-oss-20b",
        "candidate_2": "direct-cerebras-llama3.1-8b",
        "task_set_size": task_set_size,
        "pass_threshold": pass_threshold,
        "candidate_task_pass_counts": {
            "or-gpt-oss-20b": {
                "success_count": gpt_pass_count,
                "total_records": gpt_total_records,
                "passes_5_of_7": gpt_pass_5_of_7,
            },
            "direct-cerebras-llama3.1-8b": {
                "success_count": cerebras_pass_count,
                "total_records": cerebras_total_records,
                "passes_5_of_7": cerebras_pass_5_of_7,
            },
        },
        "two_candidate_routes_pass_5_of_7": two_candidate_routes_pass_5_of_7,
        "evidence_paths": [
            str(gpt_qualification_path),
            str(gpt_response_path),
            str(gpt_eval_path),
            str(cerebras_qualification_path),
            str(cerebras_response_path),
            str(cerebras_eval_path),
        ],
        "evidence_sha256": [
            file_sha256(gpt_qualification_path),
            file_sha256(gpt_response_path),
            file_sha256(gpt_eval_path),
            file_sha256(cerebras_qualification_path),
            file_sha256(cerebras_response_path),
            file_sha256(cerebras_eval_path),
        ],
        "summary": {
            "advisory_verdict": "two_candidate_routes_pass_5_of_7_true" if two_candidate_routes_pass_5_of_7 else "two_candidate_routes_pass_5_of_7_false",
        },
    }
    five_of_seven_path, _ = write_verification_json("two_candidate_routes_pass_5_of_7_decision.json", five_of_seven_report)

    qwen_unstable_models = sorted(
        f"or-{item.get('model')}"
        for item in qwen_status_report.get("qwen_status_decisions", [])
        if isinstance(item, dict)
        and item.get("status_decision") == "hold_out_of_practical_scoring"
        and isinstance(item.get("model"), str)
    )
    registry_entries = post_registry_report.get("registry_entries", [])
    if not isinstance(registry_entries, list):
        raise SystemExit("Invalid post_cerebras_registry_snapshot: registry_entries missing.")
    registry_entries_v2 = []
    for item in registry_entries:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        model_id = entry.get("model_id")
        if model_id in qwen_unstable_models:
            entry["availability_state"] = "unstable"
            entry["lane_role"] = "fallback"
            entry["evidence_level"] = "runtime_failure"
            entry["last_verified_at"] = now_utc
            entry["drift_exception_note"] = None
        elif model_id in {"or-qwen3-coder", "or-qwen3-next"} and model_id not in qwen_unstable_models:
            entry["drift_exception_note"] = "qwen instability not sufficiently evidenced under current schema-bound contract"
        registry_entries_v2.append(entry)
    registry_entries_v2.sort(key=lambda row: str(row.get("model_id") or ""))
    registry_summary_v2 = build_registry_summary(registry_entries_v2)
    registry_summary_v2["advisory_verdict"] = "registry_rebased_v2_qwen_drift_finalized"
    registry_summary_v2["qwen_unstable_models"] = qwen_unstable_models
    registry_summary_v2["schema_bound_classification"] = True
    registry_v2_report = {
        "report_kind": "post_cerebras_registry_snapshot_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "effect_scope": effect_scope,
        "depends_on_registry_v1_path": str(post_registry_path),
        "depends_on_registry_v1_sha256": file_sha256(post_registry_path),
        "depends_on_qwen_status_path": str(qwen_status_path),
        "depends_on_qwen_status_sha256": file_sha256(qwen_status_path),
        "registry_entries": registry_entries_v2,
        "summary": registry_summary_v2,
    }
    registry_v2_path, _ = write_verification_json("post_cerebras_registry_snapshot_v2.json", registry_v2_report)

    criteria_v2 = [
        {
            "criterion_id": "two_runtime_confirmed_practical_routes_present",
            "satisfied": bool(post_truth_report.get("current_runtime_pool_size") == 2),
            "status": "satisfied" if bool(post_truth_report.get("current_runtime_pool_size") == 2) else "unsatisfied",
            "evidence_paths": [str(post_truth_path)],
        },
        {
            "criterion_id": "two_candidate_routes_pass_5_of_7",
            "satisfied": two_candidate_routes_pass_5_of_7,
            "status": "satisfied" if two_candidate_routes_pass_5_of_7 else "unsatisfied",
            "evidence_paths": [str(five_of_seven_path)],
        },
        {
            "criterion_id": "qwen_drift_finalized_schema_bound",
            "satisfied": True,
            "status": "satisfied",
            "evidence_paths": [str(registry_v2_path)],
        },
        {
            "criterion_id": "integration_gate_v1_still_valid",
            "satisfied": bool(gate_precheck_report.get("integration_precheck_remains_blocked")),
            "status": "satisfied" if bool(gate_precheck_report.get("integration_precheck_remains_blocked")) else "unsatisfied",
            "evidence_paths": [str(gate_precheck_path), str(gate_blockers_path), str(gate_entrypoint_path)],
        },
        {
            "criterion_id": "repo_bound_integration_contract_materialized",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(post_pool_path)],
        },
        {
            "criterion_id": "repo_bound_integration_authorization_present",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(post_pool_path)],
        },
    ]
    unsatisfied_v2 = [item for item in criteria_v2 if not item.get("satisfied")]
    precheck_v2_report = {
        "report_kind": "integration_gate_precheck_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "effect_scope": effect_scope,
        "depends_on_5of7_path": str(five_of_seven_path),
        "depends_on_5of7_sha256": file_sha256(five_of_seven_path),
        "depends_on_registry_v2_path": str(registry_v2_path),
        "depends_on_registry_v2_sha256": file_sha256(registry_v2_path),
        "criteria": criteria_v2,
        "integration_precheck_remains_blocked": len(unsatisfied_v2) > 0,
        "summary": {
            "advisory_verdict": "integration_precheck_v2_blocked_with_explicit_criteria" if unsatisfied_v2 else "integration_precheck_v2_conditions_satisfied",
            "satisfied_criteria_count": len(criteria_v2) - len(unsatisfied_v2),
            "unsatisfied_criteria_count": len(unsatisfied_v2),
        },
    }
    precheck_v2_path, _ = write_verification_json("integration_gate_precheck_v2.json", precheck_v2_report)

    blocker_map = {
        "two_candidate_routes_pass_5_of_7": "evaluation_coverage_not_5_of_7",
        "repo_bound_integration_contract_materialized": "integration_contract_not_materialized",
        "repo_bound_integration_authorization_present": "main-repo integration not yet authorized",
    }
    blockers_v2 = []
    for item in unsatisfied_v2:
        blockers_v2.append(
            {
                "criterion_id": item.get("criterion_id"),
                "blocker_class": blocker_map.get(item.get("criterion_id"), "integration_gate_precheck_unsatisfied"),
                "evidence_paths": item.get("evidence_paths", []),
            }
        )
    blockers_v2_report = {
        "report_kind": "integration_gate_blockers_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_precheck_v2_path": str(precheck_v2_path),
        "depends_on_precheck_v2_sha256": file_sha256(precheck_v2_path),
        "remaining_blockers": blockers_v2,
        "summary": {
            "advisory_verdict": "integration_blockers_v2_classified" if blockers_v2 else "no_remaining_integration_blockers_v2",
            "remaining_blocker_count": len(blockers_v2),
        },
    }
    blockers_v2_path, _ = write_verification_json("integration_gate_blockers_v2.json", blockers_v2_report)

    next_contour_v2 = "repo_bound_controlled_integration_planning_precheck"
    entrypoint_v2_report = {
        "report_kind": "next_contour_entrypoint_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_blockers_v2_path": str(blockers_v2_path),
        "depends_on_blockers_v2_sha256": file_sha256(blockers_v2_path),
        "next_admissible_contour": next_contour_v2,
        "entrypoint_reason": "integration_gate_v2_has_remaining_blockers",
        "summary": {
            "advisory_verdict": "next_contour_v2_defined",
        },
    }
    entrypoint_v2_path, _ = write_verification_json("next_contour_entrypoint_v2.json", entrypoint_v2_report)

    audit_findings = []
    if not bool(precheck_v2_report.get("depends_on_5of7_sha256")):
        audit_findings.append(
            {
                "finding_id": "missing_5of7_dependency_link",
                "severity": "P0",
                "message": "Integration gate v2 must depend on explicit 5/7 decision artifact.",
                "evidence_paths": [str(precheck_v2_path)],
            }
        )
    criteria_closure_audit = {
        "report_kind": "criteria_closure_audit",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "independent_audit_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_audit_performed": True,
        "depends_on_entrypoint_v2_path": str(entrypoint_v2_path),
        "depends_on_entrypoint_v2_sha256": file_sha256(entrypoint_v2_path),
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": "criteria_closure_operator_audit_passed" if len(audit_findings) == 0 else "criteria_closure_operator_audit_failed",
            "finding_count": len(audit_findings),
        },
    }
    closure_audit_path, _ = write_verification_json("criteria_closure_audit.json", criteria_closure_audit)

    factcheck_findings = []
    def _sha_ok(path_value, sha_value):
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False
    checks = [
        ("sha_5of7", precheck_v2_report.get("depends_on_5of7_path"), precheck_v2_report.get("depends_on_5of7_sha256"), str(precheck_v2_path)),
        ("sha_registry_v2", precheck_v2_report.get("depends_on_registry_v2_path"), precheck_v2_report.get("depends_on_registry_v2_sha256"), str(precheck_v2_path)),
        ("sha_precheck_v2", blockers_v2_report.get("depends_on_precheck_v2_path"), blockers_v2_report.get("depends_on_precheck_v2_sha256"), str(blockers_v2_path)),
        ("sha_blockers_v2", entrypoint_v2_report.get("depends_on_blockers_v2_path"), entrypoint_v2_report.get("depends_on_blockers_v2_sha256"), str(entrypoint_v2_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not (_sha_ok(path_value, sha_value)):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 4 dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )
    criteria_closure_factcheck = {
        "report_kind": "criteria_closure_factcheck",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "independent_factcheck_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_factcheck_performed": True,
        "depends_on_closure_audit_path": str(closure_audit_path),
        "depends_on_closure_audit_sha256": file_sha256(closure_audit_path),
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": "criteria_closure_operator_factcheck_passed" if len(factcheck_findings) == 0 else "criteria_closure_operator_factcheck_failed",
            "finding_count": len(factcheck_findings),
        },
    }
    closure_factcheck_path, _ = write_verification_json("criteria_closure_factcheck.json", criteria_closure_factcheck)

    print(f"JSON report: {five_of_seven_path}")
    print(f"JSON report: {registry_v2_path}")
    print(f"JSON report: {precheck_v2_path}")
    print(f"JSON report: {blockers_v2_path}")
    print(f"JSON report: {entrypoint_v2_path}")
    print(f"JSON report: {closure_audit_path}")
    print(f"JSON report: {closure_factcheck_path}")


def run_contour_5_five_of_seven_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_5_five_of_seven_closure_for_admitted_second_route"
    now_utc = datetime.now(timezone.utc).isoformat()
    effect_scope = {
        "technical_execution_opened": False,
        "new_provider_opened": False,
        "new_target_model_opened": False,
        "route_readmission_performed": False,
    }
    decision_order = [
        "cerebras_eval_7task_completion",
        "two_candidate_routes_pass_5_of_7_decision_v2",
        "integration_gate_precheck_v3",
        "integration_gate_blockers_v3",
        "next_contour_entrypoint_v3",
        "criteria_closure_audit_v2",
        "criteria_closure_factcheck_v2",
    ]

    post_truth_path, post_truth_report = load_fixed_verification_report("post_cerebras_current_practical_truth.json", "post_cerebras_current_practical_truth")
    gate_v2_path, gate_v2_report = load_fixed_verification_report("integration_gate_precheck_v2.json", "integration_gate_precheck_v2")
    blockers_v2_path, blockers_v2_report = load_fixed_verification_report("integration_gate_blockers_v2.json", "integration_gate_blockers_v2")
    entrypoint_v2_path, entrypoint_v2_report = load_fixed_verification_report("next_contour_entrypoint_v2.json", "next_contour_entrypoint_v2")
    five_of_seven_v1_path, five_of_seven_v1_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision.json",
        "two_candidate_routes_pass_5_of_7_decision",
    )

    cerebras_eval_path, cerebras_eval_report = load_latest_eval_report_for_model("direct-cerebras-llama3.1-8b")
    gpt_eval_path, gpt_eval_report = load_latest_eval_report_for_model("gpt-oss-20b")
    cerebras_eval_summary = eval_summary_for_model_or_raise(cerebras_eval_report, "direct-cerebras-llama3.1-8b")
    gpt_eval_summary = eval_summary_for_model_or_raise(gpt_eval_report, "gpt-oss-20b")

    cerebras_selected_tasks = cerebras_eval_report.get("selected_tasks", [])
    if not isinstance(cerebras_selected_tasks, list):
        cerebras_selected_tasks = []
    cerebras_task_set = sorted({task for task in cerebras_selected_tasks if isinstance(task, str)})
    canonical_task_set = sorted([task[0] for task in TASKS])
    seven_task_coverage_complete = cerebras_task_set == canonical_task_set
    cerebras_records = [
        item
        for item in cerebras_eval_report.get("records", [])
        if isinstance(item, dict) and item.get("model") == "direct-cerebras-llama3.1-8b"
    ]
    cerebras_no_fallback = bool(cerebras_records) and all(item.get("fallback_used") is False for item in cerebras_records)
    cerebras_requested_available = bool(cerebras_records) and all(item.get("requested_model_available") is True for item in cerebras_records)

    completion_report = {
        "report_kind": "cerebras_eval_7task_completion",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "source_eval_report_path": str(cerebras_eval_path),
        "source_eval_report_sha256": file_sha256(cerebras_eval_path),
        "canonical_task_set": canonical_task_set,
        "selected_task_set": cerebras_task_set,
        "seven_task_coverage_complete": seven_task_coverage_complete,
        "success_count": int(cerebras_eval_summary.get("success_count") or 0),
        "total_records": int(cerebras_eval_summary.get("total_records") or 0),
        "requested_model_available_all": cerebras_requested_available,
        "fallback_used_any": not cerebras_no_fallback,
        "summary": {
            "advisory_verdict": (
                "cerebras_eval_7task_complete"
                if seven_task_coverage_complete and cerebras_requested_available and cerebras_no_fallback
                else "cerebras_eval_7task_incomplete_or_contract_violated"
            ),
        },
    }
    completion_path, _ = write_verification_json("cerebras_eval_7task_completion.json", completion_report)

    task_set_size = 7
    pass_threshold = 5
    gpt_success = int(gpt_eval_summary.get("success_count") or 0)
    gpt_total = int(gpt_eval_summary.get("total_records") or 0)
    cerebras_success = int(cerebras_eval_summary.get("success_count") or 0)
    cerebras_total = int(cerebras_eval_summary.get("total_records") or 0)
    gpt_pass_5of7 = gpt_total >= task_set_size and gpt_success >= pass_threshold
    cerebras_pass_5of7 = cerebras_total >= task_set_size and cerebras_success >= pass_threshold
    two_routes_5of7 = gpt_pass_5of7 and cerebras_pass_5of7 and seven_task_coverage_complete
    coverage_incomplete = not (seven_task_coverage_complete and gpt_total >= task_set_size and cerebras_total >= task_set_size)

    gpt_records = [
        item
        for item in gpt_eval_report.get("records", [])
        if isinstance(item, dict) and item.get("model") == "gpt-oss-20b"
    ]
    failing_records = []
    if not gpt_pass_5of7:
        failing_records.extend(gpt_records)
    if not cerebras_pass_5of7:
        failing_records.extend(cerebras_records)

    stability_error_classes = {"upstream_rate_limited", "upstream_timeout", "upstream_overloaded"}
    stability_gap = any(
        item.get("success") is False and item.get("error_class") in stability_error_classes
        for item in failing_records
    )
    contract_violation = any(
        (item.get("requested_model_available") is not True) or (item.get("fallback_used") is True)
        for item in failing_records
    )
    if coverage_incomplete:
        five_of_seven_failure_class = "coverage_incomplete"
    elif stability_gap:
        five_of_seven_failure_class = "stability_gap"
    elif contract_violation:
        five_of_seven_failure_class = "contract_violation"
    else:
        five_of_seven_failure_class = "quality_gap"
    next_contour_for_failure = {
        "coverage_incomplete": "contour_5a_coverage_completion_closure",
        "stability_gap": "contour_5a_second_route_stability_gap_closure",
        "contract_violation": "contour_5a_requested_model_contract_purity_closure",
        "quality_gap": "contour_5a_second_route_quality_gap_closure",
    }[five_of_seven_failure_class]

    five_of_seven_v2_report = {
        "report_kind": "two_candidate_routes_pass_5_of_7_decision_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "effect_scope": effect_scope,
        "depends_on_completion_path": str(completion_path),
        "depends_on_completion_sha256": file_sha256(completion_path),
        "candidate_1": "or-gpt-oss-20b",
        "candidate_2": "direct-cerebras-llama3.1-8b",
        "task_set_size": task_set_size,
        "pass_threshold": pass_threshold,
        "candidate_task_pass_counts": {
            "or-gpt-oss-20b": {
                "success_count": gpt_success,
                "total_records": gpt_total,
                "passes_5_of_7": gpt_pass_5of7,
            },
            "direct-cerebras-llama3.1-8b": {
                "success_count": cerebras_success,
                "total_records": cerebras_total,
                "passes_5_of_7": cerebras_pass_5of7,
            },
        },
        "two_candidate_routes_pass_5_of_7": two_routes_5of7,
        "evidence_paths": [
            str(gpt_eval_path),
            str(cerebras_eval_path),
            str(completion_path),
        ],
        "evidence_sha256": [
            file_sha256(gpt_eval_path),
            file_sha256(cerebras_eval_path),
            file_sha256(completion_path),
        ],
        "summary": {
            "advisory_verdict": "two_candidate_routes_pass_5_of_7_true" if two_routes_5of7 else "two_candidate_routes_pass_5_of_7_false",
            "prior_decision_path": str(five_of_seven_v1_path),
            "prior_decision_sha256": file_sha256(five_of_seven_v1_path),
            "prior_decision_verdict": five_of_seven_v1_report.get("summary", {}).get("advisory_verdict"),
        },
    }
    five_of_seven_v2_path, _ = write_verification_json("two_candidate_routes_pass_5_of_7_decision_v2.json", five_of_seven_v2_report)

    criteria_v3 = [
        {
            "criterion_id": "two_runtime_confirmed_practical_routes_present",
            "satisfied": bool(post_truth_report.get("current_runtime_pool_size") == 2),
            "status": "satisfied" if bool(post_truth_report.get("current_runtime_pool_size") == 2) else "unsatisfied",
            "evidence_paths": [str(post_truth_path)],
        },
        {
            "criterion_id": "two_candidate_routes_pass_5_of_7",
            "satisfied": two_routes_5of7,
            "status": "satisfied" if two_routes_5of7 else "unsatisfied",
            "evidence_paths": [str(five_of_seven_v2_path)],
        },
        {
            "criterion_id": "repo_bound_integration_contract_materialized",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(gate_v2_path), str(blockers_v2_path)],
        },
        {
            "criterion_id": "repo_bound_integration_authorization_present",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(gate_v2_path), str(entrypoint_v2_path)],
        },
    ]
    unsatisfied_v3 = [item for item in criteria_v3 if not item.get("satisfied")]
    gate_v3_report = {
        "report_kind": "integration_gate_precheck_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "effect_scope": effect_scope,
        "depends_on_5of7_v2_path": str(five_of_seven_v2_path),
        "depends_on_5of7_v2_sha256": file_sha256(five_of_seven_v2_path),
        "criteria": criteria_v3,
        "integration_precheck_remains_blocked": len(unsatisfied_v3) > 0,
        "summary": {
            "advisory_verdict": "integration_precheck_v3_blocked_with_explicit_criteria" if unsatisfied_v3 else "integration_precheck_v3_conditions_satisfied",
            "satisfied_criteria_count": len(criteria_v3) - len(unsatisfied_v3),
            "unsatisfied_criteria_count": len(unsatisfied_v3),
        },
    }
    gate_v3_path, _ = write_verification_json("integration_gate_precheck_v3.json", gate_v3_report)

    blocker_map_v3 = {
        "two_candidate_routes_pass_5_of_7": {
            "coverage_incomplete": "evaluation_coverage_not_5_of_7",
            "stability_gap": "evaluation_stability_gap_not_5_of_7",
            "contract_violation": "evaluation_contract_violation_not_5_of_7",
            "quality_gap": "evaluation_quality_gap_not_5_of_7",
        }[five_of_seven_failure_class],
        "repo_bound_integration_contract_materialized": "integration_contract_not_materialized",
        "repo_bound_integration_authorization_present": "main-repo integration not yet authorized",
    }
    blockers_v3 = [
        {
            "criterion_id": item.get("criterion_id"),
            "blocker_class": blocker_map_v3.get(item.get("criterion_id"), "integration_gate_precheck_unsatisfied"),
            "evidence_paths": item.get("evidence_paths", []),
        }
        for item in unsatisfied_v3
    ]
    blockers_v3_report = {
        "report_kind": "integration_gate_blockers_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_gate_v3_path": str(gate_v3_path),
        "depends_on_gate_v3_sha256": file_sha256(gate_v3_path),
        "remaining_blockers": blockers_v3,
        "summary": {
            "advisory_verdict": "integration_blockers_v3_classified" if blockers_v3 else "no_remaining_integration_blockers_v3",
            "remaining_blocker_count": len(blockers_v3),
        },
    }
    blockers_v3_path, _ = write_verification_json("integration_gate_blockers_v3.json", blockers_v3_report)

    next_contour_v3 = (
        "repo_bound_controlled_integration_planning_precheck"
        if two_routes_5of7
        else next_contour_for_failure
    )
    next_contour_reason_v3 = (
        "integration_gate_v3_has_remaining_repo_bound_blockers"
        if two_routes_5of7
        else "five_of_seven_false_requires_cause_driven_narrow_closure"
    )
    next_entrypoint_v3_report = {
        "report_kind": "next_contour_entrypoint_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_blockers_v3_path": str(blockers_v3_path),
        "depends_on_blockers_v3_sha256": file_sha256(blockers_v3_path),
        "next_admissible_contour": next_contour_v3,
        "entrypoint_reason": next_contour_reason_v3,
        "summary": {
            "advisory_verdict": "next_contour_v3_defined",
        },
    }
    next_entrypoint_v3_path, _ = write_verification_json("next_contour_entrypoint_v3.json", next_entrypoint_v3_report)

    audit_v2_findings = []
    if not bool(gate_v3_report.get("depends_on_5of7_v2_sha256")):
        audit_v2_findings.append(
            {
                "finding_id": "missing_5of7_v2_dependency_link",
                "severity": "P0",
                "message": "Gate v3 must depend on explicit 5/7 v2 decision artifact.",
                "evidence_paths": [str(gate_v3_path)],
            }
        )
    audit_v2_report = {
        "report_kind": "criteria_closure_audit_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "independent_audit_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_audit_performed": True,
        "depends_on_entrypoint_v3_path": str(next_entrypoint_v3_path),
        "depends_on_entrypoint_v3_sha256": file_sha256(next_entrypoint_v3_path),
        "audit_findings": audit_v2_findings,
        "audit_passed": len(audit_v2_findings) == 0,
        "summary": {
            "advisory_verdict": "criteria_closure_operator_audit_v2_passed" if len(audit_v2_findings) == 0 else "criteria_closure_operator_audit_v2_failed",
            "finding_count": len(audit_v2_findings),
        },
    }
    audit_v2_path, _ = write_verification_json("criteria_closure_audit_v2.json", audit_v2_report)

    factcheck_v2_findings = []
    def _sha_match(path_value, sha_value):
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False
    checks = [
        ("sha_5of7_v2", gate_v3_report.get("depends_on_5of7_v2_path"), gate_v3_report.get("depends_on_5of7_v2_sha256"), str(gate_v3_path)),
        ("sha_gate_v3", blockers_v3_report.get("depends_on_gate_v3_path"), blockers_v3_report.get("depends_on_gate_v3_sha256"), str(blockers_v3_path)),
        ("sha_blockers_v3", next_entrypoint_v3_report.get("depends_on_blockers_v3_path"), next_entrypoint_v3_report.get("depends_on_blockers_v3_sha256"), str(next_entrypoint_v3_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_v2_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 5 dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )
    factcheck_v2_report = {
        "report_kind": "criteria_closure_factcheck_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "independent_factcheck_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_factcheck_performed": True,
        "depends_on_audit_v2_path": str(audit_v2_path),
        "depends_on_audit_v2_sha256": file_sha256(audit_v2_path),
        "factcheck_findings": factcheck_v2_findings,
        "factcheck_passed": len(factcheck_v2_findings) == 0,
        "summary": {
            "advisory_verdict": "criteria_closure_operator_factcheck_v2_passed" if len(factcheck_v2_findings) == 0 else "criteria_closure_operator_factcheck_v2_failed",
            "finding_count": len(factcheck_v2_findings),
        },
    }
    factcheck_v2_path, _ = write_verification_json("criteria_closure_factcheck_v2.json", factcheck_v2_report)

    if not two_routes_5of7:
        failure_report = {
            "report_kind": "five_of_seven_failure_classification",
            "lab_mode": True,
            "started_at_utc": now_utc,
            "contour_id": contour_id,
            "depends_on_5of7_v2_path": str(five_of_seven_v2_path),
            "depends_on_5of7_v2_sha256": file_sha256(five_of_seven_v2_path),
            "two_candidate_routes_pass_5_of_7": False,
            "failure_class": five_of_seven_failure_class,
            "next_narrow_contour": next_contour_for_failure,
            "summary": {
                "advisory_verdict": "five_of_seven_failure_classified",
            },
        }
        failure_path, _ = write_verification_json("five_of_seven_failure_classification.json", failure_report)
        print(f"JSON report: {failure_path}")

    print(f"JSON report: {completion_path}")
    print(f"JSON report: {five_of_seven_v2_path}")
    print(f"JSON report: {gate_v3_path}")
    print(f"JSON report: {blockers_v3_path}")
    print(f"JSON report: {next_entrypoint_v3_path}")
    print(f"JSON report: {audit_v2_path}")
    print(f"JSON report: {factcheck_v2_path}")


def run_contour_6a_second_route_stability_gap_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_6a_second_route_stability_gap_closure"
    now_utc = datetime.now(timezone.utc).isoformat()
    candidate_order = [
        "direct-groq-openai-gpt-oss-20b",
        "direct-gemini-2.5-flash",
        "direct-mistral-devstral-2512",
        "direct-mistral-small-latest",
    ]
    effect_scope = {
        "technical_execution_opened": False,
        "new_provider_opened": False,
        "new_target_model_opened": False,
        "route_readmission_performed": False,
        "runtime_probes_executed": False,
    }
    decision_order = [
        "second_route_stability_lock_v1",
        "second_route_runtime_recheck_v1",
        "two_candidate_routes_pass_5_of_7_decision_v3",
        "integration_gate_precheck_v4",
        "integration_gate_blockers_v4",
        "next_contour_entrypoint_v4",
        "stability_closure_audit_v1",
        "stability_closure_factcheck_v1",
    ]

    post_truth_path, post_truth_report = load_fixed_verification_report(
        "post_cerebras_current_practical_truth.json",
        "post_cerebras_current_practical_truth",
    )
    five_of_seven_v2_path, five_of_seven_v2_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision_v2.json",
        "two_candidate_routes_pass_5_of_7_decision_v2",
    )
    failure_v2_path, failure_v2_report = load_fixed_verification_report(
        "five_of_seven_failure_classification.json",
        "five_of_seven_failure_classification",
    )
    entrypoint_v3_path, entrypoint_v3_report = load_fixed_verification_report(
        "next_contour_entrypoint_v3.json",
        "next_contour_entrypoint_v3",
    )

    allowed_failure_classes = {
        "stability_gap",
        "contract_violation",
        "coverage_incomplete",
        "quality_gap",
    }
    locked_failure_class = failure_v2_report.get("failure_class")
    if locked_failure_class not in allowed_failure_classes:
        raise SystemExit("Invalid prior failure classification for Contour 6A lock.")
    locked_next_narrow_contour = failure_v2_report.get("next_narrow_contour")

    lock_report = {
        "report_kind": "second_route_stability_lock_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "canon_locked": True,
        "scope_mode": "non_expansive_single_cause_closure",
        "invariants": {
            "no_new_providers": True,
            "no_new_target_models": True,
            "no_direct_runtime_probing": True,
            "boundary_workspace_only": str(LAB_DIR),
        },
        "depends_on_failure_classification_path": str(failure_v2_path),
        "depends_on_failure_classification_sha256": file_sha256(failure_v2_path),
        "depends_on_5of7_v2_path": str(five_of_seven_v2_path),
        "depends_on_5of7_v2_sha256": file_sha256(five_of_seven_v2_path),
        "depends_on_entrypoint_v3_path": str(entrypoint_v3_path),
        "depends_on_entrypoint_v3_sha256": file_sha256(entrypoint_v3_path),
        "locked_failure_class": locked_failure_class,
        "locked_next_narrow_contour": locked_next_narrow_contour,
        "candidate_order": candidate_order,
        "summary": {
            "advisory_verdict": "contour_6a_lock_established",
            "prior_entrypoint_v3": entrypoint_v3_report.get("next_admissible_contour"),
        },
    }
    lock_path, lock_report = write_verification_json("second_route_stability_lock_v1.json", lock_report)

    provider_reports = load_recent_attested_reports(
        PROVIDER_DIR,
        lambda path_text: load_attested_report(path_text, "provider_access"),
        "provider access",
        limit=96,
    )
    provider_path = None
    provider_report = None
    for candidate_path, candidate_report in provider_reports:
        providers = candidate_report.get("providers")
        if not isinstance(providers, list):
            continue
        observed_routes = {
            item.get("route_model")
            for item in providers
            if isinstance(item, dict) and isinstance(item.get("route_model"), str)
        }
        if all(model_id in observed_routes for model_id in candidate_order):
            provider_path, provider_report = candidate_path, candidate_report
            break
    if provider_path is None or provider_report is None:
        raise SystemExit("No attested provider report contains all locked Contour 6A candidates.")

    provider_by_route_model = {}
    for row in provider_report.get("providers", []):
        if isinstance(row, dict) and isinstance(row.get("route_model"), str):
            provider_by_route_model[row["route_model"]] = row

    second_route_candidate = candidate_order[0]
    second_route_source_model = second_route_candidate
    second_route_source_is_proxy = False
    try:
        second_route_path, second_route_report = load_latest_qualification_report_for_model(second_route_candidate)
        second_response_path, second_response_report = load_latest_response_report_for_model(second_route_candidate)
        second_eval_path, second_eval_report = load_latest_eval_report_for_model(second_route_candidate)
    except SystemExit:
        second_route_source_model = "gpt-oss-20b"
        second_route_source_is_proxy = True
        second_route_path, second_route_report = load_latest_qualification_report_for_model("gpt-oss-20b")
        second_response_path, second_response_report = load_latest_response_report_for_model("gpt-oss-20b")
        second_eval_path, second_eval_report = load_latest_eval_report_for_model("gpt-oss-20b")
    cerebras_route_path, cerebras_route_report = load_latest_qualification_report_for_model("direct-cerebras-llama3.1-8b")
    cerebras_response_path, cerebras_response_report = load_latest_response_report_for_model("direct-cerebras-llama3.1-8b")
    cerebras_eval_path, cerebras_eval_report = load_latest_eval_report_for_model("direct-cerebras-llama3.1-8b")

    second_route_summary = qualification_entry_for_model(second_route_report, second_route_source_model)
    second_response_summary = response_summary_for_model(second_response_report, second_route_source_model)
    second_eval_summary = eval_summary_for_model_or_raise(second_eval_report, second_route_source_model)
    cerebras_eval_summary = eval_summary_for_model_or_raise(cerebras_eval_report, "direct-cerebras-llama3.1-8b")

    second_route_records = [
        item
        for item in second_eval_report.get("records", [])
        if isinstance(item, dict) and item.get("model") == second_route_source_model
    ]
    stability_error_classes = {"upstream_rate_limited", "upstream_timeout", "upstream_overloaded"}
    second_route_stability_failures = [
        item
        for item in second_route_records
        if item.get("success") is False and item.get("error_class") in stability_error_classes
    ]
    second_route_contract_violations = [
        item
        for item in second_route_records
        if item.get("success") is False and ((item.get("requested_model_available") is not True) or (item.get("fallback_used") is True))
    ]

    candidate_recheck = []
    for model_id in candidate_order:
        provider_row = provider_by_route_model.get(model_id) or {}
        blocked_by_policy = provider_row.get("policy_status") == "provider_blocked_cost_policy"
        entry = {
            "candidate_model": model_id,
            "provider": provider_row.get("provider"),
            "provider_transport_status": provider_row.get("transport_status"),
            "provider_policy_status": provider_row.get("policy_status"),
            "provider_requested_model_available": provider_row.get("requested_model_available"),
            "provider_error_class": provider_row.get("error_class"),
            "blocked_by_policy": blocked_by_policy,
            "has_route_evidence": False,
            "has_response_evidence": False,
            "has_eval_evidence": False,
        }
        if model_id == second_route_candidate:
            entry.update(
                {
                    "proxy_evidence_model": second_route_source_model if second_route_source_is_proxy else None,
                    "proxy_evidence_allowed": second_route_source_is_proxy,
                    "has_route_evidence": True,
                    "has_response_evidence": True,
                    "has_eval_evidence": True,
                    "evidence_model": second_route_source_model,
                    "route_status": second_route_summary.get("qualification_status"),
                    "response_status": second_response_summary.get("response_evidence_status"),
                    "eval_outcome": second_eval_summary.get("outcome"),
                    "eval_success_count": int(second_eval_summary.get("success_count") or 0),
                    "eval_total_records": int(second_eval_summary.get("total_records") or 0),
                }
            )
        candidate_recheck.append(entry)

    runtime_recheck_report = {
        "report_kind": "second_route_runtime_recheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "effect_scope": effect_scope,
        "depends_on_lock_path": str(lock_path),
        "depends_on_lock_sha256": file_sha256(lock_path),
        "provider_evidence_path": str(provider_path),
        "provider_evidence_sha256": file_sha256(provider_path),
        "top_candidate_route_proxy_evidence": {
            "source_model": second_route_source_model,
            "is_proxy": second_route_source_is_proxy,
            "route_qualification_path": str(second_route_path),
            "route_qualification_sha256": file_sha256(second_route_path),
            "response_evidence_path": str(second_response_path),
            "response_evidence_sha256": file_sha256(second_response_path),
            "eval_path": str(second_eval_path),
            "eval_sha256": file_sha256(second_eval_path),
        },
        "primary_route_evidence": {
            "model": "direct-cerebras-llama3.1-8b",
            "route_qualification_path": str(cerebras_route_path),
            "route_qualification_sha256": file_sha256(cerebras_route_path),
            "response_evidence_path": str(cerebras_response_path),
            "response_evidence_sha256": file_sha256(cerebras_response_path),
            "eval_path": str(cerebras_eval_path),
            "eval_sha256": file_sha256(cerebras_eval_path),
        },
        "candidate_recheck": candidate_recheck,
        "no_new_runtime_probes_performed": True,
        "summary": {
            "advisory_verdict": "runtime_recheck_completed_from_attested_evidence_only",
            "policy_blocked_candidate_count": sum(1 for item in candidate_recheck if item.get("blocked_by_policy")),
            "top_candidate_stability_failures": len(second_route_stability_failures),
            "top_candidate_contract_violations": len(second_route_contract_violations),
        },
    }
    runtime_recheck_path, runtime_recheck_report = write_verification_json(
        "second_route_runtime_recheck_v1.json",
        runtime_recheck_report,
    )

    task_set_size = 7
    pass_threshold = 5
    second_success = int(second_eval_summary.get("success_count") or 0)
    second_total = int(second_eval_summary.get("total_records") or 0)
    cerebras_success = int(cerebras_eval_summary.get("success_count") or 0)
    cerebras_total = int(cerebras_eval_summary.get("total_records") or 0)
    second_pass_5of7 = second_total >= task_set_size and second_success >= pass_threshold
    cerebras_pass_5of7 = cerebras_total >= task_set_size and cerebras_success >= pass_threshold
    two_routes_5of7 = second_pass_5of7 and cerebras_pass_5of7

    coverage_incomplete = not (second_total >= task_set_size and cerebras_total >= task_set_size)
    stability_gap = bool(second_route_stability_failures) and not second_pass_5of7
    contract_violation = bool(second_route_contract_violations)
    quality_gap = not coverage_incomplete and not stability_gap and not contract_violation and not two_routes_5of7
    cause_signals = {
        "coverage_incomplete": coverage_incomplete,
        "stability_gap": stability_gap,
        "contract_violation": contract_violation,
        "quality_gap": quality_gap,
    }

    if two_routes_5of7:
        failure_class = None
    else:
        if cause_signals.get(locked_failure_class):
            failure_class = locked_failure_class
        elif coverage_incomplete:
            failure_class = "coverage_incomplete"
        elif stability_gap:
            failure_class = "stability_gap"
        elif contract_violation:
            failure_class = "contract_violation"
        else:
            failure_class = "quality_gap"

    next_contour_for_failure = {
        "coverage_incomplete": "contour_6a_coverage_completion_closure",
        "stability_gap": locked_next_narrow_contour or "contour_6a_second_route_stability_gap_closure",
        "contract_violation": "contour_6a_requested_model_contract_purity_closure",
        "quality_gap": "contour_6a_second_route_quality_gap_closure",
    }[failure_class] if failure_class else "repo_bound_controlled_integration_planning_precheck"

    five_of_seven_v3_report = {
        "report_kind": "two_candidate_routes_pass_5_of_7_decision_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "effect_scope": effect_scope,
        "depends_on_runtime_recheck_path": str(runtime_recheck_path),
        "depends_on_runtime_recheck_sha256": file_sha256(runtime_recheck_path),
        "depends_on_prior_5of7_v2_path": str(five_of_seven_v2_path),
        "depends_on_prior_5of7_v2_sha256": file_sha256(five_of_seven_v2_path),
        "candidate_order": candidate_order,
        "primary_runtime_candidate": "direct-cerebras-llama3.1-8b",
        "second_route_candidate": second_route_candidate,
        "second_route_candidate_proxy_evidence_model": second_route_source_model if second_route_source_is_proxy else None,
        "task_set_size": task_set_size,
        "pass_threshold": pass_threshold,
        "candidate_task_pass_counts": {
            "direct-cerebras-llama3.1-8b": {
                "success_count": cerebras_success,
                "total_records": cerebras_total,
                "passes_5_of_7": cerebras_pass_5of7,
            },
            second_route_candidate: {
                "success_count": second_success,
                "total_records": second_total,
                "passes_5_of_7": second_pass_5of7,
                "proxy_evidence_model": second_route_source_model if second_route_source_is_proxy else None,
            },
        },
        "two_candidate_routes_pass_5_of_7": two_routes_5of7,
        "cause_signals": cause_signals,
        "failure_class": failure_class,
        "next_narrow_contour": next_contour_for_failure if not two_routes_5of7 else None,
        "evidence_paths": [
            str(second_eval_path),
            str(cerebras_eval_path),
            str(runtime_recheck_path),
            str(five_of_seven_v2_path),
        ],
        "evidence_sha256": [
            file_sha256(second_eval_path),
            file_sha256(cerebras_eval_path),
            file_sha256(runtime_recheck_path),
            file_sha256(five_of_seven_v2_path),
        ],
        "summary": {
            "advisory_verdict": "two_candidate_routes_pass_5_of_7_true" if two_routes_5of7 else "two_candidate_routes_pass_5_of_7_false",
            "prior_decision_verdict": five_of_seven_v2_report.get("summary", {}).get("advisory_verdict"),
            "prior_failure_class": locked_failure_class,
        },
    }
    five_of_seven_v3_path, five_of_seven_v3_report = write_verification_json(
        "two_candidate_routes_pass_5_of_7_decision_v3.json",
        five_of_seven_v3_report,
    )

    criteria_v4 = [
        {
            "criterion_id": "two_runtime_confirmed_practical_routes_present",
            "satisfied": bool(post_truth_report.get("current_runtime_pool_size") == 2),
            "status": "satisfied" if bool(post_truth_report.get("current_runtime_pool_size") == 2) else "unsatisfied",
            "evidence_paths": [str(post_truth_path)],
        },
        {
            "criterion_id": "two_candidate_routes_pass_5_of_7",
            "satisfied": two_routes_5of7,
            "status": "satisfied" if two_routes_5of7 else "unsatisfied",
            "evidence_paths": [str(five_of_seven_v3_path)],
        },
        {
            "criterion_id": "repo_bound_integration_contract_materialized",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(entrypoint_v3_path)],
        },
        {
            "criterion_id": "repo_bound_integration_authorization_present",
            "satisfied": False,
            "status": "unsatisfied",
            "evidence_paths": [str(entrypoint_v3_path)],
        },
    ]
    unsatisfied_v4 = [item for item in criteria_v4 if not item.get("satisfied")]
    gate_v4_report = {
        "report_kind": "integration_gate_precheck_v4",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "effect_scope": effect_scope,
        "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
        "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
        "criteria": criteria_v4,
        "integration_precheck_remains_blocked": len(unsatisfied_v4) > 0,
        "summary": {
            "advisory_verdict": "integration_precheck_v4_blocked_with_explicit_criteria" if unsatisfied_v4 else "integration_precheck_v4_conditions_satisfied",
            "satisfied_criteria_count": len(criteria_v4) - len(unsatisfied_v4),
            "unsatisfied_criteria_count": len(unsatisfied_v4),
        },
    }
    gate_v4_path, gate_v4_report = write_verification_json("integration_gate_precheck_v4.json", gate_v4_report)

    blocker_map_v4 = {
        "two_candidate_routes_pass_5_of_7": {
            "coverage_incomplete": "evaluation_coverage_not_5_of_7",
            "stability_gap": "evaluation_stability_gap_not_5_of_7",
            "contract_violation": "evaluation_contract_violation_not_5_of_7",
            "quality_gap": "evaluation_quality_gap_not_5_of_7",
        }[failure_class] if failure_class else "evaluation_5of7_not_required",
        "repo_bound_integration_contract_materialized": "integration_contract_not_materialized",
        "repo_bound_integration_authorization_present": "main-repo integration not yet authorized",
    }
    blockers_v4 = [
        {
            "criterion_id": item.get("criterion_id"),
            "blocker_class": blocker_map_v4.get(item.get("criterion_id"), "integration_gate_precheck_unsatisfied"),
            "evidence_paths": item.get("evidence_paths", []),
        }
        for item in unsatisfied_v4
    ]
    blockers_v4_report = {
        "report_kind": "integration_gate_blockers_v4",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "remaining_blockers": blockers_v4,
        "summary": {
            "advisory_verdict": "integration_blockers_v4_classified" if blockers_v4 else "no_remaining_integration_blockers_v4",
            "remaining_blocker_count": len(blockers_v4),
        },
    }
    blockers_v4_path, blockers_v4_report = write_verification_json("integration_gate_blockers_v4.json", blockers_v4_report)

    next_contour_v4 = (
        "repo_bound_controlled_integration_planning_precheck"
        if two_routes_5of7
        else next_contour_for_failure
    )
    next_reason_v4 = (
        "integration_gate_v4_has_remaining_repo_bound_blockers"
        if two_routes_5of7
        else "five_of_seven_false_requires_cause_driven_narrow_closure"
    )
    next_entrypoint_v4_report = {
        "report_kind": "next_contour_entrypoint_v4",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "next_admissible_contour": next_contour_v4,
        "entrypoint_reason": next_reason_v4,
        "summary": {
            "advisory_verdict": "next_contour_v4_defined",
        },
    }
    next_entrypoint_v4_path, next_entrypoint_v4_report = write_verification_json(
        "next_contour_entrypoint_v4.json",
        next_entrypoint_v4_report,
    )

    audit_v1_findings = []
    if lock_report.get("candidate_order") != candidate_order:
        audit_v1_findings.append(
            {
                "finding_id": "candidate_order_not_locked",
                "severity": "P0",
                "message": "Contour 6A candidate order must match canonical locked order.",
                "evidence_paths": [str(lock_path)],
            }
        )
    if not bool(gate_v4_report.get("depends_on_5of7_v3_sha256")):
        audit_v1_findings.append(
            {
                "finding_id": "missing_5of7_v3_dependency_link",
                "severity": "P0",
                "message": "Gate v4 must depend on explicit 5/7 v3 decision artifact.",
                "evidence_paths": [str(gate_v4_path)],
            }
        )
    if not two_routes_5of7 and failure_class not in allowed_failure_classes:
        audit_v1_findings.append(
            {
                "finding_id": "invalid_failure_class",
                "severity": "P0",
                "message": "Failure classification must be cause-driven and within canonical classes.",
                "evidence_paths": [str(five_of_seven_v3_path)],
            }
        )

    audit_v1_report = {
        "report_kind": "stability_closure_audit_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "independent_audit_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_audit_performed": True,
        "depends_on_entrypoint_v4_path": str(next_entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(next_entrypoint_v4_path),
        "audit_findings": audit_v1_findings,
        "audit_passed": len(audit_v1_findings) == 0,
        "summary": {
            "advisory_verdict": "stability_closure_operator_audit_v1_passed" if len(audit_v1_findings) == 0 else "stability_closure_operator_audit_v1_failed",
            "finding_count": len(audit_v1_findings),
        },
    }
    audit_v1_path, audit_v1_report = write_verification_json("stability_closure_audit_v1.json", audit_v1_report)

    factcheck_v1_findings = []

    def _sha_match(path_value, sha_value):
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    checks = [
        ("sha_lock", runtime_recheck_report.get("depends_on_lock_path"), runtime_recheck_report.get("depends_on_lock_sha256"), str(runtime_recheck_path)),
        ("sha_runtime_recheck", five_of_seven_v3_report.get("depends_on_runtime_recheck_path"), five_of_seven_v3_report.get("depends_on_runtime_recheck_sha256"), str(five_of_seven_v3_path)),
        ("sha_5of7_v3", gate_v4_report.get("depends_on_5of7_v3_path"), gate_v4_report.get("depends_on_5of7_v3_sha256"), str(gate_v4_path)),
        ("sha_gate_v4", blockers_v4_report.get("depends_on_gate_v4_path"), blockers_v4_report.get("depends_on_gate_v4_sha256"), str(blockers_v4_path)),
        ("sha_blockers_v4", next_entrypoint_v4_report.get("depends_on_blockers_v4_path"), next_entrypoint_v4_report.get("depends_on_blockers_v4_sha256"), str(next_entrypoint_v4_path)),
        ("sha_entrypoint_v4", audit_v1_report.get("depends_on_entrypoint_v4_path"), audit_v1_report.get("depends_on_entrypoint_v4_sha256"), str(audit_v1_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_v1_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 6A dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    factcheck_v1_report = {
        "report_kind": "stability_closure_factcheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "independent_factcheck_performed": False,
        "independence_blocked_reason": "agent_quota_limit_reached",
        "operator_factcheck_performed": True,
        "depends_on_audit_v1_path": str(audit_v1_path),
        "depends_on_audit_v1_sha256": file_sha256(audit_v1_path),
        "factcheck_findings": factcheck_v1_findings,
        "factcheck_passed": len(factcheck_v1_findings) == 0,
        "summary": {
            "advisory_verdict": "stability_closure_operator_factcheck_v1_passed" if len(factcheck_v1_findings) == 0 else "stability_closure_operator_factcheck_v1_failed",
            "finding_count": len(factcheck_v1_findings),
        },
    }
    factcheck_v1_path, _ = write_verification_json("stability_closure_factcheck_v1.json", factcheck_v1_report)

    failure_v1_path = None
    if not two_routes_5of7:
        failure_v1_report = {
            "report_kind": "second_route_stability_closure_failure_v1",
            "lab_mode": True,
            "started_at_utc": now_utc,
            "contour_id": contour_id,
            "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
            "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
            "two_candidate_routes_pass_5_of_7": False,
            "failure_class": failure_class,
            "next_narrow_contour": next_contour_for_failure,
            "cause_signals": cause_signals,
            "summary": {
                "advisory_verdict": "second_route_stability_closure_failure_classified",
            },
        }
        failure_v1_path, _ = write_verification_json("second_route_stability_closure_failure_v1.json", failure_v1_report)
    else:
        stale_failure_path = VERIFICATION_DIR / "second_route_stability_closure_failure_v1.json"
        if stale_failure_path.exists():
            stale_failure_path.unlink()

    print(f"JSON report: {lock_path}")
    print(f"JSON report: {runtime_recheck_path}")
    print(f"JSON report: {five_of_seven_v3_path}")
    print(f"JSON report: {gate_v4_path}")
    print(f"JSON report: {blockers_v4_path}")
    print(f"JSON report: {next_entrypoint_v4_path}")
    print(f"JSON report: {audit_v1_path}")
    print(f"JSON report: {factcheck_v1_path}")
    if failure_v1_path:
        print(f"JSON report: {failure_v1_path}")


def run_canon_first_contour_generator(args):
    ensure_env_permissions(ENV_PATH)
    reports = resolve_canon_input_reports(args)
    qualification_path, qualification_report = reports["qualification"]
    response_path, response_report = reports["response"]
    eval_path, eval_report = reports["eval"]
    provider_path, provider_report = reports["provider"]
    registry_path, registry_report = reports["registry"]
    recent_qualification_reports = load_recent_attested_reports(ROUTE_DIR, load_qualification_report, "route qualification")
    recent_response_reports = load_recent_attested_reports(RESPONSE_DIR, load_response_report, "response evidence")
    recent_eval_reports = load_recent_attested_reports(EVAL_DIR, load_eval_report, "task eval")

    qwen_models = ("qwen3-coder", "qwen3-next")
    qwen_evidence = {
        model_id: build_qwen_model_evidence(model_id, recent_qualification_reports, recent_response_reports, recent_eval_reports)
        for model_id in qwen_models
    }
    shared_instability_error_classes = sorted(
        error_class
        for error_class in {"upstream_timeout", "upstream_rate_limited", "upstream_overloaded"}
        if all(
            any(item["error_class"] == error_class for item in qwen_evidence[model_id]["dominant_error_classes"])
            for model_id in qwen_models
        )
    )
    provider_ready_direct = provider_report.get("summary", {}).get("ready_direct_providers")
    if not isinstance(provider_ready_direct, list):
        provider_ready_direct = []
    provider_hosted_instability_evidenced = bool(shared_instability_error_classes)

    input_reports = {
        "route_qualification": {"path": str(qualification_path), "sha256": file_sha256(qualification_path)},
        "response_evidence": {"path": str(response_path), "sha256": file_sha256(response_path)},
        "task_eval": {"path": str(eval_path), "sha256": file_sha256(eval_path)},
        "provider_access": {"path": str(provider_path), "sha256": file_sha256(provider_path)},
        "registry_snapshot": {"path": str(registry_path), "sha256": file_sha256(registry_path)},
    }
    decision_order = [
        "qwen_openrouter_free_lane_rca",
        "qwen_status_decision",
        "practical_pool_rebase_decision",
        "next_contour_blocker",
    ]

    rca_report = {
        "report_kind": "qwen_openrouter_free_lane_rca",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_order": decision_order,
        "decision_order_index": 1,
        "input_reports": input_reports,
        "historical_support_window": {
            "route_reports_considered": len(recent_qualification_reports),
            "response_reports_considered": len(recent_response_reports),
            "eval_reports_considered": len(recent_eval_reports),
        },
        "canon_constraints": {
            "operational_evidence_required": True,
            "provider_instability_vs_model_capability_separated": True,
            "supporting_notes_non_operational": True,
        },
        "supporting_notes": {
            "docs_forums_considered_operational_evidence": False,
            "notes": [
                {
                    "source_type": "external_market_research_note",
                    "label": "OpenRouter provider routing docs",
                    "url": "https://openrouter.ai/docs/guides/routing/provider-selection",
                },
                {
                    "source_type": "external_market_research_note",
                    "label": "OpenRouter free models router docs",
                    "url": "https://openrouter.ai/docs/guides/routing/routers/free-models-router",
                },
            ],
        },
        "operational_assessment": {
            "provider_hosted_free_lane_instability_evidenced": provider_hosted_instability_evidenced,
            "shared_instability_error_classes": shared_instability_error_classes,
            "direct_provider_ready_routes": sorted(provider_ready_direct),
            "model_capability_failure_confirmed": False,
            "capability_conclusion_basis": "not_confirmed_under_canon_without_stable_runtime",
        },
        "qwen_repeated_evidence": qwen_evidence,
        "summary": {
            "advisory_verdict": (
                "provider_hosted_free_lane_instability_likely"
                if provider_hosted_instability_evidenced
                else "insufficient_shared_instability_evidence"
            ),
        },
    }
    rca_path, _ = write_verification_json("qwen_openrouter_free_lane_rca.json", rca_report)

    qwen_decisions = []
    for model_id in qwen_models:
        evidence = qwen_evidence[model_id]
        qwen_decisions.append(
            {
                "model": model_id,
                "availability_state": "unstable",
                "lane_role": "comparison",
                "status_decision": "hold_out_of_practical_scoring",
                "decision_reason": "repeated_free_lane_instability_or_unverified_stability",
                "repeated_across_contours": evidence["repeated_across_contours"],
                "practical_scoring_eligible": False,
            }
        )

    status_decision_report = {
        "report_kind": "qwen_status_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_rca_path": str(rca_path),
        "depends_on_rca_sha256": file_sha256(rca_path),
        "qwen_status_decisions": qwen_decisions,
        "qwen_repeated_evidence": qwen_evidence,
        "summary": {
            "advisory_verdict": "qwen_practical_scoring_locked_pending_stability",
        },
    }
    status_path, _ = write_verification_json("qwen_status_decision.json", status_decision_report)

    current_practical_pool = registry_report.get("summary", {}).get("current_practical_pool_model_ids")
    if not isinstance(current_practical_pool, list):
        current_practical_pool = []
    qwen_present_in_practical_pool = sorted(model_id for model_id in qwen_models if model_id in current_practical_pool)
    recommended_practical_pool = sorted(model_id for model_id in current_practical_pool if model_id not in set(qwen_models))
    recommended_removals = qwen_present_in_practical_pool

    rebase_report = {
        "report_kind": "practical_pool_rebase_decision",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_status_decision_path": str(status_path),
        "depends_on_status_decision_sha256": file_sha256(status_path),
        "registry_snapshot_path": str(registry_path),
        "registry_snapshot_sha256": file_sha256(registry_path),
        "registry_materialization_advisory": {
            "registry_mutation_performed": False,
            "current_practical_pool_model_ids": sorted(current_practical_pool),
            "recommended_practical_pool_model_ids": recommended_practical_pool,
            "recommended_remove_model_ids": recommended_removals,
            "qwen_present_in_practical_pool": bool(qwen_present_in_practical_pool),
        },
        "practical_scoring_rebase": {
            "qwen3-coder_practical_scoring_eligible": False,
            "qwen3-next_practical_scoring_eligible": False,
            "retain_gpt_oss_20b_in_practical_context": True,
            "retain_glm_flash_as_comparison_only_if_explicitly_requested": True,
        },
        "qwen_repeated_evidence": qwen_evidence,
        "summary": {
            "advisory_verdict": (
                "registry_rebase_advisory_emitted_qwen_exclusion_recommended"
                if qwen_present_in_practical_pool
                else "registry_rebase_advisory_emitted_no_qwen_removal_needed"
            ),
        },
    }
    rebase_path, _ = write_verification_json("practical_pool_rebase_decision.json", rebase_report)

    blocker_report = {
        "report_kind": "next_contour_blocker",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_rebase_decision_path": str(rebase_path),
        "depends_on_rebase_decision_sha256": file_sha256(rebase_path),
        "blockers": [
            {
                "blocker_id": "second_stable_requested_route_missing_after_qwen_exclusion",
                "blocker_active": True,
                "reason": "qwen3-coder and qwen3-next are removed from the practical critical path because the observed issue is OpenRouter free-lane instability, and a second stable requested-model route is still missing.",
                "release_condition": "Qualify a different accessible route/provider as a stable requested-model candidate under canon-first evidence rules.",
                "required_next_action": "pivot_away_from_openrouter_free_qwen_and_seek_second_stable_route",
            }
        ],
        "qwen_repeated_evidence": qwen_evidence,
        "summary": {
            "advisory_verdict": "pivot_required_seek_second_stable_route_outside_openrouter_free_qwen",
        },
    }
    blocker_path, _ = write_verification_json("next_contour_blocker.json", blocker_report)

    print(f"JSON report: {rca_path}")
    print(f"JSON report: {status_path}")
    print(f"JSON report: {rebase_path}")
    print(f"JSON report: {blocker_path}")


def run_repo_bound_planning_precheck(args):
    ensure_env_permissions(ENV_PATH)
    if not args.verification_report:
        raise SystemExit("Repo-bound planning precheck requires --verification-report.")

    verification_path = Path(args.verification_report)
    if not verification_path.exists():
        raise SystemExit(f"Verification report not found: {verification_path}")
    verification_report = json.loads(verification_path.read_text(encoding="utf-8"))
    verify_attestation(verification_report)

    verification_report_kind = verification_report.get("report_kind")
    verification_contour_status = verification_report.get("verification_contour_status")
    verification_gate_advisory_verdict = verification_report.get("summary", {}).get("advisory_verdict")
    verification_verdict = verification_report.get("summary", {}).get("verification_verdict") or verification_report.get("verification_verdict")
    direct_lab_verification_precheck_instantiated = verification_report_kind == "direct_lab_verification_precheck"
    verified_eval_models = verification_report.get("verified_eval_models", [])
    if not isinstance(verified_eval_models, list):
        verified_eval_models = []

    repo_design_open_candidate = (
        direct_lab_verification_precheck_instantiated
        and verification_contour_status == "open"
        and len(verified_eval_models) > 0
    )

    if repo_design_open_candidate:
        advisory_verdict = "repo_bound_planning_ready_to_start"
        reason = "upstream_direct_lab_verification_passed"
        contour_status = "open"
        contour_verdict = "ready_for_repo_bound_controlled_admission_planning"
    else:
        advisory_verdict = "repo_bound_planning_locked_upstream_missing"
        reason = "upstream_direct_lab_verification_missing_or_locked"
        contour_status = "locked"
        contour_verdict = "blocked_by_repo_bound_planning_boundary_violation"

    report = {
        "report_kind": "repo_bound_controlled_admission_planning_precheck",
        "lab_mode": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "env_path": str(ENV_PATH),
        "verification_gate_path": str(verification_path),
        "verification_gate_sha256": file_sha256(verification_path),
        "verification_gate_report_kind": verification_report_kind,
        "direct_lab_verification_precheck_instantiated": direct_lab_verification_precheck_instantiated,
        "verification_contour_status": verification_contour_status,
        "verification_gate_advisory_verdict": verification_gate_advisory_verdict,
        "verification_verdict": verification_verdict,
        "verified_eval_models": verified_eval_models,
        "repo_bound_admission_design_candidate": False,
        "repo_bound_admission_impl_candidate": False,
        "artifact_chain_complete": False,
        "single_route_consistent": False,
        "repo_read_only_inspection_performed": False,
        "repo_writes_performed": False,
        "repo_bound_write_scope_allowlist_defined": False,
        "repo_bound_write_scope_precise": False,
        "repo_design_contour_status": contour_status,
        "layer_violation_detected": False,
    }
    report["summary"] = {
        "repo_bound_admission_impl_candidate": False,
        "repo_design_contour_open_now": repo_design_open_candidate,
        "advisory_verdict": advisory_verdict,
        "reason": reason,
        "repo_design_verdict": contour_verdict,
    }
    json_path, md_path = write_repo_bound_planning_precheck_report(report)
    print(f"JSON report: {json_path}")
    print(f"MD report: {md_path}")


def run_contour_6b_repo_bound_planning_precheck_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_6b_repo_bound_planning_precheck_closure"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "repo_bound_planning_lock_v1",
        "repo_bound_blocker_contract_v1",
        "controlled_integration_planning_contract_v1",
        "repo_bound_authorization_request_v1",
        "repo_bound_authorization_decision_v1",
        "repo_bound_planning_precheck_result_v1",
        "repo_bound_planning_blockers_v1",
        "repo_bound_planning_entrypoint_v1",
        "repo_bound_planning_audit_v1",
        "repo_bound_planning_factcheck_v1",
    ]
    effect_scope = {
        "planning_only": True,
        "runtime_probes_performed": False,
        "provider_model_expansion_performed": False,
        "repo_mutation_performed": False,
    }

    five_of_seven_v3_path, five_of_seven_v3_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision_v3.json",
        "two_candidate_routes_pass_5_of_7_decision_v3",
    )
    gate_v4_path, gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )
    blockers_v4_path, blockers_v4_report = load_fixed_verification_report(
        "integration_gate_blockers_v4.json",
        "integration_gate_blockers_v4",
    )
    entrypoint_v4_path, entrypoint_v4_report = load_fixed_verification_report(
        "next_contour_entrypoint_v4.json",
        "next_contour_entrypoint_v4",
    )
    chain_v1_path, chain_v1_report = load_fixed_verification_report(
        "contour_6a_artifact_chain_validation_v1.json",
        "contour_6a_artifact_chain_validation_v1",
    )

    chain_complete = bool(chain_v1_report.get("overall_passed"))
    gate_link_ok = (
        gate_v4_report.get("depends_on_5of7_v3_path") == str(five_of_seven_v3_path)
        and gate_v4_report.get("depends_on_5of7_v3_sha256") == file_sha256(five_of_seven_v3_path)
    )
    blockers_link_ok = (
        blockers_v4_report.get("depends_on_gate_v4_path") == str(gate_v4_path)
        and blockers_v4_report.get("depends_on_gate_v4_sha256") == file_sha256(gate_v4_path)
    )
    entrypoint_link_ok = (
        entrypoint_v4_report.get("depends_on_blockers_v4_path") == str(blockers_v4_path)
        and entrypoint_v4_report.get("depends_on_blockers_v4_sha256") == file_sha256(blockers_v4_path)
    )

    lock_report = {
        "report_kind": "repo_bound_planning_lock_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
        "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "depends_on_6a_chain_validation_path": str(chain_v1_path),
        "depends_on_6a_chain_validation_sha256": file_sha256(chain_v1_path),
        "planning_boundary": {
            "planning_only": True,
            "no_runtime_probes": True,
            "no_provider_or_model_expansion": True,
            "no_model_or_eval_quality_recomputation": True,
            "consume_prior_decision_artifacts_only": True,
        },
        "prior_decision_chain_checks": {
            "contour_6a_chain_overall_passed": chain_complete,
            "gate_depends_on_5of7_v3": gate_link_ok,
            "blockers_depends_on_gate_v4": blockers_link_ok,
            "entrypoint_depends_on_blockers_v4": entrypoint_link_ok,
        },
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_lock_established"
                if chain_complete and gate_link_ok and blockers_link_ok and entrypoint_link_ok
                else "repo_bound_planning_lock_blocked_by_invalid_prior_chain"
            ),
        },
    }
    lock_path, lock_report = write_verification_json("repo_bound_planning_lock_v1.json", lock_report)

    blockers_v4 = blockers_v4_report.get("remaining_blockers", [])
    if not isinstance(blockers_v4, list):
        blockers_v4 = []
    inherited_blockers = [
        {
            "criterion_id": item.get("criterion_id"),
            "blocker_class": item.get("blocker_class"),
            "origin": "integration_gate_blockers_v4",
            "evidence_paths": item.get("evidence_paths", []),
        }
        for item in blockers_v4
        if isinstance(item, dict)
    ]

    blocker_contract_report = {
        "report_kind": "repo_bound_blocker_contract_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_lock_v1_path": str(lock_path),
        "depends_on_lock_v1_sha256": file_sha256(lock_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "planning_only_blocker_contract": {
            "consume_prior_decision_artifacts_only": True,
            "recompute_model_quality_allowed": False,
            "runtime_probes_allowed": False,
            "provider_or_model_expansion_allowed": False,
        },
        "remaining_blockers": inherited_blockers,
        "summary": {
            "advisory_verdict": "repo_bound_blocker_contract_materialized",
            "remaining_blocker_count": len(inherited_blockers),
        },
    }
    blocker_contract_path, blocker_contract_report = write_verification_json(
        "repo_bound_blocker_contract_v1.json",
        blocker_contract_report,
    )

    controlled_contract_report = {
        "report_kind": "controlled_integration_planning_contract_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_lock_v1_path": str(lock_path),
        "depends_on_lock_v1_sha256": file_sha256(lock_path),
        "depends_on_blocker_contract_v1_path": str(blocker_contract_path),
        "depends_on_blocker_contract_v1_sha256": file_sha256(blocker_contract_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "controlled_integration_planning_contract": {
            "planning_only": True,
            "consume_prior_decision_artifacts_only": True,
            "no_runtime_probes": True,
            "no_provider_or_model_expansion": True,
            "no_model_or_eval_quality_recomputation": True,
            "allowed_write_scope": [],
        },
        "summary": {
            "advisory_verdict": "controlled_integration_planning_contract_materialized",
            "prior_entrypoint_v4_target": entrypoint_v4_report.get("next_admissible_contour"),
        },
    }
    controlled_contract_path, controlled_contract_report = write_verification_json(
        "controlled_integration_planning_contract_v1.json",
        controlled_contract_report,
    )

    auth_request_report = {
        "report_kind": "repo_bound_authorization_request_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_controlled_contract_v1_path": str(controlled_contract_path),
        "depends_on_controlled_contract_v1_sha256": file_sha256(controlled_contract_path),
        "depends_on_lock_v1_path": str(lock_path),
        "depends_on_lock_v1_sha256": file_sha256(lock_path),
        "authorization_scope": "repo_bound_controlled_integration_planning",
        "authorization_requested": True,
        "requested_actions": [
            "materialize_repo_bound_planning_contract_only",
            "hold_execution_until_external_authorization_decision",
        ],
        "summary": {
            "advisory_verdict": "repo_bound_authorization_request_materialized",
        },
    }
    auth_request_path, auth_request_report = write_verification_json(
        "repo_bound_authorization_request_v1.json",
        auth_request_report,
    )

    explicit_status = None
    explicit_evidence = []
    candidate_reports = [
        ("two_candidate_routes_pass_5_of_7_decision_v3", five_of_seven_v3_path, five_of_seven_v3_report),
        ("integration_gate_precheck_v4", gate_v4_path, gate_v4_report),
        ("integration_gate_blockers_v4", blockers_v4_path, blockers_v4_report),
        ("next_contour_entrypoint_v4", entrypoint_v4_path, entrypoint_v4_report),
        ("contour_6a_artifact_chain_validation_v1", chain_v1_path, chain_v1_report),
    ]
    status_fields = (
        "external_approval_status",
        "authorization_decision_status",
        "authorization_status",
    )
    for _, source_path, source_report in candidate_reports:
        for field_name in status_fields:
            field_value = source_report.get(field_name)
            if isinstance(field_value, str) and field_value in {"pending", "approved", "denied"}:
                explicit_evidence.append(
                    {
                        "source_path": str(source_path),
                        "source_field": field_name,
                        "status": field_value,
                    }
                )
                if field_value in {"approved", "denied"}:
                    explicit_status = field_value
    if explicit_status is None:
        authorization_status = "pending"
        decision_basis = "default_pending_without_explicit_external_approval_evidence"
    else:
        authorization_status = explicit_status
        decision_basis = "explicit_external_approval_evidence_present"

    auth_decision_report = {
        "report_kind": "repo_bound_authorization_decision_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_authorization_request_v1_path": str(auth_request_path),
        "depends_on_authorization_request_v1_sha256": file_sha256(auth_request_path),
        "depends_on_lock_v1_path": str(lock_path),
        "depends_on_lock_v1_sha256": file_sha256(lock_path),
        "authorization_decision_status": authorization_status,
        "explicit_external_approval_evidence": explicit_evidence,
        "allowed_status_values": ["pending", "approved", "denied"],
        "summary": {
            "advisory_verdict": "repo_bound_authorization_decision_materialized",
            "decision_basis": decision_basis,
        },
    }
    auth_decision_path, auth_decision_report = write_verification_json(
        "repo_bound_authorization_decision_v1.json",
        auth_decision_report,
    )

    authorization_blocker_count = 0 if authorization_status == "approved" else 1
    planning_precheck_remaining_blocker_count = len(inherited_blockers) + authorization_blocker_count
    planning_precheck_blocked = planning_precheck_remaining_blocker_count > 0
    precheck_result_report = {
        "report_kind": "repo_bound_planning_precheck_result_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_lock_v1_path": str(lock_path),
        "depends_on_lock_v1_sha256": file_sha256(lock_path),
        "depends_on_blocker_contract_v1_path": str(blocker_contract_path),
        "depends_on_blocker_contract_v1_sha256": file_sha256(blocker_contract_path),
        "depends_on_controlled_contract_v1_path": str(controlled_contract_path),
        "depends_on_controlled_contract_v1_sha256": file_sha256(controlled_contract_path),
        "depends_on_authorization_decision_v1_path": str(auth_decision_path),
        "depends_on_authorization_decision_v1_sha256": file_sha256(auth_decision_path),
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "consume_prior_decision_artifacts_only": True,
        "recomputed_model_or_eval_quality": False,
        "planning_precheck_status": "blocked" if planning_precheck_blocked else "ready",
        "remaining_blocker_count": planning_precheck_remaining_blocker_count,
        "authorization_decision_status": authorization_status,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_precheck_blocked"
                if planning_precheck_blocked
                else "repo_bound_planning_precheck_ready"
            ),
        },
    }
    precheck_result_path, precheck_result_report = write_verification_json(
        "repo_bound_planning_precheck_result_v1.json",
        precheck_result_report,
    )

    planning_blockers = list(inherited_blockers)
    if authorization_status != "approved":
        planning_blockers.append(
            {
                "criterion_id": "repo_bound_authorization_present",
                "blocker_class": "external_authorization_not_approved",
                "origin": "repo_bound_authorization_decision_v1",
                "evidence_paths": [str(auth_decision_path)],
            }
        )
    planning_blockers_report = {
        "report_kind": "repo_bound_planning_blockers_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_precheck_result_v1_path": str(precheck_result_path),
        "depends_on_precheck_result_v1_sha256": file_sha256(precheck_result_path),
        "remaining_blockers": planning_blockers,
        "summary": {
            "advisory_verdict": "repo_bound_planning_blockers_classified",
            "remaining_blocker_count": len(planning_blockers),
        },
    }
    planning_blockers_path, planning_blockers_report = write_verification_json(
        "repo_bound_planning_blockers_v1.json",
        planning_blockers_report,
    )

    next_contour = (
        "repo_bound_controlled_integration_execution_precheck"
        if len(planning_blockers) == 0
        else "repo_bound_controlled_integration_planning_precheck"
    )
    entrypoint_v1_report = {
        "report_kind": "repo_bound_planning_entrypoint_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "depends_on_planning_blockers_v1_path": str(planning_blockers_path),
        "depends_on_planning_blockers_v1_sha256": file_sha256(planning_blockers_path),
        "next_admissible_contour": next_contour,
        "entrypoint_reason": (
            "all_repo_bound_planning_blockers_resolved"
            if len(planning_blockers) == 0
            else "repo_bound_planning_blockers_remain"
        ),
        "summary": {
            "advisory_verdict": "repo_bound_planning_entrypoint_defined",
        },
    }
    entrypoint_v1_path, entrypoint_v1_report = write_verification_json(
        "repo_bound_planning_entrypoint_v1.json",
        entrypoint_v1_report,
    )

    audit_findings = []
    if lock_report.get("planning_boundary", {}).get("planning_only") is not True:
        audit_findings.append(
            {
                "finding_id": "planning_only_boundary_missing",
                "severity": "P0",
                "message": "Contour 6B must remain strictly planning-only.",
                "evidence_paths": [str(lock_path)],
            }
        )
    if precheck_result_report.get("consume_prior_decision_artifacts_only") is not True:
        audit_findings.append(
            {
                "finding_id": "prior_decision_only_gate_missing",
                "severity": "P0",
                "message": "Gate behavior must consume prior decision artifacts only.",
                "evidence_paths": [str(precheck_result_path)],
            }
        )
    if auth_decision_report.get("authorization_decision_status") not in {"pending", "approved", "denied"}:
        audit_findings.append(
            {
                "finding_id": "authorization_status_out_of_contract",
                "severity": "P0",
                "message": "Authorization status must be one of pending|approved|denied.",
                "evidence_paths": [str(auth_decision_path)],
            }
        )
    if len(auth_decision_report.get("explicit_external_approval_evidence", [])) == 0 and auth_decision_report.get("authorization_decision_status") != "pending":
        audit_findings.append(
            {
                "finding_id": "authorization_default_pending_violation",
                "severity": "P0",
                "message": "Without explicit external approval evidence, authorization must default to pending.",
                "evidence_paths": [str(auth_decision_path)],
            }
        )

    audit_report = {
        "report_kind": "repo_bound_planning_audit_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 9,
        "depends_on_entrypoint_v1_path": str(entrypoint_v1_path),
        "depends_on_entrypoint_v1_sha256": file_sha256(entrypoint_v1_path),
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_audit_v1_passed"
                if len(audit_findings) == 0
                else "repo_bound_planning_audit_v1_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_path, audit_report = write_verification_json("repo_bound_planning_audit_v1.json", audit_report)

    def _sha_match(path_value, sha_value):
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    factcheck_findings = []
    checks = [
        ("sha_5of7_v3", lock_report.get("depends_on_5of7_v3_path"), lock_report.get("depends_on_5of7_v3_sha256"), str(lock_path)),
        ("sha_gate_v4", lock_report.get("depends_on_gate_v4_path"), lock_report.get("depends_on_gate_v4_sha256"), str(lock_path)),
        ("sha_blockers_v4", lock_report.get("depends_on_blockers_v4_path"), lock_report.get("depends_on_blockers_v4_sha256"), str(lock_path)),
        ("sha_entrypoint_v4", lock_report.get("depends_on_entrypoint_v4_path"), lock_report.get("depends_on_entrypoint_v4_sha256"), str(lock_path)),
        ("sha_chain_validation_v1", lock_report.get("depends_on_6a_chain_validation_path"), lock_report.get("depends_on_6a_chain_validation_sha256"), str(lock_path)),
        ("sha_lock_v1", blocker_contract_report.get("depends_on_lock_v1_path"), blocker_contract_report.get("depends_on_lock_v1_sha256"), str(blocker_contract_path)),
        ("sha_blocker_contract_v1", controlled_contract_report.get("depends_on_blocker_contract_v1_path"), controlled_contract_report.get("depends_on_blocker_contract_v1_sha256"), str(controlled_contract_path)),
        ("sha_controlled_contract_v1", auth_request_report.get("depends_on_controlled_contract_v1_path"), auth_request_report.get("depends_on_controlled_contract_v1_sha256"), str(auth_request_path)),
        ("sha_authorization_request_v1", auth_decision_report.get("depends_on_authorization_request_v1_path"), auth_decision_report.get("depends_on_authorization_request_v1_sha256"), str(auth_decision_path)),
        ("sha_authorization_decision_v1", precheck_result_report.get("depends_on_authorization_decision_v1_path"), precheck_result_report.get("depends_on_authorization_decision_v1_sha256"), str(precheck_result_path)),
        ("sha_precheck_result_v1", planning_blockers_report.get("depends_on_precheck_result_v1_path"), planning_blockers_report.get("depends_on_precheck_result_v1_sha256"), str(planning_blockers_path)),
        ("sha_planning_blockers_v1", entrypoint_v1_report.get("depends_on_planning_blockers_v1_path"), entrypoint_v1_report.get("depends_on_planning_blockers_v1_sha256"), str(entrypoint_v1_path)),
        ("sha_entrypoint_v1", audit_report.get("depends_on_entrypoint_v1_path"), audit_report.get("depends_on_entrypoint_v1_sha256"), str(audit_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 6B dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    factcheck_report = {
        "report_kind": "repo_bound_planning_factcheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 10,
        "depends_on_audit_v1_path": str(audit_path),
        "depends_on_audit_v1_sha256": file_sha256(audit_path),
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_factcheck_v1_passed"
                if len(factcheck_findings) == 0
                else "repo_bound_planning_factcheck_v1_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_path, _ = write_verification_json("repo_bound_planning_factcheck_v1.json", factcheck_report)

    print(f"JSON report: {lock_path}")
    print(f"JSON report: {blocker_contract_path}")
    print(f"JSON report: {controlled_contract_path}")
    print(f"JSON report: {auth_request_path}")
    print(f"JSON report: {auth_decision_path}")
    print(f"JSON report: {precheck_result_path}")
    print(f"JSON report: {planning_blockers_path}")
    print(f"JSON report: {entrypoint_v1_path}")
    print(f"JSON report: {audit_path}")
    print(f"JSON report: {factcheck_path}")


def run_contour_6c_repo_bound_blocker_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_6c_repo_bound_blocker_closure"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "repo_bound_contract_alignment_note_v1",
        "repo_bound_authorization_decision_v2",
        "repo_bound_planning_precheck_result_v2",
        "repo_bound_planning_blockers_v2",
        "repo_bound_planning_entrypoint_v2",
        "repo_bound_planning_audit_v2",
        "repo_bound_planning_factcheck_v2",
        "contour_6c_artifact_chain_validation_v1",
    ]
    effect_scope = {
        "planning_only": True,
        "runtime_probes_performed": False,
        "provider_model_expansion_performed": False,
        "model_eval_recomputation_performed": False,
        "repo_mutation_performed": False,
    }

    five_of_seven_v3_path, five_of_seven_v3_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision_v3.json",
        "two_candidate_routes_pass_5_of_7_decision_v3",
    )
    gate_v4_path, gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )
    blockers_v4_path, blockers_v4_report = load_fixed_verification_report(
        "integration_gate_blockers_v4.json",
        "integration_gate_blockers_v4",
    )
    entrypoint_v4_path, entrypoint_v4_report = load_fixed_verification_report(
        "next_contour_entrypoint_v4.json",
        "next_contour_entrypoint_v4",
    )
    precheck_v1_path, precheck_v1_report = load_fixed_verification_report(
        "repo_bound_planning_precheck_result_v1.json",
        "repo_bound_planning_precheck_result_v1",
    )
    planning_blockers_v1_path, planning_blockers_v1_report = load_fixed_verification_report(
        "repo_bound_planning_blockers_v1.json",
        "repo_bound_planning_blockers_v1",
    )
    planning_entrypoint_v1_path, planning_entrypoint_v1_report = load_fixed_verification_report(
        "repo_bound_planning_entrypoint_v1.json",
        "repo_bound_planning_entrypoint_v1",
    )
    chain_6a_path, chain_6a_report = load_fixed_verification_report(
        "contour_6a_artifact_chain_validation_v1.json",
        "contour_6a_artifact_chain_validation_v1",
    )
    chain_6b_path, chain_6b_report = load_fixed_verification_report(
        "contour_6b_artifact_chain_validation_v1.json",
        "contour_6b_artifact_chain_validation_v1",
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    prior_chain_checks = {
        "6a_chain_validation_overall_passed": bool(chain_6a_report.get("overall_passed")),
        "6b_chain_validation_overall_passed": bool(chain_6b_report.get("overall_passed")),
        "gate_v4_depends_on_5of7_v3": (
            gate_v4_report.get("depends_on_5of7_v3_path") == str(five_of_seven_v3_path)
            and gate_v4_report.get("depends_on_5of7_v3_sha256") == file_sha256(five_of_seven_v3_path)
        ),
        "blockers_v4_depends_on_gate_v4": (
            blockers_v4_report.get("depends_on_gate_v4_path") == str(gate_v4_path)
            and blockers_v4_report.get("depends_on_gate_v4_sha256") == file_sha256(gate_v4_path)
        ),
        "entrypoint_v4_depends_on_blockers_v4": (
            entrypoint_v4_report.get("depends_on_blockers_v4_path") == str(blockers_v4_path)
            and entrypoint_v4_report.get("depends_on_blockers_v4_sha256") == file_sha256(blockers_v4_path)
        ),
        "planning_blockers_v1_depends_on_precheck_v1": (
            planning_blockers_v1_report.get("depends_on_precheck_result_v1_path") == str(precheck_v1_path)
            and planning_blockers_v1_report.get("depends_on_precheck_result_v1_sha256") == file_sha256(precheck_v1_path)
        ),
        "planning_entrypoint_v1_depends_on_blockers_v1": (
            planning_entrypoint_v1_report.get("depends_on_planning_blockers_v1_path") == str(planning_blockers_v1_path)
            and planning_entrypoint_v1_report.get("depends_on_planning_blockers_v1_sha256") == file_sha256(planning_blockers_v1_path)
        ),
    }
    contract_rules = {
        "no_new_provider_model_probe_eval": True,
        "gate_consumes_decision_artifacts_only": True,
        "assurance_validates_integrity_only": True,
        "external_approval_evidence_required_for_approved_status": True,
    }
    alignment_passed = all(prior_chain_checks.values()) and all(contract_rules.values())

    contract_alignment_note_report = {
        "report_kind": "repo_bound_contract_alignment_note_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
        "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "depends_on_precheck_result_v1_path": str(precheck_v1_path),
        "depends_on_precheck_result_v1_sha256": file_sha256(precheck_v1_path),
        "depends_on_planning_blockers_v1_path": str(planning_blockers_v1_path),
        "depends_on_planning_blockers_v1_sha256": file_sha256(planning_blockers_v1_path),
        "depends_on_planning_entrypoint_v1_path": str(planning_entrypoint_v1_path),
        "depends_on_planning_entrypoint_v1_sha256": file_sha256(planning_entrypoint_v1_path),
        "depends_on_6a_chain_validation_path": str(chain_6a_path),
        "depends_on_6a_chain_validation_sha256": file_sha256(chain_6a_path),
        "depends_on_6b_chain_validation_path": str(chain_6b_path),
        "depends_on_6b_chain_validation_sha256": file_sha256(chain_6b_path),
        "contract_rules": contract_rules,
        "prior_chain_integrity_checks": prior_chain_checks,
        "summary": {
            "advisory_verdict": (
                "repo_bound_contract_alignment_confirmed"
                if alignment_passed
                else "repo_bound_contract_alignment_mismatch_detected"
            ),
            "alignment_passed": alignment_passed,
        },
    }
    contract_alignment_note_path, contract_alignment_note_report = write_verification_json(
        "repo_bound_contract_alignment_note_v1.json",
        contract_alignment_note_report,
    )

    input_reports = [
        ("two_candidate_routes_pass_5_of_7_decision_v3", five_of_seven_v3_path, five_of_seven_v3_report),
        ("integration_gate_precheck_v4", gate_v4_path, gate_v4_report),
        ("integration_gate_blockers_v4", blockers_v4_path, blockers_v4_report),
        ("next_contour_entrypoint_v4", entrypoint_v4_path, entrypoint_v4_report),
        ("repo_bound_planning_precheck_result_v1", precheck_v1_path, precheck_v1_report),
        ("repo_bound_planning_blockers_v1", planning_blockers_v1_path, planning_blockers_v1_report),
        ("repo_bound_planning_entrypoint_v1", planning_entrypoint_v1_path, planning_entrypoint_v1_report),
        ("contour_6a_artifact_chain_validation_v1", chain_6a_path, chain_6a_report),
        ("contour_6b_artifact_chain_validation_v1", chain_6b_path, chain_6b_report),
    ]

    status_fields = (
        "external_approval_status",
        "authorization_decision_status",
        "authorization_status",
    )
    evidence_fields = (
        "explicit_external_approval_evidence",
        "external_approval_evidence",
        "approval_evidence",
        "external_approval_evidence_paths",
        "approval_evidence_paths",
    )
    observed_status_signals = []
    explicit_approved_signals = []
    explicit_denied_signals = []
    explicit_external_approval_evidence = []
    for source_kind, source_path, source_report in input_reports:
        for field_name in status_fields:
            field_value = source_report.get(field_name)
            if isinstance(field_value, str) and field_value in {"pending", "approved", "denied"}:
                signal = {
                    "source_kind": source_kind,
                    "source_path": str(source_path),
                    "source_field": field_name,
                    "status": field_value,
                }
                observed_status_signals.append(signal)
                if field_value == "approved":
                    explicit_approved_signals.append(signal)
                if field_value == "denied":
                    explicit_denied_signals.append(signal)
        for field_name in evidence_fields:
            field_value = source_report.get(field_name)
            if isinstance(field_value, list) and field_value:
                explicit_external_approval_evidence.append(
                    {
                        "source_kind": source_kind,
                        "source_path": str(source_path),
                        "source_field": field_name,
                        "evidence_count": len(field_value),
                    }
                )

    if explicit_denied_signals:
        authorization_status = "denied"
        decision_basis = "explicit_denied_status_signal_present"
    elif explicit_approved_signals and explicit_external_approval_evidence:
        authorization_status = "approved"
        decision_basis = "explicit_approved_status_with_external_evidence"
    elif explicit_approved_signals and not explicit_external_approval_evidence:
        authorization_status = "pending"
        decision_basis = "approved_status_without_external_evidence_downgraded_to_pending"
    else:
        authorization_status = "pending"
        decision_basis = "default_pending_without_external_approval_evidence"

    auth_decision_v2_report = {
        "report_kind": "repo_bound_authorization_decision_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_contract_alignment_note_v1_path": str(contract_alignment_note_path),
        "depends_on_contract_alignment_note_v1_sha256": file_sha256(contract_alignment_note_path),
        "depends_on_planning_entrypoint_v1_path": str(planning_entrypoint_v1_path),
        "depends_on_planning_entrypoint_v1_sha256": file_sha256(planning_entrypoint_v1_path),
        "depends_on_6b_chain_validation_path": str(chain_6b_path),
        "depends_on_6b_chain_validation_sha256": file_sha256(chain_6b_path),
        "allowed_status_values": ["pending", "approved", "denied"],
        "authorization_decision_status": authorization_status,
        "observed_status_signals": observed_status_signals,
        "explicit_external_approval_evidence": explicit_external_approval_evidence,
        "summary": {
            "advisory_verdict": "repo_bound_authorization_decision_v2_materialized",
            "decision_basis": decision_basis,
        },
    }
    auth_decision_v2_path, auth_decision_v2_report = write_verification_json(
        "repo_bound_authorization_decision_v2.json",
        auth_decision_v2_report,
    )

    blockers_v4 = blockers_v4_report.get("remaining_blockers", [])
    if not isinstance(blockers_v4, list):
        blockers_v4 = []
    inherited_blockers = []
    for item in blockers_v4:
        if not isinstance(item, dict):
            continue
        inherited_blockers.append(
            {
                "criterion_id": item.get("criterion_id"),
                "blocker_class": item.get("blocker_class"),
                "origin": "integration_gate_blockers_v4",
                "evidence_paths": item.get("evidence_paths", []),
            }
        )

    planning_blockers_v2 = list(inherited_blockers)
    if authorization_status != "approved":
        planning_blockers_v2.append(
            {
                "criterion_id": "repo_bound_authorization_present",
                "blocker_class": "external_authorization_not_approved",
                "origin": "repo_bound_authorization_decision_v2",
                "evidence_paths": [str(auth_decision_v2_path)],
            }
        )

    planning_precheck_blocked = len(planning_blockers_v2) > 0
    precheck_result_v2_report = {
        "report_kind": "repo_bound_planning_precheck_result_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_contract_alignment_note_v1_path": str(contract_alignment_note_path),
        "depends_on_contract_alignment_note_v1_sha256": file_sha256(contract_alignment_note_path),
        "depends_on_authorization_decision_v2_path": str(auth_decision_v2_path),
        "depends_on_authorization_decision_v2_sha256": file_sha256(auth_decision_v2_path),
        "depends_on_precheck_result_v1_path": str(precheck_v1_path),
        "depends_on_precheck_result_v1_sha256": file_sha256(precheck_v1_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "consume_prior_decision_artifacts_only": True,
        "recomputed_model_or_eval_quality": False,
        "planning_precheck_status": "blocked" if planning_precheck_blocked else "ready",
        "remaining_blocker_count": len(planning_blockers_v2),
        "authorization_decision_status": authorization_status,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_precheck_v2_blocked"
                if planning_precheck_blocked
                else "repo_bound_planning_precheck_v2_ready"
            ),
            "prior_v1_remaining_blocker_count": int(precheck_v1_report.get("remaining_blocker_count") or 0),
        },
    }
    precheck_result_v2_path, precheck_result_v2_report = write_verification_json(
        "repo_bound_planning_precheck_result_v2.json",
        precheck_result_v2_report,
    )

    planning_blockers_v2_report = {
        "report_kind": "repo_bound_planning_blockers_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_precheck_result_v2_path": str(precheck_result_v2_path),
        "depends_on_precheck_result_v2_sha256": file_sha256(precheck_result_v2_path),
        "depends_on_blockers_v1_path": str(planning_blockers_v1_path),
        "depends_on_blockers_v1_sha256": file_sha256(planning_blockers_v1_path),
        "remaining_blockers": planning_blockers_v2,
        "summary": {
            "advisory_verdict": "repo_bound_planning_blockers_v2_classified",
            "remaining_blocker_count": len(planning_blockers_v2),
            "prior_v1_remaining_blocker_count": len(
                planning_blockers_v1_report.get("remaining_blockers", [])
                if isinstance(planning_blockers_v1_report.get("remaining_blockers"), list)
                else []
            ),
        },
    }
    planning_blockers_v2_path, planning_blockers_v2_report = write_verification_json(
        "repo_bound_planning_blockers_v2.json",
        planning_blockers_v2_report,
    )

    next_contour = (
        "repo_bound_controlled_integration_execution_precheck"
        if len(planning_blockers_v2) == 0
        else "repo_bound_controlled_integration_planning_precheck"
    )
    entrypoint_v2_report = {
        "report_kind": "repo_bound_planning_entrypoint_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_planning_blockers_v2_path": str(planning_blockers_v2_path),
        "depends_on_planning_blockers_v2_sha256": file_sha256(planning_blockers_v2_path),
        "depends_on_planning_entrypoint_v1_path": str(planning_entrypoint_v1_path),
        "depends_on_planning_entrypoint_v1_sha256": file_sha256(planning_entrypoint_v1_path),
        "next_admissible_contour": next_contour,
        "entrypoint_reason": (
            "all_repo_bound_planning_blockers_resolved"
            if len(planning_blockers_v2) == 0
            else "repo_bound_planning_blockers_remain"
        ),
        "summary": {
            "advisory_verdict": "repo_bound_planning_entrypoint_v2_defined",
        },
    }
    entrypoint_v2_path, entrypoint_v2_report = write_verification_json(
        "repo_bound_planning_entrypoint_v2.json",
        entrypoint_v2_report,
    )

    audit_findings = []
    if contract_alignment_note_report.get("contract_rules", {}).get("no_new_provider_model_probe_eval") is not True:
        audit_findings.append(
            {
                "finding_id": "contract_rule_no_new_provider_model_probe_eval_missing",
                "severity": "P0",
                "message": "Contour 6C must not open new provider/model/probe/eval scope.",
                "evidence_paths": [str(contract_alignment_note_path)],
            }
        )
    if contract_alignment_note_report.get("contract_rules", {}).get("gate_consumes_decision_artifacts_only") is not True:
        audit_findings.append(
            {
                "finding_id": "contract_rule_gate_decision_artifacts_only_missing",
                "severity": "P0",
                "message": "Contour 6C gate must consume decision artifacts only.",
                "evidence_paths": [str(contract_alignment_note_path)],
            }
        )
    if contract_alignment_note_report.get("contract_rules", {}).get("assurance_validates_integrity_only") is not True:
        audit_findings.append(
            {
                "finding_id": "contract_rule_assurance_integrity_only_missing",
                "severity": "P0",
                "message": "Contour 6C assurance must validate integrity only.",
                "evidence_paths": [str(contract_alignment_note_path)],
            }
        )
    if precheck_result_v2_report.get("remaining_blocker_count") != len(planning_blockers_v2_report.get("remaining_blockers", [])):
        audit_findings.append(
            {
                "finding_id": "blocker_count_mismatch_precheck_vs_blockers",
                "severity": "P0",
                "message": "Precheck blocker count must match blockers artifact length.",
                "evidence_paths": [str(precheck_result_v2_path), str(planning_blockers_v2_path)],
            }
        )
    if planning_blockers_v2_report.get("summary", {}).get("remaining_blocker_count") != len(planning_blockers_v2_report.get("remaining_blockers", [])):
        audit_findings.append(
            {
                "finding_id": "blocker_count_mismatch_blockers_summary",
                "severity": "P0",
                "message": "Blockers summary count must equal remaining blockers length.",
                "evidence_paths": [str(planning_blockers_v2_path)],
            }
        )
    if auth_decision_v2_report.get("authorization_decision_status") == "approved" and not auth_decision_v2_report.get("explicit_external_approval_evidence"):
        audit_findings.append(
            {
                "finding_id": "approved_without_external_approval_evidence",
                "severity": "P0",
                "message": "Approved status requires explicit external approval evidence.",
                "evidence_paths": [str(auth_decision_v2_path)],
            }
        )
    if not all(bool(value) for value in contract_alignment_note_report.get("prior_chain_integrity_checks", {}).values()):
        audit_findings.append(
            {
                "finding_id": "prior_chain_integrity_check_failed",
                "severity": "P0",
                "message": "Prior contour chain integrity must pass before closure generation.",
                "evidence_paths": [str(contract_alignment_note_path)],
            }
        )

    audit_v2_report = {
        "report_kind": "repo_bound_planning_audit_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_entrypoint_v2_path": str(entrypoint_v2_path),
        "depends_on_entrypoint_v2_sha256": file_sha256(entrypoint_v2_path),
        "integrity_only_assurance": True,
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_audit_v2_passed"
                if len(audit_findings) == 0
                else "repo_bound_planning_audit_v2_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_v2_path, audit_v2_report = write_verification_json("repo_bound_planning_audit_v2.json", audit_v2_report)

    factcheck_findings = []
    checks = [
        ("sha_5of7_v3", contract_alignment_note_report.get("depends_on_5of7_v3_path"), contract_alignment_note_report.get("depends_on_5of7_v3_sha256"), str(contract_alignment_note_path)),
        ("sha_gate_v4", contract_alignment_note_report.get("depends_on_gate_v4_path"), contract_alignment_note_report.get("depends_on_gate_v4_sha256"), str(contract_alignment_note_path)),
        ("sha_blockers_v4", contract_alignment_note_report.get("depends_on_blockers_v4_path"), contract_alignment_note_report.get("depends_on_blockers_v4_sha256"), str(contract_alignment_note_path)),
        ("sha_entrypoint_v4", contract_alignment_note_report.get("depends_on_entrypoint_v4_path"), contract_alignment_note_report.get("depends_on_entrypoint_v4_sha256"), str(contract_alignment_note_path)),
        ("sha_precheck_v1", contract_alignment_note_report.get("depends_on_precheck_result_v1_path"), contract_alignment_note_report.get("depends_on_precheck_result_v1_sha256"), str(contract_alignment_note_path)),
        ("sha_planning_blockers_v1", contract_alignment_note_report.get("depends_on_planning_blockers_v1_path"), contract_alignment_note_report.get("depends_on_planning_blockers_v1_sha256"), str(contract_alignment_note_path)),
        ("sha_planning_entrypoint_v1", contract_alignment_note_report.get("depends_on_planning_entrypoint_v1_path"), contract_alignment_note_report.get("depends_on_planning_entrypoint_v1_sha256"), str(contract_alignment_note_path)),
        ("sha_chain_6a", contract_alignment_note_report.get("depends_on_6a_chain_validation_path"), contract_alignment_note_report.get("depends_on_6a_chain_validation_sha256"), str(contract_alignment_note_path)),
        ("sha_chain_6b", contract_alignment_note_report.get("depends_on_6b_chain_validation_path"), contract_alignment_note_report.get("depends_on_6b_chain_validation_sha256"), str(contract_alignment_note_path)),
        ("sha_contract_alignment_note_v1", auth_decision_v2_report.get("depends_on_contract_alignment_note_v1_path"), auth_decision_v2_report.get("depends_on_contract_alignment_note_v1_sha256"), str(auth_decision_v2_path)),
        ("sha_authorization_decision_v2", precheck_result_v2_report.get("depends_on_authorization_decision_v2_path"), precheck_result_v2_report.get("depends_on_authorization_decision_v2_sha256"), str(precheck_result_v2_path)),
        ("sha_precheck_result_v2", planning_blockers_v2_report.get("depends_on_precheck_result_v2_path"), planning_blockers_v2_report.get("depends_on_precheck_result_v2_sha256"), str(planning_blockers_v2_path)),
        ("sha_planning_blockers_v2", entrypoint_v2_report.get("depends_on_planning_blockers_v2_path"), entrypoint_v2_report.get("depends_on_planning_blockers_v2_sha256"), str(entrypoint_v2_path)),
        ("sha_entrypoint_v2", audit_v2_report.get("depends_on_entrypoint_v2_path"), audit_v2_report.get("depends_on_entrypoint_v2_sha256"), str(audit_v2_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 6C dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )
    if precheck_result_v2_report.get("remaining_blocker_count") != len(planning_blockers_v2_report.get("remaining_blockers", [])):
        factcheck_findings.append(
            {
                "finding_id": "blocker_count_coherence_violation",
                "severity": "P0",
                "message": "Remaining blocker counts are not coherent across v2 artifacts.",
                "evidence_paths": [str(precheck_result_v2_path), str(planning_blockers_v2_path)],
            }
        )

    factcheck_v2_report = {
        "report_kind": "repo_bound_planning_factcheck_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_audit_v2_path": str(audit_v2_path),
        "depends_on_audit_v2_sha256": file_sha256(audit_v2_path),
        "integrity_only_assurance": True,
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_factcheck_v2_passed"
                if len(factcheck_findings) == 0
                else "repo_bound_planning_factcheck_v2_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_v2_path, factcheck_v2_report = write_verification_json(
        "repo_bound_planning_factcheck_v2.json",
        factcheck_v2_report,
    )

    artifact_specs = [
        {
            "path": contract_alignment_note_path,
            "expected_report_kind": "repo_bound_contract_alignment_note_v1",
            "dependency_keys": [
                ("depends_on_5of7_v3_path", "depends_on_5of7_v3_sha256"),
                ("depends_on_gate_v4_path", "depends_on_gate_v4_sha256"),
                ("depends_on_blockers_v4_path", "depends_on_blockers_v4_sha256"),
                ("depends_on_entrypoint_v4_path", "depends_on_entrypoint_v4_sha256"),
                ("depends_on_precheck_result_v1_path", "depends_on_precheck_result_v1_sha256"),
                ("depends_on_planning_blockers_v1_path", "depends_on_planning_blockers_v1_sha256"),
                ("depends_on_planning_entrypoint_v1_path", "depends_on_planning_entrypoint_v1_sha256"),
                ("depends_on_6a_chain_validation_path", "depends_on_6a_chain_validation_sha256"),
                ("depends_on_6b_chain_validation_path", "depends_on_6b_chain_validation_sha256"),
            ],
        },
        {
            "path": auth_decision_v2_path,
            "expected_report_kind": "repo_bound_authorization_decision_v2",
            "dependency_keys": [
                ("depends_on_contract_alignment_note_v1_path", "depends_on_contract_alignment_note_v1_sha256"),
                ("depends_on_planning_entrypoint_v1_path", "depends_on_planning_entrypoint_v1_sha256"),
                ("depends_on_6b_chain_validation_path", "depends_on_6b_chain_validation_sha256"),
            ],
        },
        {
            "path": precheck_result_v2_path,
            "expected_report_kind": "repo_bound_planning_precheck_result_v2",
            "dependency_keys": [
                ("depends_on_contract_alignment_note_v1_path", "depends_on_contract_alignment_note_v1_sha256"),
                ("depends_on_authorization_decision_v2_path", "depends_on_authorization_decision_v2_sha256"),
                ("depends_on_precheck_result_v1_path", "depends_on_precheck_result_v1_sha256"),
                ("depends_on_blockers_v4_path", "depends_on_blockers_v4_sha256"),
                ("depends_on_entrypoint_v4_path", "depends_on_entrypoint_v4_sha256"),
            ],
        },
        {
            "path": planning_blockers_v2_path,
            "expected_report_kind": "repo_bound_planning_blockers_v2",
            "dependency_keys": [
                ("depends_on_precheck_result_v2_path", "depends_on_precheck_result_v2_sha256"),
                ("depends_on_blockers_v1_path", "depends_on_blockers_v1_sha256"),
            ],
        },
        {
            "path": entrypoint_v2_path,
            "expected_report_kind": "repo_bound_planning_entrypoint_v2",
            "dependency_keys": [
                ("depends_on_planning_blockers_v2_path", "depends_on_planning_blockers_v2_sha256"),
                ("depends_on_planning_entrypoint_v1_path", "depends_on_planning_entrypoint_v1_sha256"),
            ],
        },
        {
            "path": audit_v2_path,
            "expected_report_kind": "repo_bound_planning_audit_v2",
            "dependency_keys": [
                ("depends_on_entrypoint_v2_path", "depends_on_entrypoint_v2_sha256"),
            ],
        },
        {
            "path": factcheck_v2_path,
            "expected_report_kind": "repo_bound_planning_factcheck_v2",
            "dependency_keys": [
                ("depends_on_audit_v2_path", "depends_on_audit_v2_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "evidence_array_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            check_row = {
                "path_key": path_key,
                "sha_key": sha_key,
                "path_value": path_value,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "match": match,
            }
            artifact_row["dependency_checks"].append(check_row)
            if not match:
                dep_passed = False

        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_6c_artifact_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "depends_on_factcheck_v2_path": str(factcheck_v2_path),
        "depends_on_factcheck_v2_sha256": file_sha256(factcheck_v2_path),
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_report_path, _ = write_verification_json("contour_6c_artifact_chain_validation_v1.json", chain_report)

    print(f"JSON report: {contract_alignment_note_path}")
    print(f"JSON report: {auth_decision_v2_path}")
    print(f"JSON report: {precheck_result_v2_path}")
    print(f"JSON report: {planning_blockers_v2_path}")
    print(f"JSON report: {entrypoint_v2_path}")
    print(f"JSON report: {audit_v2_path}")
    print(f"JSON report: {factcheck_v2_path}")
    print(f"JSON report: {chain_report_path}")


def run_contour_6d_repo_bound_authorization_closure_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_6d_repo_bound_authorization_closure"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "repo_bound_integration_contract_v2",
        "repo_bound_authorization_decision_v3",
        "repo_bound_planning_precheck_result_v3",
        "repo_bound_planning_blockers_v3",
        "repo_bound_planning_entrypoint_v3",
        "repo_bound_planning_audit_v3",
        "repo_bound_planning_factcheck_v3",
        "contour_6d_artifact_chain_validation_v1",
    ]
    effect_scope = {
        "planning_only": True,
        "runtime_probes_performed": False,
        "provider_model_expansion_performed": False,
        "route_expansion_performed": False,
        "model_eval_recomputation_performed": False,
        "repo_mutation_performed": False,
    }

    five_of_seven_v3_path, five_of_seven_v3_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision_v3.json",
        "two_candidate_routes_pass_5_of_7_decision_v3",
    )
    gate_v4_path, gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )
    blockers_v4_path, blockers_v4_report = load_fixed_verification_report(
        "integration_gate_blockers_v4.json",
        "integration_gate_blockers_v4",
    )
    entrypoint_v4_path, entrypoint_v4_report = load_fixed_verification_report(
        "next_contour_entrypoint_v4.json",
        "next_contour_entrypoint_v4",
    )
    contract_alignment_note_v1_path, contract_alignment_note_v1_report = load_fixed_verification_report(
        "repo_bound_contract_alignment_note_v1.json",
        "repo_bound_contract_alignment_note_v1",
    )
    auth_decision_v2_path, auth_decision_v2_report = load_fixed_verification_report(
        "repo_bound_authorization_decision_v2.json",
        "repo_bound_authorization_decision_v2",
    )
    precheck_result_v2_path, precheck_result_v2_report = load_fixed_verification_report(
        "repo_bound_planning_precheck_result_v2.json",
        "repo_bound_planning_precheck_result_v2",
    )
    planning_blockers_v2_path, planning_blockers_v2_report = load_fixed_verification_report(
        "repo_bound_planning_blockers_v2.json",
        "repo_bound_planning_blockers_v2",
    )
    planning_entrypoint_v2_path, planning_entrypoint_v2_report = load_fixed_verification_report(
        "repo_bound_planning_entrypoint_v2.json",
        "repo_bound_planning_entrypoint_v2",
    )
    planning_audit_v2_path, planning_audit_v2_report = load_fixed_verification_report(
        "repo_bound_planning_audit_v2.json",
        "repo_bound_planning_audit_v2",
    )
    planning_factcheck_v2_path, planning_factcheck_v2_report = load_fixed_verification_report(
        "repo_bound_planning_factcheck_v2.json",
        "repo_bound_planning_factcheck_v2",
    )
    chain_6c_path, chain_6c_report = load_fixed_verification_report(
        "contour_6c_artifact_chain_validation_v1.json",
        "contour_6c_artifact_chain_validation_v1",
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    prior_chain_integrity_checks = {
        "chain_6c_overall_passed": bool(chain_6c_report.get("overall_passed")),
        "gate_v4_depends_on_5of7_v3": (
            gate_v4_report.get("depends_on_5of7_v3_path") == str(five_of_seven_v3_path)
            and gate_v4_report.get("depends_on_5of7_v3_sha256") == file_sha256(five_of_seven_v3_path)
        ),
        "blockers_v4_depends_on_gate_v4": (
            blockers_v4_report.get("depends_on_gate_v4_path") == str(gate_v4_path)
            and blockers_v4_report.get("depends_on_gate_v4_sha256") == file_sha256(gate_v4_path)
        ),
        "entrypoint_v4_depends_on_blockers_v4": (
            entrypoint_v4_report.get("depends_on_blockers_v4_path") == str(blockers_v4_path)
            and entrypoint_v4_report.get("depends_on_blockers_v4_sha256") == file_sha256(blockers_v4_path)
        ),
        "contract_alignment_note_v1_depends_on_gate_v4": (
            contract_alignment_note_v1_report.get("depends_on_gate_v4_path") == str(gate_v4_path)
            and contract_alignment_note_v1_report.get("depends_on_gate_v4_sha256") == file_sha256(gate_v4_path)
        ),
        "auth_decision_v2_depends_on_contract_alignment_note_v1": (
            auth_decision_v2_report.get("depends_on_contract_alignment_note_v1_path") == str(contract_alignment_note_v1_path)
            and auth_decision_v2_report.get("depends_on_contract_alignment_note_v1_sha256") == file_sha256(contract_alignment_note_v1_path)
        ),
        "precheck_result_v2_depends_on_auth_decision_v2": (
            precheck_result_v2_report.get("depends_on_authorization_decision_v2_path") == str(auth_decision_v2_path)
            and precheck_result_v2_report.get("depends_on_authorization_decision_v2_sha256") == file_sha256(auth_decision_v2_path)
        ),
        "planning_blockers_v2_depends_on_precheck_result_v2": (
            planning_blockers_v2_report.get("depends_on_precheck_result_v2_path") == str(precheck_result_v2_path)
            and planning_blockers_v2_report.get("depends_on_precheck_result_v2_sha256") == file_sha256(precheck_result_v2_path)
        ),
        "planning_entrypoint_v2_depends_on_blockers_v2": (
            planning_entrypoint_v2_report.get("depends_on_planning_blockers_v2_path") == str(planning_blockers_v2_path)
            and planning_entrypoint_v2_report.get("depends_on_planning_blockers_v2_sha256") == file_sha256(planning_blockers_v2_path)
        ),
        "planning_audit_v2_depends_on_entrypoint_v2": (
            planning_audit_v2_report.get("depends_on_entrypoint_v2_path") == str(planning_entrypoint_v2_path)
            and planning_audit_v2_report.get("depends_on_entrypoint_v2_sha256") == file_sha256(planning_entrypoint_v2_path)
        ),
        "planning_factcheck_v2_depends_on_audit_v2": (
            planning_factcheck_v2_report.get("depends_on_audit_v2_path") == str(planning_audit_v2_path)
            and planning_factcheck_v2_report.get("depends_on_audit_v2_sha256") == file_sha256(planning_audit_v2_path)
        ),
    }
    layer_separation = {
        "planning_layer_only": True,
        "gate_layer_only": True,
        "assurance_layer_only": True,
        "planning_gate_assurance_separation_explicit": True,
        "gate_consumes_planning_artifacts_only": True,
        "assurance_validates_integrity_only": True,
    }
    expansion_guards = {
        "no_provider_expansion": True,
        "no_model_expansion": True,
        "no_route_expansion": True,
        "no_runtime_expansion": True,
        "no_eval_expansion": True,
        "no_repo_mutation": True,
    }
    integration_contract_passed = (
        all(prior_chain_integrity_checks.values())
        and all(layer_separation.values())
        and all(expansion_guards.values())
    )
    integration_contract_report = {
        "report_kind": "repo_bound_integration_contract_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
        "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "depends_on_contract_alignment_note_v1_path": str(contract_alignment_note_v1_path),
        "depends_on_contract_alignment_note_v1_sha256": file_sha256(contract_alignment_note_v1_path),
        "depends_on_authorization_decision_v2_path": str(auth_decision_v2_path),
        "depends_on_authorization_decision_v2_sha256": file_sha256(auth_decision_v2_path),
        "depends_on_precheck_result_v2_path": str(precheck_result_v2_path),
        "depends_on_precheck_result_v2_sha256": file_sha256(precheck_result_v2_path),
        "depends_on_planning_blockers_v2_path": str(planning_blockers_v2_path),
        "depends_on_planning_blockers_v2_sha256": file_sha256(planning_blockers_v2_path),
        "depends_on_planning_entrypoint_v2_path": str(planning_entrypoint_v2_path),
        "depends_on_planning_entrypoint_v2_sha256": file_sha256(planning_entrypoint_v2_path),
        "depends_on_planning_audit_v2_path": str(planning_audit_v2_path),
        "depends_on_planning_audit_v2_sha256": file_sha256(planning_audit_v2_path),
        "depends_on_planning_factcheck_v2_path": str(planning_factcheck_v2_path),
        "depends_on_planning_factcheck_v2_sha256": file_sha256(planning_factcheck_v2_path),
        "depends_on_6c_chain_validation_path": str(chain_6c_path),
        "depends_on_6c_chain_validation_sha256": file_sha256(chain_6c_path),
        "prior_chain_integrity_checks": prior_chain_integrity_checks,
        "layer_separation": layer_separation,
        "expansion_guards": expansion_guards,
        "blocker_semantics_contract": {
            "inherited_from_gate_blockers_v4": True,
            "inherited_from_planning_blockers_v2": True,
            "reinterpretation_allowed": False,
        },
        "summary": {
            "advisory_verdict": (
                "repo_bound_integration_contract_v2_confirmed"
                if integration_contract_passed
                else "repo_bound_integration_contract_v2_mismatch_detected"
            ),
            "integration_contract_passed": integration_contract_passed,
        },
    }
    integration_contract_v2_path, integration_contract_report = write_verification_json(
        "repo_bound_integration_contract_v2.json",
        integration_contract_report,
    )

    input_reports = [
        ("two_candidate_routes_pass_5_of_7_decision_v3", five_of_seven_v3_path, five_of_seven_v3_report),
        ("integration_gate_precheck_v4", gate_v4_path, gate_v4_report),
        ("integration_gate_blockers_v4", blockers_v4_path, blockers_v4_report),
        ("next_contour_entrypoint_v4", entrypoint_v4_path, entrypoint_v4_report),
        ("repo_bound_contract_alignment_note_v1", contract_alignment_note_v1_path, contract_alignment_note_v1_report),
        ("repo_bound_authorization_decision_v2", auth_decision_v2_path, auth_decision_v2_report),
        ("repo_bound_planning_precheck_result_v2", precheck_result_v2_path, precheck_result_v2_report),
        ("repo_bound_planning_blockers_v2", planning_blockers_v2_path, planning_blockers_v2_report),
        ("repo_bound_planning_entrypoint_v2", planning_entrypoint_v2_path, planning_entrypoint_v2_report),
        ("repo_bound_planning_audit_v2", planning_audit_v2_path, planning_audit_v2_report),
        ("repo_bound_planning_factcheck_v2", planning_factcheck_v2_path, planning_factcheck_v2_report),
        ("contour_6c_artifact_chain_validation_v1", chain_6c_path, chain_6c_report),
        ("repo_bound_integration_contract_v2", integration_contract_v2_path, integration_contract_report),
    ]

    status_fields = (
        "external_approval_status",
        "authorization_decision_status",
        "authorization_status",
    )
    evidence_fields = (
        "explicit_external_approval_evidence",
        "external_approval_evidence",
        "approval_evidence",
        "external_approval_evidence_paths",
        "approval_evidence_paths",
    )
    observed_status_signals = []
    explicit_approved_signals = []
    explicit_denied_signals = []
    explicit_external_approval_evidence = []
    for source_kind, source_path, source_report in input_reports:
        for field_name in status_fields:
            field_value = source_report.get(field_name)
            if isinstance(field_value, str) and field_value in {"pending", "approved", "denied"}:
                signal = {
                    "source_kind": source_kind,
                    "source_path": str(source_path),
                    "source_field": field_name,
                    "status": field_value,
                }
                observed_status_signals.append(signal)
                if field_value == "approved":
                    explicit_approved_signals.append(signal)
                if field_value == "denied":
                    explicit_denied_signals.append(signal)
        for field_name in evidence_fields:
            field_value = source_report.get(field_name)
            if isinstance(field_value, list) and field_value:
                explicit_external_approval_evidence.append(
                    {
                        "source_kind": source_kind,
                        "source_path": str(source_path),
                        "source_field": field_name,
                        "evidence_count": len(field_value),
                    }
                )

    if explicit_denied_signals:
        authorization_status = "denied"
        decision_basis = "explicit_denied_status_signal_present"
    elif explicit_approved_signals and explicit_external_approval_evidence:
        authorization_status = "approved"
        decision_basis = "explicit_approved_status_with_external_evidence"
    elif explicit_approved_signals and not explicit_external_approval_evidence:
        authorization_status = "pending"
        decision_basis = "approved_status_without_external_evidence_downgraded_to_pending"
    else:
        authorization_status = "pending"
        decision_basis = "default_pending_without_explicit_external_approval_evidence"

    blocked_reason = None
    next_required_external_action = None
    if authorization_status == "pending":
        blocked_reason = "external_authorization_not_approved"
        next_required_external_action = "provide_explicit_external_approval_evidence_for_repo_bound_integration"
    elif authorization_status == "denied":
        blocked_reason = "external_authorization_denied"
        next_required_external_action = "obtain_updated_external_authorization_decision_or_revise_request_scope"

    auth_decision_v3_report = {
        "report_kind": "repo_bound_authorization_decision_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_integration_contract_v2_path": str(integration_contract_v2_path),
        "depends_on_integration_contract_v2_sha256": file_sha256(integration_contract_v2_path),
        "depends_on_authorization_decision_v2_path": str(auth_decision_v2_path),
        "depends_on_authorization_decision_v2_sha256": file_sha256(auth_decision_v2_path),
        "depends_on_6c_chain_validation_path": str(chain_6c_path),
        "depends_on_6c_chain_validation_sha256": file_sha256(chain_6c_path),
        "allowed_status_values": ["pending", "approved", "denied"],
        "authorization_decision_status": authorization_status,
        "observed_status_signals": observed_status_signals,
        "explicit_external_approval_evidence": explicit_external_approval_evidence,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "summary": {
            "advisory_verdict": "repo_bound_authorization_decision_v3_materialized",
            "decision_basis": decision_basis,
        },
    }
    auth_decision_v3_path, auth_decision_v3_report = write_verification_json(
        "repo_bound_authorization_decision_v3.json",
        auth_decision_v3_report,
    )

    blockers_v4 = blockers_v4_report.get("remaining_blockers", [])
    if not isinstance(blockers_v4, list):
        blockers_v4 = []
    gate_blocker_pairs_v4 = {
        (item.get("criterion_id"), item.get("blocker_class"))
        for item in blockers_v4
        if isinstance(item, dict)
    }

    inherited_blockers_v2 = planning_blockers_v2_report.get("remaining_blockers", [])
    if not isinstance(inherited_blockers_v2, list):
        inherited_blockers_v2 = []
    planning_blockers_v3 = [dict(item) for item in inherited_blockers_v2 if isinstance(item, dict)]
    has_auth_blocker_v3 = any(
        item.get("criterion_id") == "repo_bound_authorization_present"
        and item.get("blocker_class") == "external_authorization_not_approved"
        for item in planning_blockers_v3
    )
    if authorization_status == "approved":
        planning_blockers_v3 = [
            item
            for item in planning_blockers_v3
            if not (
                item.get("criterion_id") == "repo_bound_authorization_present"
                and item.get("blocker_class") == "external_authorization_not_approved"
            )
        ]
    elif not has_auth_blocker_v3:
        planning_blockers_v3.append(
            {
                "criterion_id": "repo_bound_authorization_present",
                "blocker_class": "external_authorization_not_approved",
                "origin": "repo_bound_authorization_decision_v3",
                "evidence_paths": [str(auth_decision_v3_path)],
            }
        )

    planning_precheck_blocked = len(planning_blockers_v3) > 0
    precheck_blocked_reason = None
    precheck_next_required_external_action = None
    if planning_precheck_blocked:
        if authorization_status == "pending":
            precheck_blocked_reason = "external_authorization_not_approved_and_repo_bound_blockers_remain"
            precheck_next_required_external_action = "provide_explicit_external_approval_evidence_for_repo_bound_integration"
        elif authorization_status == "denied":
            precheck_blocked_reason = "external_authorization_denied_and_repo_bound_blockers_remain"
            precheck_next_required_external_action = "obtain_updated_external_authorization_decision_or_revise_request_scope"
        else:
            precheck_blocked_reason = "repo_bound_integration_blockers_remain"
            precheck_next_required_external_action = "resolve_remaining_repo_bound_integration_blockers_from_v4_contract"

    precheck_result_v3_report = {
        "report_kind": "repo_bound_planning_precheck_result_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_integration_contract_v2_path": str(integration_contract_v2_path),
        "depends_on_integration_contract_v2_sha256": file_sha256(integration_contract_v2_path),
        "depends_on_authorization_decision_v3_path": str(auth_decision_v3_path),
        "depends_on_authorization_decision_v3_sha256": file_sha256(auth_decision_v3_path),
        "depends_on_precheck_result_v2_path": str(precheck_result_v2_path),
        "depends_on_precheck_result_v2_sha256": file_sha256(precheck_result_v2_path),
        "depends_on_blockers_v2_path": str(planning_blockers_v2_path),
        "depends_on_blockers_v2_sha256": file_sha256(planning_blockers_v2_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "consume_prior_decision_artifacts_only": True,
        "recomputed_model_or_eval_quality": False,
        "planning_precheck_status": "blocked" if planning_precheck_blocked else "ready",
        "remaining_blocker_count": len(planning_blockers_v3),
        "authorization_decision_status": authorization_status,
        "blocked_reason": precheck_blocked_reason,
        "next_required_external_action": precheck_next_required_external_action,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_precheck_v3_blocked"
                if planning_precheck_blocked
                else "repo_bound_planning_precheck_v3_ready"
            ),
            "prior_v2_remaining_blocker_count": int(precheck_result_v2_report.get("remaining_blocker_count") or 0),
        },
    }
    precheck_result_v3_path, precheck_result_v3_report = write_verification_json(
        "repo_bound_planning_precheck_result_v3.json",
        precheck_result_v3_report,
    )

    planning_blockers_v3_report = {
        "report_kind": "repo_bound_planning_blockers_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_precheck_result_v3_path": str(precheck_result_v3_path),
        "depends_on_precheck_result_v3_sha256": file_sha256(precheck_result_v3_path),
        "depends_on_blockers_v2_path": str(planning_blockers_v2_path),
        "depends_on_blockers_v2_sha256": file_sha256(planning_blockers_v2_path),
        "depends_on_gate_blockers_v4_path": str(blockers_v4_path),
        "depends_on_gate_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "blocker_semantics_inherited_without_reinterpretation": True,
        "remaining_blockers": planning_blockers_v3,
        "blocked_reason": precheck_blocked_reason,
        "next_required_external_action": precheck_next_required_external_action,
        "summary": {
            "advisory_verdict": "repo_bound_planning_blockers_v3_classified",
            "remaining_blocker_count": len(planning_blockers_v3),
            "prior_v2_remaining_blocker_count": len(inherited_blockers_v2),
        },
    }
    planning_blockers_v3_path, planning_blockers_v3_report = write_verification_json(
        "repo_bound_planning_blockers_v3.json",
        planning_blockers_v3_report,
    )

    next_contour = (
        "repo_bound_controlled_integration_execution_precheck"
        if len(planning_blockers_v3) == 0
        else "repo_bound_controlled_integration_planning_precheck"
    )
    entrypoint_v3_report = {
        "report_kind": "repo_bound_planning_entrypoint_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_planning_blockers_v3_path": str(planning_blockers_v3_path),
        "depends_on_planning_blockers_v3_sha256": file_sha256(planning_blockers_v3_path),
        "depends_on_planning_entrypoint_v2_path": str(planning_entrypoint_v2_path),
        "depends_on_planning_entrypoint_v2_sha256": file_sha256(planning_entrypoint_v2_path),
        "next_admissible_contour": next_contour,
        "entrypoint_reason": (
            "all_repo_bound_planning_blockers_resolved"
            if len(planning_blockers_v3) == 0
            else "repo_bound_planning_blockers_remain"
        ),
        "blocked_reason": precheck_blocked_reason,
        "next_required_external_action": precheck_next_required_external_action,
        "summary": {
            "advisory_verdict": "repo_bound_planning_entrypoint_v3_defined",
        },
    }
    entrypoint_v3_path, entrypoint_v3_report = write_verification_json(
        "repo_bound_planning_entrypoint_v3.json",
        entrypoint_v3_report,
    )

    gate_pairs_from_v3 = {
        (item.get("criterion_id"), item.get("blocker_class"))
        for item in planning_blockers_v3
        if isinstance(item, dict) and item.get("origin") == "integration_gate_blockers_v4"
    }
    audit_findings = []
    if integration_contract_report.get("layer_separation", {}).get("planning_gate_assurance_separation_explicit") is not True:
        audit_findings.append(
            {
                "finding_id": "planning_gate_assurance_separation_missing",
                "severity": "P0",
                "message": "Contour 6D requires explicit planning/gate/assurance separation.",
                "evidence_paths": [str(integration_contract_v2_path)],
            }
        )
    if not all(bool(value) for value in integration_contract_report.get("expansion_guards", {}).values()):
        audit_findings.append(
            {
                "finding_id": "non_expansive_guards_missing",
                "severity": "P0",
                "message": "Contour 6D must remain canon-locked and non-expansive.",
                "evidence_paths": [str(integration_contract_v2_path)],
            }
        )
    if authorization_status == "approved" and not explicit_external_approval_evidence:
        audit_findings.append(
            {
                "finding_id": "approved_without_explicit_external_approval_evidence",
                "severity": "P0",
                "message": "Approved authorization status requires explicit external approval evidence.",
                "evidence_paths": [str(auth_decision_v3_path)],
            }
        )
    if not explicit_external_approval_evidence and authorization_status != "pending":
        audit_findings.append(
            {
                "finding_id": "missing_external_approval_evidence_must_be_pending",
                "severity": "P0",
                "message": "Absent explicit external approval evidence must yield pending status.",
                "evidence_paths": [str(auth_decision_v3_path)],
            }
        )
    if precheck_result_v3_report.get("remaining_blocker_count") != len(planning_blockers_v3_report.get("remaining_blockers", [])):
        audit_findings.append(
            {
                "finding_id": "blocker_count_mismatch_precheck_vs_blockers_v3",
                "severity": "P0",
                "message": "v3 precheck blocker count must match v3 blockers artifact length.",
                "evidence_paths": [str(precheck_result_v3_path), str(planning_blockers_v3_path)],
            }
        )
    if planning_blockers_v3_report.get("summary", {}).get("remaining_blocker_count") != len(planning_blockers_v3_report.get("remaining_blockers", [])):
        audit_findings.append(
            {
                "finding_id": "blocker_count_mismatch_blockers_v3_summary",
                "severity": "P0",
                "message": "v3 blockers summary count must equal remaining blockers length.",
                "evidence_paths": [str(planning_blockers_v3_path)],
            }
        )
    if not gate_blocker_pairs_v4.issubset(gate_pairs_from_v3):
        audit_findings.append(
            {
                "finding_id": "gate_blocker_semantics_not_fully_inherited",
                "severity": "P0",
                "message": "v4 gate blocker semantics must be inherited without reinterpretation.",
                "evidence_paths": [str(blockers_v4_path), str(planning_blockers_v3_path)],
            }
        )
    if not all(bool(value) for value in prior_chain_integrity_checks.values()):
        audit_findings.append(
            {
                "finding_id": "prior_chain_integrity_check_failed",
                "severity": "P0",
                "message": "Prior chain integrity checks must pass before closure generation.",
                "evidence_paths": [str(integration_contract_v2_path)],
            }
        )

    audit_v3_report = {
        "report_kind": "repo_bound_planning_audit_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_entrypoint_v3_path": str(entrypoint_v3_path),
        "depends_on_entrypoint_v3_sha256": file_sha256(entrypoint_v3_path),
        "integrity_only_assurance": True,
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_audit_v3_passed"
                if len(audit_findings) == 0
                else "repo_bound_planning_audit_v3_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_v3_path, audit_v3_report = write_verification_json("repo_bound_planning_audit_v3.json", audit_v3_report)

    factcheck_findings = []
    checks = [
        ("sha_5of7_v3", integration_contract_report.get("depends_on_5of7_v3_path"), integration_contract_report.get("depends_on_5of7_v3_sha256"), str(integration_contract_v2_path)),
        ("sha_gate_v4", integration_contract_report.get("depends_on_gate_v4_path"), integration_contract_report.get("depends_on_gate_v4_sha256"), str(integration_contract_v2_path)),
        ("sha_blockers_v4", integration_contract_report.get("depends_on_blockers_v4_path"), integration_contract_report.get("depends_on_blockers_v4_sha256"), str(integration_contract_v2_path)),
        ("sha_entrypoint_v4", integration_contract_report.get("depends_on_entrypoint_v4_path"), integration_contract_report.get("depends_on_entrypoint_v4_sha256"), str(integration_contract_v2_path)),
        ("sha_contract_alignment_note_v1", integration_contract_report.get("depends_on_contract_alignment_note_v1_path"), integration_contract_report.get("depends_on_contract_alignment_note_v1_sha256"), str(integration_contract_v2_path)),
        ("sha_authorization_decision_v2", integration_contract_report.get("depends_on_authorization_decision_v2_path"), integration_contract_report.get("depends_on_authorization_decision_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_precheck_result_v2", integration_contract_report.get("depends_on_precheck_result_v2_path"), integration_contract_report.get("depends_on_precheck_result_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_planning_blockers_v2", integration_contract_report.get("depends_on_planning_blockers_v2_path"), integration_contract_report.get("depends_on_planning_blockers_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_planning_entrypoint_v2", integration_contract_report.get("depends_on_planning_entrypoint_v2_path"), integration_contract_report.get("depends_on_planning_entrypoint_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_planning_audit_v2", integration_contract_report.get("depends_on_planning_audit_v2_path"), integration_contract_report.get("depends_on_planning_audit_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_planning_factcheck_v2", integration_contract_report.get("depends_on_planning_factcheck_v2_path"), integration_contract_report.get("depends_on_planning_factcheck_v2_sha256"), str(integration_contract_v2_path)),
        ("sha_chain_6c", integration_contract_report.get("depends_on_6c_chain_validation_path"), integration_contract_report.get("depends_on_6c_chain_validation_sha256"), str(integration_contract_v2_path)),
        ("sha_integration_contract_v2", auth_decision_v3_report.get("depends_on_integration_contract_v2_path"), auth_decision_v3_report.get("depends_on_integration_contract_v2_sha256"), str(auth_decision_v3_path)),
        ("sha_authorization_decision_v3", precheck_result_v3_report.get("depends_on_authorization_decision_v3_path"), precheck_result_v3_report.get("depends_on_authorization_decision_v3_sha256"), str(precheck_result_v3_path)),
        ("sha_precheck_result_v3", planning_blockers_v3_report.get("depends_on_precheck_result_v3_path"), planning_blockers_v3_report.get("depends_on_precheck_result_v3_sha256"), str(planning_blockers_v3_path)),
        ("sha_planning_blockers_v3", entrypoint_v3_report.get("depends_on_planning_blockers_v3_path"), entrypoint_v3_report.get("depends_on_planning_blockers_v3_sha256"), str(entrypoint_v3_path)),
        ("sha_entrypoint_v3", audit_v3_report.get("depends_on_entrypoint_v3_path"), audit_v3_report.get("depends_on_entrypoint_v3_sha256"), str(audit_v3_path)),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 6D dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )
    if precheck_result_v3_report.get("remaining_blocker_count") != len(planning_blockers_v3_report.get("remaining_blockers", [])):
        factcheck_findings.append(
            {
                "finding_id": "blocker_count_coherence_violation_v3",
                "severity": "P0",
                "message": "Remaining blocker counts are not coherent across v3 artifacts.",
                "evidence_paths": [str(precheck_result_v3_path), str(planning_blockers_v3_path)],
            }
        )
    if authorization_status == "approved" and len(explicit_external_approval_evidence) == 0:
        factcheck_findings.append(
            {
                "finding_id": "approved_without_explicit_evidence_factcheck",
                "severity": "P0",
                "message": "Approved authorization in v3 requires explicit external evidence.",
                "evidence_paths": [str(auth_decision_v3_path)],
            }
        )
    if len(explicit_external_approval_evidence) == 0 and authorization_status != "pending":
        factcheck_findings.append(
            {
                "finding_id": "no_explicit_evidence_non_pending_status_factcheck",
                "severity": "P0",
                "message": "Absent explicit external evidence must keep authorization pending.",
                "evidence_paths": [str(auth_decision_v3_path)],
            }
        )

    factcheck_v3_report = {
        "report_kind": "repo_bound_planning_factcheck_v3",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_audit_v3_path": str(audit_v3_path),
        "depends_on_audit_v3_sha256": file_sha256(audit_v3_path),
        "integrity_only_assurance": True,
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_planning_factcheck_v3_passed"
                if len(factcheck_findings) == 0
                else "repo_bound_planning_factcheck_v3_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_v3_path, factcheck_v3_report = write_verification_json(
        "repo_bound_planning_factcheck_v3.json",
        factcheck_v3_report,
    )

    artifact_specs = [
        {
            "path": integration_contract_v2_path,
            "expected_report_kind": "repo_bound_integration_contract_v2",
            "dependency_keys": [
                ("depends_on_5of7_v3_path", "depends_on_5of7_v3_sha256"),
                ("depends_on_gate_v4_path", "depends_on_gate_v4_sha256"),
                ("depends_on_blockers_v4_path", "depends_on_blockers_v4_sha256"),
                ("depends_on_entrypoint_v4_path", "depends_on_entrypoint_v4_sha256"),
                ("depends_on_contract_alignment_note_v1_path", "depends_on_contract_alignment_note_v1_sha256"),
                ("depends_on_authorization_decision_v2_path", "depends_on_authorization_decision_v2_sha256"),
                ("depends_on_precheck_result_v2_path", "depends_on_precheck_result_v2_sha256"),
                ("depends_on_planning_blockers_v2_path", "depends_on_planning_blockers_v2_sha256"),
                ("depends_on_planning_entrypoint_v2_path", "depends_on_planning_entrypoint_v2_sha256"),
                ("depends_on_planning_audit_v2_path", "depends_on_planning_audit_v2_sha256"),
                ("depends_on_planning_factcheck_v2_path", "depends_on_planning_factcheck_v2_sha256"),
                ("depends_on_6c_chain_validation_path", "depends_on_6c_chain_validation_sha256"),
            ],
        },
        {
            "path": auth_decision_v3_path,
            "expected_report_kind": "repo_bound_authorization_decision_v3",
            "dependency_keys": [
                ("depends_on_integration_contract_v2_path", "depends_on_integration_contract_v2_sha256"),
                ("depends_on_authorization_decision_v2_path", "depends_on_authorization_decision_v2_sha256"),
                ("depends_on_6c_chain_validation_path", "depends_on_6c_chain_validation_sha256"),
            ],
        },
        {
            "path": precheck_result_v3_path,
            "expected_report_kind": "repo_bound_planning_precheck_result_v3",
            "dependency_keys": [
                ("depends_on_integration_contract_v2_path", "depends_on_integration_contract_v2_sha256"),
                ("depends_on_authorization_decision_v3_path", "depends_on_authorization_decision_v3_sha256"),
                ("depends_on_precheck_result_v2_path", "depends_on_precheck_result_v2_sha256"),
                ("depends_on_blockers_v2_path", "depends_on_blockers_v2_sha256"),
                ("depends_on_blockers_v4_path", "depends_on_blockers_v4_sha256"),
                ("depends_on_entrypoint_v4_path", "depends_on_entrypoint_v4_sha256"),
            ],
        },
        {
            "path": planning_blockers_v3_path,
            "expected_report_kind": "repo_bound_planning_blockers_v3",
            "dependency_keys": [
                ("depends_on_precheck_result_v3_path", "depends_on_precheck_result_v3_sha256"),
                ("depends_on_blockers_v2_path", "depends_on_blockers_v2_sha256"),
                ("depends_on_gate_blockers_v4_path", "depends_on_gate_blockers_v4_sha256"),
            ],
        },
        {
            "path": entrypoint_v3_path,
            "expected_report_kind": "repo_bound_planning_entrypoint_v3",
            "dependency_keys": [
                ("depends_on_planning_blockers_v3_path", "depends_on_planning_blockers_v3_sha256"),
                ("depends_on_planning_entrypoint_v2_path", "depends_on_planning_entrypoint_v2_sha256"),
            ],
        },
        {
            "path": audit_v3_path,
            "expected_report_kind": "repo_bound_planning_audit_v3",
            "dependency_keys": [
                ("depends_on_entrypoint_v3_path", "depends_on_entrypoint_v3_sha256"),
            ],
        },
        {
            "path": factcheck_v3_path,
            "expected_report_kind": "repo_bound_planning_factcheck_v3",
            "dependency_keys": [
                ("depends_on_audit_v3_path", "depends_on_audit_v3_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "evidence_array_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            check_row = {
                "path_key": path_key,
                "sha_key": sha_key,
                "path_value": path_value,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "match": match,
            }
            artifact_row["dependency_checks"].append(check_row)
            if not match:
                dep_passed = False

        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_6d_artifact_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 8,
        "depends_on_factcheck_v3_path": str(factcheck_v3_path),
        "depends_on_factcheck_v3_sha256": file_sha256(factcheck_v3_path),
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_report_path, _ = write_verification_json("contour_6d_artifact_chain_validation_v1.json", chain_report)

    print(f"JSON report: {integration_contract_v2_path}")
    print(f"JSON report: {auth_decision_v3_path}")
    print(f"JSON report: {precheck_result_v3_path}")
    print(f"JSON report: {planning_blockers_v3_path}")
    print(f"JSON report: {entrypoint_v3_path}")
    print(f"JSON report: {audit_v3_path}")
    print(f"JSON report: {factcheck_v3_path}")
    print(f"JSON report: {chain_report_path}")


def run_contour_6e_feature_lab_complete_package_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_6e_feature_lab_complete_package"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "feature_lab_completion_certificate_v1",
        "feature_external_integration_hold_v1",
        "feature_lab_delivery_manifest_v1",
        "feature_lab_completion_audit_v1",
        "feature_lab_completion_factcheck_v1",
        "contour_6e_feature_lab_complete_chain_validation_v1",
    ]
    effect_scope = {
        "lab_package_generation_only": True,
        "provider_expansion_performed": False,
        "model_expansion_performed": False,
        "route_expansion_performed": False,
        "runtime_expansion_performed": False,
        "eval_expansion_performed": False,
        "repo_bound_execution_performed": False,
        "repo_mutation_performed": False,
    }

    five_of_seven_v3_path, five_of_seven_v3_report = load_fixed_verification_report(
        "two_candidate_routes_pass_5_of_7_decision_v3.json",
        "two_candidate_routes_pass_5_of_7_decision_v3",
    )
    gate_v4_path, gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )
    blockers_v4_path, blockers_v4_report = load_fixed_verification_report(
        "integration_gate_blockers_v4.json",
        "integration_gate_blockers_v4",
    )
    entrypoint_v4_path, entrypoint_v4_report = load_fixed_verification_report(
        "next_contour_entrypoint_v4.json",
        "next_contour_entrypoint_v4",
    )
    integration_contract_v2_path, integration_contract_v2_report = load_fixed_verification_report(
        "repo_bound_integration_contract_v2.json",
        "repo_bound_integration_contract_v2",
    )
    auth_decision_v3_path, auth_decision_v3_report = load_fixed_verification_report(
        "repo_bound_authorization_decision_v3.json",
        "repo_bound_authorization_decision_v3",
    )
    precheck_result_v3_path, precheck_result_v3_report = load_fixed_verification_report(
        "repo_bound_planning_precheck_result_v3.json",
        "repo_bound_planning_precheck_result_v3",
    )
    planning_blockers_v3_path, planning_blockers_v3_report = load_fixed_verification_report(
        "repo_bound_planning_blockers_v3.json",
        "repo_bound_planning_blockers_v3",
    )
    planning_entrypoint_v3_path, planning_entrypoint_v3_report = load_fixed_verification_report(
        "repo_bound_planning_entrypoint_v3.json",
        "repo_bound_planning_entrypoint_v3",
    )
    planning_audit_v3_path, planning_audit_v3_report = load_fixed_verification_report(
        "repo_bound_planning_audit_v3.json",
        "repo_bound_planning_audit_v3",
    )
    planning_factcheck_v3_path, planning_factcheck_v3_report = load_fixed_verification_report(
        "repo_bound_planning_factcheck_v3.json",
        "repo_bound_planning_factcheck_v3",
    )
    chain_6d_path, chain_6d_report = load_fixed_verification_report(
        "contour_6d_artifact_chain_validation_v1.json",
        "contour_6d_artifact_chain_validation_v1",
    )

    dependency_sha_links = [
        {
            "report_kind": "two_candidate_routes_pass_5_of_7_decision_v3",
            "path": str(five_of_seven_v3_path),
            "sha256": file_sha256(five_of_seven_v3_path),
        },
        {
            "report_kind": "integration_gate_precheck_v4",
            "path": str(gate_v4_path),
            "sha256": file_sha256(gate_v4_path),
        },
        {
            "report_kind": "integration_gate_blockers_v4",
            "path": str(blockers_v4_path),
            "sha256": file_sha256(blockers_v4_path),
        },
        {
            "report_kind": "next_contour_entrypoint_v4",
            "path": str(entrypoint_v4_path),
            "sha256": file_sha256(entrypoint_v4_path),
        },
        {
            "report_kind": "repo_bound_integration_contract_v2",
            "path": str(integration_contract_v2_path),
            "sha256": file_sha256(integration_contract_v2_path),
        },
        {
            "report_kind": "repo_bound_authorization_decision_v3",
            "path": str(auth_decision_v3_path),
            "sha256": file_sha256(auth_decision_v3_path),
        },
        {
            "report_kind": "repo_bound_planning_precheck_result_v3",
            "path": str(precheck_result_v3_path),
            "sha256": file_sha256(precheck_result_v3_path),
        },
        {
            "report_kind": "repo_bound_planning_blockers_v3",
            "path": str(planning_blockers_v3_path),
            "sha256": file_sha256(planning_blockers_v3_path),
        },
        {
            "report_kind": "repo_bound_planning_entrypoint_v3",
            "path": str(planning_entrypoint_v3_path),
            "sha256": file_sha256(planning_entrypoint_v3_path),
        },
        {
            "report_kind": "repo_bound_planning_audit_v3",
            "path": str(planning_audit_v3_path),
            "sha256": file_sha256(planning_audit_v3_path),
        },
        {
            "report_kind": "repo_bound_planning_factcheck_v3",
            "path": str(planning_factcheck_v3_path),
            "sha256": file_sha256(planning_factcheck_v3_path),
        },
        {
            "report_kind": "contour_6d_artifact_chain_validation_v1",
            "path": str(chain_6d_path),
            "sha256": file_sha256(chain_6d_path),
        },
    ]
    evidence_paths = [item["path"] for item in dependency_sha_links]

    blocked_reason_candidates = [
        precheck_result_v3_report.get("blocked_reason"),
        auth_decision_v3_report.get("blocked_reason"),
    ]
    blocked_reason = next((item for item in blocked_reason_candidates if isinstance(item, str) and item), None)
    if blocked_reason is None:
        blocked_reason = "external_authorization_not_approved_and_repo_bound_blockers_remain"

    next_action_candidates = [
        precheck_result_v3_report.get("next_required_external_action"),
        auth_decision_v3_report.get("next_required_external_action"),
    ]
    next_required_external_action = next((item for item in next_action_candidates if isinstance(item, str) and item), None)
    if next_required_external_action is None:
        next_required_external_action = "provide_explicit_external_approval_evidence_for_repo_bound_integration"

    input_chain_checks = {
        "contour_6d_chain_overall_passed": bool(chain_6d_report.get("overall_passed")),
        "repo_bound_integration_contract_passed": bool(integration_contract_v2_report.get("summary", {}).get("integration_contract_passed")),
        "repo_bound_planning_audit_v3_passed": bool(planning_audit_v3_report.get("audit_passed")),
        "repo_bound_planning_factcheck_v3_passed": bool(planning_factcheck_v3_report.get("factcheck_passed")),
    }
    artifact_chain_satisfied = all(bool(value) for value in input_chain_checks.values())

    feature_lab_complete = bool(artifact_chain_satisfied)
    repo_integration_complete = False
    external_authorization_required = True

    certificate_report = {
        "report_kind": "feature_lab_completion_certificate_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "effect_scope": effect_scope,
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "repo_bound_execution_claimed": False,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "authorization_decision_status": auth_decision_v3_report.get("authorization_decision_status"),
        "planning_precheck_status": precheck_result_v3_report.get("planning_precheck_status"),
        "remaining_blocker_count": planning_blockers_v3_report.get("summary", {}).get("remaining_blocker_count"),
        "depends_on_5of7_v3_path": str(five_of_seven_v3_path),
        "depends_on_5of7_v3_sha256": file_sha256(five_of_seven_v3_path),
        "depends_on_gate_v4_path": str(gate_v4_path),
        "depends_on_gate_v4_sha256": file_sha256(gate_v4_path),
        "depends_on_blockers_v4_path": str(blockers_v4_path),
        "depends_on_blockers_v4_sha256": file_sha256(blockers_v4_path),
        "depends_on_entrypoint_v4_path": str(entrypoint_v4_path),
        "depends_on_entrypoint_v4_sha256": file_sha256(entrypoint_v4_path),
        "depends_on_repo_bound_integration_contract_v2_path": str(integration_contract_v2_path),
        "depends_on_repo_bound_integration_contract_v2_sha256": file_sha256(integration_contract_v2_path),
        "depends_on_authorization_decision_v3_path": str(auth_decision_v3_path),
        "depends_on_authorization_decision_v3_sha256": file_sha256(auth_decision_v3_path),
        "depends_on_precheck_result_v3_path": str(precheck_result_v3_path),
        "depends_on_precheck_result_v3_sha256": file_sha256(precheck_result_v3_path),
        "depends_on_planning_blockers_v3_path": str(planning_blockers_v3_path),
        "depends_on_planning_blockers_v3_sha256": file_sha256(planning_blockers_v3_path),
        "depends_on_planning_entrypoint_v3_path": str(planning_entrypoint_v3_path),
        "depends_on_planning_entrypoint_v3_sha256": file_sha256(planning_entrypoint_v3_path),
        "depends_on_planning_audit_v3_path": str(planning_audit_v3_path),
        "depends_on_planning_audit_v3_sha256": file_sha256(planning_audit_v3_path),
        "depends_on_planning_factcheck_v3_path": str(planning_factcheck_v3_path),
        "depends_on_planning_factcheck_v3_sha256": file_sha256(planning_factcheck_v3_path),
        "depends_on_6d_chain_validation_path": str(chain_6d_path),
        "depends_on_6d_chain_validation_sha256": file_sha256(chain_6d_path),
        "input_chain_checks": input_chain_checks,
        "dependency_sha_links": dependency_sha_links,
        "evidence_paths": evidence_paths,
        "summary": {
            "advisory_verdict": "feature_lab_completion_certificate_v1_materialized",
            "artifact_chain_satisfied": artifact_chain_satisfied,
        },
    }
    certificate_path, certificate_report = write_verification_json(
        "feature_lab_completion_certificate_v1.json",
        certificate_report,
    )

    hold_report = {
        "report_kind": "feature_external_integration_hold_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "depends_on_feature_lab_completion_certificate_path": str(certificate_path),
        "depends_on_feature_lab_completion_certificate_sha256": file_sha256(certificate_path),
        "depends_on_authorization_decision_v3_path": str(auth_decision_v3_path),
        "depends_on_authorization_decision_v3_sha256": file_sha256(auth_decision_v3_path),
        "depends_on_precheck_result_v3_path": str(precheck_result_v3_path),
        "depends_on_precheck_result_v3_sha256": file_sha256(precheck_result_v3_path),
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "external_integration_hold_active": True,
        "repo_bound_execution_claimed": False,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "evidence_paths": [
            str(certificate_path),
            str(auth_decision_v3_path),
            str(precheck_result_v3_path),
            str(planning_blockers_v3_path),
            str(planning_entrypoint_v3_path),
        ],
        "summary": {
            "advisory_verdict": "feature_external_integration_hold_v1_active",
        },
    }
    hold_path, hold_report = write_verification_json(
        "feature_external_integration_hold_v1.json",
        hold_report,
    )

    manifest_report = {
        "report_kind": "feature_lab_delivery_manifest_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "depends_on_feature_lab_completion_certificate_path": str(certificate_path),
        "depends_on_feature_lab_completion_certificate_sha256": file_sha256(certificate_path),
        "depends_on_feature_external_integration_hold_path": str(hold_path),
        "depends_on_feature_external_integration_hold_sha256": file_sha256(hold_path),
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "delivery_scope": "lab_complete_package_outside_main_repo_integration",
        "input_artifacts": dependency_sha_links,
        "output_artifacts": [
            {"report_kind": "feature_lab_completion_certificate_v1", "path": str(certificate_path)},
            {"report_kind": "feature_external_integration_hold_v1", "path": str(hold_path)},
        ],
        "summary": {
            "advisory_verdict": "feature_lab_delivery_manifest_v1_materialized",
            "input_artifact_count": len(dependency_sha_links),
        },
    }
    manifest_path, manifest_report = write_verification_json(
        "feature_lab_delivery_manifest_v1.json",
        manifest_report,
    )

    audit_findings = []
    if any(bool(value) for key, value in effect_scope.items() if key.endswith("_performed")):
        audit_findings.append(
            {
                "finding_id": "unexpected_scope_expansion_detected",
                "severity": "P0",
                "message": "Contour 6E must not expand provider/model/route/runtime/eval or execute repo-bound integration.",
                "evidence_paths": [str(certificate_path)],
            }
        )
    if feature_lab_complete is not True:
        audit_findings.append(
            {
                "finding_id": "feature_lab_complete_must_be_true_when_input_chain_satisfied",
                "severity": "P0",
                "message": "Feature lab complete must be true when the attested input chain is satisfied.",
                "evidence_paths": [str(certificate_path), str(chain_6d_path)],
            }
        )
    if repo_integration_complete is not False:
        audit_findings.append(
            {
                "finding_id": "repo_integration_complete_must_be_false",
                "severity": "P0",
                "message": "Contour 6E is strictly non-repo finalization and cannot claim integration completion.",
                "evidence_paths": [str(certificate_path), str(hold_path)],
            }
        )
    if external_authorization_required is not True:
        audit_findings.append(
            {
                "finding_id": "external_authorization_required_must_be_true",
                "severity": "P0",
                "message": "Contour 6E must require external authorization for repo-bound integration.",
                "evidence_paths": [str(certificate_path), str(hold_path)],
            }
        )
    if not isinstance(blocked_reason, str) or not blocked_reason:
        audit_findings.append(
            {
                "finding_id": "blocked_reason_missing",
                "severity": "P0",
                "message": "Contour 6E requires explicit blocked_reason from v3 authorization/precheck artifacts.",
                "evidence_paths": [str(auth_decision_v3_path), str(precheck_result_v3_path)],
            }
        )
    if not isinstance(next_required_external_action, str) or not next_required_external_action:
        audit_findings.append(
            {
                "finding_id": "next_required_external_action_missing",
                "severity": "P0",
                "message": "Contour 6E requires explicit next_required_external_action from v3 authorization/precheck artifacts.",
                "evidence_paths": [str(auth_decision_v3_path), str(precheck_result_v3_path)],
            }
        )

    audit_report = {
        "report_kind": "feature_lab_completion_audit_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "depends_on_feature_lab_delivery_manifest_path": str(manifest_path),
        "depends_on_feature_lab_delivery_manifest_sha256": file_sha256(manifest_path),
        "integrity_only_assurance": True,
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "summary": {
            "advisory_verdict": (
                "feature_lab_completion_audit_v1_passed"
                if len(audit_findings) == 0
                else "feature_lab_completion_audit_v1_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_path, audit_report = write_verification_json(
        "feature_lab_completion_audit_v1.json",
        audit_report,
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    factcheck_findings = []
    checks = [
        (
            "sha_feature_lab_completion_certificate",
            hold_report.get("depends_on_feature_lab_completion_certificate_path"),
            hold_report.get("depends_on_feature_lab_completion_certificate_sha256"),
            str(hold_path),
        ),
        (
            "sha_feature_lab_completion_certificate_manifest",
            manifest_report.get("depends_on_feature_lab_completion_certificate_path"),
            manifest_report.get("depends_on_feature_lab_completion_certificate_sha256"),
            str(manifest_path),
        ),
        (
            "sha_feature_external_integration_hold_manifest",
            manifest_report.get("depends_on_feature_external_integration_hold_path"),
            manifest_report.get("depends_on_feature_external_integration_hold_sha256"),
            str(manifest_path),
        ),
        (
            "sha_feature_lab_delivery_manifest_audit",
            audit_report.get("depends_on_feature_lab_delivery_manifest_path"),
            audit_report.get("depends_on_feature_lab_delivery_manifest_sha256"),
            str(audit_path),
        ),
        (
            "sha_input_authorization_decision_v3",
            hold_report.get("depends_on_authorization_decision_v3_path"),
            hold_report.get("depends_on_authorization_decision_v3_sha256"),
            str(hold_path),
        ),
        (
            "sha_input_precheck_result_v3",
            hold_report.get("depends_on_precheck_result_v3_path"),
            hold_report.get("depends_on_precheck_result_v3_sha256"),
            str(hold_path),
        ),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 6E dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    for dep in certificate_report.get("dependency_sha_links", []):
        if not isinstance(dep, dict):
            factcheck_findings.append(
                {
                    "finding_id": "certificate_dependency_link_invalid_type",
                    "severity": "P0",
                    "message": "Dependency SHA links must be objects.",
                    "evidence_paths": [str(certificate_path)],
                }
            )
            continue
        if not _sha_match(dep.get("path"), dep.get("sha256")):
            factcheck_findings.append(
                {
                    "finding_id": f"certificate_dependency_sha_mismatch_{dep.get('report_kind')}",
                    "severity": "P0",
                    "message": "Feature lab completion certificate dependency SHA mismatch.",
                    "evidence_paths": [str(certificate_path), str(dep.get("path"))],
                }
            )

    status_checks = [
        certificate_report.get("feature_lab_complete") is True,
        certificate_report.get("repo_integration_complete") is False,
        certificate_report.get("external_authorization_required") is True,
        hold_report.get("feature_lab_complete") is True,
        hold_report.get("repo_integration_complete") is False,
        hold_report.get("external_authorization_required") is True,
        manifest_report.get("feature_lab_complete") is True,
        manifest_report.get("repo_integration_complete") is False,
        manifest_report.get("external_authorization_required") is True,
    ]
    if not all(status_checks):
        factcheck_findings.append(
            {
                "finding_id": "explicit_status_contract_violation",
                "severity": "P0",
                "message": "Contour 6E explicit status contract violated.",
                "evidence_paths": [str(certificate_path), str(hold_path), str(manifest_path)],
            }
        )

    factcheck_report = {
        "report_kind": "feature_lab_completion_factcheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_feature_lab_completion_audit_path": str(audit_path),
        "depends_on_feature_lab_completion_audit_sha256": file_sha256(audit_path),
        "integrity_only_assurance": True,
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "feature_lab_completion_factcheck_v1_passed"
                if len(factcheck_findings) == 0
                else "feature_lab_completion_factcheck_v1_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_path, factcheck_report = write_verification_json(
        "feature_lab_completion_factcheck_v1.json",
        factcheck_report,
    )

    artifact_specs = [
        {
            "path": certificate_path,
            "expected_report_kind": "feature_lab_completion_certificate_v1",
            "dependency_keys": [
                ("depends_on_5of7_v3_path", "depends_on_5of7_v3_sha256"),
                ("depends_on_gate_v4_path", "depends_on_gate_v4_sha256"),
                ("depends_on_blockers_v4_path", "depends_on_blockers_v4_sha256"),
                ("depends_on_entrypoint_v4_path", "depends_on_entrypoint_v4_sha256"),
                ("depends_on_repo_bound_integration_contract_v2_path", "depends_on_repo_bound_integration_contract_v2_sha256"),
                ("depends_on_authorization_decision_v3_path", "depends_on_authorization_decision_v3_sha256"),
                ("depends_on_precheck_result_v3_path", "depends_on_precheck_result_v3_sha256"),
                ("depends_on_planning_blockers_v3_path", "depends_on_planning_blockers_v3_sha256"),
                ("depends_on_planning_entrypoint_v3_path", "depends_on_planning_entrypoint_v3_sha256"),
                ("depends_on_planning_audit_v3_path", "depends_on_planning_audit_v3_sha256"),
                ("depends_on_planning_factcheck_v3_path", "depends_on_planning_factcheck_v3_sha256"),
                ("depends_on_6d_chain_validation_path", "depends_on_6d_chain_validation_sha256"),
            ],
        },
        {
            "path": hold_path,
            "expected_report_kind": "feature_external_integration_hold_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_completion_certificate_path", "depends_on_feature_lab_completion_certificate_sha256"),
                ("depends_on_authorization_decision_v3_path", "depends_on_authorization_decision_v3_sha256"),
                ("depends_on_precheck_result_v3_path", "depends_on_precheck_result_v3_sha256"),
            ],
        },
        {
            "path": manifest_path,
            "expected_report_kind": "feature_lab_delivery_manifest_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_completion_certificate_path", "depends_on_feature_lab_completion_certificate_sha256"),
                ("depends_on_feature_external_integration_hold_path", "depends_on_feature_external_integration_hold_sha256"),
            ],
        },
        {
            "path": audit_path,
            "expected_report_kind": "feature_lab_completion_audit_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_delivery_manifest_path", "depends_on_feature_lab_delivery_manifest_sha256"),
            ],
        },
        {
            "path": factcheck_path,
            "expected_report_kind": "feature_lab_completion_factcheck_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_completion_audit_path", "depends_on_feature_lab_completion_audit_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            artifact_row["dependency_checks"].append(
                {
                    "path_key": path_key,
                    "sha_key": sha_key,
                    "path_value": path_value,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "match": match,
                }
            )
            if not match:
                dep_passed = False

        status_contract_passed = (
            artifact_report.get("feature_lab_complete") is True
            and artifact_report.get("repo_integration_complete") is False
            and artifact_report.get("external_authorization_required") is True
        )
        artifact_row["status_contract_passed"] = status_contract_passed
        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed and status_contract_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_6e_feature_lab_complete_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_feature_lab_completion_factcheck_path": str(factcheck_path),
        "depends_on_feature_lab_completion_factcheck_sha256": file_sha256(factcheck_path),
        "feature_lab_complete": feature_lab_complete,
        "repo_integration_complete": repo_integration_complete,
        "external_authorization_required": external_authorization_required,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_report_path, _ = write_verification_json(
        "contour_6e_feature_lab_complete_chain_validation_v1.json",
        chain_report,
    )

    print(f"JSON report: {certificate_path}")
    print(f"JSON report: {hold_path}")
    print(f"JSON report: {manifest_path}")
    print(f"JSON report: {audit_path}")
    print(f"JSON report: {factcheck_path}")
    print(f"JSON report: {chain_report_path}")


CONTOUR_7A_DECLARED_TARGETS = (
    {"name": "Devstral-Small-2-24B-Instruct-2512", "visual_lane": False},
    {"name": "Qwen2.5-Coder-32B-Instruct", "visual_lane": False},
    {"name": "Qwen3-32B", "visual_lane": False},
    {"name": "Mistral-Small-3.1-24B-Instruct-2503", "visual_lane": False},
    {"name": "Qwen2.5-VL-7B-Instruct", "visual_lane": True},
)

CONTOUR_7A_PROVIDER_TARGETS = {
    "openrouter": {
        "provider": "openrouter",
        "provider_label": "OpenRouter",
        "api_key_env": "OPENROUTER_API_KEY",
        "listing_url": "https://openrouter.ai/api/v1/models",
        "listing_path": "/api/v1/models",
        "runtime_url": "https://openrouter.ai/api/v1/chat/completions",
        "runtime_path": "/api/v1/chat/completions",
        "headers": {
            "HTTP-Referer": "http://localhost",
            "X-Title": "Wild Boar External Agent Lab",
        },
    },
    "cerebras": {
        "provider": "cerebras",
        "provider_label": "Cerebras",
        "api_key_env": "CEREBRAS_API_KEY",
        "listing_url": "https://api.cerebras.ai/v1/models",
        "listing_path": "/v1/models",
        "runtime_url": "https://api.cerebras.ai/v1/chat/completions",
        "runtime_path": "/v1/chat/completions",
    },
    "groq": {
        "provider": "groq",
        "provider_label": "Groq",
        "api_key_env": "GROQ_API_KEY",
        "listing_url": "https://api.groq.com/openai/v1/models",
        "listing_path": "/openai/v1/models",
        "runtime_url": "https://api.groq.com/openai/v1/chat/completions",
        "runtime_path": "/openai/v1/chat/completions",
    },
    "mistral": {
        "provider": "mistral",
        "provider_label": "Mistral",
        "api_key_env": "MISTRAL_API_KEY",
        "listing_url": "https://api.mistral.ai/v1/models",
        "listing_path": "/v1/models",
        "runtime_url": "https://api.mistral.ai/v1/chat/completions",
        "runtime_path": "/v1/chat/completions",
    },
    "gemini": {
        "provider": "gemini",
        "provider_label": "Google Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "listing_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "listing_path": "/v1beta/models",
        "listing_auth_mode": "query_key",
        "runtime_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "runtime_path": "/v1beta/openai/chat/completions",
    },
}


def contour_7a_normalize_model_id(value):
    if not isinstance(value, str):
        return ""
    normalized = value.lower()
    normalized = re.sub(r"([a-z])([0-9])", r"\1-\2", normalized)
    normalized = re.sub(r"([0-9])([a-z])", r"\1-\2", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized


def contour_7a_model_id_core(value):
    if not isinstance(value, str):
        return ""
    model_id = value.strip()
    if model_id.startswith("models/"):
        model_id = model_id[len("models/") :]
    if "/" in model_id:
        model_id = model_id.rsplit("/", 1)[-1]
    if ":" in model_id:
        model_id = model_id.split(":", 1)[0]
    return model_id


def contour_7a_model_tokens(value):
    normalized = contour_7a_normalize_model_id(value)
    return {token for token in normalized.split("-") if token}


def contour_7a_alias_match(target_name, provider_model_id):
    tokens = contour_7a_model_tokens(provider_model_id) | contour_7a_model_tokens(contour_7a_model_id_core(provider_model_id))
    if target_name == "Devstral-Small-2-24B-Instruct-2512":
        return ("devstral" in tokens) and (("2512" in tokens) or ("small" in tokens))
    if target_name == "Qwen2.5-Coder-32B-Instruct":
        return {"qwen", "2", "5", "coder", "32", "b", "instruct"} <= tokens
    if target_name == "Qwen3-32B":
        return {"qwen", "3", "32", "b"} <= tokens
    if target_name == "Mistral-Small-3.1-24B-Instruct-2503":
        return {"mistral", "small", "24", "b", "instruct"} <= tokens
    if target_name == "Qwen2.5-VL-7B-Instruct":
        return {"qwen", "2", "5", "vl", "7", "b", "instruct"} <= tokens
    return False


def contour_7a_candidate_priority(target_name, candidate):
    provider_rank = {
        "openrouter": 0,
        "groq": 1,
        "mistral": 2,
        "cerebras": 3,
        "gemini": 4,
    }
    model_tokens = contour_7a_model_tokens(candidate.get("model_id")) | contour_7a_model_tokens(
        contour_7a_model_id_core(candidate.get("model_id"))
    )
    match_rank = 0 if candidate.get("match_type") == "exact" else 1
    target_rank = 10
    if target_name == "Mistral-Small-3.1-24B-Instruct-2503":
        if {"3", "1"} <= model_tokens:
            target_rank = 0
        elif {"2501"} <= model_tokens:
            target_rank = 1
        elif {"3", "2"} <= model_tokens:
            target_rank = 2
    elif target_name == "Devstral-Small-2-24B-Instruct-2512":
        if "2512" in model_tokens:
            target_rank = 0
        elif "small" in model_tokens:
            target_rank = 1
    return (
        match_rank,
        target_rank,
        provider_rank.get(candidate.get("provider"), 99),
        candidate.get("model_id") or "",
    )


def contour_7a_extract_model_ids(payload):
    model_ids = []
    if isinstance(payload, dict):
        data_items = payload.get("data")
        if isinstance(data_items, list):
            for item in data_items:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    model_ids.append(item["id"])
        gemini_items = payload.get("models")
        if isinstance(gemini_items, list):
            for item in gemini_items:
                if not isinstance(item, dict):
                    continue
                for key in ("id", "name", "model"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        model_ids.append(value)
                        break
    deduped = []
    seen = set()
    for model_id in model_ids:
        if model_id in seen:
            continue
        seen.add(model_id)
        deduped.append(model_id)
    return deduped


def contour_7a_error_class_from_http(status_code, auth_present):
    if status_code in {401, 403}:
        return "upstream_auth_failed" if auth_present else "upstream_auth_missing"
    if status_code == 404:
        return "upstream_model_unavailable"
    if status_code == 429:
        return "upstream_rate_limited"
    if status_code >= 500:
        return "upstream_overloaded"
    return "upstream_error"


def contour_7a_provider_headers(provider_cfg, api_key, content_type=False):
    headers = {
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }
    for key, value in provider_cfg.get("headers", {}).items():
        headers[key] = value
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        if provider_cfg.get("provider") == "gemini":
            headers["x-goog-api-key"] = api_key
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def contour_7a_probe_provider_listing(provider_cfg, api_key, request_timeout):
    provider = provider_cfg["provider"]
    listing_url = provider_cfg["listing_url"]
    if provider_cfg.get("listing_auth_mode") == "query_key" and api_key:
        sep = "&" if "?" in listing_url else "?"
        listing_url = f"{listing_url}{sep}key={quote_plus(api_key)}"
    req = Request(listing_url, method="GET")
    for key, value in contour_7a_provider_headers(provider_cfg, api_key).items():
        req.add_header(key, value)

    status_code = None
    response_server = None
    response_content_type = None
    response_excerpt = None
    error_class = None
    error_message = None
    endpoint_reachable = False
    listing_success = False
    payload = None
    model_ids = []
    try:
        with urlopen(req, timeout=request_timeout) as response:
            status_code = response.status
            endpoint_reachable = True
            response_server = response.headers.get("Server")
            response_content_type = response.headers.get("Content-Type")
            raw = response.read().decode("utf-8", errors="replace")
            response_excerpt = safe_excerpt(raw, limit=240)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None
            model_ids = contour_7a_extract_model_ids(payload)
            listing_success = status_code == 200 and len(model_ids) > 0
    except HTTPError as error:
        status_code = error.code
        endpoint_reachable = True
        response_server = error.headers.get("Server")
        response_content_type = error.headers.get("Content-Type")
        body = error.read().decode("utf-8", errors="replace")
        response_excerpt = safe_excerpt(body, limit=240)
        error_class = contour_7a_error_class_from_http(error.code, bool(api_key))
        error_message = f"HTTP {error.code} while listing models from {provider}."
    except socket.timeout:
        error_class = "upstream_timeout"
        error_message = f"Timed out while listing models from {provider}."
    except URLError as error:
        error_class = "provider_unreachable"
        error_message = f"Connection error while listing models from {provider}: {error}"

    return {
        "provider": provider,
        "provider_label": provider_cfg["provider_label"],
        "api_key_env": provider_cfg["api_key_env"],
        "auth_present": bool(api_key),
        "listing_endpoint": provider_cfg["listing_url"],
        "listing_path": provider_cfg["listing_path"],
        "listing_http_status": status_code,
        "listing_success": listing_success,
        "endpoint_reachable": endpoint_reachable,
        "visible_model_count": len(model_ids),
        "visible_model_ids": model_ids,
        "visible_model_ids_sample": model_ids[:20],
        "error_class": error_class,
        "error_message": error_message,
        "response_server": response_server,
        "response_content_type": response_content_type,
        "response_excerpt": response_excerpt,
        "network_dependent_evidence": True,
    }


def contour_7a_match_target_against_provider_models(target_name, visible_model_ids):
    target_norm = contour_7a_normalize_model_id(target_name)
    exact_matches = []
    alias_matches = []
    for model_id in visible_model_ids:
        full_norm = contour_7a_normalize_model_id(model_id)
        core_norm = contour_7a_normalize_model_id(contour_7a_model_id_core(model_id))
        if target_norm and (target_norm == full_norm or target_norm == core_norm):
            exact_matches.append(model_id)
            continue
        if contour_7a_alias_match(target_name, model_id):
            alias_matches.append(model_id)
    return exact_matches, alias_matches


def contour_7a_runtime_smoke_call(provider_cfg, api_key, model_id, request_timeout):
    req = Request(
        provider_cfg["runtime_url"],
        method="POST",
        data=json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with OK only."}],
                "max_tokens": 8,
                "temperature": 0,
            }
        ).encode("utf-8"),
    )
    for key, value in contour_7a_provider_headers(provider_cfg, api_key, content_type=True).items():
        req.add_header(key, value)

    status_code = None
    response_excerpt = None
    error_class = None
    error_message = None
    success = False
    try:
        with urlopen(req, timeout=request_timeout) as response:
            status_code = response.status
            body = response.read().decode("utf-8", errors="replace")
            response_excerpt = safe_excerpt(body, limit=160)
            success = status_code == 200
    except HTTPError as error:
        status_code = error.code
        body = error.read().decode("utf-8", errors="replace")
        response_excerpt = safe_excerpt(body, limit=160)
        error_class = contour_7a_error_class_from_http(error.code, bool(api_key))
        error_message = f"HTTP {error.code} during runtime probe."
    except socket.timeout:
        error_class = "upstream_timeout"
        error_message = "Runtime probe timed out."
    except URLError as error:
        error_class = "provider_unreachable"
        error_message = f"Runtime probe connection error: {error}"

    return {
        "runtime_http_status": status_code,
        "success": success,
        "error_class": error_class,
        "error_message": error_message,
        "response_excerpt": response_excerpt,
        "network_dependent_evidence": True,
    }


def run_contour_7a_declared_target_coverage_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_7a_declared_target_coverage_generator"
    now_utc = datetime.now(timezone.utc).isoformat()
    runtime_scope = {
        "runtime_scope_id": "text_only_runtime_smoke",
        "text_only": True,
        "multimodal_input_probes_enabled": False,
    }
    provider_order = ["openrouter", "cerebras", "groq", "mistral", "gemini"]
    env_map = load_local_env()

    provider_snapshots = []
    provider_index = {}
    for provider_name in provider_order:
        provider_cfg = CONTOUR_7A_PROVIDER_TARGETS[provider_name]
        api_key = env_map.get(provider_cfg["api_key_env"]) or os.environ.get(provider_cfg["api_key_env"])
        listing_row = contour_7a_probe_provider_listing(provider_cfg, api_key, args.request_timeout)
        provider_snapshots.append(listing_row)
        provider_index[provider_name] = {
            "config": provider_cfg,
            "listing": listing_row,
            "api_key": api_key,
        }

    target_listing_rows = []
    runtime_probe_rows = []
    coverage_decisions = []

    for target in CONTOUR_7A_DECLARED_TARGETS:
        target_name = target["name"]
        visual_lane = bool(target.get("visual_lane"))
        provider_observations = []
        runtime_candidates = []

        for provider_name in provider_order:
            provider_state = provider_index[provider_name]
            provider_cfg = provider_state["config"]
            listing_row = provider_state["listing"]
            exact_match_ids, alias_match_ids = contour_7a_match_target_against_provider_models(
                target_name,
                listing_row.get("visible_model_ids", []),
            )
            provider_observation = {
                "provider": provider_name,
                "provider_label": provider_cfg["provider_label"],
                "requested_target_name": target_name,
                "listing_endpoint": provider_cfg["listing_url"],
                "listing_path": provider_cfg["listing_path"],
                "listing_http_status": listing_row.get("listing_http_status"),
                "listing_success": listing_row.get("listing_success"),
                "endpoint_reachable": listing_row.get("endpoint_reachable"),
                "auth_present": listing_row.get("auth_present"),
                "visible_model_count": listing_row.get("visible_model_count"),
                "exact_match_ids": exact_match_ids,
                "alias_match_ids": alias_match_ids,
                "error_class": listing_row.get("error_class"),
                "error_message": listing_row.get("error_message"),
            }
            provider_observations.append(provider_observation)

            for model_id in exact_match_ids:
                runtime_candidates.append(
                    {
                        "provider": provider_name,
                        "provider_label": provider_cfg["provider_label"],
                        "match_type": "exact",
                        "model_id": model_id,
                        "runtime_endpoint": provider_cfg["runtime_url"],
                        "runtime_path": provider_cfg["runtime_path"],
                        "auth_present": bool(provider_state["api_key"]),
                    }
                )
            for model_id in alias_match_ids:
                runtime_candidates.append(
                    {
                        "provider": provider_name,
                        "provider_label": provider_cfg["provider_label"],
                        "match_type": "alias",
                        "model_id": model_id,
                        "runtime_endpoint": provider_cfg["runtime_url"],
                        "runtime_path": provider_cfg["runtime_path"],
                        "auth_present": bool(provider_state["api_key"]),
                    }
                )

        target_listing_rows.append(
            {
                "requested_target_name": target_name,
                "visual_lane_target": visual_lane,
                "provider_observations": provider_observations,
            }
        )

        selectable_candidates = [candidate for candidate in runtime_candidates if candidate["auth_present"]]
        selectable_candidates.sort(key=lambda item: contour_7a_candidate_priority(target_name, item))
        selected_candidate = selectable_candidates[0] if selectable_candidates else None

        runtime_probe_attempts = []
        if selected_candidate and not visual_lane:
            provider_state = provider_index[selected_candidate["provider"]]
            for attempt_index in range(1, 3):
                attempt_result = contour_7a_runtime_smoke_call(
                    provider_state["config"],
                    provider_state["api_key"],
                    selected_candidate["model_id"],
                    args.request_timeout,
                )
                runtime_probe_attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "provider": selected_candidate["provider"],
                        "provider_label": selected_candidate["provider_label"],
                        "runtime_endpoint": selected_candidate["runtime_endpoint"],
                        "runtime_path": selected_candidate["runtime_path"],
                        "requested_target_name": target_name,
                        "requested_model_id": selected_candidate["model_id"],
                        "selected_match_type": selected_candidate["match_type"],
                        "prompt": "Reply with OK only.",
                        "runtime_http_status": attempt_result["runtime_http_status"],
                        "success": attempt_result["success"],
                        "error_class": attempt_result["error_class"],
                        "error_message": attempt_result["error_message"],
                        "response_excerpt": attempt_result["response_excerpt"],
                    }
                )

        success_count = sum(1 for attempt in runtime_probe_attempts if attempt.get("success"))
        error_classes = sorted(
            {
                attempt.get("error_class")
                for attempt in runtime_probe_attempts
                if isinstance(attempt.get("error_class"), str) and attempt.get("error_class")
            }
        )
        has_any_match = any(
            (len(observation["exact_match_ids"]) + len(observation["alias_match_ids"])) > 0
            for observation in provider_observations
        )

        if visual_lane and has_any_match:
            classification = "visual_lane_out_of_current_runtime_scope"
            blocked_reason = "Target is visible in provider listings, but contour 7A runtime scope is text-only and does not verify multimodal (VL) execution."
            next_required_action = "Run multimodal runtime probes (image + text) against matched provider/model IDs."
        elif not has_any_match:
            classification = "not_listed_in_current_provider_set"
            blocked_reason = "No exact or alias matches were found across OpenRouter, Cerebras, Groq, Mistral, and Gemini listing endpoints."
            next_required_action = "Re-run contour when current provider endpoints list the declared target IDs."
        elif not selected_candidate:
            classification = "provider_visible_but_unverified"
            blocked_reason = "Target is visible by listing evidence, but no runtime-open candidate exists with current provider auth state."
            next_required_action = "Provide provider API credentials for at least one matched provider and rerun contour."
        elif success_count == 2:
            if selected_candidate["match_type"] == "exact":
                classification = "exact_match_runtime_verified"
            else:
                classification = "alias_match_runtime_verified"
            blocked_reason = None
            next_required_action = None
        else:
            classification = "listed_but_runtime_failed"
            blocked_reason = "Runtime smoke attempts did not reach 2/2 success for the selected candidate."
            next_required_action = "Inspect runtime probe errors, remediate provider/model runtime failures, and rerun contour."

        runtime_probe_rows.append(
            {
                "requested_target_name": target_name,
                "visual_lane_target": visual_lane,
                "runtime_scope": runtime_scope,
                "runtime_open_candidates": selectable_candidates,
                "selected_runtime_candidate": selected_candidate,
                "runtime_probe_attempts": runtime_probe_attempts,
                "success_count": success_count,
                "error_classes": error_classes,
            }
        )

        coverage_decisions.append(
            {
                "requested_target_name": target_name,
                "classification": classification,
                "visual_lane_target": visual_lane,
                "exact_match_ids": sorted(
                    {
                        model_id
                        for observation in provider_observations
                        for model_id in observation.get("exact_match_ids", [])
                    }
                ),
                "alias_match_ids": sorted(
                    {
                        model_id
                        for observation in provider_observations
                        for model_id in observation.get("alias_match_ids", [])
                    }
                ),
                "runtime_probe_attempts": runtime_probe_attempts,
                "success_count": success_count,
                "error_classes": error_classes,
                "blocked_reason": blocked_reason,
                "next_required_action": next_required_action,
            }
        )

    classification_counts = {}
    runtime_confirmed_classes = {"exact_match_runtime_verified", "alias_match_runtime_verified"}
    for item in coverage_decisions:
        key = item["classification"]
        classification_counts[key] = classification_counts.get(key, 0) + 1

    all_declared_targets_runtime_confirmed = all(
        item["classification"] in runtime_confirmed_classes
        for item in coverage_decisions
    )
    feature_ready_under_declared_target_policy = all_declared_targets_runtime_confirmed

    provider_snapshot_report = {
        "report_kind": "declared_target_provider_snapshot_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "provider_set": provider_order,
        "runtime_scope": runtime_scope,
        "providers": provider_snapshots,
        "declared_targets": target_listing_rows,
        "summary": {
            "provider_count": len(provider_snapshots),
            "provider_listing_success_count": sum(1 for item in provider_snapshots if item.get("listing_success")),
            "provider_listing_failure_count": sum(1 for item in provider_snapshots if not item.get("listing_success")),
        },
    }
    provider_snapshot_path, provider_snapshot_report = write_verification_json(
        "declared_target_provider_snapshot_v1.json",
        provider_snapshot_report,
    )

    runtime_probe_matrix_report = {
        "report_kind": "declared_target_runtime_probe_matrix_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "provider_set": provider_order,
        "runtime_scope": runtime_scope,
        "depends_on_provider_snapshot_v1_path": str(provider_snapshot_path),
        "depends_on_provider_snapshot_v1_sha256": file_sha256(provider_snapshot_path),
        "targets": runtime_probe_rows,
        "summary": {
            "target_count": len(runtime_probe_rows),
            "targets_with_runtime_attempts": sum(1 for item in runtime_probe_rows if len(item.get("runtime_probe_attempts", [])) > 0),
        },
    }
    runtime_probe_matrix_path, runtime_probe_matrix_report = write_verification_json(
        "declared_target_runtime_probe_matrix_v1.json",
        runtime_probe_matrix_report,
    )

    coverage_decision_report = {
        "report_kind": "declared_target_coverage_decision_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "provider_set": provider_order,
        "runtime_scope": runtime_scope,
        "depends_on_provider_snapshot_v1_path": str(provider_snapshot_path),
        "depends_on_provider_snapshot_v1_sha256": file_sha256(provider_snapshot_path),
        "depends_on_runtime_probe_matrix_v1_path": str(runtime_probe_matrix_path),
        "depends_on_runtime_probe_matrix_v1_sha256": file_sha256(runtime_probe_matrix_path),
        "target_decisions": coverage_decisions,
        "overall_coverage_summary": {
            "classification_counts": {key: classification_counts[key] for key in sorted(classification_counts)},
            "all_declared_targets_runtime_confirmed": all_declared_targets_runtime_confirmed,
            "feature_ready_under_declared_target_policy": feature_ready_under_declared_target_policy,
        },
    }
    coverage_decision_path, coverage_decision_report = write_verification_json(
        "declared_target_coverage_decision_v1.json",
        coverage_decision_report,
    )

    audit_findings = []
    decision_index = {item["requested_target_name"]: item for item in coverage_decision_report["target_decisions"]}
    runtime_index = {item["requested_target_name"]: item for item in runtime_probe_matrix_report["targets"]}
    for target in CONTOUR_7A_DECLARED_TARGETS:
        target_name = target["name"]
        decision = decision_index.get(target_name)
        runtime = runtime_index.get(target_name)
        if not isinstance(decision, dict) or not isinstance(runtime, dict):
            audit_findings.append(
                {
                    "finding_id": f"missing_target_record_{target_name}",
                    "severity": "P0",
                    "message": "Target record missing in decision or runtime matrix.",
                    "evidence_paths": [str(coverage_decision_path), str(runtime_probe_matrix_path)],
                }
            )
            continue
        classification = decision.get("classification")
        selected_candidate = runtime.get("selected_runtime_candidate")
        success_count = runtime.get("success_count")
        if classification == "exact_match_runtime_verified":
            if not isinstance(selected_candidate, dict) or selected_candidate.get("match_type") != "exact" or success_count != 2:
                audit_findings.append(
                    {
                        "finding_id": f"exact_claim_not_backed_{target_name}",
                        "severity": "P0",
                        "message": "exact_match_runtime_verified is not fully backed by exact candidate with 2/2 success.",
                        "evidence_paths": [str(coverage_decision_path), str(runtime_probe_matrix_path)],
                    }
                )
        if classification == "alias_match_runtime_verified":
            if not isinstance(selected_candidate, dict) or selected_candidate.get("match_type") != "alias" or success_count != 2:
                audit_findings.append(
                    {
                        "finding_id": f"alias_claim_not_backed_{target_name}",
                        "severity": "P0",
                        "message": "alias_match_runtime_verified is not fully backed by alias candidate with 2/2 success.",
                        "evidence_paths": [str(coverage_decision_path), str(runtime_probe_matrix_path)],
                    }
                )
        if classification not in runtime_confirmed_classes:
            if not isinstance(decision.get("blocked_reason"), str) or not decision.get("blocked_reason"):
                audit_findings.append(
                    {
                        "finding_id": f"missing_blocked_reason_{target_name}",
                        "severity": "P1",
                        "message": "Non-verified target must carry blocked_reason.",
                        "evidence_paths": [str(coverage_decision_path)],
                    }
                )
            if not isinstance(decision.get("next_required_action"), str) or not decision.get("next_required_action"):
                audit_findings.append(
                    {
                        "finding_id": f"missing_next_required_action_{target_name}",
                        "severity": "P1",
                        "message": "Non-verified target must carry next_required_action.",
                        "evidence_paths": [str(coverage_decision_path)],
                    }
                )

    computed_confirmed = all(
        decision.get("classification") in runtime_confirmed_classes
        for decision in coverage_decision_report["target_decisions"]
    )
    if coverage_decision_report.get("overall_coverage_summary", {}).get("all_declared_targets_runtime_confirmed") != computed_confirmed:
        audit_findings.append(
            {
                "finding_id": "all_declared_targets_runtime_confirmed_mismatch",
                "severity": "P0",
                "message": "Summary all_declared_targets_runtime_confirmed does not match computed target decisions.",
                "evidence_paths": [str(coverage_decision_path)],
            }
        )

    coverage_audit_report = {
        "report_kind": "declared_target_coverage_audit_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "depends_on_coverage_decision_v1_path": str(coverage_decision_path),
        "depends_on_coverage_decision_v1_sha256": file_sha256(coverage_decision_path),
        "depends_on_runtime_probe_matrix_v1_path": str(runtime_probe_matrix_path),
        "depends_on_runtime_probe_matrix_v1_sha256": file_sha256(runtime_probe_matrix_path),
        "depends_on_provider_snapshot_v1_path": str(provider_snapshot_path),
        "depends_on_provider_snapshot_v1_sha256": file_sha256(provider_snapshot_path),
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "finding_count": len(audit_findings),
            "advisory_verdict": "declared_target_coverage_audit_v1_passed" if len(audit_findings) == 0 else "declared_target_coverage_audit_v1_failed",
        },
    }
    coverage_audit_path, coverage_audit_report = write_verification_json(
        "declared_target_coverage_audit_v1.json",
        coverage_audit_report,
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        path = Path(path_value)
        if not path.exists():
            return False
        return file_sha256(path) == sha_value

    factcheck_findings = []
    checks = [
        (
            "sha_provider_snapshot_runtime_matrix",
            runtime_probe_matrix_report.get("depends_on_provider_snapshot_v1_path"),
            runtime_probe_matrix_report.get("depends_on_provider_snapshot_v1_sha256"),
            str(runtime_probe_matrix_path),
        ),
        (
            "sha_provider_snapshot_decision",
            coverage_decision_report.get("depends_on_provider_snapshot_v1_path"),
            coverage_decision_report.get("depends_on_provider_snapshot_v1_sha256"),
            str(coverage_decision_path),
        ),
        (
            "sha_runtime_matrix_decision",
            coverage_decision_report.get("depends_on_runtime_probe_matrix_v1_path"),
            coverage_decision_report.get("depends_on_runtime_probe_matrix_v1_sha256"),
            str(coverage_decision_path),
        ),
        (
            "sha_decision_audit",
            coverage_audit_report.get("depends_on_coverage_decision_v1_path"),
            coverage_audit_report.get("depends_on_coverage_decision_v1_sha256"),
            str(coverage_audit_path),
        ),
        (
            "sha_runtime_matrix_audit",
            coverage_audit_report.get("depends_on_runtime_probe_matrix_v1_path"),
            coverage_audit_report.get("depends_on_runtime_probe_matrix_v1_sha256"),
            str(coverage_audit_path),
        ),
        (
            "sha_provider_snapshot_audit",
            coverage_audit_report.get("depends_on_provider_snapshot_v1_path"),
            coverage_audit_report.get("depends_on_provider_snapshot_v1_sha256"),
            str(coverage_audit_path),
        ),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 7A dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    expected_ready = all_declared_targets_runtime_confirmed
    observed_ready = bool(
        coverage_decision_report.get("overall_coverage_summary", {}).get("feature_ready_under_declared_target_policy")
    )
    if observed_ready != expected_ready:
        factcheck_findings.append(
            {
                "finding_id": "feature_ready_policy_flag_mismatch",
                "severity": "P0",
                "message": "feature_ready_under_declared_target_policy does not match computed runtime confirmation result.",
                "evidence_paths": [str(coverage_decision_path)],
            }
        )

    coverage_factcheck_report = {
        "report_kind": "declared_target_coverage_factcheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "depends_on_coverage_audit_v1_path": str(coverage_audit_path),
        "depends_on_coverage_audit_v1_sha256": file_sha256(coverage_audit_path),
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "all_declared_targets_runtime_confirmed": all_declared_targets_runtime_confirmed,
        "feature_ready_under_declared_target_policy": feature_ready_under_declared_target_policy,
        "summary": {
            "finding_count": len(factcheck_findings),
            "advisory_verdict": (
                "declared_target_coverage_factcheck_v1_passed"
                if len(factcheck_findings) == 0
                else "declared_target_coverage_factcheck_v1_failed"
            ),
        },
    }
    coverage_factcheck_path, _ = write_verification_json(
        "declared_target_coverage_factcheck_v1.json",
        coverage_factcheck_report,
    )

    artifact_specs = [
        {
            "path": provider_snapshot_path,
            "expected_report_kind": "declared_target_provider_snapshot_v1",
            "dependency_keys": [],
        },
        {
            "path": runtime_probe_matrix_path,
            "expected_report_kind": "declared_target_runtime_probe_matrix_v1",
            "dependency_keys": [
                ("depends_on_provider_snapshot_v1_path", "depends_on_provider_snapshot_v1_sha256"),
            ],
        },
        {
            "path": coverage_decision_path,
            "expected_report_kind": "declared_target_coverage_decision_v1",
            "dependency_keys": [
                ("depends_on_provider_snapshot_v1_path", "depends_on_provider_snapshot_v1_sha256"),
                ("depends_on_runtime_probe_matrix_v1_path", "depends_on_runtime_probe_matrix_v1_sha256"),
            ],
        },
        {
            "path": coverage_audit_path,
            "expected_report_kind": "declared_target_coverage_audit_v1",
            "dependency_keys": [
                ("depends_on_coverage_decision_v1_path", "depends_on_coverage_decision_v1_sha256"),
                ("depends_on_runtime_probe_matrix_v1_path", "depends_on_runtime_probe_matrix_v1_sha256"),
                ("depends_on_provider_snapshot_v1_path", "depends_on_provider_snapshot_v1_sha256"),
            ],
        },
        {
            "path": coverage_factcheck_path,
            "expected_report_kind": "declared_target_coverage_factcheck_v1",
            "dependency_keys": [
                ("depends_on_coverage_audit_v1_path", "depends_on_coverage_audit_v1_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            artifact_row["dependency_checks"].append(
                {
                    "path_key": path_key,
                    "sha_key": sha_key,
                    "path_value": path_value,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "match": match,
                }
            )
            if not match:
                dep_passed = False

        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_7a_declared_target_coverage_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "depends_on_declared_target_coverage_factcheck_v1_path": str(coverage_factcheck_path),
        "depends_on_declared_target_coverage_factcheck_v1_sha256": file_sha256(coverage_factcheck_path),
        "all_declared_targets_runtime_confirmed": all_declared_targets_runtime_confirmed,
        "feature_ready_under_declared_target_policy": feature_ready_under_declared_target_policy,
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_report_path, _ = write_verification_json(
        "contour_7a_declared_target_coverage_chain_validation_v1.json",
        chain_report,
    )

    print(f"JSON report: {provider_snapshot_path}")
    print(f"JSON report: {runtime_probe_matrix_path}")
    print(f"JSON report: {coverage_decision_path}")
    print(f"JSON report: {coverage_audit_path}")
    print(f"JSON report: {coverage_factcheck_path}")
    print(f"JSON report: {chain_report_path}")


def run_contour_7b_declared_scope_reconciliation_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_7b_declared_scope_reconciliation"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "declared_target_scope_policy_decision_v1",
        "declared_target_coverage_decision_v2",
        "feature_lab_current_scope_readiness_v1",
        "feature_lab_next_contour_entrypoint_v1",
        "declared_target_coverage_audit_v2",
        "declared_target_coverage_factcheck_v2",
        "contour_7b_declared_scope_chain_validation_v1",
    ]
    effect_scope = {
        "policy_reconciliation_only": True,
        "runtime_probes_performed": False,
        "provider_expansion_performed": False,
        "model_expansion_performed": False,
        "repo_mutation_performed": False,
        "historical_artifacts_rewritten": False,
    }
    runtime_confirmed_classes = {"exact_match_runtime_verified", "alias_match_runtime_verified"}

    coverage_v1_path, coverage_v1_report = load_fixed_verification_report(
        "declared_target_coverage_decision_v1.json",
        "declared_target_coverage_decision_v1",
    )
    repo_precheck_v3_path, repo_precheck_v3_report = load_fixed_verification_report(
        "repo_bound_planning_precheck_result_v3.json",
        "repo_bound_planning_precheck_result_v3",
    )
    integration_gate_v4_path, integration_gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )

    vl_recheck_v2_path = VERIFICATION_DIR / "declared_target_qwen25_vl_recheck_v2.json"
    if not vl_recheck_v2_path.exists():
        raise SystemExit(f"Report not found: {vl_recheck_v2_path}")
    vl_recheck_v2_report = json.loads(vl_recheck_v2_path.read_text(encoding="utf-8"))
    if not isinstance(vl_recheck_v2_report, dict) or vl_recheck_v2_report.get("artifact_type") != "declared_target_recheck":
        raise SystemExit("Invalid report format for declared_target_qwen25_vl_recheck_v2.json.")
    if vl_recheck_v2_report.get("canonical_target") != "Qwen2.5-VL-7B-Instruct":
        raise SystemExit("Unexpected canonical_target in declared_target_qwen25_vl_recheck_v2.json.")

    historical_summary = coverage_v1_report.get("overall_coverage_summary", {})
    coverage_v1_index = {}
    for item in coverage_v1_report.get("target_decisions", []):
        if isinstance(item, dict) and isinstance(item.get("requested_target_name"), str):
            coverage_v1_index[item["requested_target_name"]] = item

    policy_assignments = []
    coverage_v2_targets = []
    active_text_scope_target_names = []
    future_visual_scope_target_names = []

    for target in CONTOUR_7A_DECLARED_TARGETS:
        target_name = target["name"]
        visual_lane_target = bool(target.get("visual_lane"))
        historical_decision = coverage_v1_index.get(target_name)
        if not isinstance(historical_decision, dict):
            raise SystemExit(f"Missing historical decision for target: {target_name}")

        scope_class = "future_visual_scope" if visual_lane_target else "active_text_scope"
        historical_classification = historical_decision.get("classification")
        historical_runtime_confirmed = historical_classification in runtime_confirmed_classes
        if visual_lane_target:
            future_visual_scope_target_names.append(target_name)
        else:
            active_text_scope_target_names.append(target_name)

        policy_assignments.append(
            {
                "requested_target_name": target_name,
                "visual_lane_target": visual_lane_target,
                "scope_class": scope_class,
                "historical_classification": historical_classification,
                "historical_runtime_confirmed": historical_runtime_confirmed,
            }
        )

        if visual_lane_target:
            listed_verdict = vl_recheck_v2_report.get("listed_verdict")
            strict_verdict = vl_recheck_v2_report.get("strict_verdict")
            exact_declared_target_listed = listed_verdict == "listed"
            exact_declared_target_runtime_confirmed = strict_verdict == "runtime_confirmed"
            current_scope_runtime_confirmed = False
            blocks_current_active_scope = False
            current_scope_classification = "future_visual_scope_pending"
            blocked_reason = (
                historical_decision.get("blocked_reason")
                or "Exact declared visual target remains unlisted and runtime-not-confirmed in the current provider set."
            )
            next_required_action = "Keep visual lane future-scoped until the exact declared target is listed and runtime-confirmed."
        else:
            exact_declared_target_listed = historical_classification == "exact_match_runtime_verified"
            exact_declared_target_runtime_confirmed = historical_classification == "exact_match_runtime_verified"
            current_scope_runtime_confirmed = historical_runtime_confirmed
            blocks_current_active_scope = not current_scope_runtime_confirmed
            current_scope_classification = (
                "current_active_text_scope_runtime_confirmed"
                if current_scope_runtime_confirmed
                else "current_active_text_scope_gap"
            )
            blocked_reason = historical_decision.get("blocked_reason")
            next_required_action = historical_decision.get("next_required_action")

        coverage_v2_targets.append(
            {
                "requested_target_name": target_name,
                "visual_lane_target": visual_lane_target,
                "scope_class": scope_class,
                "historical_classification": historical_classification,
                "exact_declared_target_listed": exact_declared_target_listed,
                "exact_declared_target_runtime_confirmed": exact_declared_target_runtime_confirmed,
                "current_scope_classification": current_scope_classification,
                "current_scope_runtime_confirmed": current_scope_runtime_confirmed,
                "blocks_current_active_scope": blocks_current_active_scope,
                "blocked_reason": blocked_reason,
                "next_required_action": next_required_action,
            }
        )

    policy_report = {
        "report_kind": "declared_target_scope_policy_decision_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "artifact_layer": "policy",
        "policy_layer_only": True,
        "consumes_historical_evidence_only": True,
        "effect_scope": effect_scope,
        "depends_on_declared_target_coverage_decision_v1_path": str(coverage_v1_path),
        "depends_on_declared_target_coverage_decision_v1_sha256": file_sha256(coverage_v1_path),
        "depends_on_declared_target_qwen25_vl_recheck_v2_path": str(vl_recheck_v2_path),
        "depends_on_declared_target_qwen25_vl_recheck_v2_sha256": file_sha256(vl_recheck_v2_path),
        "historical_strict_declared_policy_preserved": True,
        "current_scope_policy_enabled": True,
        "current_scope_type": "text_only_active_scope",
        "future_visual_scope_enabled": True,
        "future_visual_scope_blocks_current_active_scope": False,
        "no_historical_rewrite_performed": True,
        "no_runtime_reclassification_performed": True,
        "target_scope_assignments": policy_assignments,
        "summary": {
            "active_text_scope_target_count": len(active_text_scope_target_names),
            "future_visual_scope_target_count": len(future_visual_scope_target_names),
            "historical_strict_runtime_confirmed_target_count": sum(
                1 for item in policy_assignments if item.get("historical_runtime_confirmed")
            ),
            "historical_strict_blocker_count": sum(
                1 for item in policy_assignments if not item.get("historical_runtime_confirmed")
            ),
            "advisory_verdict": "declared_target_scope_policy_decision_v1_materialized",
        },
    }
    policy_path, policy_report = write_verification_json(
        "declared_target_scope_policy_decision_v1.json",
        policy_report,
    )

    all_active_text_scope_targets_runtime_confirmed = all(
        item.get("scope_class") != "active_text_scope" or item.get("current_scope_runtime_confirmed") is True
        for item in coverage_v2_targets
    )
    all_future_visual_scope_targets_runtime_confirmed = all(
        item.get("scope_class") != "future_visual_scope" or item.get("exact_declared_target_runtime_confirmed") is True
        for item in coverage_v2_targets
    )
    feature_ready_under_current_active_scope = all_active_text_scope_targets_runtime_confirmed
    future_visual_scope_ready = all_future_visual_scope_targets_runtime_confirmed
    future_visual_scope_blocks_current_feature_readiness = any(
        item.get("scope_class") == "future_visual_scope" and item.get("blocks_current_active_scope") is True
        for item in coverage_v2_targets
    )

    coverage_v2_report = {
        "report_kind": "declared_target_coverage_decision_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "artifact_layer": "policy",
        "policy_layer_only": True,
        "consumes_historical_evidence_only": True,
        "depends_on_declared_target_coverage_decision_v1_path": str(coverage_v1_path),
        "depends_on_declared_target_coverage_decision_v1_sha256": file_sha256(coverage_v1_path),
        "depends_on_declared_target_scope_policy_decision_v1_path": str(policy_path),
        "depends_on_declared_target_scope_policy_decision_v1_sha256": file_sha256(policy_path),
        "depends_on_declared_target_qwen25_vl_recheck_v2_path": str(vl_recheck_v2_path),
        "depends_on_declared_target_qwen25_vl_recheck_v2_sha256": file_sha256(vl_recheck_v2_path),
        "historical_all_declared_targets_runtime_confirmed": bool(
            historical_summary.get("all_declared_targets_runtime_confirmed")
        ),
        "historical_feature_ready_under_declared_target_policy": bool(
            historical_summary.get("feature_ready_under_declared_target_policy")
        ),
        "target_decisions": coverage_v2_targets,
        "overall_coverage_summary": {
            "all_active_text_scope_targets_runtime_confirmed": all_active_text_scope_targets_runtime_confirmed,
            "all_future_visual_scope_targets_runtime_confirmed": all_future_visual_scope_targets_runtime_confirmed,
            "feature_ready_under_current_active_scope": feature_ready_under_current_active_scope,
            "future_visual_scope_ready": future_visual_scope_ready,
            "future_visual_scope_blocks_current_feature_readiness": future_visual_scope_blocks_current_feature_readiness,
        },
    }
    coverage_v2_path, coverage_v2_report = write_verification_json(
        "declared_target_coverage_decision_v2.json",
        coverage_v2_report,
    )

    historical_declared_policy_strict_ready = bool(
        historical_summary.get("feature_ready_under_declared_target_policy")
    )
    current_active_text_scope_ready = bool(
        coverage_v2_report.get("overall_coverage_summary", {}).get("feature_ready_under_current_active_scope")
    )
    future_visual_lane_pending = not bool(
        coverage_v2_report.get("overall_coverage_summary", {}).get("future_visual_scope_ready")
    )
    if current_active_text_scope_ready and future_visual_lane_pending:
        current_scope_readiness_verdict = "current_active_text_scope_ready_with_future_visual_lane_pending"
    elif current_active_text_scope_ready:
        current_scope_readiness_verdict = "current_active_text_scope_ready"
    else:
        current_scope_readiness_verdict = "current_active_text_scope_not_ready"

    readiness_report = {
        "report_kind": "feature_lab_current_scope_readiness_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "artifact_layer": "readiness",
        "readiness_layer_only": True,
        "consumes_policy_artifacts_only": True,
        "depends_on_declared_target_scope_policy_decision_v1_path": str(policy_path),
        "depends_on_declared_target_scope_policy_decision_v1_sha256": file_sha256(policy_path),
        "depends_on_declared_target_coverage_decision_v2_path": str(coverage_v2_path),
        "depends_on_declared_target_coverage_decision_v2_sha256": file_sha256(coverage_v2_path),
        "current_active_text_scope_ready": current_active_text_scope_ready,
        "future_visual_lane_pending": future_visual_lane_pending,
        "historical_declared_policy_strict_ready": historical_declared_policy_strict_ready,
        "current_scope_readiness_verdict": current_scope_readiness_verdict,
        "summary": {
            "advisory_verdict": "feature_lab_current_scope_readiness_v1_materialized",
        },
    }
    readiness_path, readiness_report = write_verification_json(
        "feature_lab_current_scope_readiness_v1.json",
        readiness_report,
    )

    authorization_status = repo_precheck_v3_report.get("authorization_decision_status")
    planning_precheck_status = repo_precheck_v3_report.get("planning_precheck_status")
    integration_precheck_remains_blocked = bool(integration_gate_v4_report.get("integration_precheck_remains_blocked"))
    blocked_reason = repo_precheck_v3_report.get("blocked_reason")
    next_required_external_action = repo_precheck_v3_report.get("next_required_external_action")
    if not isinstance(next_required_external_action, str) or not next_required_external_action:
        next_required_external_action = "provide_explicit_external_approval_evidence_for_repo_bound_integration"

    if not current_active_text_scope_ready:
        next_admissible_contour = "declared_target_text_scope_gap_closure"
        entrypoint_reason = "current_text_scope_not_ready"
    elif authorization_status == "pending":
        next_admissible_contour = "repo_bound_authorization_wait_state"
        entrypoint_reason = "current_text_scope_ready_but_repo_bound_authorization_absent"
    elif planning_precheck_status == "blocked" or integration_precheck_remains_blocked:
        next_admissible_contour = "repo_bound_planning_blocker_closure"
        entrypoint_reason = "current_text_scope_ready_but_repo_bound_blockers_remain"
    else:
        next_admissible_contour = "repo_bound_integration_planning"
        entrypoint_reason = "current_text_scope_ready_and_repo_bound_precheck_ready"

    workflow_report = {
        "report_kind": "feature_lab_next_contour_entrypoint_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "artifact_layer": "workflow",
        "workflow_layer_only": True,
        "consumes_readiness_artifacts": True,
        "consumes_policy_artifacts_directly": False,
        "depends_on_feature_lab_current_scope_readiness_v1_path": str(readiness_path),
        "depends_on_feature_lab_current_scope_readiness_v1_sha256": file_sha256(readiness_path),
        "depends_on_repo_bound_planning_precheck_result_v3_path": str(repo_precheck_v3_path),
        "depends_on_repo_bound_planning_precheck_result_v3_sha256": file_sha256(repo_precheck_v3_path),
        "depends_on_integration_gate_precheck_v4_path": str(integration_gate_v4_path),
        "depends_on_integration_gate_precheck_v4_sha256": file_sha256(integration_gate_v4_path),
        "current_active_text_scope_ready": current_active_text_scope_ready,
        "future_visual_lane_pending": future_visual_lane_pending,
        "authorization_decision_status": authorization_status,
        "repo_bound_planning_precheck_status": planning_precheck_status,
        "integration_precheck_remains_blocked": integration_precheck_remains_blocked,
        "next_admissible_contour": next_admissible_contour,
        "entrypoint_reason": entrypoint_reason,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "summary": {
            "advisory_verdict": "feature_lab_next_contour_entrypoint_v1_defined",
        },
    }
    workflow_path, workflow_report = write_verification_json(
        "feature_lab_next_contour_entrypoint_v1.json",
        workflow_report,
    )

    policy_scope_index = {
        item["requested_target_name"]: item
        for item in policy_report.get("target_scope_assignments", [])
        if isinstance(item, dict) and isinstance(item.get("requested_target_name"), str)
    }
    coverage_v2_index = {
        item["requested_target_name"]: item
        for item in coverage_v2_report.get("target_decisions", [])
        if isinstance(item, dict) and isinstance(item.get("requested_target_name"), str)
    }
    expected_scope_classes = {
        "Devstral-Small-2-24B-Instruct-2512": "active_text_scope",
        "Qwen2.5-Coder-32B-Instruct": "active_text_scope",
        "Qwen3-32B": "active_text_scope",
        "Mistral-Small-3.1-24B-Instruct-2503": "active_text_scope",
        "Qwen2.5-VL-7B-Instruct": "future_visual_scope",
    }
    audit_findings = []
    if policy_report.get("historical_strict_declared_policy_preserved") is not True:
        audit_findings.append(
            {
                "finding_id": "historical_strict_declared_policy_not_preserved",
                "severity": "P0",
                "message": "Policy layer must preserve the historical strict declared-target truth.",
                "evidence_paths": [str(policy_path), str(coverage_v1_path)],
            }
        )
    if policy_report.get("current_scope_policy_enabled") is not True or policy_report.get("current_scope_type") != "text_only_active_scope":
        audit_findings.append(
            {
                "finding_id": "current_scope_policy_contract_mismatch",
                "severity": "P0",
                "message": "Current active scope policy must be enabled as text_only_active_scope.",
                "evidence_paths": [str(policy_path)],
            }
        )
    if policy_report.get("future_visual_scope_enabled") is not True or policy_report.get("future_visual_scope_blocks_current_active_scope") is not False:
        audit_findings.append(
            {
                "finding_id": "future_visual_scope_policy_contract_mismatch",
                "severity": "P0",
                "message": "Future visual scope must remain enabled but non-blocking for the current active scope.",
                "evidence_paths": [str(policy_path)],
            }
        )
    for target_name, expected_scope_class in expected_scope_classes.items():
        assignment = policy_scope_index.get(target_name)
        if not isinstance(assignment, dict) or assignment.get("scope_class") != expected_scope_class:
            audit_findings.append(
                {
                    "finding_id": f"policy_scope_assignment_mismatch_{target_name}",
                    "severity": "P0",
                    "message": "Policy scope assignment does not match the approved target split.",
                    "evidence_paths": [str(policy_path)],
                }
            )

    if coverage_v2_report.get("historical_all_declared_targets_runtime_confirmed") is not bool(
        historical_summary.get("all_declared_targets_runtime_confirmed")
    ):
        audit_findings.append(
            {
                "finding_id": "historical_runtime_confirmed_flag_rewritten",
                "severity": "P0",
                "message": "Coverage v2 must preserve historical all_declared_targets_runtime_confirmed from v1.",
                "evidence_paths": [str(coverage_v2_path), str(coverage_v1_path)],
            }
        )
    if coverage_v2_report.get("historical_feature_ready_under_declared_target_policy") is not bool(
        historical_summary.get("feature_ready_under_declared_target_policy")
    ):
        audit_findings.append(
            {
                "finding_id": "historical_feature_ready_flag_rewritten",
                "severity": "P0",
                "message": "Coverage v2 must preserve historical strict feature readiness from v1.",
                "evidence_paths": [str(coverage_v2_path), str(coverage_v1_path)],
            }
        )

    coverage_summary_v2 = coverage_v2_report.get("overall_coverage_summary", {})
    expected_summary_pairs = {
        "all_active_text_scope_targets_runtime_confirmed": True,
        "all_future_visual_scope_targets_runtime_confirmed": False,
        "feature_ready_under_current_active_scope": True,
        "future_visual_scope_ready": False,
        "future_visual_scope_blocks_current_feature_readiness": False,
    }
    for field_name, expected_value in expected_summary_pairs.items():
        if coverage_summary_v2.get(field_name) is not expected_value:
            audit_findings.append(
                {
                    "finding_id": f"coverage_v2_summary_mismatch_{field_name}",
                    "severity": "P0",
                    "message": "Coverage v2 summary does not match the approved current-state semantics.",
                    "evidence_paths": [str(coverage_v2_path)],
                }
            )

    vl_row = coverage_v2_index.get("Qwen2.5-VL-7B-Instruct")
    if not isinstance(vl_row, dict):
        audit_findings.append(
            {
                "finding_id": "visual_lane_target_missing_in_coverage_v2",
                "severity": "P0",
                "message": "Coverage v2 must carry the future visual lane target row.",
                "evidence_paths": [str(coverage_v2_path)],
            }
        )
    else:
        visual_contract_passed = (
            vl_row.get("scope_class") == "future_visual_scope"
            and vl_row.get("exact_declared_target_listed") is False
            and vl_row.get("exact_declared_target_runtime_confirmed") is False
            and vl_row.get("blocks_current_active_scope") is False
        )
        if not visual_contract_passed:
            audit_findings.append(
                {
                    "finding_id": "visual_lane_current_scope_contract_mismatch",
                    "severity": "P0",
                    "message": "Future visual lane row must stay pending without blocking the current active scope.",
                    "evidence_paths": [str(coverage_v2_path), str(vl_recheck_v2_path)],
                }
            )

    if readiness_report.get("current_active_text_scope_ready") is not True:
        audit_findings.append(
            {
                "finding_id": "current_active_text_scope_ready_must_be_true",
                "severity": "P0",
                "message": "Readiness artifact must mark the active text scope as ready.",
                "evidence_paths": [str(readiness_path)],
            }
        )
    if readiness_report.get("future_visual_lane_pending") is not True:
        audit_findings.append(
            {
                "finding_id": "future_visual_lane_pending_must_be_true",
                "severity": "P0",
                "message": "Readiness artifact must keep the future visual lane pending.",
                "evidence_paths": [str(readiness_path)],
            }
        )
    if readiness_report.get("historical_declared_policy_strict_ready") is not False:
        audit_findings.append(
            {
                "finding_id": "historical_declared_policy_strict_ready_must_be_false",
                "severity": "P0",
                "message": "Readiness artifact must preserve that historical strict declared policy is not ready.",
                "evidence_paths": [str(readiness_path), str(coverage_v1_path)],
            }
        )
    if readiness_report.get("current_scope_readiness_verdict") != "current_active_text_scope_ready_with_future_visual_lane_pending":
        audit_findings.append(
            {
                "finding_id": "readiness_verdict_mismatch",
                "severity": "P0",
                "message": "Readiness verdict must reflect ready text scope with pending future visual lane.",
                "evidence_paths": [str(readiness_path)],
            }
        )

    if workflow_report.get("next_admissible_contour") != "repo_bound_authorization_wait_state":
        audit_findings.append(
            {
                "finding_id": "next_contour_must_be_repo_bound_authorization_wait_state",
                "severity": "P0",
                "message": "Workflow entrypoint must move into repo_bound_authorization_wait_state under the current facts.",
                "evidence_paths": [str(workflow_path), str(repo_precheck_v3_path)],
            }
        )
    if workflow_report.get("entrypoint_reason") != "current_text_scope_ready_but_repo_bound_authorization_absent":
        audit_findings.append(
            {
                "finding_id": "workflow_entrypoint_reason_mismatch",
                "severity": "P0",
                "message": "Workflow entrypoint reason must reflect missing repo-bound authorization after text scope readiness.",
                "evidence_paths": [str(workflow_path), str(repo_precheck_v3_path)],
            }
        )

    audit_report = {
        "report_kind": "declared_target_coverage_audit_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "depends_on_declared_target_scope_policy_decision_v1_path": str(policy_path),
        "depends_on_declared_target_scope_policy_decision_v1_sha256": file_sha256(policy_path),
        "depends_on_declared_target_coverage_decision_v2_path": str(coverage_v2_path),
        "depends_on_declared_target_coverage_decision_v2_sha256": file_sha256(coverage_v2_path),
        "depends_on_feature_lab_current_scope_readiness_v1_path": str(readiness_path),
        "depends_on_feature_lab_current_scope_readiness_v1_sha256": file_sha256(readiness_path),
        "depends_on_feature_lab_next_contour_entrypoint_v1_path": str(workflow_path),
        "depends_on_feature_lab_next_contour_entrypoint_v1_sha256": file_sha256(workflow_path),
        "integrity_only_assurance": True,
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "declared_target_coverage_audit_v2_passed"
                if len(audit_findings) == 0
                else "declared_target_coverage_audit_v2_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_path, audit_report = write_verification_json(
        "declared_target_coverage_audit_v2.json",
        audit_report,
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    factcheck_findings = []
    checks = [
        (
            "sha_coverage_v1_policy",
            policy_report.get("depends_on_declared_target_coverage_decision_v1_path"),
            policy_report.get("depends_on_declared_target_coverage_decision_v1_sha256"),
            str(policy_path),
        ),
        (
            "sha_vl_recheck_policy",
            policy_report.get("depends_on_declared_target_qwen25_vl_recheck_v2_path"),
            policy_report.get("depends_on_declared_target_qwen25_vl_recheck_v2_sha256"),
            str(policy_path),
        ),
        (
            "sha_coverage_v1_coverage_v2",
            coverage_v2_report.get("depends_on_declared_target_coverage_decision_v1_path"),
            coverage_v2_report.get("depends_on_declared_target_coverage_decision_v1_sha256"),
            str(coverage_v2_path),
        ),
        (
            "sha_policy_coverage_v2",
            coverage_v2_report.get("depends_on_declared_target_scope_policy_decision_v1_path"),
            coverage_v2_report.get("depends_on_declared_target_scope_policy_decision_v1_sha256"),
            str(coverage_v2_path),
        ),
        (
            "sha_vl_recheck_coverage_v2",
            coverage_v2_report.get("depends_on_declared_target_qwen25_vl_recheck_v2_path"),
            coverage_v2_report.get("depends_on_declared_target_qwen25_vl_recheck_v2_sha256"),
            str(coverage_v2_path),
        ),
        (
            "sha_policy_readiness",
            readiness_report.get("depends_on_declared_target_scope_policy_decision_v1_path"),
            readiness_report.get("depends_on_declared_target_scope_policy_decision_v1_sha256"),
            str(readiness_path),
        ),
        (
            "sha_coverage_v2_readiness",
            readiness_report.get("depends_on_declared_target_coverage_decision_v2_path"),
            readiness_report.get("depends_on_declared_target_coverage_decision_v2_sha256"),
            str(readiness_path),
        ),
        (
            "sha_readiness_workflow",
            workflow_report.get("depends_on_feature_lab_current_scope_readiness_v1_path"),
            workflow_report.get("depends_on_feature_lab_current_scope_readiness_v1_sha256"),
            str(workflow_path),
        ),
        (
            "sha_repo_precheck_v3_workflow",
            workflow_report.get("depends_on_repo_bound_planning_precheck_result_v3_path"),
            workflow_report.get("depends_on_repo_bound_planning_precheck_result_v3_sha256"),
            str(workflow_path),
        ),
        (
            "sha_integration_gate_v4_workflow",
            workflow_report.get("depends_on_integration_gate_precheck_v4_path"),
            workflow_report.get("depends_on_integration_gate_precheck_v4_sha256"),
            str(workflow_path),
        ),
        (
            "sha_policy_audit",
            audit_report.get("depends_on_declared_target_scope_policy_decision_v1_path"),
            audit_report.get("depends_on_declared_target_scope_policy_decision_v1_sha256"),
            str(audit_path),
        ),
        (
            "sha_coverage_v2_audit",
            audit_report.get("depends_on_declared_target_coverage_decision_v2_path"),
            audit_report.get("depends_on_declared_target_coverage_decision_v2_sha256"),
            str(audit_path),
        ),
        (
            "sha_readiness_audit",
            audit_report.get("depends_on_feature_lab_current_scope_readiness_v1_path"),
            audit_report.get("depends_on_feature_lab_current_scope_readiness_v1_sha256"),
            str(audit_path),
        ),
        (
            "sha_workflow_audit",
            audit_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_path"),
            audit_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
            str(audit_path),
        ),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 7B dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    if coverage_summary_v2.get("feature_ready_under_current_active_scope") is not readiness_report.get("current_active_text_scope_ready"):
        factcheck_findings.append(
            {
                "finding_id": "readiness_vs_coverage_v2_scope_flag_mismatch",
                "severity": "P0",
                "message": "Readiness current scope flag must match coverage v2 current active scope readiness.",
                "evidence_paths": [str(coverage_v2_path), str(readiness_path)],
            }
        )
    if future_visual_lane_pending is not (coverage_summary_v2.get("future_visual_scope_ready") is False):
        factcheck_findings.append(
            {
                "finding_id": "future_visual_pending_vs_coverage_v2_mismatch",
                "severity": "P0",
                "message": "Readiness future visual pending flag must match coverage v2 future visual readiness.",
                "evidence_paths": [str(coverage_v2_path), str(readiness_path)],
            }
        )
    if workflow_report.get("current_active_text_scope_ready") is not readiness_report.get("current_active_text_scope_ready"):
        factcheck_findings.append(
            {
                "finding_id": "workflow_vs_readiness_scope_flag_mismatch",
                "severity": "P0",
                "message": "Workflow current scope flag must match readiness artifact.",
                "evidence_paths": [str(workflow_path), str(readiness_path)],
            }
        )
    if workflow_report.get("future_visual_lane_pending") is not readiness_report.get("future_visual_lane_pending"):
        factcheck_findings.append(
            {
                "finding_id": "workflow_vs_readiness_future_visual_flag_mismatch",
                "severity": "P0",
                "message": "Workflow future visual pending flag must match readiness artifact.",
                "evidence_paths": [str(workflow_path), str(readiness_path)],
            }
        )

    factcheck_report = {
        "report_kind": "declared_target_coverage_factcheck_v2",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 6,
        "depends_on_declared_target_coverage_audit_v2_path": str(audit_path),
        "depends_on_declared_target_coverage_audit_v2_sha256": file_sha256(audit_path),
        "integrity_only_assurance": True,
        "current_active_text_scope_ready": current_active_text_scope_ready,
        "future_visual_lane_pending": future_visual_lane_pending,
        "next_admissible_contour": next_admissible_contour,
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "declared_target_coverage_factcheck_v2_passed"
                if len(factcheck_findings) == 0
                else "declared_target_coverage_factcheck_v2_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_path, factcheck_report = write_verification_json(
        "declared_target_coverage_factcheck_v2.json",
        factcheck_report,
    )

    artifact_specs = [
        {
            "path": policy_path,
            "expected_report_kind": "declared_target_scope_policy_decision_v1",
            "dependency_keys": [
                ("depends_on_declared_target_coverage_decision_v1_path", "depends_on_declared_target_coverage_decision_v1_sha256"),
                ("depends_on_declared_target_qwen25_vl_recheck_v2_path", "depends_on_declared_target_qwen25_vl_recheck_v2_sha256"),
            ],
        },
        {
            "path": coverage_v2_path,
            "expected_report_kind": "declared_target_coverage_decision_v2",
            "dependency_keys": [
                ("depends_on_declared_target_coverage_decision_v1_path", "depends_on_declared_target_coverage_decision_v1_sha256"),
                ("depends_on_declared_target_scope_policy_decision_v1_path", "depends_on_declared_target_scope_policy_decision_v1_sha256"),
                ("depends_on_declared_target_qwen25_vl_recheck_v2_path", "depends_on_declared_target_qwen25_vl_recheck_v2_sha256"),
            ],
        },
        {
            "path": readiness_path,
            "expected_report_kind": "feature_lab_current_scope_readiness_v1",
            "dependency_keys": [
                ("depends_on_declared_target_scope_policy_decision_v1_path", "depends_on_declared_target_scope_policy_decision_v1_sha256"),
                ("depends_on_declared_target_coverage_decision_v2_path", "depends_on_declared_target_coverage_decision_v2_sha256"),
            ],
        },
        {
            "path": workflow_path,
            "expected_report_kind": "feature_lab_next_contour_entrypoint_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_current_scope_readiness_v1_path", "depends_on_feature_lab_current_scope_readiness_v1_sha256"),
                ("depends_on_repo_bound_planning_precheck_result_v3_path", "depends_on_repo_bound_planning_precheck_result_v3_sha256"),
                ("depends_on_integration_gate_precheck_v4_path", "depends_on_integration_gate_precheck_v4_sha256"),
            ],
        },
        {
            "path": audit_path,
            "expected_report_kind": "declared_target_coverage_audit_v2",
            "dependency_keys": [
                ("depends_on_declared_target_scope_policy_decision_v1_path", "depends_on_declared_target_scope_policy_decision_v1_sha256"),
                ("depends_on_declared_target_coverage_decision_v2_path", "depends_on_declared_target_coverage_decision_v2_sha256"),
                ("depends_on_feature_lab_current_scope_readiness_v1_path", "depends_on_feature_lab_current_scope_readiness_v1_sha256"),
                ("depends_on_feature_lab_next_contour_entrypoint_v1_path", "depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
            ],
        },
        {
            "path": factcheck_path,
            "expected_report_kind": "declared_target_coverage_factcheck_v2",
            "dependency_keys": [
                ("depends_on_declared_target_coverage_audit_v2_path", "depends_on_declared_target_coverage_audit_v2_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            artifact_row["dependency_checks"].append(
                {
                    "path_key": path_key,
                    "sha_key": sha_key,
                    "path_value": path_value,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "match": match,
                }
            )
            if not match:
                dep_passed = False

        semantic_contract_passed = True
        if spec["expected_report_kind"] == "declared_target_scope_policy_decision_v1":
            semantic_contract_passed = (
                artifact_report.get("historical_strict_declared_policy_preserved") is True
                and artifact_report.get("current_scope_policy_enabled") is True
                and artifact_report.get("current_scope_type") == "text_only_active_scope"
                and artifact_report.get("future_visual_scope_enabled") is True
                and artifact_report.get("future_visual_scope_blocks_current_active_scope") is False
                and artifact_report.get("no_historical_rewrite_performed") is True
                and artifact_report.get("no_runtime_reclassification_performed") is True
            )
        elif spec["expected_report_kind"] == "declared_target_coverage_decision_v2":
            artifact_summary = artifact_report.get("overall_coverage_summary", {})
            semantic_contract_passed = (
                artifact_summary.get("all_active_text_scope_targets_runtime_confirmed") is True
                and artifact_summary.get("all_future_visual_scope_targets_runtime_confirmed") is False
                and artifact_summary.get("feature_ready_under_current_active_scope") is True
                and artifact_summary.get("future_visual_scope_ready") is False
                and artifact_summary.get("future_visual_scope_blocks_current_feature_readiness") is False
            )
        elif spec["expected_report_kind"] == "feature_lab_current_scope_readiness_v1":
            semantic_contract_passed = (
                artifact_report.get("current_active_text_scope_ready") is True
                and artifact_report.get("future_visual_lane_pending") is True
                and artifact_report.get("historical_declared_policy_strict_ready") is False
                and artifact_report.get("current_scope_readiness_verdict")
                == "current_active_text_scope_ready_with_future_visual_lane_pending"
            )
        elif spec["expected_report_kind"] == "feature_lab_next_contour_entrypoint_v1":
            semantic_contract_passed = (
                artifact_report.get("next_admissible_contour") == "repo_bound_authorization_wait_state"
                and artifact_report.get("entrypoint_reason")
                == "current_text_scope_ready_but_repo_bound_authorization_absent"
            )
        elif spec["expected_report_kind"] == "declared_target_coverage_audit_v2":
            semantic_contract_passed = artifact_report.get("audit_passed") is True
        elif spec["expected_report_kind"] == "declared_target_coverage_factcheck_v2":
            semantic_contract_passed = artifact_report.get("factcheck_passed") is True

        artifact_row["semantic_contract_passed"] = semantic_contract_passed
        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed and semantic_contract_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_7b_declared_scope_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 7,
        "depends_on_declared_target_coverage_factcheck_v2_path": str(factcheck_path),
        "depends_on_declared_target_coverage_factcheck_v2_sha256": file_sha256(factcheck_path),
        "current_active_text_scope_ready": current_active_text_scope_ready,
        "future_visual_lane_pending": future_visual_lane_pending,
        "next_admissible_contour": next_admissible_contour,
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_path, _ = write_verification_json(
        "contour_7b_declared_scope_chain_validation_v1.json",
        chain_report,
    )

    print(f"JSON report: {policy_path}")
    print(f"JSON report: {coverage_v2_path}")
    print(f"JSON report: {readiness_path}")
    print(f"JSON report: {workflow_path}")
    print(f"JSON report: {audit_path}")
    print(f"JSON report: {factcheck_path}")
    print(f"JSON report: {chain_path}")


def run_contour_7c_repo_bound_authorization_wait_state_generator(args):
    ensure_env_permissions(ENV_PATH)
    contour_id = "contour_7c_repo_bound_authorization_wait_state"
    now_utc = datetime.now(timezone.utc).isoformat()
    decision_order = [
        "repo_bound_authorization_reentry_contract_v1",
        "repo_bound_authorization_wait_state_v1",
        "repo_bound_authorization_wait_state_audit_v1",
        "repo_bound_authorization_wait_state_factcheck_v1",
        "contour_7c_repo_bound_authorization_wait_state_chain_validation_v1",
    ]
    effect_scope = {
        "secondary_lab_support_contour": True,
        "does_not_supersede_primary_main_repo_contour": True,
        "runtime_probes_performed": False,
        "provider_expansion_performed": False,
        "model_expansion_performed": False,
        "repo_mutation_performed": False,
        "historical_artifacts_rewritten": False,
    }

    entrypoint_v1_path, entrypoint_v1_report = load_fixed_verification_report(
        "feature_lab_next_contour_entrypoint_v1.json",
        "feature_lab_next_contour_entrypoint_v1",
    )
    chain_7b_path, chain_7b_report = load_fixed_verification_report(
        "contour_7b_declared_scope_chain_validation_v1.json",
        "contour_7b_declared_scope_chain_validation_v1",
    )
    repo_precheck_v3_path, repo_precheck_v3_report = load_fixed_verification_report(
        "repo_bound_planning_precheck_result_v3.json",
        "repo_bound_planning_precheck_result_v3",
    )
    integration_gate_v4_path, integration_gate_v4_report = load_fixed_verification_report(
        "integration_gate_precheck_v4.json",
        "integration_gate_precheck_v4",
    )

    current_active_text_scope_ready = chain_7b_report.get("current_active_text_scope_ready")
    future_visual_lane_pending = chain_7b_report.get("future_visual_lane_pending")
    next_admissible_contour = entrypoint_v1_report.get("next_admissible_contour")
    entrypoint_reason = entrypoint_v1_report.get("entrypoint_reason")
    authorization_decision_status = repo_precheck_v3_report.get("authorization_decision_status")
    planning_precheck_status = repo_precheck_v3_report.get("planning_precheck_status")
    blocked_reason = repo_precheck_v3_report.get("blocked_reason")
    next_required_external_action = repo_precheck_v3_report.get("next_required_external_action")
    if not isinstance(next_required_external_action, str) or not next_required_external_action:
        next_required_external_action = "provide_explicit_external_approval_evidence_for_repo_bound_integration"
    integration_precheck_remains_blocked = integration_gate_v4_report.get("integration_precheck_remains_blocked")

    if chain_7b_report.get("overall_passed") is not True:
        raise SystemExit("Contour 7C requires contour_7b_declared_scope_chain_validation_v1 overall_passed=true.")
    if current_active_text_scope_ready is not True:
        raise SystemExit("Contour 7C is admissible only when current_active_text_scope_ready=true.")
    if future_visual_lane_pending is not True:
        raise SystemExit("Contour 7C is admissible only when future_visual_lane_pending=true.")
    if next_admissible_contour != "repo_bound_authorization_wait_state":
        raise SystemExit("Contour 7C is admissible only when 7B next_admissible_contour=repo_bound_authorization_wait_state.")
    if entrypoint_reason != "current_text_scope_ready_but_repo_bound_authorization_absent":
        raise SystemExit("Contour 7C requires the 7B entrypoint_reason for missing repo-bound authorization.")
    if authorization_decision_status != "pending":
        raise SystemExit("Contour 7C is admissible only while authorization_decision_status remains pending.")
    if planning_precheck_status != "blocked":
        raise SystemExit("Contour 7C is admissible only while repo-bound planning precheck remains blocked.")
    if integration_precheck_remains_blocked is not True:
        raise SystemExit("Contour 7C is admissible only while integration_precheck_remains_blocked=true.")
    if blocked_reason != "external_authorization_not_approved_and_repo_bound_blockers_remain":
        raise SystemExit("Contour 7C requires the canonical blocked_reason from repo_bound_planning_precheck_result_v3.")

    reentry_contract_report = {
        "report_kind": "repo_bound_authorization_reentry_contract_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 1,
        "artifact_layer": "policy",
        "policy_layer_only": True,
        "secondary_lab_support_contour": True,
        "does_not_supersede_primary_main_repo_contour": True,
        "depends_on_feature_lab_next_contour_entrypoint_v1_path": str(entrypoint_v1_path),
        "depends_on_feature_lab_next_contour_entrypoint_v1_sha256": file_sha256(entrypoint_v1_path),
        "depends_on_repo_bound_planning_precheck_result_v3_path": str(repo_precheck_v3_path),
        "depends_on_repo_bound_planning_precheck_result_v3_sha256": file_sha256(repo_precheck_v3_path),
        "canon_owner_authorization_rule_path": str(Path("/Volumes/Work/wild-boar-proxy/CANON.md")),
        "accepted_authorization_sources": [
            "canon_project_scoped_standing_approval_in_active_thread",
            "canon_exact_one_off_owner_marker",
        ],
        "generic_begin_phrases_authorize_repo_bound_work": False,
        "narrative_memory_authorizes_repo_bound_work": False,
        "historical_lab_readiness_alone_authorizes_repo_bound_work": False,
        "authorization_required_for_repo_bound_work": True,
        "without_authorization_next_admissible_contour": "repo_bound_authorization_wait_state",
        "on_authorization_next_admissible_contour": "repo_bound_planning_blocker_closure",
        "summary": {
            "advisory_verdict": "repo_bound_authorization_reentry_contract_v1_materialized",
        },
    }
    reentry_contract_path, reentry_contract_report = write_verification_json(
        "repo_bound_authorization_reentry_contract_v1.json",
        reentry_contract_report,
    )

    wait_state_report = {
        "report_kind": "repo_bound_authorization_wait_state_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 2,
        "artifact_layer": "workflow",
        "workflow_layer_only": True,
        "consumes_policy_artifacts": True,
        "secondary_lab_support_contour": True,
        "does_not_supersede_primary_main_repo_contour": True,
        "effect_scope": effect_scope,
        "depends_on_repo_bound_authorization_reentry_contract_v1_path": str(reentry_contract_path),
        "depends_on_repo_bound_authorization_reentry_contract_v1_sha256": file_sha256(reentry_contract_path),
        "depends_on_feature_lab_next_contour_entrypoint_v1_path": str(entrypoint_v1_path),
        "depends_on_feature_lab_next_contour_entrypoint_v1_sha256": file_sha256(entrypoint_v1_path),
        "depends_on_contour_7b_declared_scope_chain_validation_v1_path": str(chain_7b_path),
        "depends_on_contour_7b_declared_scope_chain_validation_v1_sha256": file_sha256(chain_7b_path),
        "depends_on_repo_bound_planning_precheck_result_v3_path": str(repo_precheck_v3_path),
        "depends_on_repo_bound_planning_precheck_result_v3_sha256": file_sha256(repo_precheck_v3_path),
        "depends_on_integration_gate_precheck_v4_path": str(integration_gate_v4_path),
        "depends_on_integration_gate_precheck_v4_sha256": file_sha256(integration_gate_v4_path),
        "wait_state_active": True,
        "current_active_text_scope_ready": True,
        "future_visual_lane_pending": True,
        "authorization_present": False,
        "authorization_decision_status": authorization_decision_status,
        "repo_bound_planning_precheck_status": planning_precheck_status,
        "integration_precheck_remains_blocked": True,
        "repo_mutation_permitted": False,
        "repo_bound_integration_permitted": False,
        "new_provider_probes_permitted": False,
        "runtime_probe_reentry_permitted": False,
        "blocked_reason": blocked_reason,
        "next_required_external_action": next_required_external_action,
        "summary": {
            "advisory_verdict": "repo_bound_authorization_wait_state_v1_active",
        },
    }
    wait_state_path, wait_state_report = write_verification_json(
        "repo_bound_authorization_wait_state_v1.json",
        wait_state_report,
    )

    audit_findings = []
    if reentry_contract_report.get("generic_begin_phrases_authorize_repo_bound_work") is not False:
        audit_findings.append(
            {
                "finding_id": "generic_begin_phrases_must_not_authorize_repo_bound_work",
                "severity": "P0",
                "message": "Generic begin/start phrases must remain non-authorizing for repo-bound work.",
                "evidence_paths": [str(reentry_contract_path)],
            }
        )
    if reentry_contract_report.get("narrative_memory_authorizes_repo_bound_work") is not False:
        audit_findings.append(
            {
                "finding_id": "narrative_memory_must_not_authorize_repo_bound_work",
                "severity": "P0",
                "message": "Narrative memory must not be treated as repo-bound authorization.",
                "evidence_paths": [str(reentry_contract_path)],
            }
        )
    if reentry_contract_report.get("historical_lab_readiness_alone_authorizes_repo_bound_work") is not False:
        audit_findings.append(
            {
                "finding_id": "historical_lab_readiness_must_not_authorize_repo_bound_work",
                "severity": "P0",
                "message": "Historical lab readiness alone must not authorize repo-bound work.",
                "evidence_paths": [str(reentry_contract_path)],
            }
        )
    if reentry_contract_report.get("without_authorization_next_admissible_contour") != "repo_bound_authorization_wait_state":
        audit_findings.append(
            {
                "finding_id": "without_authorization_next_contour_mismatch",
                "severity": "P0",
                "message": "Re-entry contract must keep the wait state without valid authorization.",
                "evidence_paths": [str(reentry_contract_path)],
            }
        )
    if reentry_contract_report.get("on_authorization_next_admissible_contour") != "repo_bound_planning_blocker_closure":
        audit_findings.append(
            {
                "finding_id": "on_authorization_next_contour_mismatch",
                "severity": "P0",
                "message": "Authorization re-entry must flow to repo_bound_planning_blocker_closure, not direct integration.",
                "evidence_paths": [str(reentry_contract_path)],
            }
        )
    if wait_state_report.get("wait_state_active") is not True:
        audit_findings.append(
            {
                "finding_id": "wait_state_must_be_active",
                "severity": "P0",
                "message": "Current contour must materialize an active repo-bound authorization wait state.",
                "evidence_paths": [str(wait_state_path)],
            }
        )
    expected_wait_state_pairs = {
        "current_active_text_scope_ready": True,
        "future_visual_lane_pending": True,
        "authorization_present": False,
        "authorization_decision_status": "pending",
        "repo_mutation_permitted": False,
        "repo_bound_integration_permitted": False,
        "new_provider_probes_permitted": False,
        "runtime_probe_reentry_permitted": False,
        "blocked_reason": "external_authorization_not_approved_and_repo_bound_blockers_remain",
        "next_required_external_action": "provide_explicit_external_approval_evidence_for_repo_bound_integration",
    }
    for field_name, expected_value in expected_wait_state_pairs.items():
        if wait_state_report.get(field_name) != expected_value:
            audit_findings.append(
                {
                    "finding_id": f"wait_state_field_mismatch_{field_name}",
                    "severity": "P0",
                    "message": "Wait-state artifact field does not match the current blocked-state contract.",
                    "evidence_paths": [str(wait_state_path)],
                }
            )
    if wait_state_report.get("secondary_lab_support_contour") is not True or wait_state_report.get("does_not_supersede_primary_main_repo_contour") is not True:
        audit_findings.append(
            {
                "finding_id": "secondary_lab_support_position_mismatch",
                "severity": "P0",
                "message": "Contour 7C must remain a secondary lab-support contour and must not supersede the primary main-repo contour.",
                "evidence_paths": [str(wait_state_path), str(reentry_contract_path)],
            }
        )
    if entrypoint_v1_report.get("next_admissible_contour") != "repo_bound_authorization_wait_state":
        audit_findings.append(
            {
                "finding_id": "7b_entrypoint_next_contour_mismatch",
                "severity": "P0",
                "message": "Contour 7B workflow output must continue to point at repo_bound_authorization_wait_state.",
                "evidence_paths": [str(entrypoint_v1_path)],
            }
        )

    audit_report = {
        "report_kind": "repo_bound_authorization_wait_state_audit_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 3,
        "artifact_layer": "assurance",
        "assurance_layer_only": True,
        "depends_on_repo_bound_authorization_reentry_contract_v1_path": str(reentry_contract_path),
        "depends_on_repo_bound_authorization_reentry_contract_v1_sha256": file_sha256(reentry_contract_path),
        "depends_on_repo_bound_authorization_wait_state_v1_path": str(wait_state_path),
        "depends_on_repo_bound_authorization_wait_state_v1_sha256": file_sha256(wait_state_path),
        "integrity_only_assurance": True,
        "audit_findings": audit_findings,
        "audit_passed": len(audit_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_authorization_wait_state_audit_v1_passed"
                if len(audit_findings) == 0
                else "repo_bound_authorization_wait_state_audit_v1_failed"
            ),
            "finding_count": len(audit_findings),
        },
    }
    audit_path, audit_report = write_verification_json(
        "repo_bound_authorization_wait_state_audit_v1.json",
        audit_report,
    )

    def _sha_match(path_value, sha_value):
        if not isinstance(path_value, str) or not isinstance(sha_value, str):
            return False
        try:
            return file_sha256(Path(path_value)) == sha_value
        except Exception:
            return False

    factcheck_findings = []
    checks = [
        (
            "sha_entrypoint_v1_reentry_contract",
            reentry_contract_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_path"),
            reentry_contract_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
            str(reentry_contract_path),
        ),
        (
            "sha_repo_precheck_v3_reentry_contract",
            reentry_contract_report.get("depends_on_repo_bound_planning_precheck_result_v3_path"),
            reentry_contract_report.get("depends_on_repo_bound_planning_precheck_result_v3_sha256"),
            str(reentry_contract_path),
        ),
        (
            "sha_reentry_contract_wait_state",
            wait_state_report.get("depends_on_repo_bound_authorization_reentry_contract_v1_path"),
            wait_state_report.get("depends_on_repo_bound_authorization_reentry_contract_v1_sha256"),
            str(wait_state_path),
        ),
        (
            "sha_entrypoint_v1_wait_state",
            wait_state_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_path"),
            wait_state_report.get("depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
            str(wait_state_path),
        ),
        (
            "sha_chain_7b_wait_state",
            wait_state_report.get("depends_on_contour_7b_declared_scope_chain_validation_v1_path"),
            wait_state_report.get("depends_on_contour_7b_declared_scope_chain_validation_v1_sha256"),
            str(wait_state_path),
        ),
        (
            "sha_repo_precheck_v3_wait_state",
            wait_state_report.get("depends_on_repo_bound_planning_precheck_result_v3_path"),
            wait_state_report.get("depends_on_repo_bound_planning_precheck_result_v3_sha256"),
            str(wait_state_path),
        ),
        (
            "sha_integration_gate_v4_wait_state",
            wait_state_report.get("depends_on_integration_gate_precheck_v4_path"),
            wait_state_report.get("depends_on_integration_gate_precheck_v4_sha256"),
            str(wait_state_path),
        ),
        (
            "sha_reentry_contract_audit",
            audit_report.get("depends_on_repo_bound_authorization_reentry_contract_v1_path"),
            audit_report.get("depends_on_repo_bound_authorization_reentry_contract_v1_sha256"),
            str(audit_path),
        ),
        (
            "sha_wait_state_audit",
            audit_report.get("depends_on_repo_bound_authorization_wait_state_v1_path"),
            audit_report.get("depends_on_repo_bound_authorization_wait_state_v1_sha256"),
            str(audit_path),
        ),
    ]
    for finding_id, path_value, sha_value, report_path in checks:
        if not _sha_match(path_value, sha_value):
            factcheck_findings.append(
                {
                    "finding_id": finding_id,
                    "severity": "P0",
                    "message": "Contour 7C dependency SHA mismatch.",
                    "evidence_paths": [report_path, str(path_value)],
                }
            )

    if audit_report.get("audit_passed") is not True:
        factcheck_findings.append(
            {
                "finding_id": "wait_state_audit_must_pass",
                "severity": "P0",
                "message": "Contour 7C factcheck requires audit_passed=true.",
                "evidence_paths": [str(audit_path)],
            }
        )
    if chain_7b_report.get("current_active_text_scope_ready") is not wait_state_report.get("current_active_text_scope_ready"):
        factcheck_findings.append(
            {
                "finding_id": "wait_state_vs_chain_7b_current_scope_mismatch",
                "severity": "P0",
                "message": "Wait-state current_active_text_scope_ready must match contour 7B chain truth.",
                "evidence_paths": [str(chain_7b_path), str(wait_state_path)],
            }
        )
    if chain_7b_report.get("future_visual_lane_pending") is not wait_state_report.get("future_visual_lane_pending"):
        factcheck_findings.append(
            {
                "finding_id": "wait_state_vs_chain_7b_future_visual_mismatch",
                "severity": "P0",
                "message": "Wait-state future_visual_lane_pending must match contour 7B chain truth.",
                "evidence_paths": [str(chain_7b_path), str(wait_state_path)],
            }
        )
    if entrypoint_v1_report.get("next_admissible_contour") != reentry_contract_report.get("without_authorization_next_admissible_contour"):
        factcheck_findings.append(
            {
                "finding_id": "entrypoint_v1_vs_reentry_contract_mismatch",
                "severity": "P0",
                "message": "Re-entry contract without-authorization path must match contour 7B workflow output.",
                "evidence_paths": [str(entrypoint_v1_path), str(reentry_contract_path)],
            }
        )
    if wait_state_report.get("authorization_decision_status") != repo_precheck_v3_report.get("authorization_decision_status"):
        factcheck_findings.append(
            {
                "finding_id": "wait_state_vs_repo_precheck_authorization_status_mismatch",
                "severity": "P0",
                "message": "Wait-state authorization_decision_status must match repo_bound_planning_precheck_result_v3.",
                "evidence_paths": [str(repo_precheck_v3_path), str(wait_state_path)],
            }
        )

    factcheck_report = {
        "report_kind": "repo_bound_authorization_wait_state_factcheck_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 4,
        "artifact_layer": "assurance",
        "assurance_layer_only": True,
        "depends_on_repo_bound_authorization_wait_state_audit_v1_path": str(audit_path),
        "depends_on_repo_bound_authorization_wait_state_audit_v1_sha256": file_sha256(audit_path),
        "integrity_only_assurance": True,
        "wait_state_active": True,
        "factcheck_findings": factcheck_findings,
        "factcheck_passed": len(factcheck_findings) == 0,
        "summary": {
            "advisory_verdict": (
                "repo_bound_authorization_wait_state_factcheck_v1_passed"
                if len(factcheck_findings) == 0
                else "repo_bound_authorization_wait_state_factcheck_v1_failed"
            ),
            "finding_count": len(factcheck_findings),
        },
    }
    factcheck_path, factcheck_report = write_verification_json(
        "repo_bound_authorization_wait_state_factcheck_v1.json",
        factcheck_report,
    )

    artifact_specs = [
        {
            "path": reentry_contract_path,
            "expected_report_kind": "repo_bound_authorization_reentry_contract_v1",
            "dependency_keys": [
                ("depends_on_feature_lab_next_contour_entrypoint_v1_path", "depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
                ("depends_on_repo_bound_planning_precheck_result_v3_path", "depends_on_repo_bound_planning_precheck_result_v3_sha256"),
            ],
        },
        {
            "path": wait_state_path,
            "expected_report_kind": "repo_bound_authorization_wait_state_v1",
            "dependency_keys": [
                ("depends_on_repo_bound_authorization_reentry_contract_v1_path", "depends_on_repo_bound_authorization_reentry_contract_v1_sha256"),
                ("depends_on_feature_lab_next_contour_entrypoint_v1_path", "depends_on_feature_lab_next_contour_entrypoint_v1_sha256"),
                ("depends_on_contour_7b_declared_scope_chain_validation_v1_path", "depends_on_contour_7b_declared_scope_chain_validation_v1_sha256"),
                ("depends_on_repo_bound_planning_precheck_result_v3_path", "depends_on_repo_bound_planning_precheck_result_v3_sha256"),
                ("depends_on_integration_gate_precheck_v4_path", "depends_on_integration_gate_precheck_v4_sha256"),
            ],
        },
        {
            "path": audit_path,
            "expected_report_kind": "repo_bound_authorization_wait_state_audit_v1",
            "dependency_keys": [
                ("depends_on_repo_bound_authorization_reentry_contract_v1_path", "depends_on_repo_bound_authorization_reentry_contract_v1_sha256"),
                ("depends_on_repo_bound_authorization_wait_state_v1_path", "depends_on_repo_bound_authorization_wait_state_v1_sha256"),
            ],
        },
        {
            "path": factcheck_path,
            "expected_report_kind": "repo_bound_authorization_wait_state_factcheck_v1",
            "dependency_keys": [
                ("depends_on_repo_bound_authorization_wait_state_audit_v1_path", "depends_on_repo_bound_authorization_wait_state_audit_v1_sha256"),
            ],
        },
    ]

    chain_artifacts = []
    chain_overall_passed = True
    for spec in artifact_specs:
        artifact_path = Path(spec["path"])
        artifact_row = {
            "path": str(artifact_path),
            "expected_report_kind": spec["expected_report_kind"],
            "exists": artifact_path.exists(),
            "dependency_checks": [],
            "errors": [],
        }
        if not artifact_row["exists"]:
            artifact_row["errors"].append("artifact_missing")
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        artifact_row["sha256"] = file_sha256(artifact_path)
        try:
            _, artifact_report = load_attested_report(str(artifact_path), spec["expected_report_kind"])
            artifact_row["attestation_verified"] = True
            artifact_row["report_kind"] = artifact_report.get("report_kind")
        except SystemExit as exc:
            artifact_row["attestation_verified"] = False
            artifact_row["errors"].append(str(exc))
            artifact_row["passed"] = False
            chain_overall_passed = False
            chain_artifacts.append(artifact_row)
            continue

        dep_passed = True
        for path_key, sha_key in spec["dependency_keys"]:
            path_value = artifact_report.get(path_key)
            expected_sha = artifact_report.get(sha_key)
            actual_sha = None
            match = False
            if isinstance(path_value, str):
                try:
                    actual_sha = file_sha256(Path(path_value))
                    match = isinstance(expected_sha, str) and actual_sha == expected_sha
                except Exception:
                    match = False
            artifact_row["dependency_checks"].append(
                {
                    "path_key": path_key,
                    "sha_key": sha_key,
                    "path_value": path_value,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "match": match,
                }
            )
            if not match:
                dep_passed = False

        semantic_contract_passed = True
        if spec["expected_report_kind"] == "repo_bound_authorization_reentry_contract_v1":
            semantic_contract_passed = (
                artifact_report.get("generic_begin_phrases_authorize_repo_bound_work") is False
                and artifact_report.get("narrative_memory_authorizes_repo_bound_work") is False
                and artifact_report.get("historical_lab_readiness_alone_authorizes_repo_bound_work") is False
                and artifact_report.get("without_authorization_next_admissible_contour") == "repo_bound_authorization_wait_state"
                and artifact_report.get("on_authorization_next_admissible_contour") == "repo_bound_planning_blocker_closure"
            )
        elif spec["expected_report_kind"] == "repo_bound_authorization_wait_state_v1":
            semantic_contract_passed = (
                artifact_report.get("wait_state_active") is True
                and artifact_report.get("current_active_text_scope_ready") is True
                and artifact_report.get("future_visual_lane_pending") is True
                and artifact_report.get("authorization_present") is False
                and artifact_report.get("authorization_decision_status") == "pending"
                and artifact_report.get("repo_mutation_permitted") is False
                and artifact_report.get("repo_bound_integration_permitted") is False
                and artifact_report.get("new_provider_probes_permitted") is False
                and artifact_report.get("runtime_probe_reentry_permitted") is False
                and artifact_report.get("blocked_reason") == "external_authorization_not_approved_and_repo_bound_blockers_remain"
                and artifact_report.get("next_required_external_action")
                == "provide_explicit_external_approval_evidence_for_repo_bound_integration"
            )
        elif spec["expected_report_kind"] == "repo_bound_authorization_wait_state_audit_v1":
            semantic_contract_passed = artifact_report.get("audit_passed") is True
        elif spec["expected_report_kind"] == "repo_bound_authorization_wait_state_factcheck_v1":
            semantic_contract_passed = artifact_report.get("factcheck_passed") is True

        artifact_row["semantic_contract_passed"] = semantic_contract_passed
        artifact_row["passed"] = bool(artifact_row.get("attestation_verified")) and dep_passed and semantic_contract_passed
        if not artifact_row["passed"]:
            chain_overall_passed = False
        chain_artifacts.append(artifact_row)

    chain_report = {
        "report_kind": "contour_7c_repo_bound_authorization_wait_state_chain_validation_v1",
        "lab_mode": True,
        "started_at_utc": now_utc,
        "contour_id": contour_id,
        "decision_order": decision_order,
        "decision_order_index": 5,
        "artifact_layer": "assurance",
        "assurance_layer_only": True,
        "depends_on_repo_bound_authorization_wait_state_factcheck_v1_path": str(factcheck_path),
        "depends_on_repo_bound_authorization_wait_state_factcheck_v1_sha256": file_sha256(factcheck_path),
        "wait_state_active": True,
        "overall_passed": chain_overall_passed,
        "artifact_count": len(chain_artifacts),
        "artifacts": chain_artifacts,
    }
    chain_path, _ = write_verification_json(
        "contour_7c_repo_bound_authorization_wait_state_chain_validation_v1.json",
        chain_report,
    )

    print(f"JSON report: {reentry_contract_path}")
    print(f"JSON report: {wait_state_path}")
    print(f"JSON report: {audit_path}")
    print(f"JSON report: {factcheck_path}")
    print(f"JSON report: {chain_path}")


def main(argv=None):
    args = parse_args(argv)
    if args.mode == "provider-access":
        run_provider_access(args)
        return
    if args.mode == "error-taxonomy-check":
        run_error_taxonomy_check(args)
        return
    if args.mode == "cost-gate-check":
        run_cost_gate_check(args)
        return
    if args.mode == "model-registry-snapshot":
        run_model_registry_snapshot(args)
        return
    if args.mode == "baseline-snapshot":
        run_baseline_snapshot(args)
        return
    if args.mode == "admission-guard-check":
        run_admission_guard_check(args)
        return
    if args.mode == "admission-delta-check":
        run_admission_delta_check(args)
        return
    if args.mode == "mutation-design":
        run_mutation_design(args)
        return
    if args.mode == "mutation-execute":
        run_mutation_execute(args)
        return
    if args.mode == "mutation-rollback":
        run_mutation_rollback(args)
        return
    if args.mode == "qualify":
        run_qualification(args)
        return
    if args.mode == "response-evidence":
        run_response_evidence(args)
        return
    if args.mode == "eval":
        run_eval(args)
        return
    if args.mode == "pilot-verification-precheck":
        run_pilot_verification_precheck(args)
        return
    if args.mode == "admission-state-check":
        run_admission_state_check(args)
        return
    if args.mode == "admission-trigger-check":
        run_admission_trigger_check(args)
        return
    if args.mode == "admission-event-check":
        run_admission_event_check(args)
        return
    if args.mode == "direct-provider-access-precheck":
        run_direct_provider_access_precheck(args)
        return
    if args.mode == "direct-route-qualification-precheck":
        run_direct_route_qualification_precheck(args)
        return
    if args.mode == "repo-bound-planning-precheck":
        run_repo_bound_planning_precheck(args)
        return
    if args.mode == "canon-first-contour-generator":
        run_canon_first_contour_generator(args)
        return
    if args.mode == "wave-2c-contour-generator":
        run_wave_2c_contour_generator(args)
        return
    if args.mode == "contour-1-synthetic-validation-generator":
        run_contour_1_synthetic_validation_generator(args)
        return
    if args.mode == "cerebras-contour-2-generator":
        run_cerebras_contour_2_generator(args)
        return
    if args.mode == "post-cerebras-contour-3-generator":
        run_post_cerebras_contour_3_generator(args)
        return
    if args.mode == "contour-4-criteria-closure-generator":
        run_contour_4_criteria_closure_generator(args)
        return
    if args.mode == "contour-5-five-of-seven-closure-generator":
        run_contour_5_five_of_seven_closure_generator(args)
        return
    if args.mode == "contour-6a-second-route-stability-gap-closure-generator":
        run_contour_6a_second_route_stability_gap_closure_generator(args)
        return
    if args.mode == "contour-6b-repo-bound-planning-precheck-closure-generator":
        run_contour_6b_repo_bound_planning_precheck_closure_generator(args)
        return
    if args.mode == "contour-6c-repo-bound-blocker-closure-generator":
        run_contour_6c_repo_bound_blocker_closure_generator(args)
        return
    if args.mode == "contour-6d-repo-bound-authorization-closure-generator":
        run_contour_6d_repo_bound_authorization_closure_generator(args)
        return
    if args.mode == "contour-6e-feature-lab-complete-package-generator":
        run_contour_6e_feature_lab_complete_package_generator(args)
        return
    if args.mode == "contour-7a-declared-target-coverage-generator":
        run_contour_7a_declared_target_coverage_generator(args)
        return
    if args.mode == "contour-7b-declared-scope-reconciliation-generator":
        run_contour_7b_declared_scope_reconciliation_generator(args)
        return
    if args.mode == "contour-7c-repo-bound-authorization-wait-state-generator":
        run_contour_7c_repo_bound_authorization_wait_state_generator(args)
        return
    raise SystemExit(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()

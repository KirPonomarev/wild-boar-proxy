#!/usr/bin/env python3
"""
OpenAI-compatible adapter lab for external coding models.

This server currently speaks:
  - GET  /v1/models
  - POST /v1/chat/completions
  - POST /v1/responses

The upstream remains chat/completions-only for now. The adapter layer exists
so terminal clients can exercise a Responses-like surface before we decide
whether the idea is worth carrying into a larger runtime.
"""

import json
import os
import sys
import time
import threading
import random
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Конфигурация ─────────────────────────────────────────────────────────────

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "models": {
            "direct-gemini-2.5-flash": {
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "upstream_model": "gemini-2.5-flash",
                "max_tokens": 8192,
                "cost_class": "paid_direct",
            },
        },
    },
    "groq": {
        "label": "Groq",
        "api_key_env": "GROQ_API_KEY",
        "models": {
            "direct-groq-openai-gpt-oss-20b": {
                "url": "https://api.groq.com/openai/v1/chat/completions",
                "upstream_model": "openai/gpt-oss-20b",
                "max_tokens": 8192,
                "cost_class": "paid_direct",
            },
        },
    },
    "cerebras": {
        "label": "Cerebras",
        "api_key_env": "CEREBRAS_API_KEY",
        "models": {
            "direct-cerebras-llama3.1-8b": {
                "url": "https://api.cerebras.ai/v1/chat/completions",
                "upstream_model": "llama3.1-8b",
                "max_tokens": 8192,
                "cost_class": "entitled_direct_limited",
            },
            "direct-cerebras-qwen-3-235b-a22b-instruct-2507": {
                "url": "https://api.cerebras.ai/v1/chat/completions",
                "upstream_model": "qwen-3-235b-a22b-instruct-2507",
                "max_tokens": 8192,
                "cost_class": "entitled_direct_limited",
            },
            "direct-cerebras-gpt-oss-120b": {
                "url": "https://api.cerebras.ai/v1/chat/completions",
                "upstream_model": "gpt-oss-120b",
                "max_tokens": 8192,
                "cost_class": "paid_direct",
            },
        },
    },
    "mistral": {
        "label": "Mistral",
        "api_key_env": "MISTRAL_API_KEY",
        "models": {
            "direct-mistral-small-latest": {
                "url": "https://api.mistral.ai/v1/chat/completions",
                "upstream_model": "mistral-small-latest",
                "max_tokens": 8192,
                "cost_class": "paid_direct",
            },
        },
    },
    "zai": {
        "label": "Z.AI",
        "api_key_env": "AI_API_KEY",
        "models": {
            "glm-4.7": {
                "url": "https://api.z.ai/api/coding/paas/v4/chat/completions",
                "upstream_model": "glm-4.7",
                "max_tokens": 8192,
                "cost_class": "paid_or_package",
            },
            "glm-4.7-flash": {
                "url": "https://api.z.ai/api/paas/v4/chat/completions",
                "upstream_model": "glm-4.7-flash",
                "max_tokens": 8192,
                "cost_class": "free_limited",
            },
        },
    },
    "openrouter": {
        "label": "OpenRouter",
        "api_key_env": "OPENROUTER_API_KEY",
        "headers": {
            "HTTP-Referer": "http://localhost",
            "X-Title": "Wild Boar External Agent Lab",
        },
        "models": {
            "or-qwen3-coder": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "qwen/qwen3-coder:free",
                "max_tokens": 8192,
                "cost_class": "free_limited",
            },
            "or-qwen3-next": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "qwen/qwen3-next-80b-a3b-instruct:free",
                "max_tokens": 8192,
                "cost_class": "free_limited",
            },
            "or-gpt-oss-20b": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "openai/gpt-oss-20b:free",
                "max_tokens": 8192,
                "cost_class": "free_limited",
            },
            "or-gpt-oss-120b": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "openai/gpt-oss-120b:free",
                "max_tokens": 8192,
                "cost_class": "free_limited",
            },
            "or-kimi-k2": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "moonshotai/kimi-k2",
                "max_tokens": 8192,
                "cost_class": "paid",
            },
            "or-deepseek-v3": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "upstream_model": "deepseek/deepseek-chat",
                "max_tokens": 8192,
                "cost_class": "paid",
            },
        },
    },
}

MODEL_ALIASES = {
    "gpt-3.5-turbo": "glm-4.7-flash",
    "gpt-4": "glm-4.7",
    "gpt-4-turbo": "glm-4.7",
    "gpt-4o": "glm-4.7",
    "gpt-4o-mini": "glm-4.7-flash",
    "gpt-5.2": "glm-4.7-flash",
    "gpt-5.3-codex": "glm-4.7",
    "gpt-5.3-codex-spark": "glm-4.7-flash",
    "gpt-5.4": "glm-4.7",
    "gpt-5.4-mini": "glm-4.7-flash",
    "gpt-5.5": "glm-4.7",
    "codex-auto-review": "glm-4.7",
    "claude-3-sonnet": "glm-4.7",
    "claude-3-haiku": "glm-4.7-flash",
    "qwen3-coder": "or-qwen3-coder",
    "qwen3-next": "or-qwen3-next",
    "gpt-oss": "or-gpt-oss-20b",
    "gpt-oss-20b": "or-gpt-oss-20b",
    "gpt-oss-120b": "or-gpt-oss-120b",
    "kimi-k2": "or-kimi-k2",
    "deepseek": "or-deepseek-v3",
    "gemini-2.5-flash-direct": "direct-gemini-2.5-flash",
    "groq-gpt-oss-20b-direct": "direct-groq-openai-gpt-oss-20b",
    "cerebras-llama3.1-8b-direct": "direct-cerebras-llama3.1-8b",
    "cerebras-qwen-3-235b-a22b-instruct-2507-direct": "direct-cerebras-qwen-3-235b-a22b-instruct-2507",
    "cerebras-gpt-oss-120b-direct": "direct-cerebras-gpt-oss-120b",
    "mistral-small-latest-direct": "direct-mistral-small-latest",
}

DEFAULT_MODEL = "glm-4.7-flash"
TIMEOUT = 120
API_KEYS = {}
CLIENT_BEARER_TOKEN = None
ALLOW_PAID_ROUTES = False
DEFAULT_PORT = 5000
RESERVED_PORTS = {8318, 8320}
MAX_RETRIES = 3
RETRYABLE_429_MARKERS = (
    "temporarily overloaded",
    "try again later",
    "rate limit",
    "too many requests",
)
FORCED_RESPONSE_ERROR_MAP = {
    "upstream_rate_limited": {
        "status": 429,
        "message": "Forced test condition: upstream rate limit reached.",
        "error_class": "upstream_rate_limited",
    },
    "upstream_overloaded": {
        "status": 429,
        "message": "Forced test condition: upstream temporarily overloaded. Try again later.",
        "error_class": "upstream_overloaded",
    },
    "upstream_timeout": {
        "status": 504,
        "message": "Forced test condition: upstream request timed out.",
        "error_class": "upstream_timeout",
    },
    "invalid_upstream_response": {
        "status": 502,
        "message": "Forced test condition: upstream returned invalid JSON.",
        "error_class": "invalid_upstream_response",
    },
}


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def load_env(env_path=".env") -> dict:
    env = {}
    path = Path(env_path)
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def build_model_registry():
    registry = {}
    for provider, provider_cfg in PROVIDERS.items():
        for model_name, model_cfg in provider_cfg.get("models", {}).items():
            registry[model_name] = {
                "provider": provider,
                "provider_label": provider_cfg.get("label", provider),
                **model_cfg,
            }
    return registry


MODEL_REGISTRY = build_model_registry()


def resolve_model(name):
    if not name:
        return DEFAULT_MODEL
    if name in MODEL_REGISTRY:
        return name
    if name in MODEL_ALIASES:
        return MODEL_ALIASES[name]
    raise RuntimeError(
        json.dumps(
            {
                "status": 404,
                "message": f"Unknown or unsupported model id: {name}",
                "error_class": "upstream_model_unavailable",
            }
        )
    )


def get_model_config(name):
    model = resolve_model(name)
    cfg = MODEL_REGISTRY[model]
    return model, cfg


def is_paid_route(cfg):
    return cfg.get("cost_class") in {"paid", "paid_direct", "paid_or_package"}


def require_route_allowed(model, cfg):
    if is_paid_route(cfg) and not ALLOW_PAID_ROUTES:
        raise RuntimeError(
            json.dumps(
                {
                    "status": 402,
                    "message": (
                        f"Route {model} -> {cfg.get('upstream_model', model)} is not allowed by default cost policy. "
                        "Run with --allow-paid-routes only if you intentionally want to test it."
                    ),
                    "error_class": "paid_route_blocked",
                }
            )
        )


def get_provider_api_key(provider):
    provider_cfg = PROVIDERS[provider]
    env_name = provider_cfg["api_key_env"]
    api_key = API_KEYS.get(provider)
    if not api_key:
        api_key = os.environ.get(env_name)
    return api_key


def require_client_auth(headers):
    auth = headers.get("Authorization", "")
    expected = f"Bearer {CLIENT_BEARER_TOKEN}"
    if not CLIENT_BEARER_TOKEN or auth == expected:
        return
    raise RuntimeError(
        json.dumps(
            {
                "status": 401,
                "message": "Missing or invalid lab client bearer token.",
                "error_class": "local_client_auth_failed",
            }
        )
    )


def build_public_models():
    data = []
    now = 1700000000
    for model_name, model_cfg in MODEL_REGISTRY.items():
        data.append(
            {
                "id": model_name,
                "object": "model",
                "created": now,
                "owned_by": model_cfg["provider_label"],
                "provider": model_cfg["provider"],
                "effective_model": model_cfg.get("upstream_model", model_name),
                "cost_class": model_cfg.get("cost_class", "unknown"),
            }
        )
    for alias_name, effective_model in sorted(MODEL_ALIASES.items()):
        model_cfg = MODEL_REGISTRY[effective_model]
        data.append(
            {
                "id": alias_name,
                "object": "model",
                "created": now,
                "owned_by": f"{model_cfg['provider_label']} (alias)",
                "effective_model": effective_model,
                "provider": model_cfg["provider"],
                "upstream_model": model_cfg.get("upstream_model", effective_model),
                "cost_class": model_cfg.get("cost_class", "unknown"),
            }
        )
    return data


PUBLIC_MODELS = build_public_models()


def make_chat_completion_id():
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return f"chatcmpl-{''.join(random.choice(chars) for _ in range(29))}"


def make_response_id():
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return f"resp_{''.join(random.choice(chars) for _ in range(24))}"


def make_message_id():
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return f"msg_{''.join(random.choice(chars) for _ in range(24))}"


def stringify_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"text", "input_text", "output_text"}:
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif item_type == "message":
                nested = item.get("content")
                nested_text = stringify_content(nested)
                if nested_text:
                    parts.append(nested_text)
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        item_type = value.get("type")
        if item_type in {"text", "input_text", "output_text"}:
            text = value.get("text")
            return text if isinstance(text, str) else ""
        if item_type == "message":
            return stringify_content(value.get("content"))
    return ""


def responses_input_to_messages(body):
    messages = []

    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions.strip()})

    input_items = body.get("input")
    if isinstance(input_items, str):
        text = input_items.strip()
        if text:
            messages.append({"role": "user", "content": text})
        return messages

    if not isinstance(input_items, list):
        return messages

    for item in input_items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                messages.append({"role": "user", "content": text})
            continue

        if not isinstance(item, dict):
            continue

        role = item.get("role", "user")
        item_type = item.get("type")
        if item_type == "message":
            content = stringify_content(item.get("content"))
            if content:
                messages.append({"role": role, "content": content})
            continue

        content = stringify_content(item)
        if content:
            messages.append({"role": role, "content": content})

    return messages


def extract_assistant_text(result):
    choices = result.get("choices", [])
    content = ""
    if choices:
        msg = choices[0].get("message", {})
        content = msg.get("content", "") or msg.get("reasoning_content", "")
    return content


def classify_upstream_error(status, message):
    msg = (message or "").lower()
    if status == 403 and ("error code: 1010" in msg or "cloudflare" in msg):
        return "upstream_edge_blocked"
    if status in (401, 403):
        return "upstream_auth_failed"
    if status == 402 or "insufficient balance" in msg or "no resource package" in msg:
        return "upstream_insufficient_balance"
    if status == 404 or "model" in msg and "not" in msg:
        return "upstream_model_unavailable"
    if status == 429:
        if "temporarily overloaded" in msg or "try again later" in msg:
            return "upstream_overloaded"
        return "upstream_rate_limited"
    if "timeout" in msg or "timed out" in msg:
        return "upstream_timeout"
    return "upstream_error"


def forced_response_error_from_metadata(metadata):
    if not isinstance(metadata, dict):
        return None
    marker = metadata.get("lab_force_error_class") or metadata.get("force_error_class")
    if not isinstance(marker, str):
        return None
    return FORCED_RESPONSE_ERROR_MAP.get(marker.strip())


def build_responses_payload(body):
    requested = body.get("model", DEFAULT_MODEL)
    model, cfg = get_model_config(requested)
    require_route_allowed(model, cfg)
    upstream_model = cfg.get("upstream_model", model)
    payload = {
        "requested_model": requested,
        "routed_model": model,
        "effective_model": upstream_model,
        "provider": cfg["provider"],
        "upstream_url": cfg["url"],
        "stream": bool(body.get("stream", False)),
        "metadata": body.get("metadata") or {},
        "chat_payload": {
            "model": upstream_model,
            "messages": responses_input_to_messages(body),
            "temperature": body.get("temperature", 0.7),
            "max_tokens": min(body.get("max_output_tokens", body.get("max_tokens", 4096)), cfg["max_tokens"]),
            "stream": bool(body.get("stream", False)),
        },
    }
    top_p = body.get("top_p")
    if top_p is not None:
        payload["chat_payload"]["top_p"] = top_p
    return payload


def build_responses_api_result(body, requested_model, effective_model, provider, cost_class, upstream_result, elapsed):
    content = extract_assistant_text(upstream_result)
    usage = upstream_result.get("usage", {})
    now = int(time.time())
    return {
        "id": make_response_id(),
        "object": "response",
        "created_at": now,
        "status": "completed",
        "model": requested_model,
        "lab_mode": True,
        "requested_model": requested_model,
        "requested_model_available": True,
        "fallback_used": False,
        "fallback_chain": [requested_model],
        "effective_model": effective_model,
        "provider": provider,
        "cost_class": cost_class,
        "latency_ms": int(elapsed * 1000),
        "network_dependent_evidence": True,
        "output": [
            {
                "id": make_message_id(),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": content,
                        "annotations": [],
                    }
                ],
            }
        ],
        "output_text": content,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "metadata": body.get("metadata") or {},
    }


def send_upstream_chat(payload):
    routed_model = payload["routed_model"]
    cfg = MODEL_REGISTRY[routed_model]
    provider = cfg["provider"]
    api_key = get_provider_api_key(provider)
    if not api_key:
        raise RuntimeError(
            json.dumps(
                {
                    "status": 401,
                    "message": f"Missing API key for provider {provider}: {PROVIDERS[provider]['api_key_env']}",
                    "error_class": "upstream_auth_missing",
                }
            )
        )
    data = json.dumps(payload["chat_payload"]).encode("utf-8")
    start = time.time()
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        req = Request(cfg["url"], data=data, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "curl/8.7.1")
        for header, value in PROVIDERS[provider].get("headers", {}).items():
            req.add_header(header, value)
        try:
            resp = urlopen(req, timeout=TIMEOUT)
            return resp, time.time() - start
        except HTTPError as error:
            err = error.read().decode("utf-8", errors="replace") if error.fp else ""
            try:
                msg = json.loads(err).get("error", {}).get("message", err[:500])
            except Exception:
                msg = err[:500]

            if error.code == 429:
                lower_msg = msg.lower()
                if any(marker in lower_msg for marker in RETRYABLE_429_MARKERS) and attempt < MAX_RETRIES:
                    sleep_for = attempt
                    print(f"  [retry] upstream 429 for {routed_model}, retry in {sleep_for}s")
                    time.sleep(sleep_for)
                    last_error = {"status": error.code, "message": msg}
                    continue

            raise RuntimeError(json.dumps({"status": error.code, "message": msg, "error_class": classify_upstream_error(error.code, msg)}))
        except (URLError, TimeoutError, ConnectionResetError) as error:
            last_error = {"status": 502, "message": f"Connection error: {error}", "error_class": "upstream_timeout"}
            if attempt < MAX_RETRIES:
                sleep_for = attempt
                print(f"  [retry] upstream connection issue for {routed_model}, retry in {sleep_for}s")
                time.sleep(sleep_for)
                continue
            raise RuntimeError(json.dumps(last_error))

    raise RuntimeError(json.dumps(last_error or {"status": 502, "message": "Unknown upstream error"}))


# ─── Обработчик ───────────────────────────────────────────────────────────────

class ProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        ts = time.strftime("%H:%M:%S")
        msg = format % args if args else format
        print(f"  [{ts}] {msg}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/v1/models", "/models"):
            self.send_json(200, {"object": "list", "data": PUBLIC_MODELS})
        elif self.path in ("/health", "/v1/health"):
            self.send_json(
                200,
                {
                    "lab_mode": True,
                    "status": "ok",
                    "providers": list(PROVIDERS.keys()),
                    "models": list(MODEL_REGISTRY.keys()),
                    "aliases": MODEL_ALIASES,
                },
            )
        else:
            self.send_error_json(404, "Not found")

    def do_POST(self):
        try:
            require_client_auth(self.headers)
        except RuntimeError as error:
            info = json.loads(str(error))
            return self.send_error_json(info["status"], info["message"], info.get("error_class"))
        if self.path in ("/v1/chat/completions", "/chat/completions"):
            self.handle_chat()
        elif self.path in ("/v1/responses", "/responses"):
            self.handle_responses()
        else:
            self.send_error_json(404, "Not found")

    def handle_chat(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception as e:
            return self.send_error_json(400, f"Invalid body: {e}")

        requested = body.get("model", DEFAULT_MODEL)
        try:
            model, cfg = get_model_config(requested)
            require_route_allowed(model, cfg)
        except RuntimeError as error:
            info = json.loads(str(error))
            return self.send_error_json(info["status"], info["message"], info.get("error_class"))
        upstream_model = cfg.get("upstream_model", model)
        stream = body.get("stream", False)

        if requested != upstream_model:
            self.log_message(f"📎 {requested} → {cfg['provider']}/{upstream_model}")

        payload = {
            "model": upstream_model,
            "messages": body.get("messages", []),
            "temperature": body.get("temperature", 0.7),
            "max_tokens": min(body.get("max_tokens", 4096), cfg["max_tokens"]),
            "stream": stream,
        }
        for k in ("top_p", "stop"):
            if k in body:
                payload[k] = body[k]

        try:
            resp, elapsed = send_upstream_chat(
                {
                    "requested_model": requested,
                    "routed_model": model,
                    "effective_model": upstream_model,
                    "provider": cfg["provider"],
                    "chat_payload": payload,
                }
            )
        except RuntimeError as error:
            info = json.loads(str(error))
            return self.send_error_json(info["status"], info["message"], info.get("error_class"))

        if stream:
            self.do_stream(resp, upstream_model)
        else:
            self.do_normal(resp, upstream_model, elapsed)

    def handle_responses(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception as error:
            return self.send_error_json(400, f"Invalid body: {error}")

        try:
            payload = build_responses_payload(body)
        except RuntimeError as error:
            info = json.loads(str(error))
            return self.send_error_json(info["status"], info["message"], info.get("error_class"))
        requested = payload["requested_model"]
        effective = payload["effective_model"]
        if requested != effective:
            self.log_message(f"📎 {requested} → {payload['provider']}/{effective}")
        forced_error = forced_response_error_from_metadata(payload.get("metadata"))
        if forced_error:
            return self.send_error_json(
                forced_error["status"],
                forced_error["message"],
                forced_error["error_class"],
            )

        if payload["stream"]:
            return self.send_error_json(
                400,
                "Responses streaming is not implemented in this adapter yet.",
            )

        try:
            resp, elapsed = send_upstream_chat(payload)
        except RuntimeError as error:
            info = json.loads(str(error))
            return self.send_error_json(info["status"], info["message"], info.get("error_class"))

        try:
            result = json.loads(resp.read().decode("utf-8"))
        except Exception as error:
            return self.send_error_json(
                502,
                f"Invalid upstream response: {error}",
                "invalid_upstream_response",
            )

        response_obj = build_responses_api_result(
            body,
            requested,
            effective,
            payload["provider"],
            MODEL_REGISTRY[payload["routed_model"]].get("cost_class", "unknown"),
            result,
            elapsed,
        )
        usage = response_obj.get("usage", {})
        self.log_message(
            f"✅ responses {payload['provider']}/{effective} → {usage.get('total_tokens', '?')} tok, {elapsed:.1f}с"
        )
        self.send_json(200, response_obj)

    def do_normal(self, resp, model, elapsed):
        try:
            result = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return self.send_error_json(502, f"Invalid response: {e}")

        choices = result.get("choices", [])
        content = ""
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "") or msg.get("reasoning_content", "")

        usage = result.get("usage", {})
        openai_resp = {
            "id": make_chat_completion_id(),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": choices[0].get("finish_reason", "stop") if choices else "stop"}],
            "usage": {"prompt_tokens": usage.get("prompt_tokens", 0),
                      "completion_tokens": usage.get("completion_tokens", 0),
                      "total_tokens": usage.get("total_tokens", 0)},
        }
        self.log_message(f"✅ {model} → {usage.get('total_tokens', '?')} tok, {elapsed:.1f}с")
        self.send_json(200, openai_resp)

    def do_stream(self, resp, model):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_cors_headers()
        self.end_headers()

        chat_id = make_chat_completion_id()
        total = ""
        try:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                delta_content = ""
                finish = None
                if choices:
                    d = choices[0].get("delta", {})
                    delta_content = d.get("content", "") or d.get("reasoning_content", "")
                    finish = choices[0].get("finish_reason")
                    total += delta_content
                oai = {"id": chat_id, "object": "chat.completion.chunk", "created": int(time.time()),
                       "model": model, "choices": [{"index": 0,
                       "delta": {"content": delta_content} if delta_content else {}, "finish_reason": finish}]}
                self.wfile.write(f"data: {json.dumps(oai, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except Exception as e:
            self.log_message(f"⚠️ Stream error: {e}")
        self.log_message(f"✅ stream {model} → {len(total)} chars")

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected (often due to local request-timeout). This is not an adapter failure.
            return

    def send_error_json(self, status, message, error_class=None):
        self.send_json(
            status,
            {
                "error": {
                    "message": message,
                    "type": "api_error",
                    "code": status,
                    "error_class": error_class or classify_upstream_error(status, message),
                }
            },
        )


class ThreadedHTTPServer(HTTPServer):
    def process_request(self, request, client_address):
        t = threading.Thread(target=self._handle, args=(request, client_address), daemon=True)
        t.start()

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main():
    global API_KEYS, ALLOW_PAID_ROUTES, CLIENT_BEARER_TOKEN
    parser = argparse.ArgumentParser(description="OpenAI-compatible external model adapter")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT)
    parser.add_argument("--key", "-k", help="Disabled for safety. Use .env or interactive prompt flow.")
    parser.add_argument("--openrouter-key", help="Disabled for safety. Use .env or interactive prompt flow.")
    parser.add_argument("--allow-paid-routes", action="store_true")
    args = parser.parse_args()

    port = args.port
    if port in RESERVED_PORTS:
        print(f"Refusing to start on reserved Codex Custom port {port}.")
        print("Use another lab port. Ports 8318 and 8320 are reserved for the live runtime.")
        sys.exit(2)

    if args.key or args.openrouter_key:
        print("Refusing plaintext key arguments. Use .env or the run_lab.py prompt flow.")
        sys.exit(2)

    ALLOW_PAID_ROUTES = args.allow_paid_routes
    env = load_env(Path(__file__).parent / ".env")
    API_KEYS = {}
    CLIENT_BEARER_TOKEN = env.get("LAB_CLIENT_TOKEN") or os.environ.get("LAB_CLIENT_TOKEN") or "lab-local"
    for provider, provider_cfg in PROVIDERS.items():
        env_name = provider_cfg["api_key_env"]
        api_key = env.get(env_name) or os.environ.get(env_name)
        if api_key:
            API_KEYS[provider] = api_key

    key_status = ", ".join(
        f"{provider}:{'set' if provider in API_KEYS else 'missing'}" for provider in PROVIDERS
    )

    print(f"""
╔══════════════════════════════════════════════════════╗
║    🚀 External Model Adapter Lab                    ║
╠══════════════════════════════════════════════════════╣
║  🌐 http://localhost:{port}/v1                          ║
║  🧪 LAB MODE ONLY                                   ║
║  🔑 Keys: {key_status:<40}║
║                                                      ║
║  📦 Providers: {', '.join(PROVIDERS.keys()):<36}║
║  💸 Paid routes: {'enabled' if ALLOW_PAID_ROUTES else 'blocked':<32}║
║                                                      ║
║  ⚙️  VS Code / Cursor:                               ║
║    Base URL:  http://localhost:{port}/v1                ║
║    API Key:   anything                               ║
║    Model:     glm-4.7-flash                          ║
║                                                      ║
║  ⏹️  Ctrl+C — остановить                              ║
╚══════════════════════════════════════════════════════╝
""")

    server = ThreadedHTTPServer(("127.0.0.1", port), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
        server.server_close()


if __name__ == "__main__":
    main()

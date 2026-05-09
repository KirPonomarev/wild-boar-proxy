#!/usr/bin/env python3
"""
One-command launcher for the external adapter lab.

Flow:
1. get API key from --key, .env, env var, or prompt
2. start proxy_server.py on a local port
3. wait for /health
4. run a small /v1/responses smoke test
5. keep the adapter running until Ctrl+C
"""

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LAB_DIR = Path(__file__).resolve().parent
ENV_PATH = LAB_DIR / ".env"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_PORT = 5000
HEALTH_TIMEOUT_SECONDS = 15
RESERVED_PORTS = {8318, 8320}
OPENROUTER_MODEL_PREFIXES = (
    "qwen3-",
    "gpt-oss",
    "kimi-",
    "deepseek",
    "or-",
)
FREE_FALLBACK_MODELS = (
    "qwen3-coder",
    "qwen3-next",
    "gpt-oss-20b",
    "gpt-oss-120b",
)
DIRECT_PROVIDER_MODEL_KEYS = {
    "direct-gemini-2.5-flash": "GEMINI_API_KEY",
    "gemini-2.5-flash-direct": "GEMINI_API_KEY",
    "direct-groq-openai-gpt-oss-20b": "GROQ_API_KEY",
    "groq-gpt-oss-20b-direct": "GROQ_API_KEY",
    "direct-cerebras-llama3.1-8b": "CEREBRAS_API_KEY",
    "cerebras-llama3.1-8b-direct": "CEREBRAS_API_KEY",
    "direct-cerebras-qwen-3-235b-a22b-instruct-2507": "CEREBRAS_API_KEY",
    "cerebras-qwen-3-235b-a22b-instruct-2507-direct": "CEREBRAS_API_KEY",
    "direct-cerebras-gpt-oss-120b": "CEREBRAS_API_KEY",
    "cerebras-gpt-oss-120b-direct": "CEREBRAS_API_KEY",
    "direct-mistral-small-latest": "MISTRAL_API_KEY",
    "mistral-small-latest-direct": "MISTRAL_API_KEY",
}
CLIENT_TOKEN_KEY = "LAB_CLIENT_TOKEN"


def load_env(env_path):
    env = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def save_key_to_env(key_name, api_key, env_path):
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key_name}="):
                lines.append(f"{key_name}={api_key}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key_name}={api_key}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass


def ensure_env_permissions(env_path):
    if env_path.exists():
        os.chmod(env_path, 0o600)


def required_key_name(model):
    lower_model = model.lower()
    if lower_model in DIRECT_PROVIDER_MODEL_KEYS:
        return DIRECT_PROVIDER_MODEL_KEYS[lower_model]
    if lower_model.startswith(OPENROUTER_MODEL_PREFIXES):
        return "OPENROUTER_API_KEY"
    return "AI_API_KEY"


def ensure_client_token():
    env = load_env(ENV_PATH)
    token = env.get(CLIENT_TOKEN_KEY) or os.environ.get(CLIENT_TOKEN_KEY)
    if token:
        return token
    token = f"lab-{secrets.token_urlsafe(16)}"
    save_key_to_env(CLIENT_TOKEN_KEY, token, ENV_PATH)
    return token


def get_or_prompt_key(args):
    key_name = required_key_name(args.model)
    if args.key:
        print("Ошибка: plaintext key arguments are disabled. Use the interactive prompt or .env.")
        raise SystemExit(2)
    env = load_env(ENV_PATH)
    api_key = env.get(key_name) or os.environ.get(key_name)
    if api_key:
        return key_name
    label = "OpenRouter" if key_name == "OPENROUTER_API_KEY" else "Z.AI / GLM"
    print(f"Вставь API key {label}:")
    api_key = input("> ").strip()
    if not api_key:
        print("Ключ пустой.")
        sys.exit(1)
    save_key_to_env(key_name, api_key, ENV_PATH)
    print(f"{key_name} сохранён в .env")
    return key_name


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def pick_port(requested_port):
    if requested_port in RESERVED_PORTS:
        raise RuntimeError("Ports 8318 and 8320 are reserved for live Codex Custom runtime.")
    if port_is_free(requested_port):
        return requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_health(base_url, timeout_seconds):
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url}/health"
    last_error = None
    while time.time() < deadline:
        try:
            with urlopen(health_url, timeout=2) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("status") == "ok":
                return payload
        except Exception as error:
            last_error = error
        time.sleep(0.3)
    raise RuntimeError(f"Adapter did not become healthy in time: {last_error}")


def run_smoke(base_url, requested_model):
    payload = {
        "model": requested_model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Скажи OK одним словом."}],
            }
        ],
    }
    req = Request(
        f"{base_url}/responses",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ensure_client_token()}",
        },
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        try:
            payload = json.loads(body)
            error_class = payload.get("error", {}).get("error_class")
            message = payload.get("error", {}).get("message", body[:500])
            if error_class:
                raise RuntimeError(f"HTTP {error.code} [{error_class}]: {message}")
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"HTTP {error.code}: {body[:500]}")
    except URLError as error:
        raise RuntimeError(f"Connection error: {error}")


def prompt_fingerprint(prompt_text):
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]


def should_try_fallback(error):
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "upstream_rate_limited",
            "upstream_overloaded",
            "upstream_timeout",
            "provider returned error",
            "429",
            "timed out",
        )
    )


def smoke_candidates(requested_model):
    candidates = [requested_model]
    if required_key_name(requested_model) == "OPENROUTER_API_KEY":
        for model in FREE_FALLBACK_MODELS:
            if model not in candidates:
                candidates.append(model)
    return candidates


def run_smoke_with_fallback(base_url, requested_model):
    errors = []
    attempts = []
    for candidate in smoke_candidates(requested_model):
        if candidate != requested_model:
            print(f"Пробую fallback model: {candidate}")
        try:
            result = run_smoke(base_url, candidate)
            attempts.append(candidate)
            result["requested_model"] = requested_model
            result["requested_model_available"] = candidate == requested_model
            result["fallback_used"] = candidate != requested_model
            result["fallback_chain"] = attempts[:]
            return candidate, result
        except RuntimeError as error:
            errors.append((candidate, str(error)))
            attempts.append(candidate)
            print(f"Smoke failed for {candidate}: {error}")
            if not should_try_fallback(error):
                break
    summary = "; ".join(f"{model}: {error}" for model, error in errors)
    raise RuntimeError(f"All smoke candidates failed: {summary}")


def start_proxy(port, allow_paid_routes=False):
    cmd = [sys.executable, str(LAB_DIR / "proxy_server.py"), "--port", str(port)]
    if allow_paid_routes:
        cmd.append("--allow-paid-routes")
    return subprocess.Popen(
        cmd,
        cwd=str(LAB_DIR),
    )


def shutdown_proxy(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-command launcher for the external adapter lab")
    parser.add_argument("--key", "-k", help="Disabled for safety. Use the interactive prompt or .env.")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-paid-routes", action="store_true")
    args = parser.parse_args(argv)

    try:
        port = pick_port(args.port)
    except RuntimeError as error:
        print(f"Ошибка: {error}")
        raise SystemExit(2)
    key_name = get_or_prompt_key(args)
    ensure_env_permissions(ENV_PATH)
    ensure_client_token()
    base_url = f"http://127.0.0.1:{port}/v1"

    print("LAB MODE ONLY. Live Codex Custom ports 8318/8320 are blocked.")
    print(f"Использую ключ: {key_name}")
    print(f"Запускаю adapter на {base_url}")
    proxy_process = start_proxy(port, args.allow_paid_routes)

    try:
        health = wait_for_health(base_url, HEALTH_TIMEOUT_SECONDS)
        print("Adapter поднялся.")
        print(f"Провайдеры: {', '.join(health.get('providers', []))}")
        print(f"Моделей: {len(health.get('models', []))}, alias: {len(health.get('aliases', {}))}")

        actual_model, result = run_smoke_with_fallback(base_url, args.model)
        routed_model = result.get("effective_model") or result.get("model")
        provider = result.get("provider", "?")
        latency_ms = result.get("latency_ms")
        fallback_used = result.get("fallback_used", False)
        fallback_chain = result.get("fallback_chain", [actual_model])
        output_text = (result.get("output_text") or "").strip()
        print("Smoke-test прошёл.")
        print(f"Запрошено: {args.model}")
        print(f"Проверено как: {actual_model}")
        print(f"Provider: {provider}")
        print(f"Роутинг: {routed_model}")
        print(f"Fallback used: {'yes' if fallback_used else 'no'}")
        print(f"Fallback chain: {' -> '.join(fallback_chain)}")
        if latency_ms is not None:
            print(f"Latency: {latency_ms} ms")
        print(f"Ответ: {output_text}")

        if args.check_only:
            print("Проверка завершена. Adapter будет остановлен.")
            return

        print("")
        print("Adapter оставлен запущенным. Остановить: Ctrl+C")
        proxy_process.wait()
    except KeyboardInterrupt:
        print("")
        print("Остановка adapter.")
    except Exception as error:
        print(f"Ошибка: {error}")
        if "Insufficient balance or no resource package" in str(error):
            print("Подсказка: текущий smoke route ушёл в платную модель.")
            print("Для бесплатной проверки запусти:")
            print("python3 run_lab.py --model gpt-5.4-mini")
        if "paid_route_blocked" in str(error) or "not marked free" in str(error):
            print("Этот route не помечен как бесплатный. Для бесплатного теста используй:")
            print("python3 run_lab.py --model qwen3-coder --check-only")
            print("python3 run_lab.py --model gpt-oss-20b --check-only")
        raise SystemExit(1)
    finally:
        shutdown_proxy(proxy_process)


if __name__ == "__main__":
    main()

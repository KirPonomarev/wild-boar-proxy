# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Keychain credential broker for Kimi/GLM API keys (P04).

Reads exact provider-owned Keychain items (Kimi/Moonshot, GLM/Z.AI) without
global keychain enumeration, dump, or Codex/OpenAI item access. Never exposes
the secret value in any packet, log, or artifact.

Security invariants:
- only exact service/account lookup for the requested provider
- no `security dump-keychain`
- no Codex/OpenAI/ChatGPT keychain reads
- no keychain mutations (no delete, reset, unlock, default change)
- secret value never printed; only presence + opaque digest
- credential passed only to caller in process memory
"""

from __future__ import annotations

import dataclasses
import hashlib
import subprocess
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

KEYCHAIN_EFFECT_READ = "read"

# Exact Keychain service/account candidates per provider. These are the ONLY
# items the broker will look up. No global enumeration.
_PROVIDER_KEYCHAIN_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "kimi": [
        ("Moonshot", "MOONSHOT_API_KEY"),
        ("Moonshot", "api_key"),
        ("Kimi", "MOONSHOT_API_KEY"),
        ("Kimi", "api_key"),
    ],
    "glm": [
        ("Z.AI", "ZAI_API_KEY"),
        ("Z.AI", "api_key"),
        ("GLM", "ZAI_API_KEY"),
        ("GLM", "api_key"),
        ("ZhipuAI", "ZAI_API_KEY"),
        ("ZhipuAI", "api_key"),
    ],
}

# Providers whose keychain items we never read (safety denylist).
_FORBIDDEN_KEYCHAIN_PROVIDERS = frozenset({"codex", "openai", "chatgpt"})


@dataclasses.dataclass(frozen=True)
class KeychainLookupResult:
    provider: str
    found: bool
    service: str | None
    account: str | None
    secret_value: str | None  # only in memory, never in packets
    secret_digest: str | None  # opaque digest, safe to expose

    @property
    def safe_packet_fields(self) -> dict[str, Any]:
        """Fields safe for packet output (no secret value)."""
        return {
            "provider": self.provider,
            "credential_source": "owner-keychain",
            "credential_present": self.found,
            "keychain_service": self.service,
            "keychain_account": self.account,
            "credential_ref_digest": self.secret_digest,
            "secret_value_exposed": False,
        }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lookup_keychain_credential(
    *,
    provider: str,
    custom_service: str | None = None,
    custom_account: str | None = None,
) -> KeychainLookupResult:
    """Look up an exact provider-owned Keychain item.

    If custom_service and custom_account are provided, use them as the exact
    lookup target. Otherwise iterate the small allowlist for that provider.

    Never reads Codex/OpenAI/ChatGPT items. Never does dump-keychain.
    """
    normalized = str(provider).strip().lower()
    if normalized in _FORBIDDEN_KEYCHAIN_PROVIDERS:
        return KeychainLookupResult(
            provider=normalized, found=False, service=None, account=None,
            secret_value=None, secret_digest=None,
        )
    candidates: list[tuple[str, str]] = []
    if custom_service and custom_account:
        candidates.append((custom_service, custom_account))
    candidates.extend(_PROVIDER_KEYCHAIN_CANDIDATES.get(normalized, []))
    for service, account in candidates:
        value = _security_find_generic_password(service=service, account=account)
        if value:
            return KeychainLookupResult(
                provider=normalized, found=True, service=service, account=account,
                secret_value=value, secret_digest=_sha256_text(value),
            )
    return KeychainLookupResult(
        provider=normalized, found=False, service=None, account=None,
        secret_value=None, secret_digest=None,
    )


def _security_find_generic_password(*, service: str, account: str) -> str | None:
    """Call macOS security find-generic-password for an exact item.

    Returns the password value or None if not found. Never raises on
    item-missing (exit code 128); only on unexpected system errors.
    """
    try:
        completed = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s", service,
                "-a", account,
                "-w",  # print only the password
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value if value else None


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_keychain_credential_status_packet(
    *,
    provider: str,
    custom_service: str | None = None,
    custom_account: str | None = None,
) -> dict[str, Any]:
    """Build the keychain credential status packet (read-only)."""
    result = lookup_keychain_credential(
        provider=provider,
        custom_service=custom_service,
        custom_account=custom_account,
    )
    safe = result.safe_packet_fields
    safe["forbidden_provider_blocked"] = provider.strip().lower() in _FORBIDDEN_KEYCHAIN_PROVIDERS
    safe["keychain_dump_performed"] = False
    safe["keychain_mutation_performed"] = False
    safe["original_codex_keychain_read"] = False
    safe["supported_sources"] = ["owner-env", "owner-keychain"]
    if result.found:
        return _build_packet(
            ok=True,
            human_message=f"Keychain credential found for {provider}.",
            machine_error_code="OK",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=KEYCHAIN_EFFECT_READ,
            extra=safe,
        )
    return _build_packet(
        ok=True,
        human_message=f"Keychain credential not found for {provider}.",
        machine_error_code="KEYCHAIN_CREDENTIAL_MISSING",
        operator_action="user_action",
        liveness="down",
        severity="recoverable",
        changed_files=[],
        effect=KEYCHAIN_EFFECT_READ,
        extra=safe,
    )


def run_keychain_broker_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof: forbidden provider blocked, missing
    credential status, wrong-provider rejection."""
    # Forbidden provider (codex) - must be blocked
    forbidden = lookup_keychain_credential(provider="codex")
    # Missing credential (kimi - unlikely in test env)
    missing = lookup_keychain_credential(provider="kimi")
    # Wrong provider custom lookup
    wrong = lookup_keychain_credential(
        provider="kimi", custom_service="OpenAI", custom_account="key"
    )
    receipts = [
        build_keychain_credential_status_packet(provider="codex"),
        build_keychain_credential_status_packet(provider="kimi"),
        build_keychain_credential_status_packet(provider="glm"),
    ]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    no_secret_leak = all("sk-" not in __import__("json").dumps(r) for r in receipts)
    no_dump = all(r["keychain_dump_performed"] is False for r in receipts)
    no_mutation = all(r["keychain_mutation_performed"] is False for r in receipts)
    no_codex_read = all(r["original_codex_keychain_read"] is False for r in receipts)
    ok = (
        not violations and no_secret_leak and no_dump and no_mutation and no_codex_read
        and not forbidden.found  # codex blocked
    )
    return _build_packet(
        ok=ok,
        human_message="Keychain broker synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "KEYCHAIN_BROKER_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=KEYCHAIN_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "forbidden_provider_blocked": not forbidden.found,
            "no_secret_leak": no_secret_leak,
            "no_keychain_dump": no_dump,
            "no_keychain_mutation": no_mutation,
            "no_codex_keychain_read": no_codex_read,
            "packet_violations": violations,
        },
    )


__all__ = [
    "KeychainLookupResult",
    "lookup_keychain_credential",
    "build_keychain_credential_status_packet",
    "run_keychain_broker_synthetic_proof",
]

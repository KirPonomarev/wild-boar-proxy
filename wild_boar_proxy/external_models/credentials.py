"""Owner-owned external-models credential admission helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wild_boar_proxy.runtime import REPO_ROOT, RuntimeErrorInfo

from . import errors
from .paths import ExternalModelsPaths
from .state import ensure_secrets_permissions


@dataclass(frozen=True)
class CredentialProviderSpec:
    provider: str
    credential_ref: str
    owner_env_candidates: tuple[str, ...]
    provider_dashboard_url: str
    provider_family: str
    auth_type: str = "bearer"
    seed_source: str = "current_runtime"


def _owner_env_candidates(*names: str) -> tuple[str, ...]:
    return tuple(str(name).strip() for name in names if str(name).strip())


_PROVIDER_SPECS: dict[str, CredentialProviderSpec] = {
    "deepseek": CredentialProviderSpec(
        provider="deepseek",
        credential_ref="DEEPSEEK_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "DEEPSEEK_API_KEY",
            "WBP_DEEPSEEK_API_KEY",
            "WBP_PROVIDER_DEEPSEEK_API_KEY",
        ),
        provider_dashboard_url="https://platform.deepseek.com/api_keys",
        provider_family="direct_provider",
    ),
    "openrouter": CredentialProviderSpec(
        provider="openrouter",
        credential_ref="OPENROUTER_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "OPENROUTER_API_KEY",
            "WBP_OPENROUTER_API_KEY",
            "WBP_PROVIDER_OPENROUTER_API_KEY",
        ),
        provider_dashboard_url="https://openrouter.ai/settings/keys",
        provider_family="provider_router",
    ),
    "mistral": CredentialProviderSpec(
        provider="mistral",
        credential_ref="MISTRAL_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "MISTRAL_API_KEY",
            "WBP_MISTRAL_API_KEY",
            "WBP_PROVIDER_MISTRAL_API_KEY",
        ),
        provider_dashboard_url="https://docs.mistral.ai/admin/security-access/api-keys",
        provider_family="direct_provider",
        seed_source="historical_seed_plus_current_schema",
    ),
    "gemini": CredentialProviderSpec(
        provider="gemini",
        credential_ref="GEMINI_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "WBP_GEMINI_API_KEY",
            "WBP_PROVIDER_GEMINI_API_KEY",
        ),
        provider_dashboard_url="https://aistudio.google.com/app/apikey",
        provider_family="direct_provider",
        seed_source="historical_seed_plus_current_schema",
    ),
    "groq": CredentialProviderSpec(
        provider="groq",
        credential_ref="GROQ_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "GROQ_API_KEY",
            "WBP_GROQ_API_KEY",
            "WBP_PROVIDER_GROQ_API_KEY",
        ),
        provider_dashboard_url="https://console.groq.com/keys",
        provider_family="direct_provider",
        seed_source="historical_seed_plus_current_schema",
    ),
    "cerebras": CredentialProviderSpec(
        provider="cerebras",
        credential_ref="CEREBRAS_API_KEY",
        owner_env_candidates=_owner_env_candidates(
            "CEREBRAS_API_KEY",
            "WBP_CEREBRAS_API_KEY",
            "WBP_PROVIDER_CEREBRAS_API_KEY",
        ),
        provider_dashboard_url="https://inference-docs.cerebras.ai/api-reference/authentication",
        provider_family="direct_provider",
        seed_source="historical_seed_plus_current_schema",
    ),
}


def admit_owner_credential(
    paths: ExternalModelsPaths, *, provider: str, source: str
) -> tuple[dict[str, Any], list[str]]:
    normalized_source = str(source).strip()
    if normalized_source != "owner-env":
        raise RuntimeErrorInfo(
            "Unsupported credential source for external-models admission.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SOURCE_UNSUPPORTED,
            operator_action="user_action",
        )
    spec = _provider_spec(provider)
    _ensure_sandbox_admission_target(paths)
    secret_value = _resolve_owner_env_secret(spec)
    if not secret_value:
        raise RuntimeErrorInfo(
            f"Owner credential source is missing for provider: {spec.provider}",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING,
            operator_action="user_action",
        )
    ensure_secrets_permissions(paths.secrets_file)
    secrets_map = _parse_secrets_file(paths.secrets_file)
    secrets_map[spec.credential_ref] = secret_value
    _write_secrets_file(paths.secrets_file, secrets_map)
    return _credential_result(
        spec=spec,
        status="admitted",
        provider=spec.provider,
        source=normalized_source,
        credential_ref=spec.credential_ref,
        credential_present=True,
    ), [str(paths.secrets_file)]


def credential_status(paths: ExternalModelsPaths, *, provider: str) -> dict[str, Any]:
    spec = _provider_spec(provider)
    _ensure_sandbox_admission_target(paths)
    ensure_secrets_permissions(paths.secrets_file)
    secrets_map = _parse_secrets_file(paths.secrets_file)
    present = bool(secrets_map.get(spec.credential_ref, "").strip())
    return _credential_result(
        spec=spec,
        status="present" if present else "missing",
        provider=spec.provider,
        source="sandbox-managed",
        credential_ref=spec.credential_ref,
        credential_present=present,
    )


def missing_credential_result(*, provider: str, source: str) -> dict[str, Any]:
    spec = _provider_spec(provider)
    return _credential_result(
        spec=spec,
        status="missing",
        provider=spec.provider,
        source=source,
        credential_ref=spec.credential_ref,
        credential_present=False,
    )


def _credential_result(
    *,
    spec: CredentialProviderSpec,
    status: str,
    provider: str,
    source: str,
    credential_ref: str,
    credential_present: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "provider_family": spec.provider_family,
        "auth_type": spec.auth_type,
        "source": source,
        "seed_source": spec.seed_source,
        "credential_ref": credential_ref,
        "credential_present": credential_present,
        "schema_admitted": True,
        "supported_sources": ["owner-env"],
        "expected_refs": list(spec.owner_env_candidates),
        "provider_dashboard_url": spec.provider_dashboard_url,
        "secret_value_exposed": False,
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "classification_scope": "credential_admission_only",
        "provider_runtime_compatibility_claimed": False,
        "model_runtime_compatibility_claimed": False,
        "generic_route_transform_support_claimed": False,
        "generic_response_compatibility_claimed": False,
        "provider_family_compatibility_claimed": False,
        "scope": "sandbox",
    }


def provider_specs_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for provider in sorted(_PROVIDER_SPECS):
        spec = _PROVIDER_SPECS[provider]
        inventory.append(
            {
                "provider": spec.provider,
                "provider_family": spec.provider_family,
                "credential_ref": spec.credential_ref,
                "owner_env_candidates": list(spec.owner_env_candidates),
                "provider_dashboard_url": spec.provider_dashboard_url,
                "auth_type": spec.auth_type,
                "supported_sources": ["owner-env"],
                "schema_admitted": True,
                "seed_source": spec.seed_source,
                "classification_scope": "credential_admission_only",
                "provider_runtime_compatibility_claimed": False,
                "model_runtime_compatibility_claimed": False,
                "generic_route_transform_support_claimed": False,
                "generic_response_compatibility_claimed": False,
                "provider_family_compatibility_claimed": False,
            }
        )
    return inventory


def _provider_spec(provider: str) -> CredentialProviderSpec:
    normalized = str(provider).strip().lower()
    if normalized in _PROVIDER_SPECS:
        return _PROVIDER_SPECS[normalized]
    raise RuntimeErrorInfo(
        f"Unsupported external-models provider: {provider}",
        machine_error_code=errors.EXTERNAL_MODELS_PROVIDER_UNSUPPORTED,
        operator_action="user_action",
    )


def _resolve_owner_env_secret(spec: CredentialProviderSpec) -> str:
    for candidate in spec.owner_env_candidates:
        value = os.environ.get(candidate, "").strip()
        if value:
            return value
    return ""


def _parse_secrets_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_secrets_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={values[key]}" for key in sorted(values)]
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)
    os.chmod(path, 0o600)


def _ensure_sandbox_admission_target(paths: ExternalModelsPaths) -> None:
    raw_external_root = os.environ.get("WBP_EXTERNAL_MODELS_DIR", "").strip()
    if not raw_external_root:
        raise RuntimeErrorInfo(
            "Sandbox credential admission requires explicit WBP_EXTERNAL_MODELS_DIR.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        )
    if not Path(os.path.expanduser(raw_external_root)).is_absolute():
        raise RuntimeErrorInfo(
            "WBP_EXTERNAL_MODELS_DIR must be an absolute path for sandbox credential admission.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        )
    external_root = Path(os.path.expanduser(raw_external_root)).resolve()
    managed_raw = os.environ.get("WBP_MANAGED_DIR", "").strip()
    if not managed_raw:
        raise RuntimeErrorInfo(
            "Sandbox credential admission requires explicit WBP_MANAGED_DIR.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        )
    if not Path(os.path.expanduser(managed_raw)).is_absolute():
        raise RuntimeErrorInfo(
            "WBP_MANAGED_DIR must be an absolute path for sandbox credential admission.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        )
    managed_dir = Path(os.path.expanduser(managed_raw)).resolve()
    if external_root != paths.root_dir:
        raise RuntimeErrorInfo(
            "External-models runtime root mismatch blocks credential admission.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        )
    try:
        external_root.relative_to(managed_dir)
    except ValueError as exc:
        raise RuntimeErrorInfo(
            "External-models credential target is outside sandbox managed dir.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        ) from exc
    try:
        paths.secrets_file.resolve().relative_to(external_root)
    except ValueError as exc:
        raise RuntimeErrorInfo(
            "External-models secrets path is outside external-models root.",
            machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
            operator_action="stop",
        ) from exc
    try:
        paths.secrets_file.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return
    raise RuntimeErrorInfo(
        "External-models credential target resolves inside repo and is not sandbox-safe.",
        machine_error_code=errors.EXTERNAL_MODELS_CREDENTIAL_SANDBOX_UNPROVEN,
        operator_action="stop",
    )

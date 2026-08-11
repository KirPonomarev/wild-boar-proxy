# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""API transport adapter binding the actor engine to provider routes (B07).

Binds the canonical actor registry (B02), the fail-closed dispatcher (B05),
and the normalized transport surface (B03) to the external-models route
machinery for the mandatory API core: DeepSeek, Kimi, and GLM, with
OpenRouter as compatibility admission.

Live provider dispatch is the B07_LIVE seam and requires credentials. This
code contour provides the full structured dispatch path:

- route binding and admission (route exists, enabled, provider admitted,
  credential presence-only)
- provider request construction with the registered thinking dialects
  (DeepSeek profile, Kimi reasoning dialects, GLM thinking)
- controlled dispatch (deterministic, credential-free, explicitly not live)
- live dispatch structure gated by credential presence
- stream normalization through the streaming delta accumulator
- typed errors; an unavailable actor never returns another actor's response
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .actor_dispatcher import DispatchResolutionError
from .actor_registry import (
    API_ADAPTER,
    CONTEXT_POLICY_CONTINUE,
    CONTEXT_POLICY_FORK,
    CONTEXT_POLICY_FRESH,
)
from .external_models import credentials as external_credentials
from .external_models import provider_transforms
from .external_models import routes as external_routes
from .external_models import transforms as external_transforms
from .external_models.capability_registry import get_entry
from .external_models.paths import ExternalModelsPaths
from .keychain_credential_broker import lookup_keychain_credential
from .provider_capability_schema_v2 import RELEASE_PROVIDERS
from .thread_context_ledger import REDACTION_PATTERNS, redact_text
from .transport_normalization import (
    ERR_AMBIGUOUS_DELIVERY,
    ERR_CANCELLED,
    ERR_IDENTITY_DRIFT,
    ERR_INVALID_CREDENTIAL,
    ERR_INVALID_UPSTREAM_RESPONSE,
    ERR_MODEL_NOT_AVAILABLE,
    ERR_NETWORK_FAILED,
    ERR_QUOTA_EXHAUSTED,
    ERR_SECRET_INPUT_BLOCKED,
    ERR_STREAM_INCOMPLETE,
    ERR_TIMEOUT,
    ERR_TOOL_UNSUPPORTED,
    NormalizedFinalResponse,
    NormalizedRequest,
    NormalizedStreamEvent,
    NormalizedToolCall,
    classify_dispatch_result,
    utc_now,
)

# OpenRouter is a compatibility/admission surface, not a mandatory provider.
OPENROUTER_PROVIDER_ID = "openrouter"
COMPATIBILITY_PROVIDERS = (OPENROUTER_PROVIDER_ID,)

ADAPTER_KIND = "api_transport_adapter"
ADAPTER_VERSION = "0.2.0"

# The ledger also redacts the bare word ``keychain`` as a conservative
# persistence policy. A normal provider prompt may discuss that subsystem;
# only value-shaped patterns are blocked at the dispatch boundary.
_SECRET_VALUE_PATTERNS = tuple(
    pattern for pattern in REDACTION_PATTERNS if pattern.pattern != r"\bkeychain\b"
)

_SAFE_ERROR_MESSAGES = {
    "DISPATCH_PLAN_NOT_READY": "Dispatch plan is not ready.",
    "PROVIDER_NOT_ADMITTED": "Provider is not admitted.",
    "ROUTE_NOT_REGISTERED": "Route is not registered.",
    "ROUTE_DISABLED": "Route is disabled.",
    "ROUTE_PROVIDER_MISMATCH": "Registered route identity does not match the provider.",
    "ROUTE_RECORD_DRIFT": "Dispatch route differs from the registered route.",
    "MODEL_NOT_IN_CATALOG": "Model is not in the capability catalog.",
    "CREDENTIAL_MISSING": "A required provider credential is unavailable.",
    ERR_IDENTITY_DRIFT: "Dispatch identity does not match the resolved plan.",
    ERR_SECRET_INPUT_BLOCKED: "Secret-shaped input was blocked before dispatch.",
    ERR_INVALID_CREDENTIAL: "Provider credential admission failed.",
    ERR_MODEL_NOT_AVAILABLE: "Provider model is unavailable.",
    ERR_QUOTA_EXHAUSTED: "Provider quota is exhausted.",
    ERR_TIMEOUT: "Provider request timed out.",
    ERR_NETWORK_FAILED: "Provider transport failed.",
    ERR_INVALID_UPSTREAM_RESPONSE: "Provider response was invalid.",
    ERR_STREAM_INCOMPLETE: "Provider stream ended before completion.",
    ERR_TOOL_UNSUPPORTED: "Provider tool call is not admitted.",
    ERR_CANCELLED: "Dispatch was cancelled.",
    ERR_AMBIGUOUS_DELIVERY: "Provider delivery outcome is ambiguous; retry is blocked.",
}


def canonical_payload_digest(payload: object) -> str:
    return hashlib.sha256(
        (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def _admitted_provider(provider_id: str) -> bool:
    return provider_id in RELEASE_PROVIDERS or provider_id in COMPATIBILITY_PROVIDERS


class ApiTransportAdapter:
    def __init__(
        self,
        *,
        routes_file: Path | None = None,
        external_models_dir: Path | None = None,
        managed_dir: Path | None = None,
    ) -> None:
        self.external_models_dir = Path(
            external_models_dir
            or ExternalModelsPaths().external_models_dir
        )
        self.routes_file = Path(
            routes_file or ExternalModelsPaths(external_models_dir=self.external_models_dir).routes_file
        )
        self.managed_dir = Path(managed_dir) if managed_dir else None
        self._sessions: dict[str, str] = {}  # binding_id -> transport_session_id

    # -- route admission ---------------------------------------------------

    def _load_routes(self) -> dict[str, dict[str, Any]]:
        try:
            document = external_routes.load_routes_file(self.routes_file)
        except (OSError, ValueError):
            return {}
        routes = document.get("routes") if isinstance(document, dict) else None
        if not isinstance(routes, list):
            return {}
        return {str(route.get("route_id") or ""): route for route in routes if isinstance(route, dict)}

    def bind(
        self,
        dispatch_plan: Mapping[str, Any],
        *,
        require_credential: bool = True,
    ) -> dict[str, Any]:
        """Admit the dispatch plan against the route registry.

        Live admission performs a presence-only credential check. Controlled
        admission validates the route without probing credentials.
        """
        if dispatch_plan.get("status") != "ok":
            return self._admission_packet("blocked", "DISPATCH_PLAN_NOT_READY", dispatch_plan)
        provider_id = str(dispatch_plan.get("provider_id") or "")
        route_id = str(dispatch_plan.get("route_id") or "")
        model_id = str((dispatch_plan.get("model_policy") or {}).get("model_id") or "")
        if not _admitted_provider(provider_id):
            return self._admission_packet(
                "blocked", "PROVIDER_NOT_ADMITTED", dispatch_plan,
                reason=f"provider {provider_id} not in release/compatibility set",
            )
        routes = self._load_routes()
        route = routes.get(route_id)
        if route is None:
            return self._admission_packet(
                "blocked", "ROUTE_NOT_REGISTERED", dispatch_plan, reason=route_id
            )
        if route.get("enabled") is not True:
            return self._admission_packet(
                "blocked", "ROUTE_DISABLED", dispatch_plan, reason=route_id
            )
        if str(route.get("provider") or "").lower() != provider_id.lower():
            return self._admission_packet(
                "blocked",
                "ROUTE_PROVIDER_MISMATCH",
                dispatch_plan,
                provider_id=provider_id,
                route_id=route_id,
                model_id=model_id,
                credential_required=require_credential,
            )
        if model_id and get_entry(model_id) is None:
            # Declared catalog mismatch: model not in the capability catalog.
            return self._admission_packet(
                "blocked", "MODEL_NOT_IN_CATALOG", dispatch_plan, reason=model_id
            )
        if not require_credential:
            try:
                route_record_sha256 = canonical_payload_digest(route)
            except (TypeError, ValueError):
                return self._admission_packet(
                    "blocked",
                    ERR_INVALID_UPSTREAM_RESPONSE,
                    dispatch_plan,
                    provider_id=provider_id,
                    route_id=route_id,
                    model_id=model_id,
                    credential_required=False,
                )
            return self._admission_packet(
                "ok",
                "OK",
                dispatch_plan,
                credential_present=False,
                credential_source="not_probed",
                credential_required=False,
                provider_id=provider_id,
                route_id=route_id,
                model_id=model_id,
                route_record_sha256=route_record_sha256,
            )
        credential_present, credential_source = self._credential_presence(provider_id, route)
        try:
            route_record_sha256 = canonical_payload_digest(route)
        except (TypeError, ValueError):
            return self._admission_packet(
                "blocked",
                ERR_INVALID_UPSTREAM_RESPONSE,
                dispatch_plan,
                provider_id=provider_id,
                route_id=route_id,
                model_id=model_id,
                credential_required=True,
            )
        return self._admission_packet(
            "ok" if credential_present else "blocked",
            "OK" if credential_present else "CREDENTIAL_MISSING",
            dispatch_plan,
            credential_present=credential_present,
            credential_source=credential_source,
            provider_id=provider_id,
            route_id=route_id,
            model_id=model_id,
            credential_required=True,
            route_record_sha256=route_record_sha256,
        )

    def _credential_presence(self, provider_id: str, route: Mapping[str, Any]) -> tuple[bool, str]:
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        if str(auth.get("type") or "") == "none":
            return True, "route_auth_none"
        try:
            status = external_credentials.credential_status(
                self.external_models_dir,
                provider=provider_id,
            )
        except Exception:  # noqa: BLE001 - presence probe must never crash
            status = {}
        if isinstance(status, dict) and status.get("credential_present") is True:
            return True, "external_models_broker"
        # Keychain presence-only fallback (never reads the value).
        try:
            keychain = lookup_keychain_credential(provider=provider_id)
        except Exception:  # noqa: BLE001 - presence probe must never crash
            return False, ""
        if isinstance(keychain.safe_packet_fields, dict) and (
            keychain.safe_packet_fields.get("credential_present") is True
        ):
            return True, "keychain_broker_presence"
        return False, ""

    @staticmethod
    def _contains_secret_shaped_value(text: str) -> bool:
        return any(pattern.search(text) is not None for pattern in _SECRET_VALUE_PATTERNS)

    @staticmethod
    def _safe_error_message(error_code: str) -> str:
        return _SAFE_ERROR_MESSAGES.get(error_code, "Dispatch failed safely.")

    @staticmethod
    def _validate_dispatch_identity(
        request: NormalizedRequest,
        dispatch_plan: Mapping[str, Any],
        *,
        dispatch_id: str,
        slot_id: str,
        binding_id: str,
        binding_revision: int | None,
        assignment_id: str,
        assignment_revision: int | None,
        text_override: str,
    ) -> bool:
        """Return True only when the request is bound to the resolved plan."""
        plan_model = str((dispatch_plan.get("model_policy") or {}).get("model_id") or "")
        required_request_fields = (
            request.dispatch_id,
            request.transport_kind,
            request.provider_id,
            request.text.strip(),
            request.idempotency_key,
            request.context_digest,
            request.effective_permission,
        )
        if not all(required_request_fields):
            return False
        if request.transport_kind != API_ADAPTER:
            return False
        if request.transport_kind != str(dispatch_plan.get("transport_adapter_id") or ""):
            return False
        if request.provider_id != str(dispatch_plan.get("provider_id") or ""):
            return False
        if request.model_id != plan_model:
            return False
        if request.requested_permission != str(dispatch_plan.get("requested_permission") or ""):
            return False
        if request.effective_permission != str(dispatch_plan.get("effective_permission") or ""):
            return False
        planned_context = str(dispatch_plan.get("context_digest") or "")
        if planned_context and request.context_digest != planned_context:
            return False
        exact_pairs = (
            (dispatch_id, request.dispatch_id),
            (slot_id, str(dispatch_plan.get("slot_id") or "")),
            (binding_id, str(dispatch_plan.get("binding_id") or "")),
            (assignment_id, str(dispatch_plan.get("assignment_id") or "")),
        )
        if any(provided and provided != expected for provided, expected in exact_pairs):
            return False
        if (
            binding_revision is not None
            and binding_revision != dispatch_plan.get("binding_revision")
        ):
            return False
        if (
            assignment_revision is not None
            and assignment_revision != dispatch_plan.get("assignment_revision")
        ):
            return False
        if text_override and text_override != request.text:
            return False
        return True

    # -- provider request construction --------------------------------------

    def build_provider_request(
        self,
        *,
        route: Mapping[str, Any],
        text: str,
        model_id: str = "",
        stream: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build the provider payload with the registered thinking dialects."""
        payload, metadata = external_transforms.build_check_request(
            route,
            user_prompt=text,
        )
        provider_id = str(route.get("provider") or "").lower()
        thinking = route.get("thinking") if isinstance(route.get("thinking"), dict) else {}
        if provider_id == "kimi" and model_id:
            payload = provider_transforms.apply_kimi_thinking(
                payload,
                model=model_id,
                thinking_enabled=thinking.get("type") == "enabled",
            )
        elif provider_id in {"glm", "zai", "zhipu"}:
            payload = provider_transforms.apply_glm_thinking(
                payload,
                thinking_enabled=thinking.get("type") == "enabled",
                clear_thinking=False,
            )
        elif provider_id == "qwen" and model_id:
            from .qwen_provider_slice import apply_qwen_thinking

            payload = apply_qwen_thinking(
                payload,
                model=model_id,
                thinking_enabled=thinking.get("type") == "enabled",
            )
        if stream:
            payload["stream"] = True
        return payload, metadata

    # -- session context policies -------------------------------------------

    def prepare_session(
        self,
        *,
        context_policy: str,
        binding_id: str,
        context_digest: str,
    ) -> dict[str, Any]:
        """continue/fresh/fork session semantics for the binding."""
        if context_policy == CONTEXT_POLICY_CONTINUE:
            session_id = self._sessions.get(binding_id)
            if session_id is None:
                session_id = f"tns-{binding_id}-{utc_now()}"
                self._sessions[binding_id] = session_id
            return {"transport_session_id": session_id, "session_created": False, "context_digest": ""}
        if context_policy == CONTEXT_POLICY_FORK:
            if not context_digest:
                raise DispatchResolutionError(
                    "FORK_CONTEXT_DIGEST_MISSING", "fork requires an exact context digest"
                )
            session_id = f"tns-{binding_id}-fork-{context_digest[:12]}"
            return {"transport_session_id": session_id, "session_created": True, "context_digest": context_digest}
        # fresh (default)
        session_id = f"tns-{binding_id}-{utc_now()}"
        self._sessions[binding_id] = session_id
        return {"transport_session_id": session_id, "session_created": True, "context_digest": ""}

    # -- dispatch ------------------------------------------------------------

    def dispatch(
        self,
        request: NormalizedRequest,
        dispatch_plan: Mapping[str, Any],
        *,
        controlled: bool = True,
        dispatch_id: str = "",
        turn_id: str = "",
        workflow_run_id: str = "",
        step_request_id: str = "",
        slot_id: str = "",
        binding_id: str = "",
        binding_revision: int | None = None,
        assignment_id: str = "",
        assignment_revision: int | None = None,
        transport_session_id: str = "",
        route: Mapping[str, Any] | None = None,
        text: str = "",
    ) -> dict[str, Any]:
        """One bounded dispatch through the adapter.

        Controlled mode is credential-free and deterministic (explicitly not
        live). Live mode requires credential presence and is the B07_LIVE
        seam. An unavailable actor never returns another actor's response.
        """
        effective_dispatch_id = dispatch_id or request.dispatch_id
        if not self._validate_dispatch_identity(
            request,
            dispatch_plan,
            dispatch_id=dispatch_id,
            slot_id=slot_id,
            binding_id=binding_id,
            binding_revision=binding_revision,
            assignment_id=assignment_id,
            assignment_revision=assignment_revision,
            text_override=text,
        ):
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_IDENTITY_DRIFT,
                controlled=controlled,
            )
        effective_slot_id = slot_id or str(dispatch_plan.get("slot_id") or "")
        effective_binding_id = binding_id or str(dispatch_plan.get("binding_id") or "")
        effective_assignment_id = assignment_id or str(
            dispatch_plan.get("assignment_id") or ""
        )
        admission = self.bind(dispatch_plan, require_credential=not controlled)
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=admission["machine_error_code"],
                controlled=controlled,
            )
        registered_route = self._load_routes().get(
            str(dispatch_plan.get("route_id") or ""), {}
        )
        if not registered_route:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                controlled=controlled,
            )
        try:
            registered_route_digest = canonical_payload_digest(registered_route)
        except (TypeError, ValueError):
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                controlled=controlled,
            )
        if admission.get("route_record_sha256") != registered_route_digest:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code="ROUTE_RECORD_DRIFT",
                controlled=controlled,
            )
        if route is not None:
            try:
                route_matches = canonical_payload_digest(route) == registered_route_digest
            except (TypeError, ValueError):
                route_matches = False
            if not route_matches:
                return self._dispatch_failure_packet(
                    dispatch_plan=dispatch_plan,
                    request=request,
                    dispatch_id=effective_dispatch_id,
                    error_code="ROUTE_RECORD_DRIFT",
                    controlled=controlled,
                )
        route = registered_route
        prompt_text = text or request.text
        if self._contains_secret_shaped_value(prompt_text):
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_SECRET_INPUT_BLOCKED,
                controlled=controlled,
            )
        try:
            payload, _metadata = self.build_provider_request(
                route=route,
                text=prompt_text,
                model_id=str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
                stream=request.stream,
            )
            request_digest = canonical_payload_digest(payload)
        except Exception:  # noqa: BLE001 - returned text is deliberately bounded
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                controlled=controlled,
            )
        provider_id = str(dispatch_plan.get("provider_id") or "")
        model_id = str(
            payload.get("model")
            or (dispatch_plan.get("model_policy") or {}).get("model_id")
            or route.get("upstream_model")
            or ""
        )
        if controlled:
            response_text = (
                f"controlled response for {provider_id}/{model_id} "
                f"digest {request_digest[:16]}"
            )
            return self._dispatch_success_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                turn_id=turn_id,
                workflow_run_id=workflow_run_id,
                step_request_id=step_request_id,
                slot_id=effective_slot_id,
                binding_id=effective_binding_id,
                assignment_id=effective_assignment_id,
                transport_session_id=transport_session_id,
                route=route,
                request_digest=request_digest,
                model_id=model_id,
                response_text=response_text,
                controlled=True,
                live_provider_called=False,
                provider_http_status=None,
            )
        return self._live_dispatch(
            dispatch_plan=dispatch_plan,
            request=request,
            dispatch_id=effective_dispatch_id,
            turn_id=turn_id,
            workflow_run_id=workflow_run_id,
            step_request_id=step_request_id,
            slot_id=effective_slot_id,
            binding_id=effective_binding_id,
            assignment_id=effective_assignment_id,
            transport_session_id=transport_session_id,
            route=route,
            payload=payload,
            request_digest=request_digest,
            model_id=model_id,
        )

    def _live_dispatch(self, **kwargs: Any) -> dict[str, Any]:
        """B07_LIVE seam: real provider HTTP dispatch (credential-gated).

        The code contour wires the full chain; live execution requires
        credentials and is exercised only in B07_LIVE.
        """
        admission = self.bind(kwargs["dispatch_plan"], require_credential=True)
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=admission["machine_error_code"],
                controlled=False,
            )
        try:
            route_record_sha256 = canonical_payload_digest(kwargs["route"])
        except (TypeError, ValueError):
            route_record_sha256 = ""
        if admission.get("route_record_sha256") != route_record_sha256:
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code="ROUTE_RECORD_DRIFT",
                controlled=False,
            )
        try:
            from .external_models.http_client import request_json
            from .external_models.validate import _provider_headers, _completion_url

            # _provider_headers requires paths — use the external models dir
            # from the adapter instance.
            paths = self._external_models_paths()
            headers = _provider_headers(kwargs["route"], paths)
            completion_url = _completion_url(kwargs["route"])
        except Exception as exc:  # noqa: BLE001 - classified without exposing text
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=self._classify_live_error(exc),
                controlled=False,
                upstream_error_code=self._classify_live_error(exc),
            )
        try:
            response = request_json(
                url=completion_url,
                method="POST",
                headers=headers,
                payload=kwargs["payload"],
            )
        except Exception as exc:  # noqa: BLE001 - request may have been delivered
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=ERR_AMBIGUOUS_DELIVERY,
                controlled=False,
                dispatch_attempted=True,
                response_observed=False,
                live_provider_called=True,
                upstream_error_code=self._classify_live_error(exc),
            )
        try:
            status_code = int(response.status_code)
        except (AttributeError, TypeError, ValueError):
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                controlled=False,
                dispatch_attempted=True,
                response_observed=True,
                live_provider_called=True,
                upstream_error_code=ERR_INVALID_UPSTREAM_RESPONSE,
            )
        if status_code < 200 or status_code >= 300:
            error_code = self._classify_http_status(status_code)
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=error_code,
                controlled=False,
                dispatch_attempted=True,
                response_observed=True,
                live_provider_called=True,
                provider_http_status=status_code,
                upstream_error_code=error_code,
            )
        try:
            response_text, _ = external_transforms.extract_check_response(
                kwargs["route"], response.payload
            )
        except Exception:  # noqa: BLE001 - raw provider body is never emitted
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                request=kwargs["request"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                controlled=False,
                dispatch_attempted=True,
                response_observed=True,
                live_provider_called=True,
                provider_http_status=status_code,
                upstream_error_code=ERR_INVALID_UPSTREAM_RESPONSE,
            )
        return self._dispatch_success_packet(
            dispatch_plan=kwargs["dispatch_plan"],
            request=kwargs["request"],
            dispatch_id=kwargs["dispatch_id"],
            turn_id=kwargs.get("turn_id", ""),
            workflow_run_id=kwargs.get("workflow_run_id", ""),
            step_request_id=kwargs.get("step_request_id", ""),
            slot_id=kwargs.get("slot_id", ""),
            binding_id=kwargs.get("binding_id", ""),
            assignment_id=kwargs.get("assignment_id", ""),
            transport_session_id=kwargs.get("transport_session_id", ""),
            route=kwargs["route"],
            request_digest=kwargs.get("request_digest", ""),
            model_id=kwargs.get("model_id", ""),
            response_text=response_text,
            controlled=False,
            live_provider_called=True,
            provider_http_status=status_code,
        )

    def _external_models_paths(self) -> ExternalModelsPaths:
        """Return the ExternalModelsPaths for this adapter's dir."""
        return ExternalModelsPaths.from_root(self.external_models_dir)

    @staticmethod
    def _classify_live_error(exc: Exception) -> str:
        machine_code = str(getattr(exc, "machine_error_code", "") or "").lower()
        message = str(exc).lower()
        combined = f"{machine_code} {message}"
        if any(
            token in combined
            for token in (
                "401",
                "403",
                "credential",
                "missing_secret",
                "invalid_secret",
                "unsafe_secret_permissions",
                "provider_auth_failed",
            )
        ):
            return ERR_INVALID_CREDENTIAL
        if "429" in combined or "quota" in combined:
            return ERR_QUOTA_EXHAUSTED
        if "404" in combined or "model" in combined:
            return ERR_MODEL_NOT_AVAILABLE
        if "timeout" in combined or "timed out" in combined:
            return ERR_TIMEOUT
        if "invalid_upstream" in combined or "schema_invalid" in combined:
            return ERR_INVALID_UPSTREAM_RESPONSE
        return ERR_NETWORK_FAILED

    @staticmethod
    def _classify_http_status(status_code: int) -> str:
        if status_code in {401, 403}:
            return ERR_INVALID_CREDENTIAL
        if status_code == 404:
            return ERR_MODEL_NOT_AVAILABLE
        if status_code == 408:
            return ERR_TIMEOUT
        if status_code == 429:
            return ERR_QUOTA_EXHAUSTED
        if status_code >= 500:
            return ERR_NETWORK_FAILED
        return ERR_INVALID_UPSTREAM_RESPONSE

    # -- streaming -----------------------------------------------------------

    def stream_dispatch(
        self,
        request: NormalizedRequest,
        dispatch_plan: Mapping[str, Any],
        chunks: Iterable[Mapping[str, Any]],
        *,
        dispatch_id: str = "",
    ) -> dict[str, Any]:
        """Normalize raw stream chunks through the delta accumulator."""
        effective_dispatch_id = dispatch_id or request.dispatch_id
        if not self._validate_dispatch_identity(
            request,
            dispatch_plan,
            dispatch_id=dispatch_id,
            slot_id="",
            binding_id="",
            binding_revision=None,
            assignment_id="",
            assignment_revision=None,
            text_override="",
        ):
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_IDENTITY_DRIFT,
                controlled=True,
            )
        if self._contains_secret_shaped_value(request.text):
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_SECRET_INPUT_BLOCKED,
                controlled=True,
            )
        admission = self.bind(dispatch_plan, require_credential=False)
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=admission["machine_error_code"],
                controlled=True,
            )
        accumulator = provider_transforms.StreamingDeltaAccumulator()
        events: list[NormalizedStreamEvent] = []
        sequence = 0
        for chunk in chunks:
            try:
                accumulator.feed_chunk(chunk)
            except (KeyError, TypeError, ValueError):
                return self._dispatch_failure_packet(
                    dispatch_plan=dispatch_plan,
                    request=request,
                    dispatch_id=effective_dispatch_id,
                    error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                    controlled=True,
                )
            delta = chunk.get("choices", [{}])[0].get("delta", {}) if isinstance(chunk.get("choices"), list) else {}
            events.append(
                NormalizedStreamEvent(
                    event_type="delta",
                    dispatch_id=effective_dispatch_id,
                    sequence=sequence,
                    text_delta=redact_text(str(delta.get("content") or "")),
                    finish_reason=str(
                        (chunk.get("choices", [{}])[0] or {}).get("finish_reason") or ""
                    ),
                )
            )
            sequence += 1
        if not accumulator.stream_complete:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                request=request,
                dispatch_id=effective_dispatch_id,
                error_code=ERR_STREAM_INCOMPLETE,
                controlled=True,
            )
        redacted_text = redact_text(accumulator.assembled_content)
        response_redacted = redacted_text != accumulator.assembled_content
        serialized_events = [event.as_dict() for event in events]
        if response_redacted:
            # A value-shaped secret can span chunk boundaries and evade
            # per-delta pattern matching. Once the complete response proves
            # redaction was needed, no original non-empty delta is emitted.
            for event in serialized_events:
                if event["text_delta"]:
                    event["text_delta"] = "[redacted]"
        final = NormalizedFinalResponse(
            dispatch_id=effective_dispatch_id,
            transport_kind=API_ADAPTER,
            provider_id=str(dispatch_plan.get("provider_id") or ""),
            model_id=str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
            text=redacted_text,
            tool_calls=tuple(
                NormalizedToolCall(
                    tool_call_id=f"tool-{index}",
                    name=call.get("name") or "",
                    arguments=call.get("arguments") or "",
                )
                for index, call in enumerate(accumulator.assembled_tool_calls)
            ),
            finish_reason="stop",
        )
        return {
            "status": "ok",
            "machine_error_code": "STREAM_DISPATCH_COMPLETE",
            "dispatch_id": effective_dispatch_id,
            "events": serialized_events,
            "final_response": {
                "text": final.text,
                "tool_calls": [call.name for call in final.tool_calls],
                "finish_reason": final.finish_reason,
            },
            "stream_complete": True,
            "dispatch_proven": True,
            "dispatch_attempted": True,
            "response_observed": True,
            "response_redacted": response_redacted,
            "response_text_sha256": hashlib.sha256(redacted_text.encode("utf-8")).hexdigest(),
            "live_provider_called": False,
            "live_provider_proven": False,
            "does_not_prove_live_provider": True,
            "evidence_level": "SYNTHETIC_PROVEN",
            "fallback_used": False,
            "actor_substitution_used": False,
            "secret_value_exposed": False,
            "raw_backend_details_exposed": False,
        }

    # -- packet builders -----------------------------------------------------

    def _admission_packet(
        self,
        status: str,
        machine_error_code: str,
        dispatch_plan: Mapping[str, Any],
        *,
        reason: str = "",
        credential_present: bool = False,
        credential_source: str = "",
        credential_required: bool = True,
        provider_id: str = "",
        route_id: str = "",
        model_id: str = "",
        route_record_sha256: str = "",
    ) -> dict[str, Any]:
        return {
            "status": status,
            "machine_error_code": machine_error_code,
            "human_message": (
                "Route bound and admitted."
                if status == "ok"
                else self._safe_error_message(machine_error_code)
            ),
            "credential_required": credential_required,
            "credential_present": credential_present,
            "credential_source": credential_source,
            "credential_value_exposed": False,
            "provider_id": provider_id,
            "route_id": route_id,
            "model_id": model_id,
            "route_record_sha256": route_record_sha256,
            "adapter_kind": ADAPTER_KIND,
            "adapter_version": ADAPTER_VERSION,
            "secret_value_exposed": False,
        }

    def _dispatch_failure_packet(
        self,
        *,
        dispatch_plan: Mapping[str, Any],
        request: NormalizedRequest | None,
        dispatch_id: str,
        error_code: str,
        controlled: bool,
        dispatch_attempted: bool = False,
        response_observed: bool = False,
        live_provider_called: bool = False,
        provider_http_status: int | None = None,
        upstream_error_code: str = "",
    ) -> dict[str, Any]:
        result = classify_dispatch_result(
            response_observed=response_observed,
            error_code=error_code,
        )
        return {
            "status": "error",
            "machine_error_code": error_code,
            "human_message": self._safe_error_message(error_code),
            "dispatch_id": dispatch_id,
            "slot_id": str(dispatch_plan.get("slot_id") or ""),
            "binding_id": str(dispatch_plan.get("binding_id") or ""),
            "binding_revision": dispatch_plan.get("binding_revision"),
            "assignment_id": str(dispatch_plan.get("assignment_id") or ""),
            "assignment_revision": dispatch_plan.get("assignment_revision"),
            "context_digest": request.context_digest if request is not None else "",
            "transport_kind": request.transport_kind if request is not None else "",
            "provider_id": str(dispatch_plan.get("provider_id") or ""),
            "model_id": str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
            "route_id": str(dispatch_plan.get("route_id") or ""),
            "dispatch_proven": False,
            "dispatch_attempted": dispatch_attempted,
            "response_observed": response_observed,
            "provider_response_observed": response_observed,
            "result": result,
            "ambiguous_delivery": result == "ambiguous",
            "retry_permitted": False,
            "controlled": controlled,
            "provider_http_status": provider_http_status,
            "upstream_error_code": upstream_error_code,
            "evidence_level": "DECLARED",
            "fallback_used": False,
            "actor_substitution_used": False,
            "cross_provider_fallback": False,
            "live_provider_called": live_provider_called,
            "live_provider_proven": False,
            "does_not_prove_live_provider": True,
            "secret_value_exposed": False,
            "raw_backend_details_exposed": False,
        }

    def _dispatch_success_packet(
        self,
        *,
        dispatch_plan: Mapping[str, Any],
        request: NormalizedRequest,
        dispatch_id: str,
        turn_id: str,
        workflow_run_id: str,
        step_request_id: str,
        slot_id: str,
        binding_id: str,
        assignment_id: str,
        transport_session_id: str,
        route: Mapping[str, Any],
        request_digest: str,
        model_id: str,
        response_text: str,
        controlled: bool,
        live_provider_called: bool,
        provider_http_status: int | None,
    ) -> dict[str, Any]:
        redacted_response = redact_text(response_text)
        response_digest = hashlib.sha256(redacted_response.encode("utf-8")).hexdigest()
        return {
            "status": "ok",
            "machine_error_code": "DISPATCH_COMPLETE",
            "dispatch_id": dispatch_id,
            "turn_id": turn_id,
            "workflow_run_id": workflow_run_id,
            "step_request_id": step_request_id,
            "slot_id": slot_id,
            "binding_id": binding_id,
            "binding_revision": dispatch_plan.get("binding_revision"),
            "assignment_id": assignment_id,
            "assignment_revision": dispatch_plan.get("assignment_revision"),
            "transport_session_id": transport_session_id,
            "context_digest": request.context_digest,
            "requested_permission": request.requested_permission,
            "effective_permission": request.effective_permission,
            "idempotency_key_sha256": hashlib.sha256(
                request.idempotency_key.encode("utf-8")
            ).hexdigest(),
            "transport_kind": request.transport_kind,
            "provider_id": str(dispatch_plan.get("provider_id") or ""),
            "model_id": model_id,
            "route_id": str(route.get("route_id") or ""),
            "route_record_sha256": canonical_payload_digest(route),
            "request_id": f"req-{request_digest[:16]}",
            "route_bound_request_sha256": request_digest,
            "dispatch_proven": True,
            "dispatch_attempted": True,
            "result": "ok",
            "response_observed": True,
            "provider_response_observed": not controlled,
            "response_text": redacted_response,
            "response_text_sha256": response_digest,
            "response_redacted": redacted_response != response_text,
            "provider_http_status": provider_http_status,
            "controlled": controlled,
            "live_provider_called": live_provider_called,
            "live_provider_proven": live_provider_called,
            "does_not_prove_live_provider": not live_provider_called,
            "evidence_level": "SYNTHETIC_PROVEN" if controlled else "LIVE_PROVEN",
            "retry_permitted": False,
            "fallback_used": False,
            "actor_substitution_used": False,
            "cross_provider_fallback": False,
            "secret_value_exposed": False,
            "raw_backend_details_exposed": False,
        }


__all__ = [
    "ADAPTER_KIND",
    "ADAPTER_VERSION",
    "OPENROUTER_PROVIDER_ID",
    "ApiTransportAdapter",
    "canonical_payload_digest",
]

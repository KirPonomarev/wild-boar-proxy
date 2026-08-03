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
    PRIMARY_SLOT_ID,
)
from .external_models import credentials as external_credentials
from .external_models import provider_transforms
from .external_models import routes as external_routes
from .external_models import transforms as external_transforms
from .external_models.capability_registry import get_entry
from .external_models.paths import ExternalModelsPaths
from .keychain_credential_broker import lookup_keychain_credential
from .provider_capability_schema_v2 import (
    EXCLUDED_PROVIDERS,
    RELEASE_PROVIDERS,
)
from .transport_normalization import (
    ERR_CANCELLED,
    ERR_INVALID_CREDENTIAL,
    ERR_INVALID_UPSTREAM_RESPONSE,
    ERR_MODEL_NOT_AVAILABLE,
    ERR_NETWORK_FAILED,
    ERR_QUOTA_EXHAUSTED,
    ERR_STREAM_INCOMPLETE,
    ERR_TIMEOUT,
    ERR_TOOL_UNSUPPORTED,
    NormalizedFinalResponse,
    NormalizedRequest,
    NormalizedStreamEvent,
    NormalizedToolCall,
    TransportError,
    classify_dispatch_result,
    utc_now,
)

# OpenRouter is a compatibility/admission surface, not a mandatory provider.
OPENROUTER_PROVIDER_ID = "openrouter"
COMPATIBILITY_PROVIDERS = (OPENROUTER_PROVIDER_ID,)

ADAPTER_KIND = "api_transport_adapter"
ADAPTER_VERSION = "0.1.0"


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

    def bind(self, dispatch_plan: Mapping[str, Any]) -> dict[str, Any]:
        """Admit the dispatch plan against the route registry.

        Presence-only credential check; returns a bounded admission packet.
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
        if model_id and get_entry(model_id) is None:
            # Declared catalog mismatch: model not in the capability catalog.
            return self._admission_packet(
                "blocked", "MODEL_NOT_IN_CATALOG", dispatch_plan, reason=model_id
            )
        credential_present, credential_source = self._credential_presence(provider_id, route)
        return self._admission_packet(
            "ok" if credential_present else "blocked",
            "OK" if credential_present else "CREDENTIAL_MISSING",
            dispatch_plan,
            credential_present=credential_present,
            credential_source=credential_source,
            provider_id=provider_id,
            route_id=route_id,
            model_id=model_id,
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
        keychain = lookup_keychain_credential(provider=provider_id)
        if isinstance(keychain.safe_packet_fields, dict) and (
            keychain.safe_packet_fields.get("credential_present") is True
        ):
            return True, "keychain_broker_presence"
        return False, ""

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
        assignment_id: str = "",
        transport_session_id: str = "",
        route: Mapping[str, Any] | None = None,
        text: str = "",
    ) -> dict[str, Any]:
        """One bounded dispatch through the adapter.

        Controlled mode is credential-free and deterministic (explicitly not
        live). Live mode requires credential presence and is the B07_LIVE
        seam. An unavailable actor never returns another actor's response.
        """
        admission = self.bind(dispatch_plan)
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                error_code=admission["machine_error_code"],
                error_message=admission.get("human_message", ""),
            )
        route = route or self._load_routes().get(str(dispatch_plan.get("route_id") or ""), {})
        if not route:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                error_message="route record unavailable at dispatch time",
            )
        prompt_text = text or request.text
        try:
            payload, metadata = self.build_provider_request(
                route=route,
                text=prompt_text,
                model_id=str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
                stream=request.stream,
            )
        except (OSError, ValueError) as exc:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                error_message=str(exc),
            )
        request_digest = canonical_payload_digest(payload)
        provider_id = str(dispatch_plan.get("provider_id") or "")
        model_id = str((dispatch_plan.get("model_policy") or {}).get("model_id") or "")
        if controlled:
            response_text = (
                f"controlled response for {provider_id}/{model_id} "
                f"digest {request_digest[:16]}"
            )
            return self._dispatch_success_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                turn_id=turn_id,
                workflow_run_id=workflow_run_id,
                step_request_id=step_request_id,
                slot_id=slot_id,
                binding_id=binding_id,
                assignment_id=assignment_id,
                transport_session_id=transport_session_id,
                route=route,
                request_digest=request_digest,
                response_text=response_text,
                controlled=True,
                live_provider_called=False,
            )
        return self._live_dispatch(
            dispatch_plan=dispatch_plan,
            dispatch_id=dispatch_id,
            turn_id=turn_id,
            workflow_run_id=workflow_run_id,
            step_request_id=step_request_id,
            slot_id=slot_id,
            binding_id=binding_id,
            assignment_id=assignment_id,
            transport_session_id=transport_session_id,
            route=route,
            payload=payload,
            request_digest=request_digest,
            text=prompt_text,
        )

    def _live_dispatch(self, **kwargs: Any) -> dict[str, Any]:
        """B07_LIVE seam: real provider HTTP dispatch (credential-gated).

        The code contour wires the full chain; live execution requires
        credentials and is exercised only in B07_LIVE.
        """
        from .external_models.validate import _completion_url  # type: ignore[attr-defined]

        admission = self.bind(kwargs["dispatch_plan"])
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=admission["machine_error_code"],
                error_message=admission.get("human_message", ""),
            )
        try:
            from .external_models.http_client import request_json
            from .external_models.validate import _provider_headers

            headers = _provider_headers(kwargs["route"])
            response = request_json(
                url=_completion_url(kwargs["route"]),
                method="POST",
                headers=headers,
                payload=kwargs["payload"],
            )
            response_text, _ = external_transforms.extract_check_response(
                kwargs["route"], response.payload
            )
        except Exception as exc:  # noqa: BLE001 - normalized below
            return self._dispatch_failure_packet(
                dispatch_plan=kwargs["dispatch_plan"],
                dispatch_id=kwargs["dispatch_id"],
                error_code=self._classify_live_error(exc),
                error_message=str(exc),
            )
        return self._dispatch_success_packet(
            **{**kwargs, "response_text": response_text, "controlled": False, "live_provider_called": True}
        )

    @staticmethod
    def _classify_live_error(exc: Exception) -> str:
        message = str(exc).lower()
        if "401" in message or "403" in message or "credential" in message:
            return ERR_INVALID_CREDENTIAL
        if "429" in message or "quota" in message:
            return ERR_QUOTA_EXHAUSTED
        if "404" in message or "model" in message:
            return ERR_MODEL_NOT_AVAILABLE
        if "timeout" in message:
            return ERR_TIMEOUT
        return ERR_NETWORK_FAILED

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
        admission = self.bind(dispatch_plan)
        if admission["status"] != "ok":
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                error_code=admission["machine_error_code"],
                error_message=admission.get("human_message", ""),
            )
        accumulator = provider_transforms.StreamingDeltaAccumulator()
        events: list[NormalizedStreamEvent] = []
        sequence = 0
        for chunk in chunks:
            try:
                accumulator.feed_chunk(chunk)
            except (KeyError, TypeError, ValueError) as exc:
                return self._dispatch_failure_packet(
                    dispatch_plan=dispatch_plan,
                    dispatch_id=dispatch_id,
                    error_code=ERR_INVALID_UPSTREAM_RESPONSE,
                    error_message=str(exc),
                )
            delta = chunk.get("choices", [{}])[0].get("delta", {}) if isinstance(chunk.get("choices"), list) else {}
            events.append(
                NormalizedStreamEvent(
                    event_type="delta",
                    dispatch_id=dispatch_id,
                    sequence=sequence,
                    text_delta=str(delta.get("content") or ""),
                    finish_reason=str(
                        (chunk.get("choices", [{}])[0] or {}).get("finish_reason") or ""
                    ),
                )
            )
            sequence += 1
        if not accumulator.stream_complete:
            return self._dispatch_failure_packet(
                dispatch_plan=dispatch_plan,
                dispatch_id=dispatch_id,
                error_code=ERR_STREAM_INCOMPLETE,
                error_message="stream ended without a terminal chunk",
            )
        final = NormalizedFinalResponse(
            dispatch_id=dispatch_id,
            transport_kind=API_ADAPTER,
            provider_id=str(dispatch_plan.get("provider_id") or ""),
            model_id=str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
            text=accumulator.assembled_content,
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
            "events": [event.as_dict() if hasattr(event, "as_dict") else event for event in events],
            "final_response": {
                "text": final.text,
                "tool_calls": [call.name for call in final.tool_calls],
                "finish_reason": final.finish_reason,
            },
            "stream_complete": True,
            "live_provider_called": False,
            "evidence_level": "SYNTHETIC_PROVEN",
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
        provider_id: str = "",
        route_id: str = "",
        model_id: str = "",
    ) -> dict[str, Any]:
        return {
            "status": status,
            "machine_error_code": machine_error_code,
            "human_message": (
                "Route bound and admitted."
                if status == "ok"
                else f"Route admission blocked: {reason or machine_error_code}"
            ),
            "credential_present": credential_present,
            "credential_source": credential_source,
            "credential_value_exposed": False,
            "provider_id": provider_id,
            "route_id": route_id,
            "model_id": model_id,
            "adapter_kind": ADAPTER_KIND,
            "adapter_version": ADAPTER_VERSION,
            "secret_value_exposed": False,
        }

    def _dispatch_failure_packet(
        self,
        *,
        dispatch_plan: Mapping[str, Any],
        dispatch_id: str,
        error_code: str,
        error_message: str,
    ) -> dict[str, Any]:
        return {
            "status": "error",
            "machine_error_code": error_code,
            "human_message": error_message,
            "dispatch_id": dispatch_id,
            "dispatch_proven": False,
            "dispatch_attempted": False,
            "result": classify_dispatch_result(response_observed=False, error_code=error_code),
            "fallback_used": False,
            "actor_substitution_used": False,
            "live_provider_called": False,
            "secret_value_exposed": False,
            "raw_backend_details_exposed": False,
        }

    def _dispatch_success_packet(
        self,
        *,
        dispatch_plan: Mapping[str, Any],
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
        response_text: str,
        controlled: bool,
        live_provider_called: bool,
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "machine_error_code": "DISPATCH_COMPLETE",
            "dispatch_id": dispatch_id,
            "turn_id": turn_id,
            "workflow_run_id": workflow_run_id,
            "step_request_id": step_request_id,
            "slot_id": slot_id,
            "binding_id": binding_id,
            "assignment_id": assignment_id,
            "transport_session_id": transport_session_id,
            "provider_id": str(dispatch_plan.get("provider_id") or ""),
            "route_id": str(route.get("route_id") or ""),
            "request_id": f"req-{request_digest[:16]}",
            "route_bound_request_sha256": request_digest,
            "dispatch_proven": True,
            "dispatch_attempted": True,
            "result": "ok",
            "response_observed": True,
            "response_text": response_text,
            "controlled": controlled,
            "live_provider_called": live_provider_called,
            "live_provider_proven": live_provider_called,
            "does_not_prove_live_provider": not live_provider_called,
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

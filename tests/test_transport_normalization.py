# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B03: normalized transport boundary tests."""

from __future__ import annotations

import unittest

from wild_boar_proxy import transport_normalization as tn


class NormalizeRequestTests(unittest.TestCase):
    def _raw(self) -> dict[str, object]:
        return {
            "dispatch_id": "dispatch-1",
            "transport_kind": tn.API,
            "provider_id": "deepseek",
            "model_id": "deepseek-chat",
            "text": "hello",
            "idempotency_key": "idem-1",
            "context_digest": "digest-1",
            "requested_permission": "context_only",
            "effective_permission": "context_only",
        }

    def test_valid_request_normalizes(self) -> None:
        request = tn.normalize_request(self._raw())
        self.assertIsInstance(request, tn.NormalizedRequest)
        assert isinstance(request, tn.NormalizedRequest)
        self.assertEqual(request.dispatch_id, "dispatch-1")
        self.assertEqual(request.transport_kind, tn.API)
        self.assertFalse(request.stream)

    def test_unknown_transport_kind_rejected(self) -> None:
        raw = self._raw()
        raw["transport_kind"] = "carrier_pigeon"
        result = tn.normalize_request(raw)
        self.assertIsInstance(result, tn.TransportError)
        assert isinstance(result, tn.TransportError)
        self.assertEqual(result.code, tn.ERR_INVALID_UPSTREAM_RESPONSE)

    def test_missing_text_rejected(self) -> None:
        raw = self._raw()
        raw["text"] = ""
        self.assertIsInstance(tn.normalize_request(raw), tn.TransportError)

    def test_missing_effective_permission_rejected(self) -> None:
        raw = self._raw()
        raw["effective_permission"] = ""
        self.assertIsInstance(tn.normalize_request(raw), tn.TransportError)

    def test_native_primary_is_a_boundary_not_a_send_adapter(self) -> None:
        # native_primary is admitted as a transport kind but this module only
        # normalizes envelopes; it never synthesizes a native dispatch result.
        raw = self._raw()
        raw["transport_kind"] = tn.NATIVE_PRIMARY
        request = tn.normalize_request(raw)
        self.assertIsInstance(request, tn.NormalizedRequest)


class NormalizeStreamEventTests(unittest.TestCase):
    def test_delta_event(self) -> None:
        event = tn.normalize_stream_event(
            {"event_type": "delta", "text_delta": "hel"}, dispatch_id="d1", sequence=1
        )
        self.assertIsInstance(event, tn.NormalizedStreamEvent)
        assert isinstance(event, tn.NormalizedStreamEvent)
        self.assertEqual(event.text_delta, "hel")
        self.assertEqual(event.sequence, 1)

    def test_unknown_event_type_rejected(self) -> None:
        result = tn.normalize_stream_event(
            {"event_type": "pulse"}, dispatch_id="d1", sequence=1
        )
        self.assertIsInstance(result, tn.TransportError)


class NormalizeFinalResponseTests(unittest.TestCase):
    def test_text_response(self) -> None:
        response = tn.normalize_final_response(
            {"text": "ok", "finish_reason": "stop", "usage": {"prompt_tokens": 5}},
            dispatch_id="d1",
            transport_kind=tn.API,
            provider_id="kimi",
            model_id="kimi-k2.5",
        )
        self.assertIsInstance(response, tn.NormalizedFinalResponse)
        assert isinstance(response, tn.NormalizedFinalResponse)
        self.assertEqual(response.text, "ok")
        self.assertEqual(response.usage["prompt_tokens"], 5)

    def test_tool_calls_normalized(self) -> None:
        response = tn.normalize_final_response(
            {
                "text": "",
                "tool_calls": [
                    {"tool_call_id": "t1", "name": "read_file", "arguments": '{"path": "x"}'}
                ],
            },
            dispatch_id="d1",
            transport_kind=tn.API,
            provider_id="glm",
            model_id="glm-4.6",
        )
        assert isinstance(response, tn.NormalizedFinalResponse)
        self.assertEqual(response.tool_calls[0].name, "read_file")

    def test_non_string_text_rejected(self) -> None:
        result = tn.normalize_final_response(
            {"text": 42}, dispatch_id="d1", transport_kind=tn.API, provider_id="p", model_id="m"
        )
        self.assertIsInstance(result, tn.TransportError)


class DispatchClassificationTests(unittest.TestCase):
    def test_observed_is_ok(self) -> None:
        self.assertEqual(
            tn.classify_dispatch_result(response_observed=True, error_code=""),
            "ok",
        )

    def test_ambiguous_never_ok(self) -> None:
        self.assertEqual(
            tn.classify_dispatch_result(
                response_observed=False, error_code=tn.ERR_AMBIGUOUS_DELIVERY
            ),
            "ambiguous",
        )

    def test_plain_error(self) -> None:
        self.assertEqual(
            tn.classify_dispatch_result(response_observed=False, error_code="network_failed"),
            "error",
        )

    def test_observed_error_is_not_false_success(self) -> None:
        self.assertEqual(
            tn.classify_dispatch_result(
                response_observed=True,
                error_code=tn.ERR_INVALID_CREDENTIAL,
            ),
            "error",
        )


class TransportErrorTests(unittest.TestCase):
    def test_serialized_error_preserves_retry_and_ambiguity_truth(self) -> None:
        error = tn.TransportError(
            tn.ERR_AMBIGUOUS_DELIVERY,
            "delivery outcome is ambiguous",
            retryable=False,
            ambiguous=True,
        )
        self.assertEqual(
            error.as_dict(),
            {
                "code": tn.ERR_AMBIGUOUS_DELIVERY,
                "message": "delivery outcome is ambiguous",
                "retryable": False,
                "ambiguous": True,
            },
        )

    def test_new_guard_codes_are_in_typed_taxonomy(self) -> None:
        self.assertIn(tn.ERR_IDENTITY_DRIFT, tn.TYPED_ERROR_CODES)
        self.assertIn(tn.ERR_SECRET_INPUT_BLOCKED, tn.TYPED_ERROR_CODES)


if __name__ == "__main__":
    unittest.main()

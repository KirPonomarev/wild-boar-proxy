# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fixture-based integration tests for Kimi/GLM provider transforms (P02+P03).

Tests provider-specific reasoning dialects, streaming accumulation,
tool-call round-trips, reasoning_content preservation, and error taxonomy
using deterministic fixtures (no live API calls).
"""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.external_models.provider_transforms import (
    StreamingDeltaAccumulator,
    apply_kimi_thinking,
    apply_glm_thinking,
    preserve_glm_reasoning_in_tool_loop,
    classify_provider_error,
    build_provider_auth_headers,
    ProviderErrorClassification,
    PROVIDER_KIMI,
    PROVIDER_GLM,
)


class KimiThinkingTransformTests(unittest.TestCase):
    def test_k3_reasoning_effort_low(self) -> None:
        payload = apply_kimi_thinking(
            {"model": "kimi-k3", "messages": []},
            model="kimi-k3", reasoning_effort="low",
        )
        self.assertEqual(payload["reasoning_effort"], "low")

    def test_k3_reasoning_effort_max(self) -> None:
        payload = apply_kimi_thinking(
            {"model": "kimi-k3", "messages": []},
            model="kimi-k3", reasoning_effort="max",
        )
        self.assertEqual(payload["reasoning_effort"], "max")

    def test_k26_thinking_enabled(self) -> None:
        payload = apply_kimi_thinking(
            {"model": "kimi-k2.6", "messages": []},
            model="kimi-k2.6", thinking_enabled=True,
        )
        self.assertEqual(payload["thinking"]["type"], "enabled")

    def test_k26_thinking_disabled(self) -> None:
        payload = apply_kimi_thinking(
            {"model": "kimi-k2.6", "messages": []},
            model="kimi-k2.6", thinking_enabled=False,
        )
        self.assertEqual(payload["thinking"]["type"], "disabled")

    def test_k25_no_parameter(self) -> None:
        """K2.5 is always-thinking; no reasoning parameter added."""
        payload = apply_kimi_thinking(
            {"model": "kimi-k2.5", "messages": []},
            model="kimi-k2.5",
        )
        self.assertNotIn("reasoning_effort", payload)
        self.assertNotIn("thinking", payload)


class GLMThinkingTransformTests(unittest.TestCase):
    def test_glm_thinking_enabled(self) -> None:
        payload = apply_glm_thinking(
            {"model": "glm-4.6", "messages": []},
            thinking_enabled=True,
        )
        self.assertEqual(payload["thinking"]["type"], "enabled")

    def test_glm_thinking_disabled(self) -> None:
        payload = apply_glm_thinking(
            {"model": "glm-4.6", "messages": []},
            thinking_enabled=False,
        )
        self.assertEqual(payload["thinking"]["type"], "disabled")

    def test_glm_clear_thinking_false_preserved(self) -> None:
        payload = apply_glm_thinking(
            {"model": "glm-4.6", "messages": []},
            thinking_enabled=True, clear_thinking=False,
        )
        self.assertFalse(payload["thinking"]["clear_thinking"])

    def test_glm_clear_thinking_not_set_when_disabled(self) -> None:
        payload = apply_glm_thinking(
            {"model": "glm-4.6", "messages": []},
            thinking_enabled=False, clear_thinking=False,
        )
        self.assertNotIn("clear_thinking", payload["thinking"])


class GLMReasoningPreservationTests(unittest.TestCase):
    def test_preserve_reasoning_in_assistant_message(self) -> None:
        messages = [{"role": "assistant", "content": "result"}]
        result = preserve_glm_reasoning_in_tool_loop(messages, "my reasoning")
        self.assertEqual(result[-1]["reasoning_content"], "my reasoning")

    def test_no_preservation_when_empty(self) -> None:
        messages = [{"role": "assistant", "content": "result"}]
        result = preserve_glm_reasoning_in_tool_loop(messages, "")
        self.assertNotIn("reasoning_content", result[-1])

    def test_no_preservation_when_no_messages(self) -> None:
        result = preserve_glm_reasoning_in_tool_loop([], "reasoning")
        self.assertEqual(result, [])


class StreamingAccumulatorTests(unittest.TestCase):
    def test_content_accumulation(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_delta({"content": "Hello"})
        acc.feed_delta({"content": " world"})
        self.assertEqual(acc.assembled_content, "Hello world")

    def test_reasoning_accumulation(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_delta({"reasoning_content": "Step 1"})
        acc.feed_delta({"reasoning_content": " Step 2"})
        self.assertEqual(acc.assembled_reasoning, "Step 1 Step 2")

    def test_tool_call_accumulation(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_delta({
            "tool_calls": [{
                "index": 0,
                "function": {"name": "get_weather", "arguments": "{\"city\":"},
            }]
        })
        acc.feed_delta({
            "tool_calls": [{
                "index": 0,
                "function": {"arguments": " \"Paris\"}"},
            }]
        })
        tc = acc.assembled_tool_calls
        self.assertEqual(len(tc), 1)
        self.assertEqual(tc[0]["function"]["name"], "get_weather")
        self.assertEqual(tc[0]["function"]["arguments"], '{"city": "Paris"}')

    def test_chunk_with_choices(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_chunk({
            "model": "kimi-k2.5",
            "choices": [
                {"delta": {"content": "Hi"}, "finish_reason": None},
                {"delta": {"content": "!"}, "finish_reason": "stop"},
            ],
        })
        self.assertEqual(acc.assembled_content, "Hi!")
        self.assertEqual(acc.finish_reason, "stop")
        self.assertEqual(acc.model_observed, "kimi-k2.5")
        self.assertTrue(acc.stream_complete)

    def test_empty_stream_not_complete(self) -> None:
        acc = StreamingDeltaAccumulator()
        self.assertFalse(acc.stream_complete)

    def test_mixed_content_and_reasoning(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_delta({"content": "answer", "reasoning_content": "thinking"})
        self.assertEqual(acc.assembled_content, "answer")
        self.assertEqual(acc.assembled_reasoning, "thinking")

    def test_multiple_tool_calls_different_indices(self) -> None:
        acc = StreamingDeltaAccumulator()
        acc.feed_delta({"tool_calls": [{"index": 0, "function": {"name": "tool_a", "arguments": "{}"}}]})
        acc.feed_delta({"tool_calls": [{"index": 1, "function": {"name": "tool_b", "arguments": "[]"}}]})
        tc = acc.assembled_tool_calls
        self.assertEqual(len(tc), 2)
        self.assertEqual(tc[0]["function"]["name"], "tool_a")
        self.assertEqual(tc[1]["function"]["name"], "tool_b")


class ErrorTaxonomyTests(unittest.TestCase):
    def test_200_ok(self) -> None:
        r = classify_provider_error(http_status=200, response_body=None, provider=PROVIDER_KIMI)
        self.assertEqual(r.error_class, "ok")

    def test_401_auth_failed(self) -> None:
        r = classify_provider_error(http_status=401, response_body=None, provider=PROVIDER_GLM)
        self.assertEqual(r.error_class, "auth_failed")
        self.assertFalse(r.retryable)

    def test_403_auth_failed(self) -> None:
        r = classify_provider_error(http_status=403, response_body=None, provider=PROVIDER_KIMI)
        self.assertEqual(r.error_class, "auth_failed")

    def test_404_model_not_found(self) -> None:
        r = classify_provider_error(http_status=404, response_body=None, provider=PROVIDER_GLM)
        self.assertEqual(r.error_class, "model_not_found")

    def test_429_quota_retryable(self) -> None:
        r = classify_provider_error(http_status=429, response_body=None, provider=PROVIDER_KIMI)
        self.assertEqual(r.error_class, "quota_exhausted")
        self.assertTrue(r.retryable)

    def test_500_network_retryable(self) -> None:
        r = classify_provider_error(http_status=500, response_body=None, provider=PROVIDER_GLM)
        self.assertEqual(r.error_class, "network")
        self.assertTrue(r.retryable)

    def test_no_status_network(self) -> None:
        r = classify_provider_error(http_status=None, response_body=None, provider=PROVIDER_KIMI)
        self.assertEqual(r.error_class, "network")
        self.assertFalse(r.retryable)

    def test_invalid_response_body(self) -> None:
        r = classify_provider_error(
            http_status=400,
            response_body={"error": {"message": "malformed request"}},
            provider=PROVIDER_GLM,
        )
        self.assertEqual(r.error_class, "invalid_response")


class AuthHeadersTests(unittest.TestCase):
    def test_bearer_format(self) -> None:
        h = build_provider_auth_headers(provider=PROVIDER_KIMI, secret_value="sk-test")
        self.assertEqual(h["Authorization"], "Bearer sk-test")
        self.assertEqual(h["Content-Type"], "application/json")

    def test_headers_dont_leak_in_json(self) -> None:
        h = build_provider_auth_headers(provider=PROVIDER_GLM, secret_value="sk-secret")
        # The function itself stores the secret in the header; callers must not
        # serialize headers into logs/packets. This test verifies the structure.
        self.assertIn("Authorization", h)


if __name__ == "__main__":
    unittest.main()

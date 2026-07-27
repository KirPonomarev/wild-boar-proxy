from unittest import mock
import time
import unittest

from wild_boar_proxy.external_models import errors
from wild_boar_proxy.external_models import http_client
from wild_boar_proxy.runtime import RuntimeErrorInfo


class FakeResponse:
    def __init__(self, chunks: list[bytes], *, content_length: int | None = None) -> None:
        self._chunks = list(chunks)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.read_calls = 0
        self.timeouts: list[float] = []

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if size >= 0 and len(chunk) > size:
            self._chunks.insert(0, chunk[size:])
            return chunk[:size]
        return chunk

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)


class UnknownLengthKeepAliveJsonResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = bytearray(payload)
        self.headers: dict[str, str] = {}
        self.read_sizes: list[int] = []
        self.timeouts: list[float] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size != http_client.UNKNOWN_LENGTH_READ_CHUNK_BYTES:
            raise AssertionError("unknown-length response used blocking large read")
        if not self._payload:
            raise AssertionError("reader waited past complete JSON document")
        chunk = bytes(self._payload[:size])
        del self._payload[:size]
        return chunk

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)


class HttpClientTests(unittest.TestCase):
    def test_read_response_body_returns_complete_bytes(self) -> None:
        response = FakeResponse([b'{"ok":', b"true}", b""])

        body = http_client._read_response_body(
            response,
            started_at=time.monotonic(),
            timeout_seconds=1.0,
        )

        self.assertEqual(body, b'{"ok":true}')
        self.assertTrue(response.timeouts)

    def test_read_response_body_returns_complete_unknown_length_json(self) -> None:
        response = UnknownLengthKeepAliveJsonResponse(b'{"status":"ok"}')

        body = http_client._read_response_body(
            response,
            started_at=time.monotonic(),
            timeout_seconds=1.0,
        )

        self.assertEqual(body, b'{"status":"ok"}')
        self.assertTrue(response.timeouts)
        self.assertEqual(
            set(response.read_sizes),
            {http_client.UNKNOWN_LENGTH_READ_CHUNK_BYTES},
        )

    def test_read_response_body_enforces_total_deadline_between_chunks(self) -> None:
        response = FakeResponse([b"x", b"x"])

        with mock.patch(
            "wild_boar_proxy.external_models.http_client.time.monotonic",
            side_effect=[0.0, 0.02],
        ):
            with self.assertRaises(TimeoutError):
                http_client._read_response_body(
                    response,
                    started_at=0.0,
                    timeout_seconds=0.01,
                )

    def test_read_response_body_rejects_declared_body_above_cap_before_read(self) -> None:
        response = FakeResponse([b"{}"], content_length=9)

        with self.assertRaises(RuntimeErrorInfo) as raised:
            http_client._read_response_body(
                response,
                started_at=time.monotonic(),
                timeout_seconds=1.0,
                max_body_bytes=8,
            )

        self.assertEqual(raised.exception.machine_error_code, errors.INVALID_UPSTREAM_RESPONSE)
        self.assertEqual(response.read_calls, 0)

    def test_read_response_body_rejects_unknown_length_body_above_cap(self) -> None:
        response = FakeResponse([b'{"payload":"', b"abcdef", b'"}'])

        with self.assertRaises(RuntimeErrorInfo) as raised:
            http_client._read_response_body(
                response,
                started_at=time.monotonic(),
                timeout_seconds=1.0,
                max_body_bytes=16,
            )

        self.assertEqual(raised.exception.machine_error_code, errors.INVALID_UPSTREAM_RESPONSE)


if __name__ == "__main__":
    unittest.main()

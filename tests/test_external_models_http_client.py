from unittest import mock
import time
import unittest

from wild_boar_proxy.external_models import http_client


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.timeouts: list[float] = []

    def read(self, _size: int = -1) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""

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


if __name__ == "__main__":
    unittest.main()

"""Tests for RetryTransport."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from recursive_content_extractor.extractors.base import RetryTransport


class MockTransport(httpx.AsyncBaseTransport):
    """Transport that returns preconfigured responses in sequence."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._call_count >= len(self._responses):
            raise RuntimeError("MockTransport exhausted")
        item = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(item, Exception):
            raise item
        return item


def _make_response(status_code: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code=status_code, headers=headers or {})


def _make_request() -> httpx.Request:
    return httpx.Request("GET", "https://example.com")


@pytest.mark.asyncio
class TestRetryTransport:
    async def test_no_retry_on_success(self):
        inner = MockTransport([_make_response(200)])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 1

    async def test_no_retry_on_404(self):
        inner = MockTransport([_make_response(404)])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 404
        assert inner._call_count == 1

    async def test_retry_on_503_then_succeed(self):
        inner = MockTransport([_make_response(503), _make_response(200)])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_retry_on_429_then_succeed(self):
        inner = MockTransport([_make_response(429), _make_response(200)])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_retry_on_429_honors_retry_after(self):
        inner = MockTransport([
            _make_response(429, headers={"retry-after": "0"}),
            _make_response(200),
        ])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_exhaust_retries_returns_last_response(self):
        inner = MockTransport([
            _make_response(503),
            _make_response(503),
            _make_response(503),
        ])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 503
        assert inner._call_count == 3

    async def test_retry_on_connect_error_then_succeed(self):
        inner = MockTransport([
            httpx.ConnectError("connection reset"),
            _make_response(200),
        ])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_exhaust_retries_raises_connect_error(self):
        inner = MockTransport([
            httpx.ConnectError("fail 1"),
            httpx.ConnectError("fail 2"),
            httpx.ConnectError("fail 3"),
        ])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        with pytest.raises(httpx.ConnectError):
            await transport.handle_async_request(_make_request())
        assert inner._call_count == 3

    async def test_retry_on_read_timeout_then_succeed(self):
        inner = MockTransport([
            httpx.ReadTimeout("timeout"),
            _make_response(200),
        ])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_no_retry_on_write_timeout(self):
        inner = MockTransport([httpx.WriteTimeout("timeout")])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        with pytest.raises(httpx.WriteTimeout):
            await transport.handle_async_request(_make_request())
        assert inner._call_count == 1

    async def test_no_retry_on_pool_timeout(self):
        inner = MockTransport([httpx.PoolTimeout("pool full")])
        transport = RetryTransport(inner, max_retries=2, backoff_factor=0)

        with pytest.raises(httpx.PoolTimeout):
            await transport.handle_async_request(_make_request())
        assert inner._call_count == 1

    async def test_max_retries_zero_disables_retry(self):
        inner = MockTransport([_make_response(503)])
        transport = RetryTransport(inner, max_retries=0, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 503
        assert inner._call_count == 1

    async def test_retry_on_500(self):
        inner = MockTransport([_make_response(500), _make_response(200)])
        transport = RetryTransport(inner, max_retries=1, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_retry_on_502(self):
        inner = MockTransport([_make_response(502), _make_response(200)])
        transport = RetryTransport(inner, max_retries=1, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_retry_on_504(self):
        inner = MockTransport([_make_response(504), _make_response(200)])
        transport = RetryTransport(inner, max_retries=1, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_retry_on_connect_timeout(self):
        inner = MockTransport([
            httpx.ConnectTimeout("timeout"),
            _make_response(200),
        ])
        transport = RetryTransport(inner, max_retries=1, backoff_factor=0)

        resp = await transport.handle_async_request(_make_request())
        assert resp.status_code == 200
        assert inner._call_count == 2

    async def test_aclose_delegates(self):
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RetryTransport(inner, max_retries=1, backoff_factor=0)

        await transport.aclose()
        inner.aclose.assert_awaited_once()


@pytest.mark.asyncio
class TestGetClientRetryWiring:
    """Verify _get_client() wires RetryTransport correctly."""

    async def test_get_client_uses_retry_transport_when_enabled(self):
        from recursive_content_extractor.extractors.base import BaseExtractor
        from recursive_content_extractor.models import ExtractorConfig

        class DummyExtractor(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return False

            async def extract(self, url: str) -> Any:
                pass

        config = ExtractorConfig(max_retries=2, retry_backoff_factor=0.5)
        ext = DummyExtractor(config)
        client = await ext._get_client()
        try:
            assert isinstance(client._transport, RetryTransport)
        finally:
            await ext.close()

    async def test_get_client_uses_plain_transport_when_disabled(self):
        from recursive_content_extractor.extractors.base import BaseExtractor
        from recursive_content_extractor.models import ExtractorConfig

        class DummyExtractor(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return False

            async def extract(self, url: str) -> Any:
                pass

        config = ExtractorConfig(max_retries=0)
        ext = DummyExtractor(config)
        client = await ext._get_client()
        try:
            assert isinstance(client._transport, httpx.AsyncHTTPTransport)
        finally:
            await ext.close()

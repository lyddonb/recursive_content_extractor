"""Base extractor interface."""

from __future__ import annotations

import abc
import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from recursive_content_extractor.models import ExtractionResult, ExtractorConfig

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ResponseTooLarge(Exception):
    """A response body went over `ExtractorConfig.max_response_bytes`."""


class SizeLimitTransport(httpx.AsyncBaseTransport):
    """Refuse a response whose body is over `limit` bytes, by its Content-Length when it has
    one and by counting while it streams when it doesn't, so a huge body is never held whole."""

    def __init__(self, transport: httpx.AsyncBaseTransport, limit: int) -> None:
        self._transport = transport
        self._limit = limit

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._transport.handle_async_request(request)
        length = response.headers.get("Content-Length", "")
        if length.isdigit() and int(length) > self._limit:
            await response.aclose()
            raise ResponseTooLarge(f"{request.url} is {length} bytes, over {self._limit} bytes")
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=_CappedStream(response, self._limit, str(request.url)),
            request=request,
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()


class _CappedStream(httpx.AsyncByteStream):
    def __init__(self, response: httpx.Response, limit: int, url: str) -> None:
        self._response = response
        self._limit = limit
        self._url = url

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        seen = 0
        async for chunk in self._response.aiter_raw():
            seen += len(chunk)
            if seen > self._limit:
                raise ResponseTooLarge(f"{self._url} is over {self._limit} bytes")
            yield chunk

    async def aclose(self) -> None:
        await self._response.aclose()


class RetryTransport(httpx.AsyncBaseTransport):
    """Async HTTP transport that retries on transient failures.

    Wraps an inner transport and retries on connection errors, read timeouts,
    and retryable HTTP status codes (429, 500, 502, 503, 504).
    Uses exponential backoff with optional Retry-After header support.
    """

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
    ) -> None:
        self._transport = transport
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        last_exc: Exception | None = None
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._transport.handle_async_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._backoff_factor * (2**attempt)
                    logger.debug(
                        "Retry %d/%d for %s due to %s (delay=%.1fs)",
                        attempt + 1,
                        self._max_retries,
                        request.url,
                        type(exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                last_response = response
                delay = self._backoff_factor * (2**attempt)
                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        with contextlib.suppress(ValueError):
                            delay = max(delay, float(retry_after))
                logger.debug(
                    "Retry %d/%d for %s due to HTTP %d (delay=%.1fs)",
                    attempt + 1,
                    self._max_retries,
                    request.url,
                    response.status_code,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            return response

        # Exhausted retries -- return last response if we have one, else raise
        if last_response is not None:
            return last_response
        raise last_exc  # type: ignore[misc]

    async def aclose(self) -> None:
        await self._transport.aclose()


class BaseExtractor(abc.ABC):
    """Abstract base class for all content extractors.

    To create a custom extractor:
    1. Subclass BaseExtractor
    2. Implement can_handle() to match your URL patterns
    3. Implement extract() to return an ExtractionResult
    4. Register with RecursiveExtractor.register_extractor()
    """

    def __init__(self, config: ExtractorConfig | None = None):
        from recursive_content_extractor.models import ExtractorConfig

        self.config = config or ExtractorConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a shared HTTP client."""
        if self._client is None or self._client.is_closed:
            transport: httpx.AsyncBaseTransport = httpx.AsyncHTTPTransport()
            if self.config.max_retries > 0:
                transport = RetryTransport(
                    transport=transport,
                    max_retries=self.config.max_retries,
                    backoff_factor=self.config.retry_backoff_factor,
                )
            if self.config.max_response_bytes is not None:
                transport = SizeLimitTransport(transport, self.config.max_response_bytes)
            hooks = [self.config.request_hook] if self.config.request_hook else []
            self._client = httpx.AsyncClient(
                transport=transport,
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
                event_hooks={"request": hooks},
            )
        return self._client

    @staticmethod
    @abc.abstractmethod
    def can_handle(url: str) -> bool:
        """Return True if this extractor can handle the given URL."""
        ...

    @abc.abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content from the given URL."""
        ...

    @staticmethod
    def priority() -> int:
        """Higher priority extractors are checked first. Default: 0."""
        return 0

    async def close(self):
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

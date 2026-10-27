"""ExtractorConfig.request_hook and max_response_bytes: a caller's checks on every request."""

from __future__ import annotations

import httpx
import pytest

from recursive_content_extractor import ExtractorConfig, RecursiveExtractor


async def extract(url: str, **config: object):  # type: ignore[no-untyped-def]
    cfg = ExtractorConfig(depth=0, max_retries=0, rate_limit_delay=0, **config)  # type: ignore[arg-type]
    async with RecursiveExtractor(config=cfg) as extractor:
        return await extractor.extract(url)


ARTICLE = (
    "<html><body><article><p>" + "A real paragraph of text. " * 40 + "</p></article></body></html>"
)


@pytest.mark.asyncio
async def test_the_hook_sees_every_request_including_each_redirect(httpx_mock) -> None:
    httpx_mock.add_response(url="https://a.example/start", status_code=302,
                            headers={"Location": "https://b.example/end"})  # fmt: skip
    httpx_mock.add_response(url="https://b.example/end", text=ARTICLE,
                            headers={"Content-Type": "text/html"})  # fmt: skip
    seen: list[str] = []

    async def hook(request: httpx.Request) -> None:
        seen.append(str(request.url))

    node = await extract("https://a.example/start", request_hook=hook)

    assert seen == ["https://a.example/start", "https://b.example/end"]
    assert node.error is None and "A real paragraph" in node.content


@pytest.mark.asyncio
async def test_a_hook_that_raises_stops_the_request_before_it_is_sent(httpx_mock) -> None:
    httpx_mock.add_response(url="https://a.example/start", status_code=302,
                            headers={"Location": "http://169.254.169.254/latest"})  # fmt: skip

    async def hook(request: httpx.Request) -> None:
        if request.url.host.startswith("169.254."):
            raise PermissionError(f"refused {request.url.host}")

    node = await extract("https://a.example/start", request_hook=hook)

    assert node.error and "refused 169.254.169.254" in node.error
    assert [str(r.url) for r in httpx_mock.get_requests()] == ["https://a.example/start"]


@pytest.mark.asyncio
async def test_a_response_over_the_size_limit_is_refused(httpx_mock) -> None:
    httpx_mock.add_response(url="https://a.example/big", content=b"x" * 5000,
                            headers={"Content-Type": "text/html"})  # fmt: skip

    node = await extract("https://a.example/big", max_response_bytes=1000)

    assert node.error and "1000 bytes" in node.error


@pytest.mark.asyncio
async def test_the_size_limit_holds_without_a_content_length(httpx_mock) -> None:
    async def chunks():  # type: ignore[no-untyped-def]
        for _ in range(10):
            yield b"y" * 500

    httpx_mock.add_response(url="https://a.example/stream", stream=httpx.AsyncByteStream.__new__(
        type("S", (httpx.AsyncByteStream,), {"__aiter__": lambda self: chunks()})),
        headers={"Content-Type": "text/html"})  # fmt: skip

    node = await extract("https://a.example/stream", max_response_bytes=1000)

    assert node.error and "1000 bytes" in node.error


@pytest.mark.asyncio
async def test_without_the_options_nothing_changes(httpx_mock) -> None:
    httpx_mock.add_response(url="https://a.example/plain", text=ARTICLE,
                            headers={"Content-Type": "text/html"})  # fmt: skip

    node = await extract("https://a.example/plain")

    assert node.error is None and "A real paragraph" in node.content

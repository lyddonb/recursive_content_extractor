"""X/Twitter thread and post extractor.

Supports multiple extraction strategies:
1. Playwright (headless browser) — most reliable, renders full threads
2. syndication.twitter.com API — works without auth for single tweets
3. Nitter instances — fallback, no JS required
4. FixTweet/FxTwitter/VxTwitter — alternative embed APIs
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

import httpx

from extractors import BaseExtractor
from models import ContentType, ExtractionResult, ExtractorConfig

logger = logging.getLogger(__name__)

# Pattern to extract tweet/status ID from URL
STATUS_ID_PATTERN = re.compile(
    r'(?:twitter\.com|x\.com)/(\w+)/status/(\d+)'
)


class TwitterExtractor(BaseExtractor):
    """Extracts content from X/Twitter posts and threads.

    Strategy order:
    1. syndication API (no auth, single tweets)
    2. FxTwitter API (threads, no auth)
    3. Playwright browser (full thread rendering)
    """

    def __init__(self, config: ExtractorConfig | None = None):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )
        return self._client

    @staticmethod
    def can_handle(url: str) -> bool:
        """Handles twitter.com and x.com URLs."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
        return domain in ("twitter.com", "x.com")

    @staticmethod
    def priority() -> int:
        return 50  # Higher than article extractor

    async def extract(self, url: str) -> ExtractionResult:
        match = STATUS_ID_PATTERN.search(url)
        if not match:
            # Profile or non-status URL — fall back to article extractor
            return ExtractionResult(
                url=url,
                content_type=ContentType.X_POST,
                content="[Non-status X URL — profile or other page]",
                metadata={"url_type": "non_status"},
            )

        username = match.group(1)
        status_id = match.group(2)

        # Strategy 1: Try FxTwitter API (supports threads)
        result = await self._try_fxtwitter(url, username, status_id)
        if result and result.content:
            return result

        # Strategy 2: Try syndication API
        result = await self._try_syndication(url, username, status_id)
        if result and result.content:
            return result

        # Strategy 3: Try Playwright if enabled
        if self.config.use_browser:
            result = await self._try_playwright(url, username, status_id)
            if result and result.content:
                return result

        # Strategy 4: Return minimal info from URL
        logger.warning(f"All extraction strategies failed for {url}")
        return ExtractionResult(
            url=url,
            title=f"@{username} post",
            content=f"[Could not extract content from {url}. "
                    f"Try --browser flag or check if the post exists.]",
            content_type=ContentType.X_POST,
            metadata={"username": username, "status_id": status_id},
        )

    async def _try_fxtwitter(
        self, original_url: str, username: str, status_id: str
    ) -> ExtractionResult | None:
        """Use FxTwitter/FixTweet API for extraction.

        FxTwitter provides a JSON API at api.fxtwitter.com that returns
        tweet content, thread context, and media info without auth.
        """
        client = await self._get_client()
        api_url = f"https://api.fxtwitter.com/{username}/status/{status_id}"

        try:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                logger.debug(f"FxTwitter returned {resp.status_code} for {status_id}")
                return None

            data = resp.json()
            tweet = data.get("tweet", {})

            if not tweet:
                return None

            # Build content from tweet and thread
            parts = []
            author = tweet.get("author", {})
            author_name = author.get("name", username)
            author_handle = author.get("screen_name", username)

            parts.append(f"@{author_handle} ({author_name}):")
            parts.append(tweet.get("text", ""))

            # Thread / conversation
            if "thread" in tweet:
                thread_tweets = tweet["thread"]
                if isinstance(thread_tweets, list):
                    for i, t in enumerate(thread_tweets):
                        parts.append(f"\n--- Thread [{i+1}] ---")
                        parts.append(t.get("text", ""))

            # Quote tweet
            if "quote" in tweet and tweet["quote"]:
                qt = tweet["quote"]
                qt_author = qt.get("author", {}).get("screen_name", "?")
                parts.append(f"\n[Quoted @{qt_author}]: {qt.get('text', '')}")

            # Extract embedded media URLs
            links = []
            media = tweet.get("media", {})
            if media:
                for m in media.get("all", []):
                    if m.get("type") == "video":
                        url_val = m.get("url", "")
                        if url_val:
                            links.append(url_val)

            # Extract URLs from tweet entities
            urls_in_tweet = tweet.get("urls", [])
            if isinstance(urls_in_tweet, list):
                for u in urls_in_tweet:
                    expanded = u if isinstance(u, str) else u.get("url", "")
                    if expanded:
                        links.append(expanded)

            content = "\n".join(parts)

            return ExtractionResult(
                url=original_url,
                title=f"@{author_handle}: {content[:80]}...",
                content=content,
                content_type=ContentType.X_THREAD if "thread" in tweet else ContentType.X_POST,
                links=links,
                metadata={
                    "username": author_handle,
                    "status_id": status_id,
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "replies": tweet.get("replies", 0),
                    "created_at": tweet.get("created_at", ""),
                    "source": "fxtwitter",
                },
            )
        except Exception as e:
            logger.debug(f"FxTwitter extraction failed: {e}")
            return None

    async def _try_syndication(
        self, original_url: str, username: str, status_id: str
    ) -> ExtractionResult | None:
        """Use Twitter's syndication API (public, no auth).

        This endpoint is used by embedded tweets on websites.
        Works for single tweets but not full threads.
        """
        client = await self._get_client()
        api_url = (
            f"https://syndication.twitter.com/srv/timeline-profile/"
            f"screen-name/{username}"
        )
        tweet_url = f"https://cdn.syndication.twimg.com/tweet-result?id={status_id}&token=0"

        try:
            resp = await client.get(
                tweet_url,
                headers={"Referer": "https://platform.twitter.com/"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            text = data.get("text", "")
            user = data.get("user", {})
            name = user.get("name", username)
            screen_name = user.get("screen_name", username)

            if not text:
                return None

            # Extract links from entities
            links = []
            entities = data.get("entities", {})
            for url_entity in entities.get("urls", []):
                expanded = url_entity.get("expanded_url", "")
                if expanded:
                    links.append(expanded)

            return ExtractionResult(
                url=original_url,
                title=f"@{screen_name}: {text[:80]}...",
                content=f"@{screen_name} ({name}):\n{text}",
                content_type=ContentType.X_POST,
                links=links,
                metadata={
                    "username": screen_name,
                    "status_id": status_id,
                    "created_at": data.get("created_at", ""),
                    "source": "syndication",
                },
            )
        except Exception as e:
            logger.debug(f"Syndication extraction failed: {e}")
            return None

    async def _try_playwright(
        self, original_url: str, username: str, status_id: str
    ) -> ExtractionResult | None:
        """Use Playwright headless browser to render the full thread.

        This is the most reliable method but requires playwright to be installed.
        It renders the page fully and extracts all visible tweet text.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not installed, skipping browser strategy")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.config.user_agent,
                    viewport={"width": 1280, "height": 900},
                )
                page = await context.new_page()

                await page.goto(original_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)  # Extra time for tweets to load

                # Extract tweet text from the rendered page
                tweet_texts = await page.evaluate("""
                    () => {
                        const tweets = [];
                        // Main tweet and thread tweets
                        const tweetElements = document.querySelectorAll(
                            '[data-testid="tweetText"]'
                        );
                        tweetElements.forEach(el => {
                            tweets.push(el.innerText);
                        });
                        return tweets;
                    }
                """)

                # Extract all links from the page
                page_links = await page.evaluate("""
                    () => {
                        const links = [];
                        document.querySelectorAll('a[href]').forEach(a => {
                            const href = a.href;
                            if (href && !href.startsWith('javascript:')) {
                                links.push(href);
                            }
                        });
                        return [...new Set(links)];
                    }
                """)

                await browser.close()

                if not tweet_texts:
                    return None

                # Build content
                parts = [f"@{username} thread ({len(tweet_texts)} tweets):"]
                for i, text in enumerate(tweet_texts):
                    parts.append(f"\n[{i+1}/{len(tweet_texts)}] {text}")

                content = "\n".join(parts)

                # Filter links to interesting ones
                filtered_links = [
                    link for link in page_links
                    if not any(
                        skip in link for skip in [
                            "/login", "/signup", "analytics",
                            "/settings", "/compose", "/i/flow",
                        ]
                    )
                ]

                return ExtractionResult(
                    url=original_url,
                    title=f"@{username} thread",
                    content=content,
                    content_type=ContentType.X_THREAD,
                    links=filtered_links[:20],
                    metadata={
                        "username": username,
                        "status_id": status_id,
                        "tweet_count": len(tweet_texts),
                        "source": "playwright",
                    },
                )
        except Exception as e:
            logger.debug(f"Playwright extraction failed: {e}")
            return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

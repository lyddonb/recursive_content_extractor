"""YouTube video extractor.

Extracts video metadata and transcripts using multiple strategies:
1. youtube-transcript-api -- fastest, uses YouTube's built-in captions
2. yt-dlp -- reliable fallback, can extract auto-generated subs
3. oEmbed API -- metadata only (always works)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import parse_qs, urlparse

from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import ContentType, ExtractionResult

logger = logging.getLogger(__name__)

# Patterns to extract video IDs
YOUTUBE_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=)([\w-]{11})"),
    re.compile(r"(?:youtube\.com/embed/)([\w-]{11})"),
    re.compile(r"(?:youtube\.com/v/)([\w-]{11})"),
    re.compile(r"(?:youtube\.com/shorts/)([\w-]{11})"),
    re.compile(r"(?:youtu\.be/)([\w-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from various URL formats."""
    for pattern in YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)

    # Try query parameter parsing as fallback
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    v = params.get("v")
    if v:
        return v[0]

    return None


class YouTubeExtractor(BaseExtractor):
    """Extracts transcripts and metadata from YouTube videos."""

    @staticmethod
    def can_handle(url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        return domain in ("youtube.com", "youtu.be", "m.youtube.com")

    @staticmethod
    def priority() -> int:
        return 50

    async def extract(self, url: str) -> ExtractionResult:
        video_id = extract_video_id(url)
        if not video_id:
            return ExtractionResult(
                url=url,
                content_type=ContentType.YOUTUBE,
                content="[Could not extract video ID from URL]",
                metadata={"error": "no_video_id"},
            )

        canonical_url = f"https://www.youtube.com/watch?v={video_id}"

        # Get metadata via oEmbed (always works)
        metadata = await self._get_oembed_metadata(video_id)

        # Try to get transcript
        transcript = await self._get_transcript(video_id)

        title = metadata.get("title", f"YouTube video {video_id}")
        author = metadata.get("author_name", "Unknown")

        # Build content
        parts = []
        parts.append(f"Title: {title}")
        parts.append(f"Channel: {author}")

        if transcript:
            parts.append("\n--- Transcript ---\n")
            parts.append(transcript)
        else:
            parts.append("\n[Transcript not available]")

        # Extract related links from description (if we got it)
        links = metadata.get("description_links", [])

        return ExtractionResult(
            url=canonical_url,
            title=title,
            content="\n".join(parts),
            content_type=ContentType.YOUTUBE,
            links=links,
            metadata={
                "video_id": video_id,
                "author": author,
                "author_url": metadata.get("author_url", ""),
                "thumbnail": metadata.get("thumbnail_url", ""),
                "has_transcript": bool(transcript),
            },
        )

    async def _get_oembed_metadata(self, video_id: str) -> dict:
        """Get video metadata via YouTube's oEmbed endpoint."""
        client = await self._get_client()
        oembed_url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}"
            f"&format=json"
        )
        try:
            resp = await client.get(oembed_url)
            if resp.status_code == 200:
                return dict(resp.json())
        except Exception as e:
            logger.debug(f"oEmbed fetch failed: {e}")
        return {}

    async def _get_transcript(self, video_id: str) -> str | None:
        """Get video transcript using available methods."""
        # Strategy 1: youtube-transcript-api
        transcript = await self._try_transcript_api(video_id)
        if transcript:
            return transcript

        # Strategy 2: Direct page parsing
        transcript = await self._try_page_parsing(video_id)
        if transcript:
            return transcript

        return None

    async def _try_transcript_api(self, video_id: str) -> str | None:
        """Use youtube-transcript-api library."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            transcript_list = await asyncio.to_thread(api.fetch, video_id)

            if transcript_list:
                parts = []
                for snippet in transcript_list:
                    start = int(snippet.start)
                    minutes, seconds = divmod(start, 60)
                    hours, minutes = divmod(minutes, 60)
                    timestamp = (
                        f"{hours}:{minutes:02d}:{seconds:02d}"
                        if hours
                        else f"{minutes}:{seconds:02d}"
                    )
                    text = snippet.text.strip()
                    if text:
                        parts.append(f"[{timestamp}] {text}")

                return "\n".join(parts)

        except ImportError:
            logger.debug("youtube-transcript-api not installed")
        except Exception as e:
            logger.debug(f"Transcript API failed for {video_id}: {e}")

        return None

    async def _try_page_parsing(self, video_id: str) -> str | None:
        """Try to extract transcript data from the YouTube page HTML."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            html = resp.text

            pattern = re.compile(
                r'"captions":\s*(\{.*?"playerCaptionsTracklistRenderer".*?\})'
                r'\s*,\s*"videoDetails"'
            )
            match = pattern.search(html)
            if not match:
                return None

            captions_json = match.group(1)
            captions_data = json.loads(captions_json)

            tracks = captions_data.get("playerCaptionsTracklistRenderer", {}).get(
                "captionTracks", []
            )

            if not tracks:
                return None

            # Prefer English, fall back to first available
            track_url = None
            for track in tracks:
                if track.get("languageCode", "").startswith("en"):
                    track_url = track.get("baseUrl")
                    break
            if not track_url and tracks:
                track_url = tracks[0].get("baseUrl")

            if not track_url:
                return None

            caption_resp = await client.get(track_url + "&fmt=json3")
            if caption_resp.status_code != 200:
                return None

            caption_data = caption_resp.json()
            events = caption_data.get("events", [])

            parts = []
            for event in events:
                start_ms = event.get("tStartMs", 0)
                start_s = start_ms // 1000
                minutes, seconds = divmod(start_s, 60)
                hours, minutes = divmod(minutes, 60)
                timestamp = (
                    f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
                )

                segs = event.get("segs", [])
                text = "".join(s.get("utf8", "") for s in segs).strip()
                if text and text != "\n":
                    parts.append(f"[{timestamp}] {text}")

            return "\n".join(parts) if parts else None

        except Exception as e:
            logger.debug(f"Page parsing failed for {video_id}: {e}")
            return None

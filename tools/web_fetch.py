"""Web page fetcher tool for Terramon agents.

Phase 12 (Agents & Tools): retrieves and extracts text content from web pages
so agents can read articles, docs, or reference material.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

from terramon.ports.tool_port import ToolPort, ToolResult

log = logging.getLogger("terramon.tools.web_fetch")

FETCH_TIMEOUT = 20
MAX_CHARS = 5000


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract plain text."""

    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._text.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._text)


@dataclass
class WebFetchTool:
    """Fetch and extract plain text from a web page."""

    name: str = "web_fetch"
    description: str = (
        "Fetch the content of a web page and extract its readable text. "
        "Provide a URL to read articles, documentation, or reference material. "
        "Returns up to 5000 characters of extracted text."
    )
    timeout: int = FETCH_TIMEOUT
    max_chars: int = MAX_CHARS

    def run(self, url: str = "", **kwargs: str) -> ToolResult:
        """Fetch a web page and return its text content.

        Args:
            url: The URL to fetch.

        Returns:
            ToolResult with extracted text content.
        """
        if not url:
            return ToolResult(success=False, output="", error="No URL provided")

        # Basic URL validation
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid URL: {url}",
            )

        try:
            return self._fetch(url)
        except Exception as exc:
            log.error("Web fetch failed for %s: %s", url, exc)
            return ToolResult(
                success=False,
                output="",
                error=f"Fetch failed: {exc}",
            )

    def _fetch(self, url: str) -> ToolResult:
        """Download and extract text from a URL."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Terramon/1.0 (educational project; contact@terramon.game)",
                "Accept": "text/html,application/xhtml+xml,text/plain",
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()

        # Try to detect encoding
        content_type = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        charset_match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
        if charset_match:
            charset = charset_match.group(1)

        try:
            html = raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html = raw.decode("utf-8", errors="replace")

        # Extract text
        extractor = _HTMLTextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            # Fallback: rough tag stripping
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
        else:
            text = extractor.get_text()

        # Limit length
        if len(text) > self.max_chars:
            text = text[:self.max_chars] + "\n\n... [truncated]"

        if not text.strip():
            return ToolResult(
                success=True,
                output="Page appears to have no readable text content.",
            )

        return ToolResult(
            success=True,
            output=f"Content from {url}:\n\n{text.strip()}",
        )

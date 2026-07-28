"""DuckDuckGo web search tool for Terramon agents.

Phase 12 (Agents & Tools): provides live web search capability to agents
like Scout, using the DuckDuckGo Lite API (no API key required).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from terramon.ports.tool_port import ToolPort, ToolResult

log = logging.getLogger("terramon.tools.web_search")

SEARCH_TIMEOUT = 15
MAX_RESULTS = 5


@dataclass
class WebSearchTool:
    """DuckDuckGo Lite HTML search — parses results from the HTML response."""

    name: str = "web_search"
    description: str = (
        "Search the web for information about a topic. "
        "Returns a list of results with titles, URLs, and snippets. "
        "Use this to research real-world objects, species, places, or concepts."
    )
    timeout: int = SEARCH_TIMEOUT
    max_results: int = MAX_RESULTS

    def run(self, query: str = "", **kwargs: str) -> ToolResult:
        """Execute a DuckDuckGo Lite search.

        Args:
            query: The search query string.

        Returns:
            ToolResult with formatted search results.
        """
        if not query:
            return ToolResult(success=False, output="", error="No query provided")

        try:
            return self._search(query)
        except Exception as exc:
            log.error("Web search failed for %r: %s", query, exc)
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {exc}",
            )

    def _search(self, query: str) -> ToolResult:
        """Hit DuckDuckGo Lite HTML endpoint and extract results."""
        params = urllib.parse.urlencode({"q": query})
        url = f"https://lite.duckduckgo.com/lite/?{params}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Terramon/1.0 (educational project; contact@terramon.game)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Parse DDG Lite HTML results
        results = self._parse_results(html)

        if not results:
            return ToolResult(
                success=True,
                output="No results found.",
            )

        lines = [f"DuckDuckGo search results for: {query}", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            lines.append(f"   {r['snippet']}")
            lines.append("")

        return ToolResult(success=True, output="\n".join(lines).strip())

    @staticmethod
    def _parse_results(html: str) -> list[dict[str, str]]:
        """Parse DuckDuckGo Lite HTML to extract result links.

        DDG Lite uses a simple table structure:
        <tr><td class="result-snippet">snippet</td></tr>
        with preceding <a> tags for the title/URL.
        """
        results: list[dict[str, str]] = []
        # Simple state-machine parser
        lines = html.splitlines()
        current: dict[str, str] = {}
        in_result = False

        for line in lines:
            stripped = line.strip()

            # Find result links
            if 'class="result-link"' in stripped or 'class="result-snippet"' in stripped:
                if 'result-link' in stripped:
                    # New result
                    if current:
                        results.append(current)
                    current = {"title": "", "url": "", "snippet": ""}

                    # Extract URL from href
                    href_start = stripped.find('href="')
                    if href_start >= 0:
                        href_start += 6
                        href_end = stripped.find('"', href_start)
                        if href_end > href_start:
                            current["url"] = stripped[href_start:href_end]

                    # Extract title text
                    import re
                    title_match = re.search(r'>([^<]+)<', stripped[stripped.find('">') + 2:])
                    if title_match:
                        current["title"] = title_match.group(1).strip()

                elif 'result-snippet' in stripped:
                    # Extract snippet text
                    import re
                    snippet_match = re.search(r'>([^<]+)<', stripped)
                    if snippet_match:
                        current["snippet"] = snippet_match.group(1).strip()

        if current:
            results.append(current)

        return results[:MAX_RESULTS]

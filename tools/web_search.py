"""Web search - let agents search the internet via DuckDuckGo.

Uses DuckDuckGoSearchResults for richer output with multiple results,
titles, URLs, and longer snippets. Also includes a web_read tool
for fetching full text content from URLs found during search.
No API key needed - DuckDuckGo is free and anonymous.
Ref: https://python.langchain.com/docs/integrations/tools/ddg/
Ref: https://pypi.org/project/duckduckgo-search/
"""

import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool
from logging_utils import log_panel
from config import WEB_SEARCH_NUM_RESULTS, WEB_READ_MAX_CHARS


# --- Shared search instance ---
# num_results configured in config.py (WEB_SEARCH_NUM_RESULTS).

_ddg = DuckDuckGoSearchResults(num_results=WEB_SEARCH_NUM_RESULTS)


# --- HTML text extractor ---

class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text converter. Strips tags, scripts, and styles."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._skip = False
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._text.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        raw = "".join(self._text)
        # -- Collapse whitespace but keep paragraph breaks --
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _extract_page_text(html: str, max_chars: int = WEB_READ_MAX_CHARS) -> str:
    """Convert HTML to readable text, capped at max_chars."""
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    text = extractor.get_text()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n... [truncated]"
    return text


# --- Web search tool ---

@tool(parse_docstring=True)
def web_search(query: str, reasoning: str = "") -> str:
    """Search the internet for current information.

    Use this when you need facts, documentation, recent news, or
    anything not already in the knowledge base or database.
    Returns up to 6 results with titles, URLs, and content snippets.
    Do MULTIPLE searches with different queries to get a thorough picture.

    Args:
        query: The search query (natural language or keywords).
        reasoning: Optional. Why you need to search the web.

    Returns:
        Search results with titles, URLs, and snippets.
    """
    if reasoning:
        log_panel(reasoning, title="web_search - Reasoning")
    log_panel(query, title="web_search - Query")
    try:
        result = _ddg.run(query)
    except Exception as e:
        result = f"Search failed: {e}"
    log_panel(result[:800], title="web_search - Result")
    return result


@tool(parse_docstring=True)
def web_read(url: str, reasoning: str = "") -> str:
    """Fetch and read the text content of a web page.

    Use this AFTER web_search to read the full content of a promising URL.
    Returns the page text stripped of HTML tags, scripts, and navigation.
    Great for reading articles, documentation, tutorials, and reference pages.

    Args:
        url: The full URL to fetch (e.g. "https://example.com/page").
        reasoning: Optional. Why you are reading this page.

    Returns:
        The page text content (up to 12000 chars), or an error message.
    """
    if reasoning:
        log_panel(reasoning, title="web_read - Reasoning")
    log_panel(url, title="web_read - Fetching")

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (QueryMaster/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            # -- Only read text content --
            content_type = resp.headers.get("Content-Type", "")
            if "text" not in content_type and "html" not in content_type:
                return f"Not a text page (Content-Type: {content_type}). Use for HTML/text URLs only."
            html = resp.read(500_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return f"HTTP error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Connection failed: {e.reason}"
    except Exception as e:
        return f"Fetch failed: {e}"

    text = _extract_page_text(html)
    if not text.strip():
        return "Page loaded but no readable text content found (might be JS-rendered)."

    log_panel(f"{len(text)} chars extracted", title="web_read - Done")
    return text


# --- Accessor ---

def get_web_tools() -> list:
    """Web tools - search the internet and read web pages."""
    return [web_search, web_read]

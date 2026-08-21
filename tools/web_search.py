"""Web search — let agents search the internet via DuckDuckGo.

Uses langchain_community's DuckDuckGoSearchRun under the hood.
No API key needed — DuckDuckGo is free and anonymous.
Ref: https://python.langchain.com/docs/integrations/tools/ddg/
Ref: https://pypi.org/project/duckduckgo-search/
"""

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from logging_utils import log_panel


# --- Shared search instance ---

_ddg = DuckDuckGoSearchRun()


# --- Web search tool ---

@tool(parse_docstring=True)
def web_search(query: str, reasoning: str = "") -> str:
    """Search the internet for current information.

    Use this when you need facts, documentation, recent news, or
    anything not already in the knowledge base or database.

    Args:
        query: The search query (natural language or keywords).
        reasoning: Optional. Why you need to search the web.

    Returns:
        Search results as text (top results summarized).
    """
    if reasoning:
        log_panel(reasoning, title="web_search - Reasoning")
    log_panel(query, title="web_search - Query")
    try:
        result = _ddg.run(query)
    except Exception as e:
        result = f"Search failed: {e}"
    log_panel(result[:500], title="web_search - Result")
    return result


# --- Accessor ---

def get_web_tools() -> list:
    """Web search tools — internet access via DuckDuckGo."""
    return [web_search]

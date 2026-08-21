"""Knowledge base tools - let agents save and retrieve learned information.

Agents call save_knowledge() to store useful findings (query patterns,
web search results, translations, code snippets). On future requests,
search_knowledge() checks the Wissensdatenbank first so the system
improves over time.
Ref: https://docs.python.org/3/library/sqlite3.html
"""

from langchain_core.tools import tool
from logging_utils import log_panel
from knowledge_store import save_entry, search_entries


# --- Knowledge tools ---

@tool(parse_docstring=True)
def save_knowledge(topic: str, content: str, reasoning: str = "") -> str:
    """Save a piece of information to the knowledge base for future use.

    Use this whenever you learn something useful that could help with
    future questions: query patterns, definitions, translations, code
    snippets, or domain-specific facts.

    Args:
        topic: Short label for this knowledge (e.g. "SQL join syntax",
               "German greetings", "ecommerce schema").
        content: The actual knowledge to save. Be specific and concise.
        reasoning: Optional. Why you are saving this.

    Returns:
        Confirmation message with the entry ID.
    """
    if reasoning:
        log_panel(reasoning, title="save_knowledge - Reasoning")
    entry = save_entry(topic, content, source="agent")
    log_panel(
        f"Topic: {topic}\nContent: {content[:200]}",
        title="save_knowledge - Saved",
    )
    return f"Saved to knowledge base (ID {entry['id']}): {topic}"


@tool(parse_docstring=True)
def search_knowledge(query: str, reasoning: str = "") -> str:
    """Search the knowledge base for previously saved information.

    Check this BEFORE doing expensive operations (web search, database
    queries) - the answer might already be stored.

    Args:
        query: What to search for (keywords or a short phrase).
        reasoning: Optional. Why you are searching.

    Returns:
        Matching knowledge entries, or a message if nothing was found.
    """
    if reasoning:
        log_panel(reasoning, title="search_knowledge - Reasoning")
    entries = search_entries(query, limit=5)
    if not entries:
        result = f"No knowledge found for: {query}"
    else:
        lines = []
        for e in entries:
            lines.append(f"[{e['topic']}] {e['content']}")
        result = "\n---\n".join(lines)
    log_panel(result[:500], title="search_knowledge - Result")
    return result


# --- Accessor ---

def get_knowledge_tools() -> list:
    """Knowledge base tools - save and search learned information."""
    return [save_knowledge, search_knowledge]

"""Log tools - let the AI inspect its own action history."""

from langchain_core.tools import tool
from logging_utils import log_panel
from action_logger import read_log


@tool(parse_docstring=True)
def view_action_log(last_n: int = 30, reasoning: str = "") -> str:
    """View the most recent entries in the AI action log.

    Args:
        last_n: Number of recent log lines to show. Defaults to 30.
        reasoning: Optional. Why you want to view the log.

    Returns:
        The last N lines from the action log.
    """
    if reasoning:
        log_panel(reasoning, title="view_action_log - Reasoning")
    result = read_log(last_n)
    log_panel(result[:500], title="view_action_log - Result")
    return result


@tool(parse_docstring=True)
def search_action_log(keyword: str, reasoning: str = "") -> str:
    """Search the action log for lines containing a keyword.

    Args:
        keyword: The text to search for in log entries.
        reasoning: Optional. Why you are searching the log.

    Returns:
        Matching log lines.
    """
    if reasoning:
        log_panel(reasoning, title=f"search_action_log({keyword}) - Reasoning")
    full_log = read_log(last_n=500)
    matches = [line for line in full_log.splitlines() if keyword.lower() in line.lower()]
    result = "\n".join(matches) if matches else f"No log entries matching '{keyword}'"
    log_panel(result[:500], title=f"search_action_log({keyword}) - Result")
    return result


def get_log_tools() -> list:
    return [view_action_log, search_action_log]

"""Delegation tool - lets agents hand off tasks to each other.

Example: SQL agent gets data, then delegates to translator agent
to translate the results into another language.
"""

from langchain_core.tools import tool
from logging_utils import log_panel
from action_logger import log_tool_call, log_tool_result

_delegation_depth = 0
MAX_DEPTH = 2


@tool(parse_docstring=True)
def delegate_task(agent_name: str, task: str, reasoning: str = "") -> str:
    """Send a task to another specialized agent and get their response.

    Use this when the task needs a different expert. Available agents:
    - sql: queries databases, finds data
    - translator: translates text between languages
    - coder: writes, explains, and debugs code
    - reviewer: reviews code for bugs, security, performance (read-only)
    - planner: breaks down complex tasks, builds execution plans

    Args:
        agent_name: Which agent to use (sql, translator, or coder).
        task: Clear description of what the other agent should do. Be specific.
        reasoning: Optional. Why you are delegating this task.

    Returns:
        The other agent's complete response.
    """
    global _delegation_depth
    if _delegation_depth >= MAX_DEPTH:
        return "Cannot delegate further - maximum depth reached."

    from agents import AGENTS
    from config import create_model_for_agent

    if agent_name not in AGENTS:
        available = ", ".join(AGENTS.keys())
        return f"Unknown agent '{agent_name}'. Available: {available}"

    if reasoning:
        log_panel(reasoning, title="Delegation - Reasoning")
    log_panel(f"Delegating to {agent_name}: {task}", title="Delegation")
    log_tool_call("delegation", agent_name, {"task": task})

    agent_cls = AGENTS[agent_name]
    agent = agent_cls()
    model = create_model_for_agent(agent_name)

    own_tools = agent.get_tools()
    if own_tools:
        model = model.bind_tools(own_tools)

    history = agent.create_history()

    _delegation_depth += 1
    try:
        result = agent.ask(task, history, model, max_iterations=8)
    except Exception as e:
        result = f"Agent '{agent_name}' failed: {e}"
    finally:
        _delegation_depth -= 1

    log_tool_result("delegation", agent_name, result)
    return result


def get_delegation_tools() -> list:
    return [delegate_task]

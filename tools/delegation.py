"""Delegation tool - lets agents hand off tasks to each other.

Example: SQL agent gets data, then delegates to translator agent
to translate the results into another language.

The delegation context (internet access, thinking mode, model name)
is injected by set_delegation_context() before each request so that
delegated agents inherit the parent's settings.
"""

from langchain_core.tools import tool
from logging_utils import log_panel
from action_logger import log_tool_call, log_tool_result
from config import MAX_DELEGATION_DEPTH, MAX_DELEGATION_ITERATIONS

_delegation_depth = 0

# -- Parent context passed to delegated agents --
_delegation_ctx = {
    "include_internet": True,
    "thinking_enabled": None,
    "model_name": None,
    "num_ctx": 8192,
}


def set_delegation_context(
    include_internet: bool = True,
    thinking_enabled=None,
    model_name: str | None = None,
    num_ctx: int = 8192,
):
    """Set the context that delegated agents inherit.

    Called by server.py before each request so that delegated agents
    use the same model, internet access, and thinking mode as the parent.
    """
    _delegation_ctx["include_internet"] = include_internet
    _delegation_ctx["thinking_enabled"] = thinking_enabled
    _delegation_ctx["model_name"] = model_name
    _delegation_ctx["num_ctx"] = num_ctx


@tool(parse_docstring=True)
def delegate_task(agent_name: str, task: str, reasoning: str = "") -> str:
    """Send a task to another specialized agent and get their response.

    Use this when the task needs a different expert. Available agents:
    - sql: queries databases, finds data
    - translator: translates text between languages
    - coder: writes, explains, and debugs code (has write_file and create_spreadsheet)
    - reviewer: reviews code for bugs, security, performance (read-only)
    - planner: breaks down complex tasks, builds execution plans

    IMPORTANT: Be VERY specific in your task description. Include:
    - Exactly what to create/do
    - What content/data to include
    - File names and formats expected
    - Any research the delegated agent should do first

    Args:
        agent_name: Which agent to use (sql, translator, coder, reviewer, planner).
        task: Detailed description of what the other agent should do. Be specific and thorough.
        reasoning: Optional. Why you are delegating this task.

    Returns:
        The other agent's complete response.
    """
    global _delegation_depth
    if _delegation_depth >= MAX_DELEGATION_DEPTH:
        return "Cannot delegate further - maximum depth reached."

    from agents import AGENTS
    from config import create_model, ModelConfig, model_supports_thinking

    if agent_name not in AGENTS:
        available = ", ".join(AGENTS.keys())
        return f"Unknown agent '{agent_name}'. Available: {available}"

    if reasoning:
        log_panel(reasoning, title="Delegation - Reasoning")
    log_panel(f"Delegating to {agent_name}: {task[:200]}", title="Delegation")
    log_tool_call("delegation", agent_name, {"task": task[:300]})

    # -- Create agent with parent's context --
    agent_cls = AGENTS[agent_name]
    include_internet = _delegation_ctx.get("include_internet", True)
    thinking = _delegation_ctx.get("thinking_enabled")

    agent = agent_cls(
        include_internet=include_internet,
        thinking_enabled=thinking,
    )

    # -- Use parent's model if available, else agent's default --
    model_name = _delegation_ctx.get("model_name") or agent_cls.DEFAULT_MODEL
    num_ctx = _delegation_ctx.get("num_ctx", 8192)

    # -- Check thinking support for the actual model --
    reasoning_flag = None
    if agent.thinking_enabled and model_supports_thinking(model_name):
        reasoning_flag = True

    model = create_model(
        ModelConfig(
            name=model_name,
            temperature=agent_cls.DEFAULT_TEMPERATURE,
            reasoning=reasoning_flag,
        ),
        num_ctx=num_ctx,
    )

    # -- Bind agent's own tools (not delegation - prevent infinite loops) --
    own_tools = agent.get_tools()
    if own_tools:
        model = model.bind_tools(own_tools)

    history = agent.create_history(query=task)

    _delegation_depth += 1
    try:
        result = agent.ask(
            task, history, model,
            max_iterations=MAX_DELEGATION_ITERATIONS,
            include_delegation=(_delegation_depth < MAX_DELEGATION_DEPTH),
            num_ctx=num_ctx,
        )
    except Exception as e:
        result = f"Agent '{agent_name}' failed: {e}"
    finally:
        _delegation_depth -= 1

    log_tool_result("delegation", agent_name, result[:500])
    return result


def get_delegation_tools() -> list:
    return [delegate_task]

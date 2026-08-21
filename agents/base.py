"""Base agent - shared logic that all agents use.

To create a new agent:
  1. Subclass BaseAgent
  2. Set AGENT_NAME, DESCRIPTION, and SYSTEM_PROMPT
  3. Override get_tools() to return the tools this agent can use
  4. Drop the file in agents/ - auto-discovery handles the rest
"""

import json
import re
import uuid
from datetime import datetime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from logging_utils import log_panel
from action_logger import log_query, log_tool_call, log_tool_result, log_response, log_error

MAX_ITERATIONS = 15


# --- Tool severity map ---
# Used by the frontend to show severity badges on each tool call.
# low = read-only / safe, medium = modifies data, high = writes files / destructive.

TOOL_SEVERITY = {
    # -- Read (green) --
    "read_file":         "low",
    "list_files":        "low",
    "search_knowledge":  "low",
    "web_search":        "low",
    "search_github":     "low",
    "github_tree":       "low",
    "github_file":       "low",
    "list_tables":       "low",
    "describe_table":    "low",
    "delegate_task":     "medium",
    # -- Modify (yellow) --
    "save_knowledge":    "medium",
    "execute_sql":       "medium",
    # -- Write (red) --
    "write_file":        "high",
}


# --- Tool usage guide ---
# Appended to every agent's system prompt so they know the search priority
# and auto-save useful findings to the knowledge base.

TOOL_GUIDE = """
TOOL USAGE PRIORITY:
1. FIRST check the knowledge base (search_knowledge) - you may already know the answer from a previous session.
2. THEN check local files (list_files, read_file) - the answer might be in the project.
3. ONLY THEN search the internet (web_search) or GitHub (search_github, github_file) for external references.
4. When you find useful code, patterns, or information - ALWAYS save it with save_knowledge so you remember it next time.
   Use a clear topic (e.g. "python: flask routing", "sql: window functions") and include the source in the content.
"""

CONFIRMATION_GUIDE = """
CONFIRMATION MODE IS ON:
Before executing any write or modify operation (write_file, execute_sql with INSERT/UPDATE/DELETE),
you MUST first describe exactly what you plan to change and ask for user confirmation.
Format your request as: "I want to [describe action]. Shall I proceed?"
Do NOT execute the operation until the user explicitly says "yes", "go ahead", "do it", or similar.
If the user says "no" or "cancel", acknowledge and do not execute.
"""


class BaseAgent:
    AGENT_NAME = "base"
    DISPLAY_NAME = "Base Agent"
    DESCRIPTION = "A generic assistant."
    SYSTEM_PROMPT = "You are a helpful assistant."
    DEFAULT_MODEL = "qwen2.5-coder:7b"
    DEFAULT_TEMPERATURE = 0.0

    def __init__(self, include_internet: bool = True,
                 confirmation_mode: bool = False):
        self.include_internet = include_internet
        self.confirmation_mode = confirmation_mode
        self.tool_events = []

    def get_tools(self) -> list:
        """Base tools for every agent: read-only files + knowledge base.
        When internet is enabled, also includes web search + GitHub.
        Override in subclasses and call super().get_tools() to keep these."""
        from tools.file_tools import get_file_read_tools
        from tools.knowledge import get_knowledge_tools
        tools = get_file_read_tools() + get_knowledge_tools()
        if self.include_internet:
            from tools.web_search import get_web_tools
            from tools.github import get_github_tools
            tools += get_web_tools() + get_github_tools()
        return tools

    def get_all_tools(self, include_delegation: bool = True) -> list:
        tools = list(self.get_tools())
        if include_delegation:
            from tools.delegation import get_delegation_tools
            tools += get_delegation_tools()
        return tools

    def get_tool_names(self, include_delegation: bool = True) -> set:
        return {t.name for t in self.get_all_tools(include_delegation)}

    @staticmethod
    def _tool_severity(tool_name: str) -> str:
        """Return severity level for a tool: low / medium / high."""
        return TOOL_SEVERITY.get(tool_name, "low")

    def create_history(self) -> list[BaseMessage]:
        prompt = self.SYSTEM_PROMPT.replace(
            "{current_datetime}",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        prompt += TOOL_GUIDE
        if self.confirmation_mode:
            prompt += CONFIRMATION_GUIDE
        return [SystemMessage(content=prompt)]

    def bind_tools(self, model: BaseChatModel, include_delegation: bool = True) -> BaseChatModel:
        tools = self.get_all_tools(include_delegation)
        if tools:
            return model.bind_tools(tools)
        return model

    def _call_tool(self, tool_call, include_delegation: bool = True) -> ToolMessage:
        tools_by_name = {t.name: t for t in self.get_all_tools(include_delegation)}
        if tool_call["name"] not in tools_by_name:
            return ToolMessage(
                content=f"Unknown tool: {tool_call['name']}",
                tool_call_id=tool_call["id"],
            )
        tool_fn = tools_by_name[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        return ToolMessage(content=str(result), tool_call_id=tool_call["id"])

    def _parse_tool_call_from_text(self, content: str, include_delegation: bool = True) -> dict | None:
        """Extract tool calls from text when model outputs JSON instead of structured tool_calls."""
        tag_match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL)
        candidates = []
        if tag_match:
            candidates.append(tag_match.group(1).strip())

        i = 0
        while i < len(content):
            if content[i] == '{':
                depth = 0
                start = i
                for j in range(i, len(content)):
                    if content[j] == '{':
                        depth += 1
                    elif content[j] == '}':
                        depth -= 1
                    if depth == 0:
                        candidates.append(content[start:j + 1])
                        i = j + 1
                        break
                else:
                    break
            else:
                i += 1

        tool_names = self.get_tool_names(include_delegation)
        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "name" in data and data["name"] in tool_names:
                return {
                    "name": data["name"],
                    "args": data.get("arguments", {}),
                    "id": str(uuid.uuid4()),
                }
        return None

    def ask(
        self,
        query: str,
        history: list[BaseMessage],
        model: BaseChatModel,
        max_iterations: int = MAX_ITERATIONS,
        include_delegation: bool = True,
    ) -> str:
        self.tool_events = []
        history.append(HumanMessage(content=query))
        log_panel(query, title=f"[{self.DISPLAY_NAME}] User Query")
        log_query(self.DISPLAY_NAME, query)

        iteration = 0
        while iteration < max_iterations:
            response = model.invoke(history)

            tool_calls = response.tool_calls

            if not tool_calls and response.content:
                parsed = self._parse_tool_call_from_text(
                    str(response.content), include_delegation
                )
                if parsed:
                    tool_calls = [parsed]
                    response = AIMessage(content="", tool_calls=tool_calls)

            history.append(response)

            if not tool_calls:
                log_panel(str(response.content), title=f"[{self.DISPLAY_NAME}] Final Response")
                log_response(self.DISPLAY_NAME, str(response.content))
                return str(response.content)

            for tool_call in tool_calls:
                severity = self._tool_severity(tool_call["name"])
                args = tool_call.get("args", {})

                log_panel(
                    f"Tool: {tool_call['name']}\nArgs: {args}",
                    title=f"[{self.DISPLAY_NAME}] Tool Call (iteration {iteration + 1})",
                )
                log_tool_call(self.DISPLAY_NAME, tool_call["name"], args)

                try:
                    tool_response = self._call_tool(tool_call, include_delegation)
                    result_text = str(tool_response.content)
                    log_tool_result(self.DISPLAY_NAME, tool_call["name"], result_text)
                except Exception as e:
                    log_error(self.DISPLAY_NAME, f"{tool_call['name']}: {e}")
                    result_text = f"Error: {e}"
                    tool_response = ToolMessage(
                        content=result_text,
                        tool_call_id=tool_call["id"],
                    )

                # -- Record this step for the frontend thought process --
                self.tool_events.append({
                    "tool": tool_call["name"],
                    "args": {k: v for k, v in args.items()
                             if k != "reasoning"},
                    "reasoning": args.get("reasoning", ""),
                    "result": result_text[:500],
                    "severity": severity,
                })

                history.append(tool_response)

            iteration += 1

        log_error(self.DISPLAY_NAME, f"Exceeded max iterations ({max_iterations})")
        raise RuntimeError(
            f"Agent exceeded maximum iterations ({max_iterations})."
        )

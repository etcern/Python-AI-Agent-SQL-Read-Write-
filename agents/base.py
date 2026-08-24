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
from config import MAX_ITERATIONS, MAX_TOOL_RETRIES, KNOWLEDGE_INJECTION_LIMIT, KNOWLEDGE_INJECTION_MAX_CHARS


# --- Tool severity map ---
# Used by the frontend to show severity badges on each tool call.
# low = read-only / safe, medium = modifies data, high = writes files / destructive.

TOOL_SEVERITY = {
    # -- Read (green) --
    "read_file":         "low",
    "list_files":        "low",
    "search_knowledge":  "low",
    "web_search":        "low",
    "web_read":          "low",
    "search_github":     "low",
    "github_tree":       "low",
    "github_file":       "low",
    "list_tables":       "low",
    "describe_table":    "low",
    "memory_status":     "low",
    # -- Modify (yellow) --
    "delegate_task":     "medium",
    "save_knowledge":    "medium",
    "execute_sql":       "medium",
    # -- Write (red) --
    "write_file":          "high",
    "create_spreadsheet":  "high",
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

RESEARCH DEPTH:
- Do NOT settle for one search. Do at least 2-3 searches with different angles/keywords to cover the topic properly.
- After web_search, use web_read on the most relevant URLs to get the FULL content, not just snippets.
- Extract real data, real examples, and real explanations from pages you read.
- When creating documents or reports, fill them with actual researched content - not generic summaries.

FILE OUTPUT:
- When you create or write a file, ALWAYS tell the user the exact file path in your response.
- Include the path from the tool result so the user can find the file on their system.
- NEVER use write_file for binary formats (.pdf, .docx, .pptx, .png, etc.) - it only writes plain text.
- For documents: use .md (Markdown) or .txt. For spreadsheets: use create_spreadsheet (.xlsx).

FORMATTING RULES:
- NEVER use emojis in your responses. No emoji characters at all.
- Use Markdown formatting instead: **bold** for emphasis, headings (#, ##, ###), bullet lists (-), numbered lists (1. 2. 3.), and horizontal rules (---) for section breaks.
- Keep responses professional and clean. Use clear structure, not decorative symbols.
"""

CONFIRMATION_GUIDE = """
CONFIRMATION MODE IS ON:
Before executing any write or modify operation (write_file, execute_sql with INSERT/UPDATE/DELETE),
you MUST first describe exactly what you plan to change and ask for user confirmation.
Format your request as: "I want to [describe action]. Shall I proceed?"
Do NOT execute the operation until the user explicitly says "yes", "go ahead", "do it", or similar.
If the user says "no" or "cancel", acknowledge and do not execute.
"""

THINKING_GUIDE = """
THINKING MODE IS ON:
Take your time to reason through the problem step by step before giving your answer.
Consider edge cases, potential issues, and alternative approaches.
Break down complex tasks into smaller parts and think through each one.
"""


class BaseAgent:
    AGENT_NAME = "base"
    DISPLAY_NAME = "Base Agent"
    DESCRIPTION = "A generic assistant."
    SYSTEM_PROMPT = "You are a helpful assistant."
    DEFAULT_MODEL = "qwen2.5-coder:7b"
    DEFAULT_TEMPERATURE = 0.0
    THINKING_DEFAULT = False

    def __init__(self, include_internet: bool = True,
                 confirmation_mode: bool = False,
                 thinking_enabled: bool | None = None):
        self.include_internet = include_internet
        self.confirmation_mode = confirmation_mode
        # -- thinking_enabled: None = use agent default, True/False = override --
        if thinking_enabled is None:
            self.thinking_enabled = self.THINKING_DEFAULT
        else:
            self.thinking_enabled = thinking_enabled
        self.tool_events = []

    def get_tools(self) -> list:
        """Base tools for every agent: read-only files + knowledge + diagnostics.
        When internet is enabled, also includes web search + GitHub.
        Override in subclasses and call super().get_tools() to keep these."""
        from tools.file_tools import get_file_read_tools
        from tools.knowledge import get_knowledge_tools
        from tools.memory_profiler import get_memory_tools
        tools = get_file_read_tools() + get_knowledge_tools() + get_memory_tools()
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

    # --- Knowledge injection ---

    def _get_relevant_knowledge(self, query: str, limit: int = KNOWLEDGE_INJECTION_LIMIT) -> str:
        """Search knowledge base for entries relevant to the query.
        Returns formatted context string, or empty string if nothing found.
        """
        try:
            from knowledge_store import search_entries
            results = search_entries(query, limit=limit)
            if not results:
                return ""
            lines = ["RELEVANT KNOWLEDGE FROM PREVIOUS SESSIONS:"]
            for r in results:
                lines.append(f"- [{r['topic']}]: {r['content'][:KNOWLEDGE_INJECTION_MAX_CHARS]}")
            return "\n".join(lines) + "\n"
        except Exception:
            return ""

    # --- History management ---

    def create_history(self, query: str = "") -> list[BaseMessage]:
        prompt = self.SYSTEM_PROMPT.replace(
            "{current_datetime}",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        prompt += TOOL_GUIDE
        if self.confirmation_mode:
            prompt += CONFIRMATION_GUIDE
        if self.thinking_enabled:
            prompt += THINKING_GUIDE

        # -- Inject relevant knowledge if we have a query --
        if query:
            knowledge_ctx = self._get_relevant_knowledge(query)
            if knowledge_ctx:
                prompt += "\n" + knowledge_ctx

        return [SystemMessage(content=prompt)]

    @staticmethod
    def _estimate_tokens(messages: list[BaseMessage]) -> int:
        """Rough token estimate: ~4 chars per token for English, ~2 for code.
        Uses 3 as a conservative middle ground.
        """
        total_chars = sum(len(str(m.content)) for m in messages)
        return total_chars // 3

    @staticmethod
    def _trim_history(history: list[BaseMessage], max_tokens: int) -> list[BaseMessage]:
        """Keep system message + most recent messages that fit in max_tokens.

        Drops oldest non-system messages first to stay within budget.
        Always keeps at least the system message and the last 2 messages.
        """
        if not history:
            return history

        # -- Always keep system message (first) and last 2 messages --
        system_msgs = [m for m in history if isinstance(m, SystemMessage)]
        non_system = [m for m in history if not isinstance(m, SystemMessage)]

        if len(non_system) <= 2:
            return history

        # -- Trim from the front of non-system messages --
        budget = int(max_tokens * 0.8)  # leave 20% room for the response
        result = list(system_msgs)

        # -- Start from the most recent and work backward --
        kept = []
        running_tokens = BaseAgent._estimate_tokens(system_msgs)
        for msg in reversed(non_system):
            msg_tokens = len(str(msg.content)) // 3
            if running_tokens + msg_tokens > budget:
                break
            kept.append(msg)
            running_tokens += msg_tokens

        # -- Always keep at least the last 2 --
        if len(kept) < 2 and len(non_system) >= 2:
            kept = non_system[-2:]

        result.extend(reversed(kept))
        return result

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

    def _call_tool_with_retry(self, tool_call, include_delegation: bool = True) -> ToolMessage:
        """Call a tool with automatic retry on failure.

        On error, returns the error as a ToolMessage so the model can
        see what went wrong and try again with corrected arguments.
        """
        for attempt in range(MAX_TOOL_RETRIES):
            try:
                return self._call_tool(tool_call, include_delegation)
            except Exception as e:
                error_msg = f"Error (attempt {attempt + 1}/{MAX_TOOL_RETRIES}): {e}"
                log_error(self.DISPLAY_NAME, f"{tool_call['name']}: {error_msg}")
                if attempt == MAX_TOOL_RETRIES - 1:
                    return ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call["id"],
                    )
        # Shouldn't reach here, but just in case
        return ToolMessage(
            content="Tool call failed after retries",
            tool_call_id=tool_call["id"],
        )

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

    def _extract_thinking(self, response) -> str:
        """Extract thinking/reasoning content from a model response.

        Checks additional_kwargs (LangChain ChatOllama reasoning mode)
        and <think> tags in content (raw thinking output).
        """
        thinking = ""

        # -- Check LangChain reasoning output --
        if hasattr(response, "additional_kwargs"):
            thinking = response.additional_kwargs.get("reasoning_content", "")

        # -- Check for <think> tags in content --
        if not thinking and response.content:
            think_match = re.search(
                r"<think>(.*?)</think>", str(response.content), re.DOTALL
            )
            if think_match:
                thinking = think_match.group(1).strip()

        return thinking

    def _clean_response_content(self, content: str) -> str:
        """Remove <think> tags from the response content if present."""
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def ask(
        self,
        query: str,
        history: list[BaseMessage],
        model: BaseChatModel,
        max_iterations: int = MAX_ITERATIONS,
        include_delegation: bool = True,
        num_ctx: int = 8192,
    ) -> str:
        self.tool_events = []
        history.append(HumanMessage(content=query))
        log_panel(query, title=f"[{self.DISPLAY_NAME}] User Query")
        log_query(self.DISPLAY_NAME, query)

        iteration = 0
        while iteration < max_iterations:
            # -- Trim history to fit context window --
            history = self._trim_history(history, num_ctx)

            response = model.invoke(history)

            # -- Extract thinking content if present --
            thinking = self._extract_thinking(response)
            if thinking:
                self.tool_events.insert(0, {
                    "tool": "_thinking",
                    "args": {},
                    "reasoning": thinking[:1000],
                    "result": "",
                    "severity": "low",
                })

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
                content = self._clean_response_content(str(response.content))
                log_panel(content, title=f"[{self.DISPLAY_NAME}] Final Response")
                log_response(self.DISPLAY_NAME, content)
                return content

            for tool_call in tool_calls:
                severity = self._tool_severity(tool_call["name"])
                args = tool_call.get("args", {})

                log_panel(
                    f"Tool: {tool_call['name']}\nArgs: {args}",
                    title=f"[{self.DISPLAY_NAME}] Tool Call (iteration {iteration + 1})",
                )
                log_tool_call(self.DISPLAY_NAME, tool_call["name"], args)

                try:
                    tool_response = self._call_tool_with_retry(tool_call, include_delegation)
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

    def ask_stream(
        self,
        query: str,
        history: list[BaseMessage],
        model: BaseChatModel,
        max_iterations: int = MAX_ITERATIONS,
        include_delegation: bool = True,
        num_ctx: int = 8192,
    ):
        """Generator version of ask() that yields SSE events.

        Yields dicts with 'type' key:
          - {"type": "thinking", "content": "..."}
          - {"type": "tool", "tool": "...", "args": {...}, "severity": "..."}
          - {"type": "tool_result", "tool": "...", "result": "..."}
          - {"type": "token", "content": "word "}
          - {"type": "done", "content": "full response", "tool_events": [...]}
        """
        self.tool_events = []
        history.append(HumanMessage(content=query))
        log_panel(query, title=f"[{self.DISPLAY_NAME}] User Query")
        log_query(self.DISPLAY_NAME, query)

        iteration = 0
        while iteration < max_iterations:
            history = self._trim_history(history, num_ctx)

            response = model.invoke(history)

            # -- Extract and yield thinking --
            thinking = self._extract_thinking(response)
            if thinking:
                yield {"type": "thinking", "content": thinking[:1000]}
                self.tool_events.insert(0, {
                    "tool": "_thinking",
                    "args": {},
                    "reasoning": thinking[:1000],
                    "result": "",
                    "severity": "low",
                })

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
                content = self._clean_response_content(str(response.content))
                log_panel(content, title=f"[{self.DISPLAY_NAME}] Final Response")
                log_response(self.DISPLAY_NAME, content)

                # -- Stream final response token by token --
                for i in range(0, len(content), 6):
                    yield {"type": "token", "content": content[i:i + 6]}

                yield {
                    "type": "done",
                    "content": content,
                    "tool_events": self.tool_events,
                }
                return

            # -- Process tool calls and yield events --
            for tool_call in tool_calls:
                severity = self._tool_severity(tool_call["name"])
                args = tool_call.get("args", {})

                log_tool_call(self.DISPLAY_NAME, tool_call["name"], args)

                yield {
                    "type": "tool",
                    "tool": tool_call["name"],
                    "args": {k: v for k, v in args.items() if k != "reasoning"},
                    "reasoning": args.get("reasoning", ""),
                    "severity": severity,
                }

                try:
                    tool_response = self._call_tool_with_retry(tool_call, include_delegation)
                    result_text = str(tool_response.content)
                    log_tool_result(self.DISPLAY_NAME, tool_call["name"], result_text)
                except Exception as e:
                    log_error(self.DISPLAY_NAME, f"{tool_call['name']}: {e}")
                    result_text = f"Error: {e}"
                    tool_response = ToolMessage(
                        content=result_text,
                        tool_call_id=tool_call["id"],
                    )

                yield {
                    "type": "tool_result",
                    "tool": tool_call["name"],
                    "result": result_text[:500],
                }

                self.tool_events.append({
                    "tool": tool_call["name"],
                    "args": {k: v for k, v in args.items() if k != "reasoning"},
                    "reasoning": args.get("reasoning", ""),
                    "result": result_text[:500],
                    "severity": severity,
                })

                history.append(tool_response)

            iteration += 1

        error_msg = f"Agent exceeded maximum iterations ({max_iterations})."
        log_error(self.DISPLAY_NAME, error_msg)
        yield {"type": "error", "content": error_msg}

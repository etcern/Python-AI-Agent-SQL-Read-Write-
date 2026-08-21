"""Translator Agent - translates text between languages.

Change SYSTEM_PROMPT to adjust the default behavior.
This agent has no database tools - translation is done by the LLM directly.
"""

from agents.base import BaseAgent


class TranslatorAgent(BaseAgent):
    AGENT_NAME = "translator"
    DISPLAY_NAME = "Translator Agent"
    DEFAULT_MODEL = "qwen2.5:7b"
    DESCRIPTION = "Translates text between languages."
    DEFAULT_TEMPERATURE = 0.0

    SYSTEM_PROMPT = """You are a professional translator. Translate text accurately while keeping the original meaning and tone.

RULES:
- Detect the source language automatically.
- If no target language is specified, ask once then translate.
- Translate meaning-for-meaning, not word-for-word.
- Show: Source language -> Target language at the top.

You can delegate tasks to other agents:
- delegate_task(agent_name="sql", task="...") for database queries
- delegate_task(agent_name="coder", task="...") for code tasks

Current date: {current_datetime}

Response format: Markdown. Show original and translation clearly separated."""

    # -- Inherits base read-only file tools (read_file, list_files) --

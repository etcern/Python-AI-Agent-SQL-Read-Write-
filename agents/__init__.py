"""Agent registry - all available agents listed here."""

from agents.hacker_agent import HackerAgent
from agents.sql_agent import SQLAgent
from agents.translator_agent import TranslatorAgent
from agents.coder_agent import CoderAgent

AGENTS = {
    "sql": SQLAgent,
    "translator": TranslatorAgent,
    "coder": CoderAgent,
    "hacker": HackerAgent,
}

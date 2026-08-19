"""Logs every AI action (queries, tool calls, responses) to a text file."""

import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "actions.txt")


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def _write(line: str):
    _ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {line}\n")


def log_query(agent_name: str, query: str):
    _write(f"QUERY | agent={agent_name} | {query}")


def log_tool_call(agent_name: str, tool_name: str, args: dict):
    _write(f"TOOL  | agent={agent_name} | {tool_name}({args})")


def log_tool_result(agent_name: str, tool_name: str, result: str):
    preview = result[:200].replace("\n", " ")
    _write(f"RESULT| agent={agent_name} | {tool_name} -> {preview}")


def log_response(agent_name: str, response: str):
    preview = response[:300].replace("\n", " ")
    _write(f"REPLY | agent={agent_name} | {preview}")


def log_error(agent_name: str, error: str):
    _write(f"ERROR | agent={agent_name} | {error}")


def read_log(last_n: int = 50) -> str:
    if not os.path.exists(LOG_FILE):
        return "(no actions logged yet)"
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-last_n:])


def clear_log():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

"""File tools — let agents read and write files in the workspace.

Split into read-only and write groups so agents can be given granular access.
All paths are relative to WORKSPACE_DIR (defined in config.py).
Ref: https://docs.python.org/3/library/os.path.html
"""

import os
from langchain_core.tools import tool
from logging_utils import log_panel
from config import WORKSPACE_DIR


# --- Read-only tools ---

@tool(parse_docstring=True)
def read_file(file_path: str, reasoning: str = "") -> str:
    """Read the contents of a file.

    Args:
        file_path: Path to the file (relative to workspace folder).
        reasoning: Optional. Why you need to read this file.

    Returns:
        The file contents as text, or an error message.
    """
    if reasoning:
        log_panel(reasoning, title=f"read_file({file_path}) - Reasoning")
    full_path = os.path.join(WORKSPACE_DIR, file_path)
    if not os.path.exists(full_path):
        return f"File not found: {file_path}"
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    log_panel(content[:500], title=f"read_file({file_path}) - Result")
    return content


@tool(parse_docstring=True)
def list_files(directory: str = ".", reasoning: str = "") -> str:
    """List files in a directory.

    Args:
        directory: Directory path (relative to workspace folder). Defaults to root.
        reasoning: Optional. Why you need to list files.

    Returns:
        A list of file and folder names.
    """
    if reasoning:
        log_panel(reasoning, title=f"list_files({directory}) - Reasoning")
    full_path = os.path.join(WORKSPACE_DIR, directory)
    if not os.path.exists(full_path):
        return f"Directory not found: {directory}"
    entries = os.listdir(full_path)
    result = "\n".join(entries) if entries else "(empty directory)"
    log_panel(result, title=f"list_files({directory}) - Result")
    return result


# --- Write tools ---

@tool(parse_docstring=True)
def write_file(file_path: str, content: str, reasoning: str = "") -> str:
    """Write content to a file. Creates the file if it doesn't exist.

    Args:
        file_path: Path to the file (relative to workspace folder).
        content: The text content to write.
        reasoning: Optional. Why you are writing this file.

    Returns:
        Confirmation message.
    """
    if reasoning:
        log_panel(reasoning, title=f"write_file({file_path}) - Reasoning")
    full_path = os.path.join(WORKSPACE_DIR, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    log_panel(f"Wrote {len(content)} characters", title=f"write_file({file_path}) - Result")
    return f"File written: {file_path} ({len(content)} characters)"


# --- Tool group accessors ---

def get_file_read_tools() -> list:
    """Read-only file tools — safe to give any agent."""
    return [read_file, list_files]


def get_file_write_tools() -> list:
    """Write-only file tools — only for agents that need disk access."""
    return [write_file]


def get_file_tools() -> list:
    """All file tools (read + write). Backward compatible."""
    return [read_file, write_file, list_files]

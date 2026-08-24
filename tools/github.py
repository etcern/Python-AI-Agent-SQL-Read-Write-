"""GitHub tools - let agents search repos, browse files, and fetch code.

Uses the public GitHub API (no API key needed for public repos).
Rate limit: 60 requests/hour without a token - plenty for local use.
Ref: https://docs.github.com/en/rest
Ref: https://docs.python.org/3/library/urllib.request.html
"""

import json
import urllib.request
import urllib.parse

from langchain_core.tools import tool
from logging_utils import log_panel
from config import GITHUB_FILE_MAX_CHARS, GITHUB_USER_AGENT


# --- HTTP helpers ---

_HEADERS = {
    "User-Agent": GITHUB_USER_AGENT,
    "Accept": "application/vnd.github.v3+json",
}


def _github_api(url: str) -> dict | list:
    """GET request to the GitHub REST API. Returns parsed JSON."""
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("GitHub API rate limit reached (60/hour). Try again later.")
        if e.code == 404:
            raise RuntimeError("Repository or path not found on GitHub.")
        raise RuntimeError(f"GitHub API error: {e.code} {e.reason}")


def _github_raw(url: str) -> str:
    """GET raw file content from raw.githubusercontent.com."""
    req = urllib.request.Request(url, headers={"User-Agent": GITHUB_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("File not found on GitHub.")
        raise RuntimeError(f"GitHub raw fetch error: {e.code} {e.reason}")


# --- GitHub tools ---

@tool(parse_docstring=True)
def search_github(query: str, language: str = "", reasoning: str = "") -> str:
    """Search GitHub for repositories matching a query.

    Use this to find reference implementations, libraries, or code examples.
    Results are sorted by stars so you get the most popular repos first.

    Args:
        query: What to search for (e.g. "flask REST API", "React todo app").
        language: Optional. Filter by programming language (e.g. "python", "javascript").
        reasoning: Optional. Why you are searching GitHub.

    Returns:
        Top repositories with name, stars, description, and language.
    """
    if reasoning:
        log_panel(reasoning, title="search_github - Reasoning")

    q = query
    if language:
        q += f" language:{language}"
    params = urllib.parse.urlencode({"q": q, "sort": "stars", "per_page": 5})
    url = f"https://api.github.com/search/repositories?{params}"
    log_panel(f"Query: {q}", title="search_github - Searching")

    data = _github_api(url)
    items = data.get("items", [])
    if not items:
        return f"No repositories found for: {query}"

    lines = []
    for repo in items[:5]:
        lines.append(
            f"• {repo['full_name']} ⭐ {repo['stargazers_count']}\n"
            f"  {repo.get('description') or 'No description'}\n"
            f"  Language: {repo.get('language') or 'Unknown'} | "
            f"Default branch: {repo.get('default_branch', 'main')}"
        )
    result = "\n\n".join(lines)
    log_panel(result[:500], title="search_github - Results")
    return result


@tool(parse_docstring=True)
def github_tree(owner: str, repo: str, path: str = "", branch: str = "main", reasoning: str = "") -> str:
    """List files and folders in a GitHub repository directory.

    Use this to browse a repo's file structure before fetching specific files.

    Args:
        owner: Repository owner (e.g. "pallets").
        repo: Repository name (e.g. "flask").
        path: Directory path inside the repo (e.g. "src/flask"). Leave empty for root.
        branch: Branch name. Defaults to "main".
        reasoning: Optional. Why you are browsing this repo.

    Returns:
        List of files and folders with sizes.
    """
    if reasoning:
        log_panel(reasoning, title="github_tree - Reasoning")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    if branch:
        url += f"?ref={branch}"
    log_panel(f"{owner}/{repo}/{path} ({branch})", title="github_tree - Browsing")

    data = _github_api(url)
    if not isinstance(data, list):
        return "Not a directory, or path not found."

    lines = []
    # -- Sort: folders first, then files --
    dirs = [i for i in data if i["type"] == "dir"]
    files = [i for i in data if i["type"] != "dir"]
    for item in dirs:
        lines.append(f"📁 {item['name']}/")
    for item in files:
        size = item.get("size", 0)
        label = f"{size:,} B" if size < 10240 else f"{size / 1024:.1f} KB"
        lines.append(f"📄 {item['name']}  ({label})")

    result = "\n".join(lines)
    log_panel(result[:500], title="github_tree - Contents")
    return result


@tool(parse_docstring=True)
def github_file(owner: str, repo: str, path: str, branch: str = "main", reasoning: str = "") -> str:
    """Read a file from a public GitHub repository.

    Use this to fetch source code, configs, READMEs, or any text file.
    Large files are truncated to keep things manageable.

    Args:
        owner: Repository owner (e.g. "pallets").
        repo: Repository name (e.g. "flask").
        path: File path inside the repo (e.g. "src/flask/app.py").
        branch: Branch name. Defaults to "main".
        reasoning: Optional. Why you are reading this file.

    Returns:
        The file content as text.
    """
    if reasoning:
        log_panel(reasoning, title="github_file - Reasoning")

    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    log_panel(f"{owner}/{repo}/{path} ({branch})", title="github_file - Fetching")

    content = _github_raw(url)

    # -- Truncate very large files (limit from config.py) --
    if len(content) > GITHUB_FILE_MAX_CHARS:
        content = content[:GITHUB_FILE_MAX_CHARS] + "\n\n... [truncated - file too large, fetch a specific section]"

    log_panel(f"{len(content)} chars", title="github_file - Fetched")
    return content


# --- Accessor ---

def get_github_tools() -> list:
    """GitHub tools - search repos, browse files, fetch code."""
    return [search_github, github_tree, github_file]

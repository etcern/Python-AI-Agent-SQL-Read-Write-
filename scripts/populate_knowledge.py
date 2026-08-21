"""Wissensdatenbank population - pre-load the knowledge base with coding patterns.

Seeds the knowledge base so agents write better code from the start.
Includes curated patterns for Python, SQL, JavaScript, design patterns,
security, and testing. Optionally imports from HuggingFace datasets.

Usage:
    python scripts/populate_knowledge.py --all              Load all built-in knowledge packs
    python scripts/populate_knowledge.py --pack python      Load a specific pack
    python scripts/populate_knowledge.py --pack sql,security Load multiple packs
    python scripts/populate_knowledge.py --huggingface      Import code patterns from HuggingFace
    python scripts/populate_knowledge.py --list             Show available packs
    python scripts/populate_knowledge.py --stats            Show knowledge base stats
    python scripts/populate_knowledge.py --clear            Wipe all knowledge entries

Ref: https://docs.python.org/3/library/sqlite3.html
Ref: https://huggingface.co/docs/datasets/
"""

import argparse
import os
import sys

# -- Resolve paths relative to project root --
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from knowledge_store import init_knowledge_db, save_entry, search_entries, _connect


# --- Knowledge packs ---
# Each pack is a list of {topic, content} dicts.
# Topics use the format "category: specific thing" so agents can search them.

PACKS = {}

PACKS["python"] = [
    {
        "topic": "python: list comprehension",
        "content": "[expr for item in iterable if condition]\n"
                   "Use for simple transforms. For complex logic, use a regular loop.\n"
                   "Example: squares = [x**2 for x in range(10) if x % 2 == 0]",
    },
    {
        "topic": "python: error handling pattern",
        "content": "try:\n    result = risky_operation()\nexcept SpecificError as e:\n"
                   "    log.error(f'Failed: {e}')\n    return fallback\n"
                   "Never use bare 'except:'. Always catch the most specific exception.",
    },
    {
        "topic": "python: context manager",
        "content": "from contextlib import contextmanager\n\n@contextmanager\n"
                   "def managed_resource(name):\n    resource = acquire(name)\n"
                   "    try:\n        yield resource\n    finally:\n        resource.release()\n\n"
                   "Use 'with' statements for anything that needs cleanup (files, connections, locks).",
    },
    {
        "topic": "python: dataclass pattern",
        "content": "from dataclasses import dataclass, field\n\n@dataclass\nclass Config:\n"
                   "    name: str\n    debug: bool = False\n"
                   "    tags: list[str] = field(default_factory=list)\n\n"
                   "Use dataclasses for simple data holders. Use Pydantic for validation.",
    },
    {
        "topic": "python: decorator pattern",
        "content": "import functools\n\ndef retry(max_attempts=3):\n"
                   "    def decorator(func):\n        @functools.wraps(func)\n"
                   "        def wrapper(*args, **kwargs):\n"
                   "            for attempt in range(max_attempts):\n"
                   "                try:\n                    return func(*args, **kwargs)\n"
                   "                except Exception:\n"
                   "                    if attempt == max_attempts - 1:\n"
                   "                        raise\n        return wrapper\n"
                   "    return decorator\n\nAlways use @functools.wraps to preserve the original function metadata.",
    },
    {
        "topic": "python: typing best practices",
        "content": "def process(items: list[str], limit: int = 10) -> dict[str, int]:\n"
                   "Use built-in generics (list[], dict[], tuple[]) instead of typing.List etc.\n"
                   "Use X | None instead of Optional[X] (Python 3.10+).\n"
                   "Use -> None for functions that don't return anything meaningful.",
    },
    {
        "topic": "python: pathlib over os.path",
        "content": "from pathlib import Path\n\ndata_dir = Path(__file__).parent / 'data'\n"
                   "config = data_dir / 'config.json'\nif config.exists():\n"
                   "    text = config.read_text(encoding='utf-8')\n\n"
                   "Prefer pathlib.Path over os.path for cleaner file operations.",
    },
    {
        "topic": "python: generator for large data",
        "content": "def read_chunks(filepath, chunk_size=8192):\n"
                   "    with open(filepath, 'rb') as f:\n"
                   "        while chunk := f.read(chunk_size):\n"
                   "            yield chunk\n\n"
                   "Use generators when processing large datasets to avoid loading everything into memory.",
    },
    {
        "topic": "python: enum for constants",
        "content": "from enum import Enum, auto\n\nclass Status(Enum):\n"
                   "    PENDING = auto()\n    ACTIVE = auto()\n    DONE = auto()\n\n"
                   "Use Enum instead of string constants for type safety and IDE autocomplete.",
    },
    {
        "topic": "python: f-string formatting",
        "content": "name = 'World'\nprint(f'Hello {name}!')        # basic\n"
                   "print(f'{value:.2f}')              # 2 decimal places\n"
                   "print(f'{num:,}')                  # thousands separator\n"
                   "print(f'{text:>20}')               # right-align in 20 chars\n"
                   "print(f'{dt:%Y-%m-%d %H:%M}')      # datetime formatting",
    },
]

PACKS["sql"] = [
    {
        "topic": "sql: window functions",
        "content": "SELECT name, department, salary,\n"
                   "  RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank,\n"
                   "  SUM(salary) OVER (PARTITION BY department) as dept_total,\n"
                   "  AVG(salary) OVER () as company_avg\nFROM employees;\n\n"
                   "Window functions compute values across rows without collapsing them. "
                   "Use PARTITION BY to group, ORDER BY to sequence.",
    },
    {
        "topic": "sql: CTE (Common Table Expression)",
        "content": "WITH monthly_sales AS (\n"
                   "  SELECT strftime('%Y-%m', order_date) AS month,\n"
                   "    SUM(total_amount) AS revenue\n  FROM orders\n  GROUP BY 1\n)\n"
                   "SELECT month, revenue,\n"
                   "  LAG(revenue) OVER (ORDER BY month) AS prev_month\n"
                   "FROM monthly_sales;\n\n"
                   "CTEs make complex queries readable. Chain them with commas: WITH cte1 AS (...), cte2 AS (...)",
    },
    {
        "topic": "sql: JOIN types",
        "content": "INNER JOIN - only matching rows from both tables\n"
                   "LEFT JOIN  - all rows from left + matching from right (NULL if no match)\n"
                   "RIGHT JOIN - all rows from right + matching from left\n"
                   "CROSS JOIN - every row from left paired with every row from right\n\n"
                   "Always specify the join condition with ON. Never use implicit joins (comma in FROM).",
    },
    {
        "topic": "sql: aggregation patterns",
        "content": "SELECT category,\n  COUNT(*) AS total,\n  COUNT(DISTINCT customer_id) AS unique_customers,\n"
                   "  ROUND(AVG(price), 2) AS avg_price,\n  MIN(price) AS cheapest,\n  MAX(price) AS most_expensive,\n"
                   "  SUM(quantity) AS total_sold\nFROM products\n"
                   "JOIN order_items ON products.id = order_items.product_id\n"
                   "GROUP BY category\nHAVING COUNT(*) > 5\nORDER BY total DESC;",
    },
    {
        "topic": "sql: subquery vs JOIN",
        "content": "-- Subquery (use for existence checks, single values)\n"
                   "SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders WHERE total > 100);\n\n"
                   "-- JOIN (use when you need columns from both tables)\n"
                   "SELECT c.name, o.total FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.total > 100;\n\n"
                   "Prefer JOIN for multi-column results. Use EXISTS for large IN lists.",
    },
    {
        "topic": "sql: date functions (SQLite)",
        "content": "SELECT date('now');                          -- today\n"
                   "SELECT date('now', '-7 days');               -- 7 days ago\n"
                   "SELECT strftime('%Y-%m', order_date);        -- year-month\n"
                   "SELECT strftime('%W', order_date);           -- week number\n"
                   "SELECT julianday('now') - julianday(created_at); -- days between",
    },
    {
        "topic": "sql: CASE expression",
        "content": "SELECT name, price,\n  CASE\n    WHEN price < 20 THEN 'budget'\n"
                   "    WHEN price < 50 THEN 'mid-range'\n    ELSE 'premium'\n"
                   "  END AS tier\nFROM products;\n\n"
                   "CASE works in SELECT, WHERE, ORDER BY, and GROUP BY. "
                   "Use it for conditional logic inside queries.",
    },
]

PACKS["javascript"] = [
    {
        "topic": "javascript: fetch API pattern",
        "content": "async function api(path, opts = {}) {\n"
                   "  const res = await fetch(path, {\n"
                   "    headers: { 'Content-Type': 'application/json', ...opts.headers },\n"
                   "    ...opts,\n  });\n"
                   "  if (!res.ok) throw new Error(`HTTP ${res.status}`);\n"
                   "  return res.json();\n}\n\n"
                   "Always check res.ok. Wrap in try/catch for error handling.",
    },
    {
        "topic": "javascript: DOM manipulation",
        "content": "// Create element\nconst el = document.createElement('div');\n"
                   "el.className = 'card';\nel.textContent = 'Hello';\n"
                   "container.appendChild(el);\n\n"
                   "// Query elements\ndocument.getElementById('id');\n"
                   "document.querySelector('.class');\n"
                   "document.querySelectorAll('[data-type]');\n\n"
                   "Use textContent (not innerHTML) for user input to prevent XSS.",
    },
    {
        "topic": "javascript: event delegation",
        "content": "// Instead of adding listeners to each item:\n"
                   "document.getElementById('list').addEventListener('click', (e) => {\n"
                   "  const item = e.target.closest('.item');\n"
                   "  if (!item) return;\n  handleClick(item.dataset.id);\n});\n\n"
                   "Attach one listener to the parent. Use e.target.closest() to find the actual target.",
    },
    {
        "topic": "javascript: async/await error handling",
        "content": "async function loadData() {\n  try {\n"
                   "    const [users, posts] = await Promise.all([\n"
                   "      fetch('/api/users').then(r => r.json()),\n"
                   "      fetch('/api/posts').then(r => r.json()),\n"
                   "    ]);\n    return { users, posts };\n"
                   "  } catch (e) {\n    console.error('Load failed:', e);\n"
                   "    return { users: [], posts: [] };\n  }\n}\n\n"
                   "Use Promise.all for parallel requests. Always handle errors.",
    },
    {
        "topic": "javascript: localStorage pattern",
        "content": "function loadSetting(key, fallback) {\n"
                   "  const val = localStorage.getItem(key);\n"
                   "  return val !== null ? JSON.parse(val) : fallback;\n}\n\n"
                   "function saveSetting(key, value) {\n"
                   "  localStorage.setItem(key, JSON.stringify(value));\n}\n\n"
                   "Always use JSON.parse/stringify. localStorage only stores strings.",
    },
]

PACKS["design_patterns"] = [
    {
        "topic": "pattern: factory",
        "content": "class AgentFactory:\n    _registry = {}\n\n"
                   "    @classmethod\n    def register(cls, name, agent_cls):\n"
                   "        cls._registry[name] = agent_cls\n\n"
                   "    @classmethod\n    def create(cls, name, **kwargs):\n"
                   "        if name not in cls._registry:\n"
                   "            raise ValueError(f'Unknown: {name}')\n"
                   "        return cls._registry[name](**kwargs)\n\n"
                   "Use Factory when you need to create objects by name/config without knowing the class.",
    },
    {
        "topic": "pattern: strategy",
        "content": "class Validator:\n    def __init__(self, strategy):\n"
                   "        self.strategy = strategy\n\n"
                   "    def validate(self, data):\n"
                   "        return self.strategy(data)\n\n"
                   "# Usage:\nvalidator = Validator(lambda d: len(d) > 0)\n\n"
                   "Use Strategy when you need to swap algorithms at runtime.",
    },
    {
        "topic": "pattern: observer / event system",
        "content": "class EventBus:\n    def __init__(self):\n"
                   "        self._listeners = {}\n\n"
                   "    def on(self, event, callback):\n"
                   "        self._listeners.setdefault(event, []).append(callback)\n\n"
                   "    def emit(self, event, *args):\n"
                   "        for cb in self._listeners.get(event, []):\n"
                   "            cb(*args)\n\n"
                   "Use Observer when components need to react to events without tight coupling.",
    },
    {
        "topic": "pattern: repository",
        "content": "class UserRepository:\n    def __init__(self, db_connection):\n"
                   "        self.db = db_connection\n\n"
                   "    def find_by_id(self, user_id): ...\n"
                   "    def find_by_email(self, email): ...\n"
                   "    def save(self, user): ...\n"
                   "    def delete(self, user_id): ...\n\n"
                   "Repository abstracts data access. Swap SQLite for PostgreSQL without changing business logic.",
    },
]

PACKS["security"] = [
    {
        "topic": "security: SQL injection prevention",
        "content": "# NEVER do this:\ncursor.execute(f'SELECT * FROM users WHERE name = \"{name}\"')\n\n"
                   "# ALWAYS use parameterized queries:\ncursor.execute('SELECT * FROM users WHERE name = ?', (name,))\n\n"
                   "Parameters are escaped by the database driver. String formatting is never safe for SQL.",
    },
    {
        "topic": "security: input validation",
        "content": "import re\nfrom pathlib import PurePosixPath\n\n"
                   "# Sanitize filenames (prevent path traversal)\n"
                   "safe_name = PurePosixPath(user_input).name\n\n"
                   "# Validate email format\n"
                   "if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$', email):\n"
                   "    raise ValueError('Invalid email')\n\n"
                   "Never trust user input. Validate type, length, format, and range.",
    },
    {
        "topic": "security: XSS prevention",
        "content": "// In JavaScript:\n"
                   "element.textContent = userInput;  // SAFE - escapes HTML\n"
                   "element.innerHTML = userInput;    // DANGEROUS - executes HTML/JS\n\n"
                   "// If you must render HTML, sanitize it:\n"
                   "const clean = DOMPurify.sanitize(userInput);\n"
                   "element.innerHTML = clean;\n\n"
                   "Use textContent for plain text. Use DOMPurify when rendering HTML.",
    },
    {
        "topic": "security: secrets management",
        "content": "import os\n\n# Read from environment variables, not hardcoded:\n"
                   "API_KEY = os.environ.get('API_KEY')\nif not API_KEY:\n"
                   "    raise RuntimeError('API_KEY not set')\n\n"
                   "# Use .env files for local dev (add .env to .gitignore):\n"
                   "# pip install python-dotenv\nfrom dotenv import load_dotenv\nload_dotenv()\n\n"
                   "Never commit secrets to git. Use environment variables or a vault.",
    },
]

PACKS["testing"] = [
    {
        "topic": "testing: unit test structure",
        "content": "import pytest\n\ndef test_create_user_valid():\n"
                   "    # Arrange\n    data = {'name': 'Alice', 'email': 'alice@example.com'}\n\n"
                   "    # Act\n    user = create_user(data)\n\n"
                   "    # Assert\n    assert user.name == 'Alice'\n"
                   "    assert user.email == 'alice@example.com'\n\n"
                   "Follow Arrange-Act-Assert. One concept per test. Name describes expected behavior.",
    },
    {
        "topic": "testing: mocking",
        "content": "from unittest.mock import patch, MagicMock\n\n"
                   "@patch('module.external_api')\ndef test_fetch_data(mock_api):\n"
                   "    mock_api.return_value = {'status': 'ok'}\n"
                   "    result = fetch_data()\n    assert result['status'] == 'ok'\n"
                   "    mock_api.assert_called_once()\n\n"
                   "Mock external dependencies (APIs, databases, file system). Never mock the thing you're testing.",
    },
    {
        "topic": "testing: parametrize",
        "content": "import pytest\n\n@pytest.mark.parametrize('input,expected', [\n"
                   "    ('hello', 'HELLO'),\n    ('World', 'WORLD'),\n"
                   "    ('', ''),\n    ('123', '123'),\n])\n"
                   "def test_uppercase(input, expected):\n"
                   "    assert to_upper(input) == expected\n\n"
                   "Use parametrize for testing multiple inputs. Covers edge cases without code duplication.",
    },
]

PACKS["fastapi"] = [
    {
        "topic": "fastapi: endpoint pattern",
        "content": "from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\n"
                   "app = FastAPI()\n\nclass ItemCreate(BaseModel):\n"
                   "    name: str\n    price: float\n\n"
                   "@app.post('/api/items', status_code=201)\n"
                   "def create_item(body: ItemCreate):\n"
                   "    if body.price < 0:\n"
                   "        raise HTTPException(400, 'Price must be positive')\n"
                   "    return {'name': body.name, 'price': body.price}\n\n"
                   "Use Pydantic models for request bodies. HTTPException for errors.",
    },
    {
        "topic": "fastapi: file upload",
        "content": "from fastapi import UploadFile, File\nimport os\n\n"
                   "@app.post('/api/upload')\nasync def upload(file: UploadFile = File(...)):\n"
                   "    content = await file.read()\n"
                   "    path = os.path.join('uploads', file.filename)\n"
                   "    with open(path, 'wb') as f:\n        f.write(content)\n"
                   "    return {'name': file.filename, 'size': len(content)}\n\n"
                   "Always sanitize filenames to prevent path traversal.",
    },
]


# --- Import logic ---

def load_pack(pack_name: str) -> int:
    """Load a single knowledge pack into the database. Returns count of entries added."""
    if pack_name not in PACKS:
        print(f"Unknown pack: {pack_name}")
        print(f"Available: {', '.join(sorted(PACKS.keys()))}")
        return 0

    entries = PACKS[pack_name]
    added = 0
    for entry in entries:
        existing = search_entries(entry["topic"], limit=1)
        if existing and existing[0]["topic"] == entry["topic"]:
            continue
        save_entry(entry["topic"], entry["content"], source=f"pack:{pack_name}")
        added += 1
    return added


def load_all_packs() -> int:
    """Load all built-in knowledge packs."""
    total = 0
    for name in sorted(PACKS.keys()):
        added = load_pack(name)
        print(f"  {name}: {added} entries added")
        total += added
    return total


def show_stats():
    """Print knowledge base statistics."""
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    sources = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM knowledge GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    topics = conn.execute(
        "SELECT topic FROM knowledge ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()

    print(f"Total entries: {total}")
    print("\nBy source:")
    for row in sources:
        print(f"  {row['source']}: {row['cnt']}")
    if topics:
        print("\nRecent topics:")
        for row in topics:
            print(f"  - {row['topic']}")


def clear_all():
    """Delete all knowledge entries."""
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    conn.execute("DELETE FROM knowledge")
    conn.commit()
    conn.close()
    print(f"Cleared {count} entries from the knowledge base.")


def import_huggingface():
    """Import code instruction pairs from HuggingFace as knowledge entries.

    Uses a code instruction dataset and extracts the most useful patterns.
    Ref: https://huggingface.co/docs/datasets/
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("=" * 60)
        print("HuggingFace 'datasets' library not installed.")
        print()
        print("To install it:")
        print("  pip install datasets")
        print()
        print("Then run this command again:")
        print("  python scripts/populate_knowledge.py --huggingface")
        print("=" * 60)
        return

    print("Loading code instruction dataset from HuggingFace...")
    print("Dataset: iamtarun/python_code_instructions_18k_alpaca")
    print()

    try:
        ds = load_dataset(
            "iamtarun/python_code_instructions_18k_alpaca",
            split="train",
        )
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        print()
        print("Alternative datasets you can try (edit the script):")
        print("  - sahil2801/CodeAlpaca-20k")
        print("  - TokenBender/code_instructions_122k_alpaca_style")
        print("  - Search: https://huggingface.co/datasets?search=code+instructions")
        return

    # -- Extract the most useful entries (short, focused, high quality) --
    added = 0
    max_entries = 200
    for row in ds:
        if added >= max_entries:
            break

        instruction = row.get("instruction", "").strip()
        output = row.get("output", "").strip()

        if not instruction or not output:
            continue
        if len(output) > 2000 or len(output) < 50:
            continue
        if len(instruction) > 200:
            continue

        topic = f"python: {instruction[:80]}"
        content = f"Q: {instruction}\n\nA:\n{output}"

        existing = search_entries(topic[:30], limit=1)
        if existing:
            continue

        save_entry(topic, content, source="huggingface")
        added += 1

    print(f"Imported {added} code patterns from HuggingFace.")
    print("Your agents can now search these with search_knowledge().")


# --- CLI ---

def main():
    init_knowledge_db()

    parser = argparse.ArgumentParser(
        description="Populate the Wissensdatenbank with coding knowledge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/populate_knowledge.py --all                Load all built-in packs
  python scripts/populate_knowledge.py --pack python        Load Python patterns
  python scripts/populate_knowledge.py --pack sql,security  Load multiple packs
  python scripts/populate_knowledge.py --huggingface        Import from HuggingFace
  python scripts/populate_knowledge.py --stats              Show knowledge base info
  python scripts/populate_knowledge.py --clear --all        Wipe and reload everything
        """,
    )
    parser.add_argument("--all", action="store_true", help="Load all built-in knowledge packs")
    parser.add_argument("--pack", type=str, help="Load specific packs (comma-separated)")
    parser.add_argument("--huggingface", action="store_true", help="Import from HuggingFace dataset")
    parser.add_argument("--list", action="store_true", help="Show available knowledge packs")
    parser.add_argument("--stats", action="store_true", help="Show knowledge base statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all knowledge entries")

    args = parser.parse_args()

    if not any([args.all, args.pack, args.huggingface, args.list, args.stats, args.clear]):
        parser.print_help()
        return

    if args.list:
        print("Available knowledge packs:")
        for name, entries in sorted(PACKS.items()):
            print(f"  {name:20s} ({len(entries)} entries)")
        return

    if args.stats:
        show_stats()
        return

    if args.clear:
        clear_all()

    if args.all:
        print("Loading all knowledge packs...")
        total = load_all_packs()
        print(f"Done! {total} new entries added.")

    if args.pack:
        for name in args.pack.split(","):
            name = name.strip()
            added = load_pack(name)
            print(f"  {name}: {added} entries added")

    if args.huggingface:
        import_huggingface()


if __name__ == "__main__":
    main()

"""Database tools - let the AI query SQLite databases."""

import sqlite3
from contextlib import contextmanager
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from config import DB_PATH
from logging_utils import log_panel


@contextmanager
def sqlite_cursor():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@tool(parse_docstring=True)
def list_tables(reasoning: str = "") -> str:
    """List all tables available in the database.

    Args:
        reasoning: Optional. Why you are listing the tables.

    Returns:
        A comma-separated list of table names in the database.
    """
    if reasoning:
        log_panel(reasoning, title="list_tables - Reasoning")
    with sqlite_cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        result = ", ".join(t[0] for t in tables)
        log_panel(result, title="list_tables - Result")
        return result


@tool(parse_docstring=True)
def sample_table(table_name: str, row_count: int = 5, reasoning: str = "") -> str:
    """Get a sample of rows from a specific table.

    Args:
        table_name: The name of the table to sample from.
        row_count: The number of rows to return. Defaults to 5.
        reasoning: Optional. Why you are sampling this table.

    Returns:
        A string representation of the sampled rows.
    """
    if reasoning:
        log_panel(reasoning, title=f"sample_table({table_name}) - Reasoning")
    with sqlite_cursor() as cursor:
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT ?;", (row_count,))
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result = f"Columns: {', '.join(columns)}\n"
        for row in rows:
            result += str(row) + "\n"
        log_panel(result, title=f"sample_table({table_name}) - Result")
        return result


@tool(parse_docstring=True)
def describe_table(table_name: str, reasoning: str = "") -> str:
    """Describe the structure of a specific table, showing column names and types.

    Args:
        table_name: The name of the table to describe.
        reasoning: Optional. Why you are describing this table.

    Returns:
        A string representation of the table structure with column names and types.
    """
    if reasoning:
        log_panel(reasoning, title=f"describe_table({table_name}) - Reasoning")
    with sqlite_cursor() as cursor:
        cursor.execute(f"PRAGMA table_info([{table_name}]);")
        columns = cursor.fetchall()
        result = "\n".join(
            f"{col[1]} ({col[2]})" + (" NOT NULL" if col[3] else "") + (f" DEFAULT {col[4]}" if col[4] else "")
            for col in columns
        )
        log_panel(result, title=f"describe_table({table_name}) - Result")
        return result


@tool(parse_docstring=True)
def execute_sql(query: str, reasoning: str = "") -> str:
    """Execute a SQL query against the database and return the results.

    Args:
        query: The SQL query to execute.
        reasoning: Optional. Why you are executing this query.

    Returns:
        The query results as a string.
    """
    if reasoning:
        log_panel(reasoning, title="execute_sql - Reasoning")
    log_panel(query, title="execute_sql - Query")
    with sqlite_cursor() as cursor:
        cursor.execute(query)
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result = f"Columns: {', '.join(columns)}\n"
            for row in rows:
                result += str(row) + "\n"
            if not rows:
                result += "(no rows returned)\n"
        else:
            result = f"Query executed successfully. Rows affected: {cursor.rowcount}"
        log_panel(result, title="execute_sql - Result")
        return result


def get_database_tools() -> list:
    return [list_tables, sample_table, describe_table, execute_sql]

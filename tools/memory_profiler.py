"""Memory profiler - tracemalloc wrapper for debugging and diagnostics.

Tracks Python memory allocations at runtime, stores periodic summaries
in diagnostics.db, and exposes an agent tool so agents can inspect
their own memory footprint when troubleshooting performance issues.

Uses tracemalloc (stdlib) - zero external dependencies.
Ref: https://docs.python.org/3/library/tracemalloc.html
Ref: https://docs.python.org/3/library/resource.html
"""

import json
import os
import sqlite3
import tracemalloc
from datetime import datetime

from langchain_core.tools import tool
from logging_utils import log_panel
from config import (
    DATA_DIR, DIAGNOSTICS_DB_PATH, PROFILER_MAX_SNAPSHOTS,
    PROFILER_RSS_WARN_MB, PROFILER_RSS_ALERT_MB, PROFILER_GROWTH_WARN_MB,
)


# --- In-memory snapshot store ---
# Keeps the last N snapshots for quick comparison without DB round-trips.

_snapshots: list[dict] = []


# --- Database setup ---

def _connect() -> sqlite3.Connection:
    """Open diagnostics.db with dict-like row access."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DIAGNOSTICS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_diagnostics_db():
    """Create the memory_snapshots table if it doesn't exist.

    Stores lightweight summaries - not full snapshot data.
    Columns:
      label         - human-readable tag (e.g. "baseline", "after_pdf_parse")
      rss_mb        - resident set size from psutil (0 if unavailable)
      traced_mb     - total bytes tracked by tracemalloc
      top_allocs    - JSON: top 10 allocation sites [{file, line, size_kb}]
      snapshot_type - baseline / manual / request / periodic / alert
    """
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            label         TEXT NOT NULL,
            rss_mb        REAL NOT NULL DEFAULT 0,
            traced_mb     REAL NOT NULL DEFAULT 0,
            peak_mb       REAL NOT NULL DEFAULT 0,
            top_allocs    TEXT NOT NULL DEFAULT '[]',
            snapshot_type TEXT NOT NULL DEFAULT 'manual',
            created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# --- tracemalloc control ---

def start_profiling(nframes: int = 10):
    """Start tracemalloc if not already running.

    nframes controls call-stack depth per allocation.
    Higher = more detail but more overhead. 10 is a good balance.
    Ref: https://docs.python.org/3/library/tracemalloc.html#tracemalloc.start
    """
    if not tracemalloc.is_tracing():
        tracemalloc.start(nframes)


def stop_profiling():
    """Stop tracemalloc and clear data."""
    if tracemalloc.is_tracing():
        tracemalloc.stop()


def is_profiling() -> bool:
    """Check if tracemalloc is currently active."""
    return tracemalloc.is_tracing()


# --- Snapshot helpers ---

def _get_rss_mb() -> float:
    """Get current process RSS (resident set size) in MB via psutil.
    Falls back to 0 if psutil is not installed.
    """
    try:
        import psutil
        process = psutil.Process()
        return round(process.memory_info().rss / (1024 ** 2), 2)
    except (ImportError, Exception):
        return 0.0


def _format_top_allocs(snapshot, limit: int = 10) -> list[dict]:
    """Extract top allocation sites from a tracemalloc snapshot.

    Returns a list of dicts: {file, lineno, size_kb, count}.
    Ref: https://docs.python.org/3/library/tracemalloc.html#tracemalloc.Snapshot.statistics
    """
    stats = snapshot.statistics("lineno")
    result = []
    for stat in stats[:limit]:
        frame = stat.traceback[0]
        result.append({
            "file": frame.filename,
            "lineno": frame.lineno,
            "size_kb": round(stat.size / 1024, 2),
            "count": stat.count,
        })
    return result


def take_snapshot(label: str = "manual",
                  snapshot_type: str = "manual",
                  save_to_db: bool = True) -> dict:
    """Take a tracemalloc snapshot and return a summary dict.

    Optionally stores the summary in diagnostics.db for trend tracking.
    The full snapshot object is kept in-memory for comparison.
    """
    if not tracemalloc.is_tracing():
        return {"error": "Profiling not active. Call start_profiling() first."}

    snap = tracemalloc.take_snapshot()

    # -- Filter out tracemalloc's own allocations --
    snap = snap.filter_traces([
        tracemalloc.Filter(False, tracemalloc.__file__),
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
    ])

    current, peak = tracemalloc.get_traced_memory()
    rss = _get_rss_mb()
    top_allocs = _format_top_allocs(snap, limit=10)

    summary = {
        "label": label,
        "rss_mb": rss,
        "traced_mb": round(current / (1024 ** 2), 2),
        "peak_mb": round(peak / (1024 ** 2), 2),
        "top_allocs": top_allocs,
        "snapshot_type": snapshot_type,
        "timestamp": datetime.now().isoformat(),
    }

    # -- Keep in memory for quick comparison --
    _snapshots.append({"summary": summary, "snapshot": snap})
    if len(_snapshots) > PROFILER_MAX_SNAPSHOTS:
        _snapshots.pop(0)

    # -- Persist to DB --
    if save_to_db:
        _save_summary(summary)

    return summary


def _save_summary(summary: dict):
    """Write a snapshot summary to diagnostics.db."""
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO memory_snapshots
               (label, rss_mb, traced_mb, peak_mb, top_allocs, snapshot_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                summary["label"],
                summary["rss_mb"],
                summary["traced_mb"],
                summary["peak_mb"],
                json.dumps(summary["top_allocs"]),
                summary["snapshot_type"],
                summary["timestamp"],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # diagnostics should never crash the app


def compare_snapshots(old_idx: int = -2, new_idx: int = -1) -> dict:
    """Compare two in-memory snapshots and return the diff.

    Defaults to comparing the two most recent snapshots.
    Shows which allocations grew, shrank, or appeared.
    Ref: https://docs.python.org/3/library/tracemalloc.html#tracemalloc.Snapshot.compare_to
    """
    if len(_snapshots) < 2:
        return {"error": "Need at least 2 snapshots to compare."}

    try:
        old_snap = _snapshots[old_idx]["snapshot"]
        new_snap = _snapshots[new_idx]["snapshot"]
    except IndexError:
        return {"error": f"Invalid snapshot indices: {old_idx}, {new_idx}"}

    stats = new_snap.compare_to(old_snap, "lineno")

    grew = []
    shrank = []
    new_allocs = []

    for stat in stats[:15]:
        frame = stat.traceback[0]
        entry = {
            "file": frame.filename,
            "lineno": frame.lineno,
            "size_diff_kb": round(stat.size_diff / 1024, 2),
            "size_kb": round(stat.size / 1024, 2),
            "count_diff": stat.count_diff,
        }
        if stat.size_diff > 0:
            if stat.count_diff == stat.count:
                new_allocs.append(entry)
            else:
                grew.append(entry)
        elif stat.size_diff < 0:
            shrank.append(entry)

    old_summary = _snapshots[old_idx]["summary"]
    new_summary = _snapshots[new_idx]["summary"]

    return {
        "old": {"label": old_summary["label"], "traced_mb": old_summary["traced_mb"]},
        "new": {"label": new_summary["label"], "traced_mb": new_summary["traced_mb"]},
        "diff_mb": round(new_summary["traced_mb"] - old_summary["traced_mb"], 2),
        "grew": grew[:5],
        "shrank": shrank[:5],
        "new_allocs": new_allocs[:5],
    }


def get_memory_summary() -> dict:
    """Current memory state - no new snapshot, just reads live values.

    Returns RSS, tracemalloc stats, and the most recent snapshot info.
    """
    rss = _get_rss_mb()

    result = {
        "profiling_active": tracemalloc.is_tracing(),
        "rss_mb": rss,
        "traced_mb": 0,
        "peak_mb": 0,
        "snapshot_count": len(_snapshots),
    }

    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        result["traced_mb"] = round(current / (1024 ** 2), 2)
        result["peak_mb"] = round(peak / (1024 ** 2), 2)

    if _snapshots:
        result["last_snapshot"] = _snapshots[-1]["summary"]

    return result


def get_snapshot_history(limit: int = 20) -> list[dict]:
    """Read snapshot summaries from diagnostics.db for trend analysis."""
    try:
        conn = _connect()
        rows = conn.execute(
            """SELECT id, label, rss_mb, traced_mb, peak_mb,
                      snapshot_type, created_at
               FROM memory_snapshots
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_snapshot_detail(snapshot_id: int) -> dict | None:
    """Read a single snapshot with its full top_allocs from the DB."""
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM memory_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        result = dict(row)
        result["top_allocs"] = json.loads(result["top_allocs"])
        return result
    except Exception:
        return None


def check_memory_health() -> dict:
    """Quick health check - flags potential issues.

    Checks:
      - RSS over threshold (warn at 500MB, alert at 1GB)
      - Traced memory growing faster than expected
      - Peak memory significantly higher than current (possible spike)
    """
    rss = _get_rss_mb()
    status = "ok"
    warnings = []

    # -- RSS thresholds (from config.py) --
    if rss > PROFILER_RSS_ALERT_MB:
        status = "alert"
        warnings.append(f"RSS is {rss}MB - exceeds {PROFILER_RSS_ALERT_MB}MB threshold")
    elif rss > PROFILER_RSS_WARN_MB:
        status = "warning"
        warnings.append(f"RSS is {rss}MB - above {PROFILER_RSS_WARN_MB}MB")

    # -- Check for memory growth trend --
    if len(_snapshots) >= 3:
        recent = [s["summary"]["traced_mb"] for s in _snapshots[-3:]]
        if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
            growth = recent[-1] - recent[0]
            if growth > PROFILER_GROWTH_WARN_MB:
                status = "warning" if status == "ok" else status
                warnings.append(
                    f"Traced memory grew {growth:.1f}MB over last "
                    f"{len(recent)} snapshots - possible leak"
                )

    # -- Peak vs current gap --
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / (1024 ** 2)
        peak_mb = peak / (1024 ** 2)
        if peak_mb > 0 and current_mb > 0:
            ratio = peak_mb / current_mb
            if ratio > 3:
                warnings.append(
                    f"Peak ({peak_mb:.1f}MB) is {ratio:.1f}x current "
                    f"({current_mb:.1f}MB) - memory spikes detected"
                )

    return {
        "status": status,
        "rss_mb": rss,
        "warnings": warnings,
        "snapshot_count": len(_snapshots),
    }


# --- Agent tool ---

@tool(parse_docstring=True)
def memory_status(reasoning: str = "") -> str:
    """Check the server's current memory usage and health.

    Use this when troubleshooting performance issues, investigating
    slowness, or when asked about system resource usage.
    Returns RSS, traced allocations, health status, and recent trend.

    Args:
        reasoning: Optional. Why you are checking memory.

    Returns:
        A formatted memory status report.
    """
    if reasoning:
        log_panel(reasoning, title="memory_status - Reasoning")

    summary = get_memory_summary()
    health = check_memory_health()

    lines = [
        f"Memory Status: {health['status'].upper()}",
        f"  RSS (total process): {summary['rss_mb']} MB",
        f"  Profiling active: {summary['profiling_active']}",
    ]

    if summary["profiling_active"]:
        lines.append(f"  Traced allocations: {summary['traced_mb']} MB")
        lines.append(f"  Peak traced: {summary['peak_mb']} MB")
        lines.append(f"  Snapshots taken: {summary['snapshot_count']}")

    if health["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for w in health["warnings"]:
            lines.append(f"  - {w}")

    # -- Recent trend from DB --
    history = get_snapshot_history(limit=5)
    if history:
        lines.append("")
        lines.append("Recent snapshots:")
        for h in history:
            lines.append(
                f"  [{h['label']}] RSS={h['rss_mb']}MB "
                f"traced={h['traced_mb']}MB ({h['created_at']})"
            )

    result = "\n".join(lines)
    log_panel(result, title="memory_status - Result")
    return result


# --- Tool accessor ---

def get_memory_tools() -> list:
    """Memory diagnostic tools - read-only, safe for all agents."""
    return [memory_status]

"""Agent dispatch helpers — ported from VIPER's viper_live_dashboard.py (Phase 1.3).

Reads the Continental trio's ledger and task files so Control can serve
/api/agents/summary, /api/agents/tasks, /api/agents/cost_series, etc.
"""

import json
import os
import re
from pathlib import Path

LEDGER_PATH = Path("/home/ubuntu/.openclaw/workspace/polymarket-rbi-bot/cache/agent_costs.jsonl")
TASK_DIR = Path("/tmp/agent_tasks")
ALLOWED_LOG_ROOTS = (
    "/home/ubuntu/winston-logs/",
    "/home/ubuntu/chron-logs/",
)


def read_agent_ledger():
    """Parse the agent_costs.jsonl ledger, returning a list of dicts."""
    if not LEDGER_PATH.exists():
        return []
    rows = []
    with LEDGER_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def read_agent_task_files(limit=20):
    """Read the most recent task JSON files from /tmp/agent_tasks."""
    if not TASK_DIR.exists():
        return []
    files = sorted(TASK_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def resolve_log_path(task_id: str):
    """Return the validated log path for a task, or None.

    Only returns paths under explicitly allowed roots to prevent
    path-traversal via crafted task files.
    """
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", task_id or ""):
        return None
    # Prefer ledger entry — wrapper writes it last & is authoritative.
    for r in read_agent_ledger():
        if r.get("task_id") == task_id and r.get("log_path"):
            p = r["log_path"]
            if any(p.startswith(root) for root in ALLOWED_LOG_ROOTS):
                return p
    # Fall back to task file (gateway-side).
    tf = TASK_DIR / f"{task_id}.json"
    if tf.exists():
        try:
            t = json.loads(tf.read_text())
            p = t.get("log_path") or ""
            if p and any(p.startswith(root) for root in ALLOWED_LOG_ROOTS):
                return p
        except (json.JSONDecodeError, OSError):
            pass
    return None

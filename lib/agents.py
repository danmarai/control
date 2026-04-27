"""Agent fleet mapping and status helpers for the Agents tab."""

import os
import subprocess
from datetime import datetime, timezone


AGENT_FLEET = [
    {"id": "marvis",   "name": "MARVIS",   "role": "Commander",             "unit": "openclaw-gateway.service",   "scope": "user",   "type": "gateway",          "workspace": None,                                              "memory": "/home/ubuntu/.openclaw/MEMORY.md"},
    {"id": "forge",    "name": "FORGE",    "role": "Health Coach",          "unit": "openclaw-gateway.service",   "scope": "user",   "type": "openclaw",         "workspace": "/home/ubuntu/.openclaw/forge-workspace",          "memory": "/home/ubuntu/.openclaw/forge-workspace/MEMORY.md"},
    {"id": "edward",   "name": "EDWARD",   "role": "Engineering",           "unit": "openclaw-gateway.service",   "scope": "user",   "type": "openclaw",         "workspace": None,                                              "memory": None},
    {"id": "beacon",   "name": "BEACON",   "role": "Briefings",             "unit": "openclaw-gateway.service",   "scope": "user",   "type": "openclaw",         "workspace": None,                                              "memory": None},
    {"id": "alvin",    "name": "ALVIN",    "role": "Finance/Email",         "unit": "alvin.service",              "scope": "system", "type": "system_service",   "workspace": "/home/ubuntu/.openclaw/workspace/alvin",          "memory": None},
    {"id": "aegis",    "name": "AEGIS",    "role": "Listener",              "unit": "openclaw-aegis.service",     "scope": "user",   "type": "listener",         "workspace": None,                                              "memory": None},
    {"id": "oracle",   "name": "ORACLE",   "role": "Listener",              "unit": None,                         "scope": None,     "type": "listener_forked",  "workspace": "/home/ubuntu/.openclaw/agents/oracle",            "memory": None,  "process_path": "/home/ubuntu/.openclaw/agents/oracle/discord_listener.py"},
    {"id": "scribe",   "name": "SCRIBE",   "role": "Listener",              "unit": None,                         "scope": None,     "type": "listener_forked",  "workspace": "/home/ubuntu/.openclaw/agents/scribe",            "memory": None,  "process_path": "/home/ubuntu/.openclaw/agents/scribe/discord_listener.py"},
    {"id": "medic",    "name": "MEDIC",    "role": "Fleet Watchdog",        "unit": "openclaw-medic.service",     "scope": "user",   "type": "monitor",          "workspace": "/home/ubuntu/owen-hunt-medic",                    "memory": None},
    {"id": "winston",  "name": "WINSTON",  "role": "Builder (Claude CLI)",  "unit": None,                         "scope": None,     "type": "cli_invocation",   "workspace": "/home/ubuntu/winston-logs",                       "memory": "/home/ubuntu/winston-persona.md",  "process_path": None},
    {"id": "chron",    "name": "CHRON",    "role": "Reviewer (Codex CLI)",  "unit": None,                         "scope": None,     "type": "cli_invocation",   "workspace": "/home/ubuntu/chron-logs",                         "memory": "/home/ubuntu/chron-persona.md",    "process_path": None},
    {"id": "sinclair", "name": "SINCLAIR", "role": "Architect (Cowork)",    "unit": None,                         "scope": None,     "type": "remote",           "workspace": None,                                              "memory": None},
]


def get_agent_by_id(agent_id):
    """Look up an agent by id. Returns None if not found."""
    return next((a for a in AGENT_FLEET if a["id"] == agent_id), None)


def get_unit_status(unit, scope):
    """Check systemd unit status. Returns 'active', 'inactive', 'failed', or 'unknown'."""
    try:
        cmd = ["systemctl"]
        if scope == "user":
            cmd.append("--user")
        cmd.extend(["is-active", unit])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def get_listener_forked_status(process_path):
    """Check if a forked listener process is running via pgrep."""
    if not process_path:
        return "unknown"
    try:
        out = subprocess.run(
            ["pgrep", "-af", process_path],
            capture_output=True, text=True, timeout=2
        ).stdout.strip()
        return "active" if out else "inactive"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def get_cli_status(workspace):
    """Check CLI agent status by looking at recent log file activity."""
    if not workspace or not os.path.isdir(workspace):
        return "idle", None
    try:
        # Find most recently modified file in the logs dir
        newest_mtime = 0
        for entry in os.scandir(workspace):
            if entry.is_file():
                mt = entry.stat().st_mtime
                if mt > newest_mtime:
                    newest_mtime = mt
        if newest_mtime == 0:
            return "idle", None
        last_dt = datetime.fromtimestamp(newest_mtime, tz=timezone.utc)
        return "idle", last_dt.strftime("%Y-%m-%d %H:%M UTC")
    except OSError:
        return "idle", None


def get_last_seen(unit, scope):
    """Get most recent journal entry timestamp for a systemd unit."""
    if not unit:
        return None
    try:
        cmd = ["journalctl"]
        if scope == "user":
            cmd.append("--user")
        cmd.extend(["-u", unit, "-n", "1", "--no-pager", "--output=short-iso"])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        line = result.stdout.strip()
        if line:
            # First token is the ISO timestamp
            parts = line.split(" ", 1)
            return parts[0] if parts else None
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def get_workspace_size(path):
    """Get human-readable size of a directory."""
    if not path or not os.path.isdir(path):
        return None
    try:
        result = subprocess.run(
            ["du", "-sh", path],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.split()[0] if result.stdout.strip() else None
    except (subprocess.SubprocessError, OSError, IndexError):
        return None


def get_memory_size(path):
    """Get size of a MEMORY.md file."""
    if not path:
        return None
    try:
        size = os.path.getsize(path)
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size // 1024} KB"
        else:
            return f"{size // (1024 * 1024)} MB"
    except OSError:
        return None


def get_journal_lines(unit, scope, n=50):
    """Get last N lines from a systemd unit's journal."""
    if not unit:
        return None
    try:
        cmd = ["journalctl"]
        if scope == "user":
            cmd.append("--user")
        cmd.extend(["-u", unit, "-n", str(n), "--no-pager", "--output=short-iso"])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout if result.stdout.strip() else None
    except (subprocess.SubprocessError, OSError):
        return None


def gather_fleet_status():
    """Build the full fleet status table for the Agents tab."""
    fleet = []
    for agent in AGENT_FLEET:
        row = {
            "id": agent["id"],
            "name": agent["name"],
            "role": agent["role"],
            "type": agent["type"],
            "status": "unknown",
            "last_seen": None,
            "workspace_size": None,
            "memory_size": None,
            "has_unit": agent.get("unit") is not None,
            "scope": agent.get("scope"),
            "unit": agent.get("unit"),
            "can_restart": agent.get("scope") == "user" and agent.get("unit") is not None,
        }

        # Status
        if agent["type"] == "remote":
            row["status"] = "remote"
        elif agent["type"] == "cli_invocation":
            status, last_invoked = get_cli_status(agent.get("workspace"))
            row["status"] = status
            row["last_seen"] = last_invoked
        elif agent["type"] == "listener_forked":
            row["status"] = get_listener_forked_status(agent.get("process_path"))
        elif agent.get("unit"):
            row["status"] = get_unit_status(agent["unit"], agent["scope"])

        # Last seen (from journal, if we have a unit and didn't already set it)
        if not row["last_seen"] and agent.get("unit"):
            row["last_seen"] = get_last_seen(agent["unit"], agent["scope"])

        # Workspace size
        row["workspace_size"] = get_workspace_size(agent.get("workspace"))

        # Memory size
        row["memory_size"] = get_memory_size(agent.get("memory"))

        fleet.append(row)
    return fleet

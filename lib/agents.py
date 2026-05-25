"""Agent fleet mapping and status helpers for the Agents tab."""

import os
import subprocess
from datetime import datetime, timezone


HOME = os.path.expanduser("~")
OPENCLAW = os.path.join(HOME, ".openclaw")
LOG_DIR = os.path.join(OPENCLAW, "logs")


def _log(name):
    return os.path.join(LOG_DIR, name)


AGENT_FLEET = [
    {
        "id": "marvis",
        "name": "MARVIS",
        "role": "Commander",
        "unit": "com.openclaw.gateway",
        "scope": "launchd",
        "type": "gateway",
        "workspace": None,
        "memory": os.path.join(OPENCLAW, "MEMORY.md"),
        "log_path": _log("gateway.log"),
        "err_path": _log("gateway.err"),
    },
    {
        "id": "forge",
        "name": "FORGE",
        "role": "Health Coach",
        "unit": "com.openclaw.gateway",
        "scope": "launchd",
        "type": "openclaw",
        "workspace": os.path.join(OPENCLAW, "forge-workspace"),
        "memory": os.path.join(OPENCLAW, "forge-workspace", "MEMORY.md"),
        "log_path": _log("gateway.log"),
        "err_path": _log("gateway.err"),
    },
    {
        "id": "edward",
        "name": "EDWARD",
        "role": "Engineering",
        "unit": "com.openclaw.gateway",
        "scope": "launchd",
        "type": "openclaw",
        "workspace": None,
        "memory": None,
        "log_path": _log("gateway.log"),
        "err_path": _log("gateway.err"),
    },
    {
        "id": "beacon",
        "name": "BEACON",
        "role": "Briefings",
        "unit": "com.openclaw.gateway",
        "scope": "launchd",
        "type": "openclaw",
        "workspace": None,
        "memory": None,
        "log_path": _log("gateway.log"),
        "err_path": _log("gateway.err"),
    },
    {
        "id": "aegis",
        "name": "AEGIS",
        "role": "Listener",
        "unit": "com.openclaw.aegis",
        "scope": "launchd",
        "type": "listener",
        "workspace": os.path.join(OPENCLAW, "agents", "aegis"),
        "memory": None,
        "log_path": _log("aegis.log"),
        "err_path": _log("aegis.err"),
    },
    {
        "id": "oracle",
        "name": "ORACLE",
        "role": "Listener",
        "unit": "com.openclaw.oracle",
        "scope": "launchd",
        "type": "listener",
        "workspace": os.path.join(OPENCLAW, "agents", "oracle"),
        "memory": None,
        "log_path": _log("oracle.log"),
        "err_path": _log("oracle.err"),
    },
    {
        "id": "scribe",
        "name": "SCRIBE",
        "role": "Listener",
        "unit": "com.openclaw.scribe",
        "scope": "launchd",
        "type": "listener",
        "workspace": os.path.join(OPENCLAW, "agents", "scribe"),
        "memory": None,
        "log_path": _log("scribe.log"),
        "err_path": _log("scribe.err"),
    },
    {
        "id": "medic",
        "name": "MEDIC",
        "role": "Fleet Watchdog",
        "unit": "com.openclaw.medic",
        "scope": "launchd",
        "type": "monitor",
        "workspace": OPENCLAW,
        "memory": None,
        "log_path": _log("medic.log"),
        "err_path": _log("medic.err"),
    },
    {
        "id": "api_proxy",
        "name": "API PROXY",
        "role": "Model/API proxy",
        "unit": "com.openclaw.api-proxy",
        "scope": "launchd",
        "type": "agent_platform",
        "workspace": OPENCLAW,
        "memory": None,
        "log_path": _log("api-proxy.log"),
        "err_path": _log("api-proxy.err"),
    },
    {
        "id": "mlx_server",
        "name": "MLX SERVER",
        "role": "Local model endpoint",
        "unit": "com.openclaw.mlx-server",
        "scope": "launchd",
        "type": "model_server",
        "workspace": os.path.join(HOME, "ollama", "mlx"),
        "memory": None,
        "log_path": _log("mlx-server.log"),
        "err_path": _log("mlx-server.err"),
    },
    {
        "id": "marvis_voice",
        "name": "MARVIS VOICE",
        "role": "Voice interface",
        "unit": "com.openclaw.marvis-voice",
        "scope": "launchd",
        "type": "agent_platform",
        "workspace": OPENCLAW,
        "memory": None,
        "log_path": _log("marvis-voice.log"),
        "err_path": _log("marvis-voice.err"),
    },
    {
        "id": "winston",
        "name": "WINSTON",
        "role": "Builder (Claude CLI)",
        "unit": None,
        "scope": None,
        "type": "cli_invocation",
        "workspace": os.path.join(HOME, "winston-logs"),
        "memory": os.path.join(HOME, "winston-persona.md"),
        "process_path": None,
    },
    {
        "id": "chron",
        "name": "CHRON",
        "role": "Reviewer (Codex CLI)",
        "unit": None,
        "scope": None,
        "type": "cli_invocation",
        "workspace": os.path.join(HOME, "chron-logs"),
        "memory": os.path.join(HOME, "chron-persona.md"),
        "process_path": None,
    },
    {
        "id": "sinclair",
        "name": "SINCLAIR",
        "role": "Architect (Cowork)",
        "unit": None,
        "scope": None,
        "type": "remote",
        "workspace": None,
        "memory": None,
    },
]


def get_agent_by_id(agent_id):
    """Look up an agent by id. Returns None if not found."""
    return next((a for a in AGENT_FLEET if a["id"] == agent_id), None)


def _is_launchd(scope, unit=None):
    return scope == "launchd" or (unit or "").startswith("com.")


def get_unit_status(unit, scope):
    """Check launchd or systemd unit status."""
    if not unit:
        return "unknown"
    try:
        if _is_launchd(scope, unit):
            result = subprocess.run(
                ["launchctl", "list", unit],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return "inactive"
            has_pid = '"PID" =' in result.stdout or "\t\"PID\" =" in result.stdout
            return "active" if has_pid else "inactive"

        cmd = ["systemctl"]
        if scope == "user":
            cmd.append("--user")
        cmd.extend(["is-active", unit])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def restart_unit(unit, scope):
    """Restart a launchd or systemd unit and return the subprocess result."""
    if _is_launchd(scope, unit):
        return subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{unit}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    cmd = ["systemctl"]
    if scope == "user":
        cmd.append("--user")
    cmd.extend(["restart", unit])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15)


def get_listener_forked_status(process_path):
    """Check if a forked listener process is running via pgrep."""
    if not process_path:
        return "unknown"
    try:
        out = subprocess.run(
            ["pgrep", "-fl", process_path],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        return "active" if out else "inactive"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def get_cli_status(workspace):
    """Check CLI agent status by looking at recent log file activity."""
    if not workspace or not os.path.isdir(workspace):
        return "idle", None
    try:
        newest_mtime = 0
        for entry in os.scandir(workspace):
            if entry.is_file():
                mt = entry.stat().st_mtime
                if mt > newest_mtime:
                    newest_mtime = mt
        if newest_mtime == 0:
            return "idle", None
        return "idle", _format_timestamp(newest_mtime)
    except OSError:
        return "idle", None


def get_last_seen(unit, scope, log_path=None, err_path=None):
    """Get most recent activity timestamp for a unit."""
    if _is_launchd(scope, unit):
        newest = _newest_mtime([log_path, err_path])
        return _format_timestamp(newest) if newest else None
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
            capture_output=True,
            text=True,
            timeout=10,
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
        if size < 1024 * 1024:
            return f"{size // 1024} KB"
        return f"{size // (1024 * 1024)} MB"
    except OSError:
        return None


def get_journal_lines(unit, scope, n=50, log_path=None, err_path=None):
    """Get recent lines from launchd log files or a systemd journal."""
    if _is_launchd(scope, unit):
        return _tail_files([log_path, err_path], n=n)
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
            "can_restart": agent.get("scope") in {"user", "launchd"} and agent.get("unit") is not None,
        }

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

        if not row["last_seen"] and agent.get("unit"):
            row["last_seen"] = get_last_seen(
                agent["unit"],
                agent["scope"],
                log_path=agent.get("log_path"),
                err_path=agent.get("err_path"),
            )

        row["workspace_size"] = get_workspace_size(agent.get("workspace"))
        row["memory_size"] = get_memory_size(agent.get("memory"))

        fleet.append(row)
    return fleet


def _newest_mtime(paths):
    newest = 0
    for path in paths:
        if not path:
            continue
        try:
            newest = max(newest, os.path.getmtime(path))
        except OSError:
            pass
    return newest


def _format_timestamp(epoch):
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _tail_files(paths, n=50):
    existing = [path for path in paths if path and os.path.exists(path)]
    if not existing:
        return None
    parts = []
    for path in existing:
        try:
            result = subprocess.run(
                ["tail", "-n", str(n), path],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            parts.append(f"==> {path} <==\nRead error: {exc}")
            continue
        body = result.stdout.strip()
        if body:
            parts.append(f"==> {path} <==\n{body}")
    return "\n\n".join(parts) if parts else None

"""Auto-discover services, cron jobs, and git repos on this box."""

import os
import subprocess


def discover_systemd_units():
    """List user systemd service units."""
    try:
        out = subprocess.run(
            ["systemctl", "--user", "list-units", "--type=service", "--no-pager", "--plain"],
            capture_output=True, text=True, timeout=10
        )
        units = []
        for line in out.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                units.append(parts[0])
        return units
    except (subprocess.SubprocessError, OSError):
        return []


def discover_cron_jobs():
    """Parse crontab -l for cron entries."""
    try:
        out = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10
        )
        jobs = []
        for line in out.stdout.strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                jobs.append(line)
        return jobs
    except (subprocess.SubprocessError, OSError):
        return []


def discover_git_repos():
    """Scan ~/ and ~/.openclaw/workspace/ for git directories."""
    repos = []
    home = os.path.expanduser("~")

    # Top-level ~/*/  .git dirs
    try:
        for entry in os.listdir(home):
            full = os.path.join(home, entry)
            if os.path.isdir(full) and os.path.isdir(os.path.join(full, ".git")):
                repos.append({"id": entry, "path": full, "source": "home"})
    except OSError:
        pass

    # ~/.openclaw/workspace sub-projects
    ws = os.path.join(home, ".openclaw", "workspace")
    try:
        for entry in os.listdir(ws):
            full = os.path.join(ws, entry)
            if os.path.isdir(full) and os.path.isdir(os.path.join(full, ".git")):
                repos.append({"id": entry, "path": full, "source": "workspace"})
    except OSError:
        pass

    return repos


def discover_all():
    """Return a list of discovered project dicts."""
    discovered = []
    for repo in discover_git_repos():
        discovered.append({
            "id": repo["id"],
            "name": repo["id"],
            "type": "discovered",
            "description": f"Git repo at {repo['path']}",
            "code_path": repo["path"],
            "tags": ["discovered", repo["source"]],
        })
    return discovered

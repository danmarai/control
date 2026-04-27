"""Control — fleet ops portal for Dan's EC2 enterprise."""

import glob
import json
import os
import subprocess
import time
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, jsonify, Response

from lib.manifest import read_manifest
from lib.registry import load_registry, merge_projects
from lib.discovery import discover_all

APP_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

app = Flask(__name__)


def _get_context():
    """Build template context: projects, links, manifest, errors."""
    registry, reg_error = load_registry(APP_DIR)
    manifest, manifest_age = read_manifest()
    discovered = discover_all()

    reg_projects = registry.get("projects", [])
    links = registry.get("links", [])
    projects = merge_projects(reg_projects, discovered)

    return {
        "projects": projects,
        "links": links,
        "manifest": manifest,
        "manifest_age": manifest_age,
        "registry_error": reg_error,
    }


# --- Core tabs ---

@app.route("/")
def index():
    return redirect("/projects")


@app.route("/projects")
def projects():
    ctx = _get_context()
    all_projects = ctx["projects"]
    ctx["primary_count"] = sum(1 for p in all_projects if p.get("tier") == "primary")
    ctx["secondary_count"] = sum(1 for p in all_projects if p.get("tier") != "primary")
    return render_template("projects.html", **ctx)


@app.route("/links")
def links():
    ctx = _get_context()
    return render_template("links.html", **ctx)


@app.route("/agents")
def agents():
    """Agents tab — real data from cost-tracker JSONL."""
    jsonl_path = os.path.join(
        HOME, ".openclaw/workspace/polymarket-rbi-bot/cost-tracker/api_calls.jsonl"
    )
    agent_data = {}
    now = time.time()
    seven_days_ago = now - 7 * 86400

    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # The field is 'note' (caller alias)
                caller = entry.get("note", "unknown")
                ts_str = entry.get("ts", "")
                cost = entry.get("real_cost_usd") or entry.get("cost_estimate") or 0
                model = entry.get("model", "unknown")

                if caller not in agent_data:
                    agent_data[caller] = {
                        "name": caller,
                        "calls_7d": 0,
                        "spend_7d": 0.0,
                        "has_real_cost": False,
                        "last_call": "",
                        "models": set(),
                    }

                agent_data[caller]["models"].add(model)
                agent_data[caller]["last_call"] = ts_str

                # Check if within 7 days
                try:
                    ts_dt = datetime.fromisoformat(ts_str)
                    ts_epoch = ts_dt.timestamp()
                    if ts_epoch >= seven_days_ago:
                        agent_data[caller]["calls_7d"] += 1
                        agent_data[caller]["spend_7d"] += float(cost)
                except (ValueError, TypeError):
                    pass

                if entry.get("real_cost_usd") and float(entry["real_cost_usd"]) > 0:
                    agent_data[caller]["has_real_cost"] = True

        # Convert sets to sorted lists for template
        for a in agent_data.values():
            a["models"] = sorted(a["models"])
        jsonl_exists = True
    else:
        jsonl_exists = False

    # Static fleet roster from registry
    fleet_roster = [
        "MARVIS", "FORGE", "EDWARD", "BEACON", "ALVIN",
        "AEGIS", "ORACLE", "SCRIBE", "MEDIC"
    ]

    return render_template(
        "agents.html",
        agents=sorted(agent_data.values(), key=lambda a: a["name"]),
        jsonl_exists=jsonl_exists,
        fleet_roster=fleet_roster,
        now=datetime.now(timezone.utc),
    )


@app.route("/health")
def health():
    """Health tab — live system data, read at request time."""
    data = {}

    # Host info
    try:
        data["uptime"] = subprocess.run(
            ["uptime", "-p"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        data["uptime"] = "unknown"

    try:
        data["loadavg"] = open("/proc/loadavg").read().strip()
    except OSError:
        data["loadavg"] = "unknown"

    # Memory
    try:
        meminfo = {}
        for line in open("/proc/meminfo"):
            parts = line.split(":")
            if len(parts) == 2:
                meminfo[parts[0].strip()] = parts[1].strip()
        data["mem_total"] = meminfo.get("MemTotal", "?")
        data["mem_free"] = meminfo.get("MemFree", "?")
        data["mem_available"] = meminfo.get("MemAvailable", "?")
    except OSError:
        data["mem_total"] = data["mem_free"] = data["mem_available"] = "?"

    # Disk
    try:
        df_out = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=5
        ).stdout
        lines = df_out.strip().splitlines()
        if len(lines) >= 2:
            data["disk"] = lines[1]
        else:
            data["disk"] = "unknown"
    except (subprocess.SubprocessError, OSError):
        data["disk"] = "unknown"

    # Systemd units
    units = [
        {"name": "viper-dashboard.service", "scope": "system"},
        {"name": "control-portal.service", "scope": "user"},
        {"name": "openclaw-gateway.service", "scope": "system"},
        {"name": "openclaw-medic.service", "scope": "system"},
        {"name": "life360-context.service", "scope": "system"},
        {"name": "nginx.service", "scope": "system"},
    ]
    for unit in units:
        try:
            cmd = ["systemctl"]
            if unit["scope"] == "user":
                cmd.append("--user")
            cmd.extend(["is-active", unit["name"]])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            unit["state"] = result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            unit["state"] = "unknown"
    data["units"] = units

    # Pipeline freshness
    cron_log = os.path.join(
        HOME, ".openclaw/workspace/polymarket-rbi-bot/cache/cron_pipeline.log"
    )
    if os.path.exists(cron_log):
        mtime = os.path.getmtime(cron_log)
        age_hours = (time.time() - mtime) / 3600.0
        data["pipeline_age_hours"] = round(age_hours, 1)
    else:
        data["pipeline_age_hours"] = None

    # Cert expiry
    domains = ["frameapp", "control", "viper", "cortex"]
    certs = []
    for domain in domains:
        fqdn = f"{domain}.dmarantz.com" if domain != "frameapp" else "frameapp"
        cert_path = f"/etc/letsencrypt/live/{fqdn}/cert.pem"
        # All domains share control.dmarantz.com cert in this setup
        if domain != "frameapp":
            cert_path = f"/etc/letsencrypt/live/control.dmarantz.com/cert.pem"
        try:
            result = subprocess.run(
                ["sudo", "openssl", "x509", "-enddate", "-noout", "-in", cert_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse: notAfter=Jul 26 15:30:00 2026 GMT
                end_str = result.stdout.strip().split("=", 1)[1]
                end_dt = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %Z")
                days_left = (end_dt - datetime.utcnow()).days
                certs.append({"domain": fqdn, "days_left": days_left, "error": None})
            else:
                certs.append({"domain": fqdn, "days_left": None, "error": result.stderr.strip()})
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            certs.append({"domain": fqdn, "days_left": None, "error": str(e)})

    # Also check frameapp cert specifically
    try:
        result = subprocess.run(
            ["sudo", "openssl", "x509", "-enddate", "-noout", "-in",
             "/etc/letsencrypt/live/frameapp/cert.pem"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            end_str = result.stdout.strip().split("=", 1)[1]
            end_dt = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %GMT")
            days_left = (end_dt - datetime.utcnow()).days
            certs[0] = {"domain": "frameapp", "days_left": days_left, "error": None}
        else:
            certs[0] = {"domain": "frameapp", "days_left": None, "error": result.stderr.strip()}
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        certs[0] = {"domain": "frameapp", "days_left": None, "error": str(e)}

    data["certs"] = certs

    return render_template("health.html", **data)


# --- Data routes ---

@app.route("/forge/latest-weekly")
def forge_latest_weekly():
    """Serve the most recent Forge weekly report HTML."""
    base = os.path.join(HOME, ".openclaw/forge-workspace/archive/weeks")
    # Path traversal guard
    base_real = os.path.realpath(base)
    if not base_real.startswith(HOME):
        return "<h1>403 Forbidden</h1>", 403

    matches = sorted(glob.glob(os.path.join(base, "week*_report.html")))
    if not matches:
        return render_template("_simple_page.html",
                               title="Forge Weekly",
                               message="No Forge weekly report found yet."), 404

    latest = matches[-1]
    # Verify path stays under HOME
    if not os.path.realpath(latest).startswith(HOME):
        return "<h1>403 Forbidden</h1>", 403

    with open(latest, "r") as f:
        content = f.read()
    return Response(content, mimetype="text/html")


@app.route("/life360/recent")
def life360_recent():
    """Render current Life360 location state."""
    state_file = os.path.join(HOME, "life360-context/location_state.json")
    # Path traversal guard
    if not os.path.realpath(state_file).startswith(HOME):
        return "<h1>403 Forbidden</h1>", 403

    if not os.path.exists(state_file):
        return render_template("_simple_page.html",
                               title="Life360 Recent",
                               message="location_state.json not found."), 404

    mtime = os.path.getmtime(state_file)
    age_seconds = time.time() - mtime
    stale = age_seconds > 3600  # >1 hour

    with open(state_file, "r") as f:
        data = json.load(f)

    return render_template(
        "life360.html",
        data=data,
        stale=stale,
        age_seconds=int(age_seconds),
        updated_at=data.get("updated_at", "unknown"),
    )


@app.route("/api/cron/list")
def api_cron_list():
    """Read-only crontab listing."""
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        return Response(result.stdout, mimetype="text/plain")
    except (subprocess.SubprocessError, OSError):
        return "Could not read crontab", 500


@app.route("/api/medic/recent")
def api_medic_recent():
    """Last 20 lines of medic log."""
    log_path = os.path.join(HOME, "owen-hunt-medic/medic.log")
    if not os.path.realpath(log_path).startswith(HOME):
        return "403 Forbidden", 403
    if not os.path.exists(log_path):
        return "Medic log not found at owen-hunt-medic/medic.log", 404
    try:
        result = subprocess.run(
            ["tail", "-20", log_path], capture_output=True, text=True, timeout=5
        )
        return Response(result.stdout, mimetype="text/plain")
    except (subprocess.SubprocessError, OSError):
        return "Could not read medic log", 500


# --- API ---

@app.route("/api/projects.json")
def api_projects():
    ctx = _get_context()
    return jsonify(ctx["projects"])


@app.route("/api/links.json")
def api_links():
    ctx = _get_context()
    return jsonify(ctx["links"])


@app.route("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8081)

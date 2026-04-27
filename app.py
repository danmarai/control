"""Control — fleet ops portal for Dan's EC2 enterprise."""

import glob
import json
import os
import subprocess
import time
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, jsonify, Response, request

from lib.manifest import read_manifest
from lib.registry import load_registry, merge_projects
from lib.discovery import discover_all
from lib.agents import (
    AGENT_FLEET, get_agent_by_id, gather_fleet_status,
    get_journal_lines, get_listener_forked_status,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

# Phase 1.3 will enable this after SSO + CSRF ships
ALLOW_RESTART_ACTIONS = False

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
    """Agents tab — fleet health + cost-tracker JSONL."""
    # Section A: Fleet health
    fleet = gather_fleet_status()

    # Section B: Spend (last 7 days) from cost-tracker JSONL
    jsonl_path = os.path.join(
        HOME, ".openclaw/workspace/polymarket-rbi-bot/cost-tracker/api_calls.jsonl"
    )
    agent_costs = {}
    now_ts = time.time()
    seven_days_ago = now_ts - 7 * 86400

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
                caller = entry.get("note", "unknown")
                ts_str = entry.get("ts", "")
                cost = entry.get("real_cost_usd") or entry.get("cost_estimate") or 0
                model = entry.get("model", "unknown")

                if caller not in agent_costs:
                    agent_costs[caller] = {
                        "name": caller,
                        "calls_7d": 0,
                        "spend_7d": 0.0,
                        "has_real_cost": False,
                        "last_call": "",
                        "models": set(),
                    }

                agent_costs[caller]["models"].add(model)
                agent_costs[caller]["last_call"] = ts_str

                try:
                    ts_dt = datetime.fromisoformat(ts_str)
                    ts_epoch = ts_dt.timestamp()
                    if ts_epoch >= seven_days_ago:
                        agent_costs[caller]["calls_7d"] += 1
                        agent_costs[caller]["spend_7d"] += float(cost)
                except (ValueError, TypeError):
                    pass

                if entry.get("real_cost_usd") and float(entry["real_cost_usd"]) > 0:
                    agent_costs[caller]["has_real_cost"] = True

        for a in agent_costs.values():
            a["models"] = sorted(a["models"])
        jsonl_exists = True
    else:
        jsonl_exists = False

    return render_template(
        "agents.html",
        fleet=fleet,
        agent_costs=sorted(agent_costs.values(), key=lambda a: a["name"]),
        jsonl_exists=jsonl_exists,
        now=datetime.now(timezone.utc),
        allow_restart=ALLOW_RESTART_ACTIONS,
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

    # Systemd units — scopes verified 2026-04-27 (Phase 1.2)
    units = [
        # User-systemd services (the openclaw fleet)
        {"name": "control-portal.service", "scope": "user", "category": "ops"},
        {"name": "openclaw-gateway.service", "scope": "user", "category": "agent_platform"},
        {"name": "openclaw-medic.service", "scope": "user", "category": "monitor"},
        {"name": "openclaw-aegis.service", "scope": "user", "category": "agent"},
        {"name": "openclaw-api-proxy.service", "scope": "user", "category": "agent_platform"},
        {"name": "marvis-memory-webhook.service", "scope": "user", "category": "agent_platform"},
        # System-systemd services
        {"name": "alvin.service", "scope": "system", "category": "agent"},
        {"name": "viper-dashboard.service", "scope": "system", "category": "trading"},
        {"name": "life360-context.service", "scope": "system", "category": "data_feed"},
        {"name": "nginx.service", "scope": "system", "category": "infra"},
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
    # Group by category for template rendering
    from collections import OrderedDict
    cat_order = ["ops", "agent_platform", "agent", "monitor", "trading", "data_feed", "infra"]
    by_cat = OrderedDict()
    for cat in cat_order:
        group = [u for u in units if u.get("category") == cat]
        if group:
            by_cat[cat] = group
    data["units_by_category"] = list(by_cat.items())

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


@app.route("/api/projects/<project_id>/log/tail")
def project_log_tail(project_id):
    """Return last N lines of a project's log_path (from registry).

    Read-only. Path-traversal guarded. Caps response at 500 lines.
    """
    n = min(int(request.args.get("n", 100)), 500)
    registry, _ = load_registry(APP_DIR)
    projects = registry.get("projects", [])
    proj = next((p for p in projects if p.get("id") == project_id), None)
    if not proj:
        return Response(f"Unknown project: {project_id}", 404, mimetype="text/plain")
    log_path = proj.get("log_path")
    if not log_path:
        return Response(f"No log_path defined for {project_id}", 404, mimetype="text/plain")
    real = os.path.realpath(log_path)
    if not real.startswith("/home/ubuntu/"):
        return Response("log_path outside allowed root", 403, mimetype="text/plain")
    if not os.path.exists(real):
        return Response(f"Log not found: {log_path}", 404, mimetype="text/plain")
    try:
        out = subprocess.run(
            ["tail", "-n", str(n), real],
            capture_output=True, text=True, timeout=5
        ).stdout
        return Response(out, 200, mimetype="text/plain")
    except (subprocess.SubprocessError, OSError) as e:
        return Response(f"Read error: {e}", 500, mimetype="text/plain")


@app.route("/api/medic/recent")
def api_medic_recent():
    """Last 30 lines from openclaw-medic.service user journal."""
    try:
        out = subprocess.run(
            ["journalctl", "--user", "-u", "openclaw-medic.service",
             "-n", "30", "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=5
        ).stdout
        if not out.strip():
            return Response("No recent medic activity in journal.", 200, mimetype="text/plain")
        return Response(out, 200, mimetype="text/plain")
    except (subprocess.SubprocessError, OSError) as e:
        return Response(f"journalctl error: {e}", 500, mimetype="text/plain")


# --- Agent API routes ---

@app.route("/api/agents/<agent_id>/log")
def api_agent_log(agent_id):
    """Last 50 journal lines for an agent's unit (or pgrep output for forked)."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        return Response(f"Unknown agent: {agent_id}", 404, mimetype="text/plain")

    if agent["type"] == "listener_forked":
        pp = agent.get("process_path", "")
        if pp:
            try:
                out = subprocess.run(
                    ["pgrep", "-af", pp],
                    capture_output=True, text=True, timeout=2
                ).stdout
                return Response(out or "No matching process found.", 200, mimetype="text/plain")
            except (subprocess.SubprocessError, OSError) as e:
                return Response(f"pgrep error: {e}", 500, mimetype="text/plain")
        return Response("No process_path configured for this agent.", 404, mimetype="text/plain")

    if agent["type"] in ("cli_invocation", "remote"):
        return Response(f"No journal available for {agent['type']} agent.", 200, mimetype="text/plain")

    unit = agent.get("unit")
    scope = agent.get("scope")
    if not unit:
        return Response("No systemd unit configured for this agent.", 404, mimetype="text/plain")

    out = get_journal_lines(unit, scope, n=50)
    if out:
        return Response(out, 200, mimetype="text/plain")
    return Response("No recent journal entries.", 200, mimetype="text/plain")


@app.route("/api/agents/<agent_id>/restart", methods=["POST"])
def api_agent_restart(agent_id):
    """Restart a user-systemd agent. Disabled by default (Phase 1.3)."""
    if not ALLOW_RESTART_ACTIONS:
        return jsonify({"error": "restart actions disabled — Phase 1.3"}), 503

    agent = get_agent_by_id(agent_id)
    if not agent:
        return jsonify({"error": f"unknown agent: {agent_id}"}), 404
    if agent.get("scope") != "user" or not agent.get("unit"):
        return jsonify({"error": f"agent {agent_id} is not a restartable user-systemd unit"}), 400

    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", agent["unit"]],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return jsonify({"ok": True, "agent": agent_id, "unit": agent["unit"]})
        return jsonify({"error": result.stderr.strip()}), 500
    except (subprocess.SubprocessError, OSError) as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents.json")
def api_agents_json():
    """JSON dump of fleet status data."""
    fleet = gather_fleet_status()
    return jsonify(fleet)


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

"""Control — fleet ops portal for Dan's EC2 enterprise."""

import os
from flask import Flask, render_template, redirect, jsonify

from lib.manifest import read_manifest
from lib.registry import load_registry, merge_projects
from lib.discovery import discover_all

APP_DIR = os.path.dirname(os.path.abspath(__file__))

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


@app.route("/")
def index():
    return redirect("/projects")


@app.route("/projects")
def projects():
    ctx = _get_context()
    return render_template("projects.html", **ctx)


@app.route("/links")
def links():
    ctx = _get_context()
    return render_template("links.html", **ctx)


@app.route("/agents")
def agents():
    return render_template("_stub.html", tab_name="Agents",
                           message="Wired up in v1.1 — see directive-control-phase2.md")


@app.route("/health")
def health():
    return render_template("_stub.html", tab_name="Health",
                           message="Wired up in v1.1 — see directive-control-phase2.md")


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

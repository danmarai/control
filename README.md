# Control

Fleet ops portal for Dan's EC2 enterprise.

## Tabs

- **Projects**: registry + auto-discovered services, repos, cron jobs. Split into Primary (explicit, important) and Discovered/Secondary (auto-discovered + demoted). Secondary section is behind a collapsible `<details>` expando, collapsed by default.
- **Links**: bookmarks to API consoles, dashboards, admin panels, server infra.
- **Agents**: live agent status + cost rollup from `cost-tracker/api_calls.jsonl`. Shows calls, spend, models per agent. "Unmonitored" badge if no real cost data.
- **Health**: system health — host stats, critical systemd units, pipeline freshness, TLS cert expiry.

## Agents view

The Agents tab has three sections:

1. **Fleet Health** — table showing every agent's status, last-seen timestamp, workspace size, memory file size, and a "Recent log" action link. Status is pulled live from `systemctl`, `journalctl`, or `pgrep` depending on agent type.
2. **Spend (last 7 days)** — cost rollup from `cost-tracker/api_calls.jsonl`. Shows calls, spend, models per agent. "Unmonitored" badge if no real cost data.
3. **Quick Actions** — collapsible section with SSH tunnel instructions for the OpenClaw Gateway portal and per-agent restart buttons (disabled by default — see below).

### `AGENT_FLEET` mapping

The fleet roster lives in `lib/agents.py` as `AGENT_FLEET`. Each entry has: `id`, `name`, `role`, `unit` (systemd unit name or None), `scope` (user/system/None), `type` (gateway/openclaw/listener/listener_forked/monitor/system_service/cli_invocation/remote), `workspace`, `memory`.

**To add a new agent:** append an entry to `AGENT_FLEET` in `lib/agents.py`. If it has a systemd unit, status will be auto-detected. For forked listeners, set `type: "listener_forked"` and provide `process_path`.

### `ALLOW_RESTART_ACTIONS`

Set to `False` in `app.py`. The restart route (`POST /api/agents/<id>/restart`) exists but returns 503 until Phase 1.3 ships SSO + CSRF protection. Dan flips it to `True` after reviewing the auth story.

## Routes

| Route | Purpose |
|---|---|
| `/` | Redirect to `/projects` |
| `/projects` | Projects tab (primary + secondary expando) |
| `/links` | Links tab (categorized bookmarks) |
| `/agents` | Agents tab (fleet health + costs + quick actions) |
| `/health` | Health tab (host, services grouped by category, pipeline, certs) |
| `/forge/latest-weekly` | Serve latest Forge weekly report HTML |
| `/life360/recent` | Render current Life360 location state |
| `/api/cron/list` | Read-only crontab listing (text/plain) |
| `/api/medic/recent` | Last 30 lines from medic user journal |
| `/api/projects/<id>/log/tail` | Generic per-project log tail with path-traversal guard |
| `/api/agents/<id>/log` | Last 50 journal lines for agent (or pgrep for forked) |
| `/api/agents/<id>/restart` | POST — restart user-systemd agent (disabled, returns 503) |
| `/api/agents.json` | JSON dump of fleet status data |
| `/api/projects.json` | Projects as JSON |
| `/api/links.json` | Links as JSON |
| `/healthz` | Health check endpoint |

## Registry tier convention

Each project in `registry.yaml` has a `tier` field:

- **`primary`** (default): Explicitly important projects. Shown in the main Projects card grid.
- **`secondary`**: Demoted or auto-discovered projects. Shown in the collapsible expando. Auto-discovered entries from `lib/discovery.py` always get `tier: secondary`.

Registry entries are authoritative — if a project is in the registry, its tier stays as specified even if auto-discovery would also find it.

## Adding a new project

Add an entry to `registry.yaml` under `projects:`:

```yaml
- id: my_project
  name: My Project
  tier: primary          # primary | secondary (default: primary)
  type: web              # trading | agent | web | monitor | data_feed | data_pipeline | ops | planned
  description: What it does
  status_source:
    type: systemd_unit   # systemd_unit | http_probe | cron_log | planned | deprecated
    unit: my-project.service
  dashboard_url: https://example.com
  repo_url: https://github.com/danmarai/my-project
  code_path: /home/ubuntu/my-project
  tags: [web]
  links:                 # optional per-project links
    - { label: "Docs", url: "https://docs.example.com" }
```

## Auto-discovery

`lib/discovery.py` scans `~/` and `~/.openclaw/workspace/` for git repos. Discovered entries get `tier: secondary` and `discovered: true`. The merge logic in `lib/registry.py` gives registry entries precedence by `id` — discovered entries only appear if no registry entry shares the same `id`.

## Run

```bash
python3 app.py   # binds 127.0.0.1:8081
```

Served via nginx reverse proxy at `https://control.dmarantz.com`.

## Stack

Flask + YAML registry + systemd/cron auto-discovery. Dark theme. nginx + htpasswd + LetsEncrypt.

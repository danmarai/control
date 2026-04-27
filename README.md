# Control

Fleet ops portal for Dan's EC2 enterprise.

- **Projects**: registry + auto-discovered services, repos, cron jobs
- **Links**: bookmarks to API consoles, dashboards, admin panels
- **Agents**: (v1.1) live agent status + cost rollup
- **Health**: (v1.1) system health + cron freshness matrix

## Run

```bash
python3 app.py   # binds 127.0.0.1:8081
```

Served via nginx reverse proxy at `https://control.dmarantz.com`.

## Stack

Flask + YAML registry + systemd/cron auto-discovery. Dark theme. nginx + htpasswd + LetsEncrypt.

# Changelog

## v1.2 — 2026-04-27 (Phase 1.2)
- Added /api/projects/<id>/log/tail (generic per-project log tail with traversal guard).
- Added /api/medic/recent (reads user-journal — corrected scope from Phase 1.1 mistake).
- Fixed Health tab systemd unit scopes (user vs system) and expanded coverage.
- Built out Agents tab: fleet health table, costs, quick actions expando.
- Added AGENT_FLEET mapping in lib/agents.py covering 12 agents (gateway, openclaw, listeners, monitor, CLI, remote).
- Added /api/agents/<id>/log and /api/agents.json.
- Restart action route exists but disabled by default (ALLOW_RESTART_ACTIONS=False, pending Phase 1.3 SSO).

## v1.1 — 2026-04-27 (Phase 1.1)
- Projects: split primary vs. secondary with collapsible `<details>` for discovered.
- Demoted life360 to secondary.
- Built out Agents tab (real data from cost-tracker, "unmonitored" badge fallback).
- Built out Health tab (host, services, pipeline freshness, cert expiry).
- Added per-project `links:` field; populated for primary projects.
- Added /forge/latest-weekly and /life360/recent routes.
- Added /api/cron/list (read-only) and /api/medic/recent routes.
- Updated Links tab with Forge, Life360, Server & Infra categories.
- Synced nginx/*.conf snapshots to deployed reality.

## v1.0 — 2026-04-27 (Phase 1)
- Initial scaffold: Flask, systemd --user, nginx behind htpasswd, 17 projects discovered, Projects + Links tabs live, Agents + Health stubs.
- Locked viper-dashboard to 127.0.0.1:8080.
- Killed :8099 orphan, archived legacy viper tree.

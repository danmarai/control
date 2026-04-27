# Changelog

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

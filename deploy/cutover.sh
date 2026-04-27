#!/usr/bin/env bash
# Phase 1.3 SSO cutover — oauth2-proxy + Google OAuth replacing htpasswd.
# Run on EC2 as: sudo bash ~/control/deploy/cutover.sh
# Reads client_id / client_secret interactively (no echo, no shell history).
# Generates cookie_secret. Backs up existing nginx configs. Rolls back on nginx -t failure.

set -euo pipefail

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root: sudo bash $0" >&2
  exit 1
fi

REPO=/home/ubuntu/control
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=/etc/nginx/backups-pre-sso-$TS
NGINX_AVAIL=/etc/nginx/sites-available
OAUTH_DIR=/etc/oauth2-proxy

if [[ ! -d "$REPO/deploy/nginx" ]]; then
  echo "ERROR: $REPO/deploy/nginx not found. cd ~/control && git pull first." >&2
  exit 1
fi

if ! command -v oauth2-proxy >/dev/null 2>&1; then
  echo "ERROR: oauth2-proxy binary missing from PATH. Re-run Phase 1.3 install step." >&2
  exit 1
fi

echo "═══ Phase 1.3 SSO cutover ═══"
echo "Backup dir: $BACKUP_DIR"
echo

# ── Read OAuth credentials from stdin (silent) ────────────────────────────────
read -r -p "Google OAuth Client ID: " CLIENT_ID
echo
read -r -s -p "Google OAuth Client Secret: " CLIENT_SECRET
echo
echo

if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "ERROR: client_id and client_secret are required." >&2
  exit 1
fi

# Generate cookie_secret (32 random bytes, urlsafe base64).
COOKIE_SECRET=$(python3 -c 'import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')

# ── Write oauth2-proxy config ─────────────────────────────────────────────────
echo "[1/8] Writing $OAUTH_DIR/oauth2-proxy.cfg"
mkdir -p "$OAUTH_DIR"

# Use python3 to do the substitution so we never put secrets in argv/sed.
python3 - "$REPO/deploy/oauth2-proxy.cfg.example" "$OAUTH_DIR/oauth2-proxy.cfg" \
         "$CLIENT_ID" "$CLIENT_SECRET" "$COOKIE_SECRET" <<'PYEOF'
import sys, pathlib
src, dst, cid, csec, ck = sys.argv[1:6]
text = pathlib.Path(src).read_text()
# Match the quoted placeholder ("REPLACE_FROM_DAN") so we don't pick up the
# word in the comment line at the top of the template.
marker = '"REPLACE_FROM_DAN"'
parts = text.split(marker)
if len(parts) != 4:
    raise SystemExit(f"Template has {len(parts)-1} quoted placeholders, expected 3")
# Substitute in order: client_id, client_secret, cookie_secret.
out = (parts[0] + f'"{cid}"'
       + parts[1] + f'"{csec}"'
       + parts[2] + f'"{ck}"'
       + parts[3])
pathlib.Path(dst).write_text(out)
PYEOF
chown root:nogroup "$OAUTH_DIR/oauth2-proxy.cfg"
chmod 640 "$OAUTH_DIR/oauth2-proxy.cfg"

# ── Email allowlist ───────────────────────────────────────────────────────────
echo "[2/8] Writing $OAUTH_DIR/emails (daniel.marantz@gmail.com)"
echo "daniel.marantz@gmail.com" > "$OAUTH_DIR/emails"
chown root:nogroup "$OAUTH_DIR/emails"
chmod 640 "$OAUTH_DIR/emails"

# ── Install systemd unit ──────────────────────────────────────────────────────
echo "[3/8] Installing oauth2-proxy.service"
install -m 644 "$REPO/deploy/systemd/oauth2-proxy.service" /etc/systemd/system/oauth2-proxy.service
systemctl daemon-reload

# ── Start oauth2-proxy ────────────────────────────────────────────────────────
echo "[4/8] Starting oauth2-proxy"
systemctl enable --now oauth2-proxy

# Wait for /ping to respond (max 10s)
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://127.0.0.1:4180/ping >/dev/null 2>&1; then
    echo "      → oauth2-proxy /ping OK"
    break
  fi
  if [[ $i -eq 10 ]]; then
    echo "ERROR: oauth2-proxy did not respond on /ping within 10s. Showing journal:" >&2
    journalctl -u oauth2-proxy -n 30 --no-pager >&2
    exit 1
  fi
  sleep 1
done

# ── Backup existing nginx configs ─────────────────────────────────────────────
echo "[5/8] Backing up nginx configs to $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
for host in control viper cortex; do
  cp -p "$NGINX_AVAIL/$host.dmarantz.com" "$BACKUP_DIR/$host.dmarantz.com.bak"
done

# ── Install oauth nginx configs ───────────────────────────────────────────────
echo "[6/8] Installing oauth nginx configs"
for host in control viper cortex; do
  install -m 644 "$REPO/deploy/nginx/$host.dmarantz.com.oauth-template.conf" \
                  "$NGINX_AVAIL/$host.dmarantz.com"
done

# ── nginx -t with rollback ────────────────────────────────────────────────────
echo "[7/8] nginx -t"
if ! nginx -t 2>&1; then
  echo "ERROR: nginx config test failed. Rolling back." >&2
  for host in control viper cortex; do
    cp -p "$BACKUP_DIR/$host.dmarantz.com.bak" "$NGINX_AVAIL/$host.dmarantz.com"
  done
  echo "Rolled back. Backups remain at $BACKUP_DIR" >&2
  exit 1
fi

# ── Reload nginx ──────────────────────────────────────────────────────────────
echo "[8/8] Reloading nginx"
systemctl reload nginx

# ── Smoke test ────────────────────────────────────────────────────────────────
echo
echo "═══ Smoke test ═══"
for host in control viper cortex; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "https://$host.dmarantz.com/")
  echo "  https://$host.dmarantz.com/ → $code (expect 302 to Google sign-in)"
done

echo
echo "═══ DONE ═══"
echo "Sign in: https://control.dmarantz.com/  (will redirect to Google)"
echo "Allowed email: daniel.marantz@gmail.com"
echo "Cookie persists: 30 days, scoped to .dmarantz.com (one login → all 3 subdomains)"
echo
echo "Rollback (if anything looks wrong):"
echo "  sudo cp $BACKUP_DIR/*.bak $NGINX_AVAIL/  # rename without .bak"
echo "  sudo systemctl reload nginx"
echo "  sudo systemctl stop oauth2-proxy"
echo
echo "Old htpasswd configs preserved in: $BACKUP_DIR"
echo "Once SSO is verified working for 24h, those backups can be deleted."

# Deploy Notes

## One-shot setup (Phase 1)

1. Install deps: `pip3 install flask pyyaml requests`
2. Enable systemd user service: `systemctl --user enable --now control-portal.service`
3. Stage nginx configs in `/etc/nginx/sites-available/` and symlink to `sites-enabled/`
4. Create htpasswd files (Dan): `sudo htpasswd -c /etc/nginx/.htpasswd-control dmarantz`
5. Provision certs: `sudo certbot --nginx -d control.dmarantz.com ...`
6. Reload nginx: `sudo systemctl reload nginx`

## Post-deploy

- Remove AWS Security Group rule allowing :8080 inbound (VIPER locked to localhost)
- Remove AWS Security Group rule allowing :8099 inbound (orphan killed)

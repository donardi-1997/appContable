# La Patrona VIP — Production Deployment

## Architecture

```
Internet → Nginx (port 80/443)
            ├── /         → Static files (index.html, app.js, styles.css)
            ├── /api/*    → FastAPI/Uvicorn (127.0.0.1:8000)
            └── /uploads  → FastAPI (product images)
```

## AWS Lightsail

| Item | Value |
|------|-------|
| Instance | `la-patrona-prod` |
| Region | `us-east-2` (Ohio) |
| Bundle | `micro_3_0` ($7/mo) |
| RAM | 1 GB |
| vCPU | 2 |
| Disk | 40 GB SSD |
| Static IP | `3.135.181.212` |
| Ubuntu | 24.04 LTS |

## Server Layout

```
/opt/la-patrona/
    app/          ← Git repo (code)
    venv/         ← Python virtualenv
    data/         ← SQLite database (PERSISTENT)
    uploads/      ← Product images (PERSISTENT)
    backups/      ← Daily DB backups (7-day rotation)

/etc/la-patrona/
    la-patrona.env  ← Environment variables (chmod 600)

/var/log/la-patrona/
    backup.log    ← Backup cron log

/etc/systemd/system/
    la-patrona.service  ← Systemd service

/etc/nginx/sites-available/
    la-patrona    ← Nginx config
```

## Services

- **la-patrona.service**: FastAPI via Uvicorn, user `lapatrona`, binds `127.0.0.1:8000`
- **nginx**: Reverse proxy, serves static files, proxies `/api/` and `/uploads/`

## Environment Variables

File: `/etc/la-patrona/la-patrona.env`

Required:
- `DATABASE_URL` — SQLite path
- `AUTH_SECRET` — JWT signing key
- `ADMIN_API_KEY` — Admin authentication
- `ELECTRONIC_INVOICE_PROVIDER` — `mock` or `dian`

## Database

- File: `/opt/la-patrona/data/gato_contable.db`
- SQLite with WAL mode (auto-enabled)
- Backup: `/usr/local/bin/backup-la-patrona` (cron at 3:00 AM daily)
- Retention: 7 days

## Updating the Application

```bash
# 1. SSH into server
ssh -i ~/.ssh/la-patrona-prod.pem ubuntu@3.135.181.212

# 2. Backup database
sudo /usr/local/bin/backup-la-patrona

# 3. Pull latest code
cd /opt/la-patrona/app
sudo -u lapatrona git pull

# 4. Install new dependencies (if changed)
sudo -u lapatrona /opt/la-patrona/venv/bin/pip install -r backend/requirements.txt

# 5. Restart backend
sudo systemctl restart la-patrona

# 6. Verify
curl http://127.0.0.1:8000/api/products
```

## Monitoring

```bash
# Service status
sudo systemctl status la-patrona --no-pager

# Logs
sudo journalctl -u la-patrona -f --no-pager

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Backup log
sudo tail -f /var/log/la-patrona/backup.log
```

## HTTPS (Future)

When a domain is available:
1. Point DNS A record to `3.135.181.212`
2. Install certbot: `sudo apt install certbot python3-certbot-nginx`
3. Run: `sudo certbot --nginx -d yourdomain.com`
4. Auto-renewal is configured automatically

## Security Notes

- App runs as non-root user `lapatrona`
- Backend only listens on `127.0.0.1` (not publicly exposed)
- `.env` file is `chmod 600` owned by root
- Nginx blocks access to `.env`, `.db`, `.git` files
- Firewall only allows ports 22, 80, 443
- SSH key-only authentication

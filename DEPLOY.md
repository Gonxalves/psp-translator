# Deployment Guide — PSP Translator (HTTPS)

Run the PSP Translator 24/7 on a VPS with Docker, nginx reverse proxy, and automatic Let's Encrypt SSL.
Access from any device at `https://YOUR_DOMAIN`.

---

## Prerequisites

- A VPS (Ubuntu 22.04+ recommended, 2+ GB RAM)
- A registered domain name
- SSH access to the VPS as root

---

## Step 1: DNS Setup

Go to your domain registrar (or DNS provider) and create an **A record**:

| Type | Name | Value |
|------|------|-------|
| A | translate (or @) | YOUR_VPS_IP |

Wait 5–30 minutes for propagation. Verify:
```bash
dig translate.yourdomain.com
```
The answer should show your VPS IP address.

---

## Step 2: Connect to your VPS

```bash
ssh root@YOUR_VPS_IP
```

---

## Step 3: Install Docker and firewall

```bash
apt update && apt upgrade -y
apt install -y curl git ufw apache2-utils

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Firewall: allow SSH, HTTP (for Let's Encrypt), HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

> **Note:** Port 8501 is NOT opened — the app is only accessible through nginx on port 443.
> `apache2-utils` provides `htpasswd` for creating basic auth credentials.

---

## Step 4: Create data directory

```bash
mkdir -p /opt/psp-data
```

---

## Step 5: Set up OneDrive sync (rclone)

### Install rclone
```bash
curl https://rclone.org/install.sh | bash
```

### Authorize OneDrive

**On your Windows PC** (has a browser):
```bash
rclone authorize "onedrive"
```
A browser opens — sign in and authorize. Copy the JSON token it prints.

**On the VPS:**
```bash
rclone config
```
- Name: `onedrive`
- Storage: `onedrive`
- Client ID/Secret: leave blank
- Region: `global`
- Auto config: `n`
- Paste the token from your PC
- Drive type: `onedrive` (personal or business)
- Root folder: leave blank
- Confirm: `y`

### Test and sync
```bash
# Find your files
rclone ls onedrive:/

# Copy Excel files to the server
rclone copy "onedrive:/PATH/TO/Glossary.xlsx" /opt/psp-data/
rclone copy "onedrive:/PATH/TO/ActionLog.xlsx" /opt/psp-data/

# Verify
ls -la /opt/psp-data/
```

### Set up auto-sync (every 2 minutes)

```bash
# Initialize bidirectional sync (one-time)
rclone bisync "onedrive:/PATH/TO/FOLDER" /opt/psp-data --resync

# Create sync script
cat > /opt/psp-sync.sh << 'SCRIPT'
#!/bin/bash
rclone bisync "onedrive:/PATH/TO/FOLDER" "/opt/psp-data" \
    --include "Glossary.xlsx" --include "ActionLog.xlsx" \
    --conflict-resolve newer 2>> /var/log/psp-sync.log
SCRIPT

chmod +x /opt/psp-sync.sh

# Add to cron
crontab -l 2>/dev/null | { cat; echo "*/2 * * * * /opt/psp-sync.sh"; } | crontab -
```

Replace `PATH/TO/FOLDER` with your actual OneDrive path in both places.

---

## Step 6: Get the code on the server

```bash
git clone YOUR_REPO_URL /opt/psp-translator
cd /opt/psp-translator
```

---

## Step 7: Create the .env file

```bash
nano /opt/psp-translator/.env
```

Paste this (fill in your real values):
```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
EXCEL_GLOSSARY_PATH=/app/data/Glossary.xlsx
EXCEL_ACTION_LOG_PATH=/app/data/ActionLog.xlsx
GLOSSARY_SHEET_NAME=Glossary
ACTION_LOG_SHEET_NAME=Action Log
APP_PASSWORD=choose_a_password_here
```

Save (`Ctrl+O`, Enter, `Ctrl+X`), then lock it:
```bash
chmod 600 /opt/psp-translator/.env
```

---

## Step 8: Configure your domain in nginx

Replace `YOUR_DOMAIN` in `nginx.conf` with your actual domain:

```bash
cd /opt/psp-translator
sed -i 's/YOUR_DOMAIN/translate.yourdomain.com/g' nginx.conf
```

Replace `translate.yourdomain.com` with your actual domain.

---

## Step 9: Create basic auth credentials

nginx basic auth is the first layer of protection (before the app's own password screen):

```bash
cd /opt/psp-translator
htpasswd -c .htpasswd psp-user
```

Enter a password when prompted. To add more users later:
```bash
htpasswd .htpasswd another-user
```

---

## Step 10: Bootstrap SSL certificate

Edit the init script with your domain and email:

```bash
nano init-letsencrypt.sh
```

Change the two lines at the top:
```bash
domains=(translate.yourdomain.com)     # Your actual domain
email="your-email@example.com"         # Your email for expiry notices
staging=1                              # Keep 1 for the first test
```

Run it:
```bash
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

If it succeeds with staging, change `staging=0` and run again for a real certificate:
```bash
nano init-letsencrypt.sh   # Change staging=1 to staging=0
./init-letsencrypt.sh
```

> **Why staging first?** Let's Encrypt limits you to 5 real certificates per week.
> Staging certificates work the same way but don't count toward the limit.

---

## Step 11: Launch everything

```bash
cd /opt/psp-translator
docker compose up -d --build
```

Wait 2–3 minutes for the build. Check status:
```bash
docker compose ps
```

You should see 3 services running: `psp-translator`, `psp-nginx`, `psp-certbot`.

---

## Step 12: Verify

1. Open `https://translate.yourdomain.com` in a browser
2. Confirm the HTTPS lock icon appears (no certificate warnings)
3. Enter basic auth credentials (from Step 9)
4. Enter the app password (from Step 7)
5. Test: translate a text, look up a term, add a glossary entry, download a Word file
6. Open a second browser/incognito — confirm both sessions work independently

Check from the command line:
```bash
docker compose ps                                    # All 3 services "Up"
docker compose logs certbot                          # Renewal timer running
curl -I https://translate.yourdomain.com 2>/dev/null | head -20  # Check headers
```

---

## Maintenance

### View logs
```bash
docker compose logs -f app      # App logs
docker compose logs -f nginx    # Nginx access/error logs
docker compose logs certbot     # Certificate renewal logs
```

### Update after code changes
```bash
cd /opt/psp-translator && git pull && docker compose up -d --build
```

### Restart
```bash
docker compose restart
```

### Force certificate renewal
```bash
docker compose run --rm certbot renew --force-renewal
docker compose exec nginx nginx -s reload
```

### Check certificate expiry
```bash
docker compose run --rm certbot certificates
```

### Check OneDrive sync logs
```bash
tail -20 /var/log/psp-sync.log
```

### Check disk space
```bash
df -h && docker system df
```

### Clean up Docker if disk fills
```bash
docker system prune -f
```

---

## Troubleshooting

### 502 Bad Gateway
The Streamlit app hasn't finished starting. Wait 30 seconds and retry.
```bash
docker compose logs app
```

### Certificate renewal fails
Ensure port 80 is open and the ACME challenge path works:
```bash
curl http://translate.yourdomain.com/.well-known/acme-challenge/test
```
Should return 404 (not "connection refused").

### Basic auth not working
Check the `.htpasswd` file exists:
```bash
ls -la /opt/psp-translator/.htpasswd
```

### Scraping fails
```bash
docker compose exec app chromium --version
```

### Out of memory
```bash
free -h
docker compose restart
```

### WebSocket errors in browser console
Check nginx logs:
```bash
docker compose logs nginx | grep upgrade
```

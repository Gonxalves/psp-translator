# Deployment Guide — PSP Translator

Run the PSP Translator 24/7 on a VPS with Docker and OneDrive sync.
Access from any device at `http://YOUR_SERVER_IP:8501`.

---

## Step 1: Connect to your VPS

Open PowerShell on your PC:
```bash
ssh root@YOUR_SERVER_IP
```

---

## Step 2: Install Docker and firewall

```bash
apt update && apt upgrade -y
apt install -y curl git ufw

curl -fsSL https://get.docker.com | sh
systemctl enable docker

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 8501/tcp
ufw enable
```

---

## Step 3: Create data directory

```bash
mkdir -p /opt/psp-data
```

---

## Step 4: Set up OneDrive sync (rclone)

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

## Step 5: Get the code on the server

```bash
git clone YOUR_REPO_URL /opt/psp-translator
cd /opt/psp-translator
```

---

## Step 6: Create the .env file

```bash
nano /opt/psp-translator/.env
```

Paste this:
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

## Step 7: Launch

```bash
cd /opt/psp-translator
docker compose up -d --build
```

Wait 2-3 minutes for the build. Check status:
```bash
docker compose ps
```

---

## Step 8: Use it

Open `http://YOUR_SERVER_IP:8501` in any browser (phone, laptop, tablet).
Enter the password you set in `.env`.

Test:
1. Translate a text (Claude API)
2. Look up a term on TERMIUM/OQLF/Canada.ca (Selenium)
3. Add a glossary term (Excel write)
4. Download Word (docx export)

---

## Maintenance

```bash
# View logs
docker compose logs -f app

# Restart
docker compose restart app

# Update after code changes
cd /opt/psp-translator && git pull && docker compose up -d --build

# Check OneDrive sync logs
tail -20 /var/log/psp-sync.log

# Check disk space
df -h && docker system df

# Clean up Docker if disk fills
docker system prune -f
```

---

## Troubleshooting

### App won't start
```bash
docker compose logs app
```

### Scraping fails
```bash
docker compose exec app chromium --version
```

### Out of memory
```bash
free -h
docker compose restart app
```

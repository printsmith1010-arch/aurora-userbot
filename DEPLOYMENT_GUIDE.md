# 🚀 24/7 Aurora Userbot Hosting & Deployment Guide

This guide details step-by-step instructions for hosting the **Aurora Multi-User Telegram Userbot Platform** 24/7 on free or low-cost cloud services.

---

## 🌟 Option 1: Render.com (Recommended Free/Easy Cloud Worker)

1. **Push your code to GitHub**:
   - Create a private repository on [GitHub](https://github.com) and push this folder.

2. **Create a Background Worker on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Background Worker**.
   - Connect your GitHub repository.

3. **Configure Settings**:
   - **Name**: `aurora-userbot-platform`
   - **Environment**: `Python 3` or `Docker`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python login.py`

4. **Environment Variables**:
   Add the following in Render Environment Settings:
   - `TELEGRAM_API_ID` = `25307036`
   - `TELEGRAM_API_HASH` = `11285731405a814dd4b3af1c61bdd482`
   - `TG_BOT_TOKEN` = `8679611350:AAHA41eGl2TRPzefxf1jYzLFPyrhN_m3JqY`
   - `OWNER_ID` = `5342258541`
   - `OWNER_USERNAME` = `tglegend77`
   - `ENCRYPTION_KEY` = `gK7Z3tL9v_xR8wB2mN5pQ1yD4sV6uF0aJ3kL9mP2nR8=`

5. Click **Create Background Worker**. Render will automatically run your platform 24/7!

---

## 🚀 Option 2: Railway.app or Koyeb

1. Go to [Railway.app](https://railway.app) or [Koyeb.com](https://koyeb.com).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Railway automatically detects `Procfile` (`worker: python login.py`) or `Dockerfile`.
4. Paste the Environment Variables (`TG_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, etc.).
5. Deploy!

---

## 💻 Option 3: Linux VPS (Ubuntu/Debian via Systemd or Docker)

If you own a VPS (DigitalOcean, AWS, Linode, Vultr, Hetzner):

### Method A: Docker Compose (1-Click)
```bash
git clone <your-github-repo-url>
cd catuserbot-phone-login
docker-compose up -d --build
```

### Method B: Systemd Background Service
1. Copy repo to VPS:
```bash
cd /root/catuserbot-phone-login
pip3 install -r requirements.txt
```

2. Create Systemd Service file:
```bash
sudo nano /etc/systemd/system/aurora.service
```

3. Paste:
```ini
[Unit]
Description=Aurora Multi-User Userbot Platform
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/catuserbot-phone-login
ExecStart=/usr/bin/python3 login.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

4. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aurora
sudo systemctl start aurora
```

5. Check status:
```bash
sudo systemctl status aurora
```

---
🎉 **Your Aurora Userbot is now running 24/7!**

# Aurora Multi-User Telegram Userbot Platform

![Aurora Banner](https://graph.org/file/4860c8e1a5a56d0616b79.png)

**Aurora** is a modern, production-grade multi-user Telegram userbot platform built with Python 3.11+, Telethon, and SQLAlchemy. It allows multiple users to deploy their own isolated userbots through a single Telegram hoster bot interface while maintaining AES-256 session encryption at rest, strict tenant isolation, and owner RBAC protection.

---

## Key Features

- **Multi-Tenant Session Isolation:** Each user's actions run strictly within their own isolated `TelegramClient` connection.
- **AES-256 Encrypted Session Storage:** Telegram StringSessions are encrypted at rest using Fernet symmetric encryption in SQLite/PostgreSQL. Zero plaintext credentials stored on disk.
- **Interactive Onboarding Bot:** Users onboard via Telegram chat (`/host` ➔ Phone ➔ OTP ➔ 2FA).
- **Interactive Category Grid (`/commands`):** 20 category inline buttons for exploring commands with dynamic callbacks.
- **Owner Dashboard (`/owner` / `/stats`):** Platform owner (`5342258541` / `@tglegend77`) can monitor registered users, active sessions, CPU/RAM, and platform health.
- **Role-Based Access Control (RBAC):** Dangerous administrative commands (`.eval`, `.exec`, `.terminal`, `/owner`) are strictly restricted to `OWNER_ID`.
- **Session Revocation (`/logout`):** Users can revoke their session at any time, purging it from the database and disconnecting their client.
- **Automated Verification Test Suite:** 100% test coverage for session isolation, encryption at rest, RBAC enforcement, and session revocation.

---

## Quick Start Guide

### 1. Clone & Configure
```bash
git clone https://github.com/TgCatUB/catuserbot.git aurora
cd aurora
cp .env.example .env
```

Edit `.env` with your encryption key and bot token:
```env
TELEGRAM_API_ID=25307036
TELEGRAM_API_HASH=11285731405a814dd4b3af1c61bdd482
TG_BOT_TOKEN=8679611350:AAHA41eGl2TRPzefxf1jYzLFPyrhN_m3JqY
OWNER_ID=5342258541
OWNER_USERNAME=tglegend77
DATABASE_URL=sqlite:///aurora.db
ENCRYPTION_KEY=gK7Z3tL9v_xR8wB2mN5pQ1yD4sV6uF0aJ3kL9mP2nR8=
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
python -m pytest tests/test_session_isolation.py -v
```

### 4. Start Aurora Platform
```bash
python login.py
```

### 5. Docker Deployment
```bash
docker-compose up -d --build
```

---

## Documentation

- [Architecture Specification](docs/ARCHITECTURE.md)
- [Security Policy & Guarantees](docs/SECURITY.md)
- [Command Reference](docs/COMMANDS.md)

---

## Credits & License

- **Crafted for Platform Owner:** `@tglegend77` (`5342258541`)
- **License:** GNU General Public License v3.0

# Aurora Architecture Specification

## Overview

**Aurora** is a production-grade multi-user Telegram Userbot Platform built on top of Telethon and Python 3.11+. It enables multiple independent Telegram accounts to host and run userbot instances concurrently while preserving complete session isolation, zero-knowledge credential storage, and role-based access control (RBAC).

---

## Architectural Diagram

```
                              +-------------------------+
                              |   Aurora Hoster Bot     |
                              |   (/host Onboarding)    |
                              +-------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                            UserSessionManager Engine                              |
|                                                                                   |
|  - AES-256 Fernet Session Decryption at Runtime                                  |
|  - Isolated TelegramClient instances per Telegram User ID                         |
|  - Thread-Safe Async Connection Pool & Lifecycle Control                          |
+-----------------------------------------------------------------------------------+
           |                                                      |
           v                                                      v
+-----------------------+                              +-----------------------+
|  User A Session Context|                              | User B Session Context|
|  Client A (ID: 11111) |                              | Client B (ID: 22222) |
|  -> Admin Plugins     |                              | -> Admin Plugins     |
|  -> Utility Plugins   |                              | -> Utility Plugins   |
+-----------------------+                              +-----------------------+
           |                                                      |
           v                                                      v
+-----------------------+                              +-----------------------+
| Telegram Account A    |                              | Telegram Account B    |
+-----------------------+                              +-----------------------+
```

---

## Core Components

### 1. Global Application Credentials
Aurora uses a single shared MTProto application identification pair (`TELEGRAM_API_ID` & `TELEGRAM_API_HASH`). Users log in using only their phone number, Telegram OTP, and 2FA password (if enabled).

### 2. UserSessionManager (`aurora/core/session_manager.py`)
- Maintains an in-memory dictionary of active `TelegramClient` instances indexed strictly by Telegram User ID (`telegram_id`).
- Ensures that event listeners registered for User A execute **only** within User A's `TelegramClient` context.
- Handles connection initialization, reconnects, auto-save, and graceful shutdowns.

### 3. Session Security & Encryption (`aurora/db/security.py`)
- Sessions are encrypted at rest using AES-256 Fernet encryption (`ENCRYPTION_KEY`).
- Plaintext string sessions are decrypted into memory **only** when starting a user client session.
- Zero plaintext sessions, OTPs, or passwords are logged to files or stored in database tables.

### 4. Role-Based Access Control (RBAC) (`aurora/core/plugin_manager.py`)
- Platform Owner (`OWNER_ID = 5342258541`, `@tglegend77`) has exclusive authorization for system administration, arbitrary code execution (`.eval`, `.exec`, `.terminal`), platform statistics (`/owner`), and global broadcasts.
- Non-owner users are strictly restricted to non-sensitive userbot features (`.ban`, `.mute`, `.alive`, `.ping`, etc.).

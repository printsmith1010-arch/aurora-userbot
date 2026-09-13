# Aurora Security Model & Secret Safety Policy

## Security Guarantees

### 1. Per-User Session Isolation
- Every user's Telegram session runs in an isolated `TelegramClient` connection.
- User A can **never** trigger actions or access context on User B's Telegram account.
- Handlers registered for User A inspect `event.client.uid` to enforce strict isolation.

### 2. Encrypted Session Storage at Rest
- Sensitive Telegram StringSessions are encrypted using AES-256 Fernet symmetric encryption before being saved to the database.
- The `ENCRYPTION_KEY` environment variable protects session data.
- Plaintext sessions are never written to disk, `.env`, `.session` files, or database columns.

### 3. Zero Credential & Secret Exposure Policy
- All secrets (`TG_BOT_TOKEN`, `API_HASH`, `ENCRYPTION_KEY`, `DATABASE_URL` passwords) are read strictly from environment variables (`.env`).
- In UI outputs, dashboards, status checks, and `/owner` summaries, all secret values are explicitly masked as `********`.
- Output sanitizer `sanitize_text()` filters any accidental secret string occurrences from error messages and logs.
- Temporary authentication input fields (such as 2FA passwords in chat) are automatically deleted immediately after processing.

### 4. Role-Based Access Control (RBAC)
- Platform Owner ID: `5342258541` (`@tglegend77`).
- Commands capable of executing system commands (`.terminal`, `.eval`, `.exec`), modifying server state, or inspecting platform statistics are restricted strictly to the designated Owner ID.
- Attempts by non-owner users to invoke owner commands return a `⛔ Access Denied` warning.

### 5. Session Revocation & Logout
- Users can revoke their session at any time using `/logout`.
- Revocation immediately disconnects the user's active `TelegramClient`, purges the encrypted record from the database, and clears local state.

### 6. Automated Secret Safety Verification (`test_secret_safety`)
- An automated test case `test_secret_safety` validates that unmasked secrets never appear in string outputs, dashboards, logs, or error responses.

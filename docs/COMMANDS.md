# Aurora Command Reference

## Telegram Hoster Bot Commands

| Command | Usage | Description | Access |
|---|---|---|---|
| `/start` | `/start` | Launches bot with premium welcome card & help button | All |
| `/help` | `/help` | Displays full list of available platform commands | All |
| `/commands` | `/commands` | Opens interactive 20-category inline button grid | All |
| `/host` | `/host` | Starts interactive onboarding (Phone ➔ OTP ➔ 2FA) | All |
| `/status` | `/status` | Checks status of userbot session | All |
| `/logout` | `/logout` | Safely disconnects and revokes encrypted session from DB | All |
| `/support` | `/support` | Displays support contact info | All |
| `/owner` | `/owner` | Opens platform owner dashboard (users, system stats, uptime) | Owner Only (`5342258541`) |

---

## Userbot Commands

### Administration (`admin`)
- `.ban <reply/user>` - Bans target user from group.
- `.unban <reply/user>` - Unbans target user.
- `.mute <reply/user>` - Mutes target user.
- `.unmute <reply/user>` - Unmutes target user.
- `.kick <reply/user>` - Kicks user from group.
- `.purge` - Deletes all messages from replied message downwards.
- `.pin` - Pins replied message.

### Utility & General (`general`)
- `.alive` - Checks if userbot is active & displays platform status.
- `.ping` - Measures server response latency.
- `.id` - Displays chat, user, and message IDs.
- `.info <user>` - Displays user profile info.
- `.help [command/category]` - Generates dynamic help menu.

### Owner Administration (`owner` - Restricted to `5342258541`)
- `.eval <code>` - Evaluates Python code snippet.
- `.exec <code>` - Executes Python code block.
- `.terminal <cmd>` - Executes shell command.
- `.sysstats` - Displays CPU, RAM, disk, and platform status.

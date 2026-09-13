"""
Aurora Owner-Only Administration Plugin.

SECURITY CRITICAL:
All commands in this plugin MUST strictly verify `sender_id == Config.OWNER_ID` (5342258541).
Non-owner users are strictly forbidden from executing arbitrary code, shell commands, or platform settings.
"""

import sys
import subprocess
import traceback
import psutil
from datetime import datetime
from telethon import events

from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

# Register owner-only commands in PluginManager
plugin_manager.register_command("eval", "owner", "Evaluates Python code snippet.", f"{Config.COMMAND_HANDLER}eval <code>", owner_only=True)
plugin_manager.register_command("exec", "owner", "Executes Python code snippet.", f"{Config.COMMAND_HANDLER}exec <code>", owner_only=True)
plugin_manager.register_command("terminal", "owner", "Runs shell command.", f"{Config.COMMAND_HANDLER}terminal <cmd>", owner_only=True, aliases=["term", "bash"])
plugin_manager.register_command("sysstats", "owner", "Displays system & platform statistics.", f"{Config.COMMAND_HANDLER}sysstats", owner_only=True)


def register_owner_handlers(client):
    """
    Registers owner-restricted handlers on client with strict sender_id check.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.eval(?:\s+([\s\S]+))?"))
    async def eval_handler(event):
        if event.sender_id != Config.OWNER_ID:
            await event.edit("⛔ **Access Denied:** Platform Owner privileges required.")
            return

        cmd = event.pattern_match.group(1)
        if not cmd:
            await event.edit("❌ Provide Python code to evaluate.")
            return

        await event.edit("⏳ **Evaluating...**")
        try:
            # Evaluate expression
            result = eval(cmd)
            await event.edit(f"💻 **Eval Output:**\n```python\n{result}\n```")
        except Exception as e:
            await event.edit(f"❌ **Eval Error:**\n```python\n{traceback.format_exc()}\n```")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.exec(?:\s+([\s\S]+))?"))
    async def exec_handler(event):
        if event.sender_id != Config.OWNER_ID:
            await event.edit("⛔ **Access Denied:** Platform Owner privileges required.")
            return

        code = event.pattern_match.group(1)
        if not code:
            await event.edit("❌ Provide Python code to execute.")
            return

        await event.edit("⏳ **Executing...**")
        try:
            exec(f"async def _aexec(event, client):\n" + "".join(f"    {line}\n" for line in code.split("\n")))
            await locals()["_aexec"](event, event.client)
            await event.edit("✅ **Execution finished successfully.**")
        except Exception as e:
            await event.edit(f"❌ **Exec Error:**\n```python\n{traceback.format_exc()}\n```")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(?:terminal|term|bash)(?:\s+([\s\S]+))?"))
    async def terminal_handler(event):
        if event.sender_id != Config.OWNER_ID:
            await event.edit("⛔ **Access Denied:** Platform Owner privileges required.")
            return

        cmd = event.pattern_match.group(1)
        if not cmd:
            await event.edit("❌ Provide a terminal command to execute.")
            return

        await event.edit("⏳ **Running command...**")
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode().strip() or stderr.decode().strip() or "No output."

            if len(output) > 3500:
                output = output[:3500] + "\n...[Output truncated]"

            await event.edit(f"🖥️ **Terminal Output:**\n```bash\n{output}\n```")
        except Exception as e:
            await event.edit(f"❌ **Terminal Error:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.sysstats$"))
    async def sysstats_handler(event):
        if event.sender_id != Config.OWNER_ID:
            await event.edit("⛔ **Access Denied:** Platform Owner privileges required.")
            return

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        stats_text = (
            "👑 **Aurora Platform System Statistics**\n\n"
            f"💻 **CPU Usage:** `{cpu}%`\n"
            f"🧠 **RAM Usage:** `{ram}%`\n"
            f"💽 **Disk Usage:** `{disk}%`\n"
            f"🛡️ **Platform Owner:** `{Config.OWNER_ID}`"
        )
        await event.edit(stats_text)

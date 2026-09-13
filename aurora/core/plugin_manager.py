"""
Aurora Plugin & Command Manager.

Handles dynamic plugin loading, metadata extraction, dynamic help generation,
and RBAC (Role-Based Access Control) security checks for owner-restricted commands.
"""

import importlib
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from telethon import events

from aurora.config import Config

LOGS = logging.getLogger("AuroraPluginManager")


@dataclass
class CommandMeta:
    name: str
    category: str
    description: str
    usage: str
    owner_only: bool = False
    aliases: List[str] = field(default_factory=list)


class PluginManager:
    def __init__(self):
        self._commands: Dict[str, CommandMeta] = {}
        self._plugins: Dict[str, dict] = {}

    def register_command(
        self,
        name: str,
        category: str = "General",
        description: str = "",
        usage: str = "",
        owner_only: bool = False,
        aliases: Optional[List[str]] = None,
    ):
        meta = CommandMeta(
            name=name,
            category=category,
            description=description,
            usage=usage or f"{Config.COMMAND_HANDLER}{name}",
            owner_only=owner_only,
            aliases=aliases or [],
        )
        self._commands[name] = meta
        for alias in meta.aliases:
            self._commands[alias] = meta

    def get_command(self, name: str) -> Optional[CommandMeta]:
        return self._commands.get(name)

    def is_owner(self, user_id: int) -> bool:
        return user_id == Config.OWNER_ID

    def get_help(self, category_or_cmd: Optional[str] = None) -> str:
        """
        Generates dynamic help text grouped by category or for a specific command.
        """
        if not category_or_cmd:
            # Group commands by category
            categories: Dict[str, List[CommandMeta]] = {}
            for name, meta in self._commands.items():
                if name != meta.name:
                    continue  # skip aliases
                cat = meta.category.capitalize()
                categories.setdefault(cat, []).append(meta)

            help_str = "✨ **Aurora Multi-User Userbot Help** ✨\n\n"
            for cat, cmds in sorted(categories.items()):
                help_str += f"🔹 **{cat}**:\n"
                for cmd in sorted(cmds, key=lambda c: c.name):
                    owner_tag = " `[Owner]`" if cmd.owner_only else ""
                    help_str += f"  • `{Config.COMMAND_HANDLER}{cmd.name}`{owner_tag} - {cmd.description}\n"
                help_str += "\n"
            help_str += f"Type `{Config.COMMAND_HANDLER}help <command>` for detailed usage."
            return help_str

        search = category_or_cmd.lower().lstrip(Config.COMMAND_HANDLER)
        if meta := self._commands.get(search):
            owner_tag = " (Owner Only)" if meta.owner_only else ""
            aliases_str = f", `.{"`, `.".join(meta.aliases)}`" if meta.aliases else "None"
            return (
                f"📖 **Help for `{Config.COMMAND_HANDLER}{meta.name}`**{owner_tag}\n\n"
                f"**Category:** {meta.category.capitalize()}\n"
                f"**Description:** {meta.description}\n"
                f"**Usage:** `{meta.usage}`\n"
                f"**Aliases:** {aliases_str}"
            )

        return f"❌ Command or category `{category_or_cmd}` not found."


# Singleton Instance
plugin_manager = PluginManager()

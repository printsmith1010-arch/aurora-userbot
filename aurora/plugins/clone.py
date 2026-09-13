"""
Aurora Profile Cloning & Reverting Plugin.

Commands: .clone, .dclone, .revert
Clones First Name, Last Name, Bio (about), Profile Photo, and Username (+1).
"""

import os
import logging
from telethon import events
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraClonePlugin")

plugin_manager.register_command("clone", "custom", "Clones a target user's name, bio, photo, and username.", f"{Config.COMMAND_HANDLER}clone <username/reply>")
plugin_manager.register_command("dclone", "custom", "Restores original name, bio, photo, and username.", f"{Config.COMMAND_HANDLER}dclone")

ORIGINAL_PROFILES = {}


def extract_user_bio(full_user_obj) -> str:
    """
    Safely extracts bio from Telethon's UserFull / messages.UserFull response structure.
    """
    if not full_user_obj:
        return ""

    # 1. Primary Telethon structure: full_user_obj.full_user.about
    full_u = getattr(full_user_obj, "full_user", None)
    if full_u:
        about = getattr(full_u, "about", None)
        if about is not None and str(about).strip():
            return str(about).strip()

    # 2. Direct attribute check: full_user_obj.about
    about = getattr(full_user_obj, "about", None)
    if about is not None and str(about).strip():
        return str(about).strip()

    # 3. Check inside users list if available
    users = getattr(full_user_obj, "users", [])
    for u in users:
        u_about = getattr(u, "about", None)
        if u_about is not None and str(u_about).strip():
            return str(u_about).strip()

    return ""


def register_clone_handlers(client):
    """
    Registers profile clone and revert handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.clone(?:\s+([\s\S]+))?"))
    async def clone_handler(event):
        reply = await event.get_reply_message()
        input_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif input_str:
            target = input_str.strip()

        if not target:
            await event.edit("❌ **Reply to a user or provide a username/ID to clone.**")
            return

        msg = await event.edit("⏳ **Cloning complete profile (name, bio, photo, username)...**")

        try:
            target_entity = await client.get_entity(target)
            target_full = await client(GetFullUserRequest(target_entity))

            me = await client.get_me()
            me_full = await client(GetFullUserRequest(me))

            # Accurately extract target bio
            target_bio = extract_user_bio(target_full)
            LOGS.info(f"Cloning target {target_entity.id} - Extracted bio: '{target_bio}'")

            # Store original profile if not cached yet
            if me.id not in ORIGINAL_PROFILES:
                orig_photo = await client.download_profile_photo("me", file=f"orig_{me.id}.jpg")
                orig_bio = extract_user_bio(me_full)
                ORIGINAL_PROFILES[me.id] = {
                    "first_name": me.first_name or "",
                    "last_name": me.last_name or "",
                    "bio": orig_bio,
                    "username": me.username or "",
                    "photo": orig_photo,
                }

            target_first = target_entity.first_name or ""
            target_last = target_entity.last_name or ""
            target_username = getattr(target_entity, "username", None)

            # Update Name & Bio
            await client(UpdateProfileRequest(
                first_name=target_first,
                last_name=target_last,
                about=target_bio[:70] if target_bio else ""
            ))

            # Update Username (append '1')
            new_uname_str = ""
            if target_username:
                candidate_unames = [f"{target_username}1", f"{target_username}_1", f"{target_username}11"]
                for candidate in candidate_unames:
                    try:
                        await client(UpdateUsernameRequest(username=candidate))
                        new_uname_str = f" (Username set to @{candidate})"
                        break
                    except Exception:
                        pass

            # Download & Upload Profile Photo
            target_photo = await client.download_profile_photo(target_entity, file=f"target_{target_entity.id}.jpg")
            if target_photo and os.path.exists(target_photo):
                file = await client.upload_file(target_photo)
                await client(UploadProfilePhotoRequest(file=file))
                try:
                    os.remove(target_photo)
                except Exception:
                    pass

            target_name = f"{target_first} {target_last}".strip()
            bio_disp = f"\n📝 **Bio:** `{target_bio}`" if target_bio else "\n📝 **Bio:** *(No Bio)*"
            await msg.edit(f"👤 **Successfully Cloned Profile of:** `{target_name}`{new_uname_str}{bio_disp}")

        except Exception as e:
            await msg.edit(f"❌ **Clone failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(dclone|revert)$"))
    async def revert_handler(event):
        me = await client.get_me()
        msg = await event.edit("⏳ **Reverting profile, bio, and username to original...**")

        if me.id not in ORIGINAL_PROFILES:
            await msg.edit("ℹ️ **No cloned profile found to revert.**")
            return

        orig = ORIGINAL_PROFILES.pop(me.id)
        try:
            # Revert profile & bio
            await client(UpdateProfileRequest(
                first_name=orig["first_name"],
                last_name=orig["last_name"],
                about=orig["bio"]  # Restores original bio (or clears it if "")
            ))

            # Revert username
            if orig.get("username"):
                try:
                    await client(UpdateUsernameRequest(username=orig["username"]))
                except Exception:
                    pass

            # Revert profile photo
            if orig.get("photo") and os.path.exists(orig["photo"]):
                file = await client.upload_file(orig["photo"])
                await client(UploadProfilePhotoRequest(file=file))
                try:
                    os.remove(orig["photo"])
                except Exception:
                    pass

            await msg.edit("🔄 **Profile, bio, and username successfully restored to original!**")
        except Exception as e:
            await msg.edit(f"❌ **Revert failed:** `{e}`")

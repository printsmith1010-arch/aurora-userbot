"""
Aurora Profile Cloning & Reverting Plugin.

Commands: .clone, .dclone / .revert
"""

import os
import json
import logging
from telethon import events
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoto
from telethon.utils import get_input_photo
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraClonePlugin")

BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "downloads", "clone_backups"))
os.makedirs(BACKUP_DIR, exist_ok=True)

plugin_manager.register_command(
    "clone", "custom",
    "Clones a target user's name, bio, profile photo, and username.",
    f"{Config.COMMAND_HANDLER}clone <username/reply>"
)
plugin_manager.register_command(
    "dclone", "custom",
    "Deletes cloned DPs and restores all your original DPs.",
    f"{Config.COMMAND_HANDLER}dclone"
)


def _index_path(user_id: int) -> str:
    return os.path.join(BACKUP_DIR, f"backup_{user_id}.json")


def save_backup(user_id: int, data: dict):
    with open(_index_path(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_backup(user_id: int) -> dict | None:
    path = _index_path(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOGS.warning(f"Failed to load backup for {user_id}: {e}")
        return None


def delete_backup(user_id: int):
    path = _index_path(user_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup_files(paths: list):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def extract_user_bio(full_user_obj) -> str:
    if not full_user_obj:
        return ""
    full_u = getattr(full_user_obj, "full_user", None)
    if full_u:
        about = getattr(full_u, "about", None)
        if about and str(about).strip():
            return str(about).strip()
    about = getattr(full_user_obj, "about", None)
    if about and str(about).strip():
        return str(about).strip()
    for u in getattr(full_user_obj, "users", []):
        about = getattr(u, "about", None)
        if about and str(about).strip():
            return str(about).strip()
    return ""


async def download_all_photos(client, entity, prefix: str) -> list:
    """Downloads all profile photos of entity to disk."""
    saved = []
    try:
        photos = await client.get_profile_photos(entity, limit=10)
    except Exception as e:
        LOGS.warning(f"Error fetching profile photos for {entity}: {e}")
        photos = []

    if photos:
        # oldest to newest
        photos_ordered = list(reversed(photos))
        for i, photo in enumerate(photos_ordered):
            dest = os.path.join(BACKUP_DIR, f"{prefix}_{i}.jpg")
            try:
                path = await client.download_media(photo, file=dest)
                if path and os.path.exists(path):
                    saved.append(os.path.abspath(path))
            except Exception as e:
                LOGS.warning(f"Could not download photo {i} [{prefix}]: {e}")
    else:
        # Fallback to single profile photo
        dest = os.path.join(BACKUP_DIR, f"{prefix}_single.jpg")
        try:
            path = await client.download_profile_photo(entity, file=dest)
            if path and os.path.exists(path):
                saved.append(os.path.abspath(path))
        except Exception as e:
            LOGS.warning(f"Could not download single profile photo [{prefix}]: {e}")

    return saved


async def delete_all_profile_photos(client) -> int:
    """Deletes all profile photos using get_input_photo."""
    try:
        photos = await client.get_profile_photos("me", limit=50)
    except Exception as e:
        LOGS.warning(f"Error fetching own photos to delete: {e}")
        photos = []

    if not photos:
        return 0

    input_photos = []
    for p in photos:
        try:
            inp = get_input_photo(p)
            if inp:
                input_photos.append(inp)
        except Exception:
            pass

    if input_photos:
        try:
            await client(DeletePhotosRequest(id=input_photos))
            LOGS.info(f"Deleted {len(input_photos)} profile photos")
            return len(input_photos)
        except Exception as e:
            LOGS.warning(f"DeletePhotosRequest error: {e}")
    return 0


async def upload_photos_in_order(client, photo_paths: list) -> int:
    """Uploads photos oldest to newest so newest stays as main DP."""
    uploaded = 0
    for path in photo_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            file = await client.upload_file(path)
            await client(UploadProfilePhotoRequest(file=file))
            uploaded += 1
        except Exception as e:
            LOGS.warning(f"Failed to upload photo {path}: {e}")
    return uploaded


def register_clone_handlers(client):
    """Registers .clone and .dclone/.revert handlers."""

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]clone(?:\s+([\s\S]+))?"))
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

        msg = await event.edit("⏳ **Starting clone...**")

        try:
            target_entity = await client.get_entity(target)
            target_full = await client(GetFullUserRequest(target_entity))
            me = await client.get_me()
            me_full = await client(GetFullUserRequest(me))

            target_bio = extract_user_bio(target_full)
            target_first = target_entity.first_name or ""
            target_last = target_entity.last_name or ""
            target_uname = getattr(target_entity, "username", None)

            # Step 1: Backup current photos & profile
            old_backup = load_backup(me.id)
            if old_backup:
                cleanup_files(old_backup.get("photos", []))
                delete_backup(me.id)

            await msg.edit("⏳ **[1/4] Backing up your current profile photos...**")
            my_photos = await download_all_photos(client, "me", f"orig_{me.id}")

            backup_data = {
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "bio": extract_user_bio(me_full),
                "username": me.username or "",
                "photos": my_photos,
            }
            save_backup(me.id, backup_data)

            # Step 2: Download target's profile photo(s)
            await msg.edit("⏳ **[2/4] Downloading target's profile photos...**")
            target_photos = await download_all_photos(client, target_entity, f"target_{target_entity.id}")

            # Step 3: Delete current profile photos
            await msg.edit("⏳ **[3/4] Updating profile photo...**")
            await delete_all_profile_photos(client)

            # Step 4: Upload target's profile photo(s)
            uploaded = 0
            if target_photos:
                uploaded = await upload_photos_in_order(client, target_photos)
                cleanup_files(target_photos)

            # Step 5: Update name and bio (never tamper with your @username)
            await msg.edit("⏳ **[4/4] Updating name & bio...**")
            await client(UpdateProfileRequest(
                first_name=target_first,
                last_name=target_last,
                about=target_bio[:70] if target_bio else ""
            ))

            target_name = f"{target_first} {target_last}".strip()
            bio_disp = f"\n📝 **Bio:** `{target_bio}`" if target_bio else "\n📝 **Bio:** *(No Bio)*"
            dp_disp = f"\n📸 **DP Cloned:** `{uploaded}` photo(s)" if uploaded > 0 else "\n📸 **DP:** *(Target has no photo or private)*"

            await msg.edit(
                f"👤 **Cloned:** `{target_name}`{bio_disp}{dp_disp}\n"
                f"💾 **Original DP backed up** (use `.revert` or `.dclone` to restore)"
            )

        except Exception as e:
            LOGS.exception("Clone failed")
            await msg.edit(f"❌ **Clone failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](dclone|revert)$"))
    async def revert_handler(event):
        me = await client.get_me()
        msg = await event.edit("⏳ **Reverting profile...**")

        orig = load_backup(me.id)
        if not orig:
            await msg.edit("ℹ️ **No backup found. Use `.clone` first.**")
            return

        orig_photos = orig.get("photos") or []
        existing = [p for p in orig_photos if os.path.exists(p)]

        try:
            # Step 1: Delete cloned profile photos
            await msg.edit("⏳ **[1/3] Removing cloned profile photos...**")
            await delete_all_profile_photos(client)

            # Step 2: Restore original profile photos
            restored = 0
            if existing:
                await msg.edit(f"⏳ **[2/3] Restoring original profile photo(s)...**")
                restored = await upload_photos_in_order(client, existing)
                cleanup_files(existing)

            # Step 3: Restore name and bio
            await msg.edit("⏳ **[3/3] Restoring name & bio...**")
            await client(UpdateProfileRequest(
                first_name=orig.get("first_name", ""),
                last_name=orig.get("last_name", ""),
                about=orig.get("bio", "")
            ))

            # If username was modified, safely restore it
            orig_uname = orig.get("username", "")
            if orig_uname:
                try:
                    curr_me = await client.get_me()
                    if curr_me.username != orig_uname:
                        await client(UpdateUsernameRequest(username=orig_uname))
                except Exception as e:
                    LOGS.warning(f"Could not restore username @{orig_uname}: {e}")

            delete_backup(me.id)

            await msg.edit(
                f"🔄 **Profile fully restored!**\n"
                f"📸 **DP:** `{restored}` photo(s) restored\n"
                f"👤 **Name:** `{orig.get('first_name', '')} {orig.get('last_name', '')}`.strip()"
            )

        except Exception as e:
            LOGS.exception("Revert failed")
            await msg.edit(f"❌ **Revert failed:** `{e}`")

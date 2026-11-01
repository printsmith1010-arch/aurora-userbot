"""
Aurora Profile Cloning & Reverting Plugin.

Commands: .clone, .dclone / .revert

.clone  → 1. Back up ALL your current DPs + profile info to disk (JSON index + image files)
          2. Download ALL of the target's DPs
          3. Delete ALL your DPs
          4. Upload target's DPs in same order (oldest→newest = their current DP on top)
          5. Copy target's name, bio, username

.dclone → 1. Delete ALL current (cloned) DPs
          2. Re-upload ALL your original DPs in original order
          3. Restore your original name, bio, username
          4. Clean up backup files from disk

Backup is persisted to disk so it survives bot restarts.
"""

import os
import json
import logging
from telethon import events
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoto
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraClonePlugin")

# Absolute directory where all clone backup files are stored
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "downloads", "clone_backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

plugin_manager.register_command(
    "clone", "custom",
    "Clones a target user's name, bio, ALL photos, and username.",
    f"{Config.COMMAND_HANDLER}clone <username/reply>"
)
plugin_manager.register_command(
    "dclone", "custom",
    "Deletes cloned DPs and restores all your original DPs.",
    f"{Config.COMMAND_HANDLER}dclone"
)


# ─────────────────────────── Persistence Helpers ───────────────────────────

def _index_path(user_id: int) -> str:
    """Path to the JSON index file for a user's backup."""
    return os.path.join(BACKUP_DIR, f"backup_{user_id}.json")


def save_backup(user_id: int, data: dict):
    """Save backup metadata to disk as JSON."""
    with open(_index_path(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_backup(user_id: int) -> dict | None:
    """Load backup metadata from disk. Returns None if no backup exists."""
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
    """Delete the JSON index file for a user."""
    path = _index_path(user_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup_files(paths: list):
    """Delete a list of files from disk."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


# ─────────────────────────── Bio Extractor ─────────────────────────────────

def extract_user_bio(full_user_obj) -> str:
    """Safely extracts bio from Telethon's UserFull response."""
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


# ─────────────────────────── Photo Helpers ─────────────────────────────────

async def fetch_all_photos(client, entity) -> list:
    """
    Fetch ALL profile Photo objects for entity, oldest→newest.
    Telegram returns newest-first, so we reverse.
    limit=0 = fetch everything with no cap.
    """
    photos = await client.get_profile_photos(entity, limit=0)
    return list(reversed(photos))  # oldest first


async def download_all_photos(client, entity, prefix: str) -> list:
    """
    Download ALL profile photos of entity to BACKUP_DIR (oldest→newest).
    Returns list of absolute file paths in that order.
    """
    photos = await fetch_all_photos(client, entity)
    saved = []
    for i, photo in enumerate(photos):
        dest = os.path.join(BACKUP_DIR, f"{prefix}_{i}.jpg")
        try:
            path = await client.download_media(photo, file=dest)
            if path and os.path.exists(path):
                saved.append(os.path.abspath(path))
        except Exception as e:
            LOGS.warning(f"Could not download photo {i} [{prefix}]: {e}")
    return saved


async def delete_all_profile_photos(client) -> int:
    """
    Delete ALL profile photos from account.
    Builds correct InputPhoto list — no silent failures.
    Returns count deleted.
    """
    photos = await client.get_profile_photos("me", limit=0)
    if not photos:
        return 0
    input_photos = [
        InputPhoto(
            id=p.id,
            access_hash=p.access_hash,
            file_reference=p.file_reference
        )
        for p in photos
    ]
    await client(DeletePhotosRequest(id=input_photos))
    LOGS.info(f"Deleted {len(input_photos)} profile photos")
    return len(input_photos)


async def upload_photos_in_order(client, photo_paths: list) -> int:
    """
    Upload photos oldest→newest so the newest ends up as current DP.
    Returns count of successfully uploaded photos.
    """
    uploaded = 0
    for path in photo_paths:
        if not os.path.exists(path):
            LOGS.warning(f"Photo file missing, skipping: {path}")
            continue
        try:
            file = await client.upload_file(path)
            await client(UploadProfilePhotoRequest(file=file))
            uploaded += 1
        except Exception as e:
            LOGS.warning(f"Failed to upload {path}: {e}")
    return uploaded


# ─────────────────────────── Handlers ──────────────────────────────────────

def register_clone_handlers(client):
    """Registers .clone and .dclone/.revert handlers."""

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]clone(?:\s+([\s\S]+))?"))
    async def clone_handler(event):
        reply     = await event.get_reply_message()
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
            target_full   = await client(GetFullUserRequest(target_entity))
            me            = await client.get_me()
            me_full       = await client(GetFullUserRequest(me))

            target_bio   = extract_user_bio(target_full)
            target_first = target_entity.first_name or ""
            target_last  = target_entity.last_name  or ""
            target_uname = getattr(target_entity, "username", None)

            # ── Step 1: Always back up YOUR CURRENT state fresh ──────────────────
            # Delete any old backup files for this user first (stale data cleanup)
            old_backup = load_backup(me.id)
            if old_backup:
                cleanup_files(old_backup.get("photos", []))
                delete_backup(me.id)

            await msg.edit("⏳ **[1/4] Backing up your current profile photos...**")
            my_photos = await download_all_photos(client, "me", f"orig_{me.id}")
            LOGS.info(f"Backed up {len(my_photos)} DPs for user {me.id}: {my_photos}")

            # Persist backup to disk so it survives bot restarts
            backup_data = {
                "first_name": me.first_name or "",
                "last_name":  me.last_name  or "",
                "bio":        extract_user_bio(me_full),
                "username":   me.username   or "",
                "photos":     my_photos,
            }
            save_backup(me.id, backup_data)

            # ── Step 2: Download ALL of target's DPs ─────────────────────────────
            await msg.edit("⏳ **[2/4] Downloading target's profile photos...**")
            target_photos = await download_all_photos(client, target_entity, f"target_{target_entity.id}")
            LOGS.info(f"Downloaded {len(target_photos)} target DPs: {target_photos}")

            # ── Step 3: Delete ALL your current DPs ──────────────────────────────
            await msg.edit("⏳ **[3/4] Removing all your DPs...**")
            deleted = await delete_all_profile_photos(client)

            # ── Step 4: Upload ALL target's DPs in same order ────────────────────
            await msg.edit("⏳ **[4/4] Uploading target's profile photos...**")
            uploaded = await upload_photos_in_order(client, target_photos)
            cleanup_files(target_photos)

            # ── Step 5: Set name, bio, username ──────────────────────────────────
            await client(UpdateProfileRequest(
                first_name=target_first,
                last_name=target_last,
                about=target_bio[:70] if target_bio else ""
            ))

            new_uname_str = ""
            if target_uname:
                for candidate in [f"{target_uname}1", f"{target_uname}_1", f"{target_uname}11"]:
                    try:
                        await client(UpdateUsernameRequest(username=candidate))
                        new_uname_str = f"\n🔗 **Username:** @{candidate}"
                        break
                    except Exception:
                        pass

            target_name = f"{target_first} {target_last}".strip()
            bio_disp    = f"\n📝 **Bio:** `{target_bio}`" if target_bio else "\n📝 **Bio:** *(No Bio)*"

            await msg.edit(
                f"👤 **Cloned:** `{target_name}`{new_uname_str}{bio_disp}\n"
                f"📸 **{uploaded}/{len(target_photos)} target DP(s) set**\n"
                f"💾 **{len(my_photos)} of your DP(s) backed up to disk**"
            )

        except Exception as e:
            LOGS.exception("Clone failed")
            await msg.edit(f"❌ **Clone failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](dclone|revert)$"))
    async def revert_handler(event):
        me  = await client.get_me()
        msg = await event.edit("⏳ **Reverting profile...**")

        # Load backup from disk (works even after bot restart)
        orig = load_backup(me.id)
        if not orig:
            await msg.edit("ℹ️ **No backup found. Use `.clone` first.**")
            return

        orig_photos = orig.get("photos") or []

        # Verify at least some backup files still exist on disk
        existing = [p for p in orig_photos if os.path.exists(p)]
        if orig_photos and not existing:
            await msg.edit(
                "⚠️ **Backup photo files are missing from disk** "
                "(bot may have been moved/restarted on a different machine).\n"
                "Clearing stale backup."
            )
            delete_backup(me.id)
            return

        try:
            # ── Step 1: Delete ALL current (cloned) DPs ──────────────────────────
            await msg.edit("⏳ **[1/3] Removing cloned profile photos...**")
            deleted = await delete_all_profile_photos(client)

            # ── Step 2: Re-upload ALL your original DPs in original order ─────────
            await msg.edit(f"⏳ **[2/3] Restoring your {len(existing)} original DP(s)...**")
            restored = await upload_photos_in_order(client, existing)
            cleanup_files(existing)

            # ── Step 3: Restore name, bio, username ──────────────────────────────
            await msg.edit("⏳ **[3/3] Restoring name, bio, username...**")
            await client(UpdateProfileRequest(
                first_name=orig["first_name"],
                last_name=orig["last_name"],
                about=orig.get("bio", "")
            ))
            if orig.get("username"):
                try:
                    await client(UpdateUsernameRequest(username=orig["username"]))
                except Exception:
                    pass

            # Clean up backup index from disk
            delete_backup(me.id)

            await msg.edit(
                f"🔄 **Profile fully restored!**\n"
                f"📸 **{restored}/{len(existing)} original DP(s) restored.**"
            )

        except Exception as e:
            LOGS.exception("Revert failed")
            await msg.edit(f"❌ **Revert failed:** `{e}`")

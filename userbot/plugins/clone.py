# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement"

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Special Credits: @ViperAdnan and @mrconfused(revert)[will add sql soon]

import html
import os

from telethon.tl import functions
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoto

from ..Config import Config
from ..sql_helper.globals import gvarstatus
from . import ALIVE_NAME, BOTLOG, BOTLOG_CHATID, catub, edit_delete, get_user_from_event

plugin_category = "utils"

# Path where original dp is saved before cloning
_ORIG_DP_PATH = os.path.join(Config.TEMP_DIR, "original_dp_backup.jpg")


async def _backup_my_dp(client):
    """Download and save current profile photo to disk. Returns path or None."""
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    path = await client.download_profile_photo("me", file=_ORIG_DP_PATH)
    return path if path and os.path.exists(path) else None


async def _delete_all_my_dps(client):
    """Delete all current profile photos."""
    photos = await client.get_profile_photos("me", limit=0)
    if not photos:
        return
    input_photos = [
        InputPhoto(
            id=p.id,
            access_hash=p.access_hash,
            file_reference=p.file_reference,
        )
        for p in photos
    ]
    await client(functions.photos.DeletePhotosRequest(id=input_photos))


@catub.cat_cmd(
    pattern="clone(?:\\s|$)([\\s\\S]*)",
    command=("clone", plugin_category),
    info={
        "header": "To clone account of mentioned user or replied user",
        "usage": "{tr}clone <username/userid/reply>",
    },
)
async def _(event):
    "To clone account of mentioned user or replied user"
    replied_user, error_i_a = await get_user_from_event(event)
    if replied_user is None:
        return
    user_id = replied_user.id

    # --- Back up YOUR current dp before cloning ---
    await _backup_my_dp(event.client)

    # --- Download target's dp ---
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    target_dp_path = os.path.join(Config.TEMP_DIR, f"clone_target_{user_id}.jpg")
    profile_pic = await event.client.download_profile_photo(user_id, file=target_dp_path)

    # --- Clone name & bio ---
    first_name = html.escape(replied_user.first_name or "")
    first_name = first_name.replace("\u2060", "")
    last_name = replied_user.last_name
    if last_name is not None:
        last_name = html.escape(last_name).replace("\u2060", "")
    if not last_name:
        last_name = "⁪⁬⁮⁮⁮⁮ ‌‌‌‌"
    replied_user_full = (await event.client(GetFullUserRequest(replied_user.id))).full_user
    user_bio = replied_user_full.about

    await event.client(functions.account.UpdateProfileRequest(first_name=first_name))
    await event.client(functions.account.UpdateProfileRequest(last_name=last_name))
    await event.client(functions.account.UpdateProfileRequest(about=user_bio))

    # --- Clone dp ---
    if profile_pic and os.path.exists(profile_pic):
        try:
            pfile = await event.client.upload_file(profile_pic)
            await event.client(functions.photos.UploadProfilePhotoRequest(pfile))
        except Exception as e:
            await edit_delete(event, f"**Cloned name/bio but failed to clone DP:**\n__{e}__")
            return
        finally:
            # Clean up target dp temp file
            try:
                os.remove(profile_pic)
            except Exception:
                pass
    # If target has no dp, we just clone name/bio silently

    await edit_delete(event, "**LET US BE AS ONE**")
    if BOTLOG:
        await event.client.send_message(
            BOTLOG_CHATID,
            f"#CLONED\nsuccessfully cloned [{first_name}](tg://user?id={user_id})",
        )


@catub.cat_cmd(
    pattern="revert$",
    command=("revert", plugin_category),
    info={
        "header": "To revert back to your original name, bio and profile pic",
        "note": "For proper Functioning of this command you need to set DEFAULT_USER in Database",
        "usage": "{tr}revert",
    },
)
async def revert(event):
    "To reset your original details"
    firstname = gvarstatus("FIRST_NAME") or ALIVE_NAME
    lastname = gvarstatus("LAST_NAME") or ""
    bio = (
        gvarstatus("DEFAULT_BIO")
        or "sıɥʇ ǝpoɔǝp uǝɥʇ llıʇu∩ ˙ǝɔɐds ǝʇɐʌıɹd ǝɯos ǝɯ ǝʌı⅁"
    )

    # --- Delete all cloned dps ---
    await _delete_all_my_dps(event.client)

    # --- Restore original dp if backup exists ---
    if os.path.exists(_ORIG_DP_PATH):
        try:
            pfile = await event.client.upload_file(_ORIG_DP_PATH)
            await event.client(functions.photos.UploadProfilePhotoRequest(pfile))
        except Exception:
            pass
        finally:
            try:
                os.remove(_ORIG_DP_PATH)
            except Exception:
                pass

    # --- Restore name & bio ---
    await event.client(functions.account.UpdateProfileRequest(about=bio))
    await event.client(functions.account.UpdateProfileRequest(first_name=firstname))
    await event.client(functions.account.UpdateProfileRequest(last_name=lastname))

    await edit_delete(event, "**Successfully reverted to your original profile!**")
    if BOTLOG:
        await event.client.send_message(
            BOTLOG_CHATID,
            "#REVERT\nsuccessfully reverted back to your profile",
        )

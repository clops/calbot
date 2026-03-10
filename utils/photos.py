"""
Photo utilities — download Telegram photos and encode for Claude vision API.
"""

import base64

from telegram import PhotoSize


async def photo_to_base64(photo: PhotoSize, bot) -> str:
    """Download a Telegram photo and return it as a base64-encoded string.

    Args:
        photo: The PhotoSize object (use update.message.photo[-1] for highest res).
        bot: The Telegram Bot instance (available as context.bot in handlers).

    Returns:
        Base64-encoded JPEG string suitable for passing to Claude's vision API.
    """
    file = await bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()
    return base64.b64encode(data).decode("utf-8")

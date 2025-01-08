import logging
import re
from telethon import events

logger = logging.getLogger(__name__)

def init(client):
    """
    Ловим все сообщения (под конец), чтобы не мешать другим.
    """
    @client.on(events.NewMessage(pattern="(?s).*"))  # (?s) — "dotall", ловит всё
    async def debug_all_handler(event):
        # Логируем любые сообщения
        msg_text = event.raw_text or ""
        chat_id = event.chat_id
        user_id = event.sender_id or "None"
        logger.info(f"[DEBUG_ALL] Chat={chat_id}, User={user_id}, Text={msg_text}")

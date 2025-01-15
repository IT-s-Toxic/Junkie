import re
import logging
from telethon import events, types
from pymongo import MongoClient
from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

delete_channel_messages = False

def init(client):
    register_help("channel_filter", {
        "Джанки, к чёрту маски": "Включает удаление сообщений от каналов (только для AUTHORIZED_USERS).",
        "Джанки, пусть прячутся": "Выключает удаление сообщений от каналов (только для AUTHORIZED_USERS)."
    })

    # Подключение к базе данных для получения шуток (если нужно)
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    jokes_col = db["jokes"]

    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*к\s*чёрту\s*маски\s*$")))
    async def enable_channel_filter(event):
        global delete_channel_messages
        if event.sender_id not in AUTHORIZED_USERS:
            try:
                joke = await jokes_col.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                response = joke[0]["text"] if joke else "Нет прав."
            except Exception:
                response = "У тебя нет прав."
            await event.reply(response)
            return

        delete_channel_messages = True
        await event.reply("Удаление сообщений от каналов включено.")

    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*пусть\s*прячутся\s*$")))
    async def disable_channel_filter(event):
        global delete_channel_messages
        if event.sender_id not in AUTHORIZED_USERS:
            try:
                joke = await jokes_col.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                response = joke[0]["text"] if joke else "Нет прав."
            except Exception:
                response = "У тебя нет прав."
            await event.reply(response)
            return

        delete_channel_messages = False
        await event.reply("Удаление сообщений от каналов выключено.")

    @client.on(events.NewMessage)
    async def channel_message_filter(event):
        global delete_channel_messages
        if not delete_channel_messages:
            return

        message = event.message
        # Проверяем, отправлено ли сообщение от имени канала
        if isinstance(message.from_id, types.PeerChannel):
            try:
                await client.delete_messages(message.chat_id, [message.id])
                logger.info(f"Удалено сообщение {message.id} от канала.")
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения {message.id}: {e}")

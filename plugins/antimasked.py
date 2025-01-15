import re
import logging
from telethon import events, types, errors, functions
from pymongo import MongoClient
from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

# Регэкспы для команд
ENABLE_PATTERN = re.compile(r"(?i)^джанки,\s*к\s*чёрту\s*маски\s*$")
DISABLE_PATTERN = re.compile(r"(?i)^джанки,\s*пусть\s*прячутся\s*$")

def init(client):
    register_help("channel_filter", {
        "Джанки, к чёрту маски": "Включает удаление сообщений от пользователей под масками каналов (только AUTHORIZED_USERS).",
        "Джанки, пусть прячутся": "Выключает удаление сообщений от пользователей под масками каналов (только AUTHORIZED_USERS)."
    })

    # Подключение к MongoDB и коллекции
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    states_col = db["states"]
    jokes_col = db["jokes"]

    # Инициализируем состояние плагина, если не существует
    state = states_col.find_one({"plugin": "channel_filter"})
    if state is None:
        states_col.insert_one({"plugin": "channel_filter", "enabled": False})

    @client.on(events.NewMessage(pattern=ENABLE_PATTERN))
    async def enable_channel_filter(event):
        if event.sender_id not in AUTHORIZED_USERS:
            try:
                joke = await jokes_col.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                response = joke[0]["text"] if joke else "Нет прав."
            except Exception:
                response = "У тебя нет прав."
            await event.reply(response)
            return

        states_col.update_one({"plugin": "channel_filter"}, {"$set": {"enabled": True}})
        await event.reply("Удаление сообщений от пользователей под масками каналов включено.")

    @client.on(events.NewMessage(pattern=DISABLE_PATTERN))
    async def disable_channel_filter(event):
        if event.sender_id not in AUTHORIZED_USERS:
            try:
                joke = await jokes_col.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                response = joke[0]["text"] if joke else "Нет прав."
            except Exception:
                response = "У тебя нет прав."
            await event.reply(response)
            return

        states_col.update_one({"plugin": "channel_filter"}, {"$set": {"enabled": False}})
        await event.reply("Удаление сообщений от пользователей под масками каналов выключено.")

    @client.on(events.NewMessage)
    async def channel_message_filter(event):
        # Проверяем состояние плагина из базы
        state = states_col.find_one({"plugin": "channel_filter"})
        if not state or not state.get("enabled", False):
            return

        message = event.message
        # Проверяем, что сообщение отправлено от канала
        if isinstance(message.from_id, types.PeerChannel):
            try:
                await client.delete_messages(message.chat_id, [message.id])
                logger.info(f"Удалено сообщение {message.id} от канала.")
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения {message.id}: {e}")

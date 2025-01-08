import re
import logging
import time
from telethon import events
from pymongo import MongoClient

from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

ADD_JOKE_PATTERN = re.compile(r"(?i)^джанки,\s*в\s+шутейки\s*$")
REMOVE_JOKE_PATTERN = re.compile(r"(?i)^джанки,\s*не\s+смешно\s*$")

def init(client):
    register_help("jokes_manager", {
        "Джанки, в шутейки": "Добавляет шутку из реплай-сообщения в коллекцию jokes (AUTHORIZED_USERS).",
        "Джанки, не смешно": "Удаляет шутку из реплай-сообщения из коллекции jokes (AUTHORIZED_USERS)."
    })
    
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    jokes_col = db['jokes']
    
    @client.on(events.NewMessage(pattern=ADD_JOKE_PATTERN))
    async def add_joke(event):
        if event.sender_id not in AUTHORIZED_USERS:
            return
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение с шуткой.")
            return
        reply = await event.get_reply_message()
        joke_text = reply.text
        if not joke_text:
            await event.reply("Сообщение не содержит текста для шутки.")
            return
        try:
            jokes_col.insert_one({
                "text": joke_text,
                "added_by": event.sender_id,
                "added_at": time.time()
            })
            await event.reply("Шутка успешно добавлена в коллекцию!")
            logger.info(f"Добавлена шутка: {joke_text[:30]}... от пользователя {event.sender_id}")
        except Exception as e:
            await event.reply("Произошла ошибка при добавлении шутки.")
            logger.error(f"Ошибка при добавлении шутки: {e}")
    
    @client.on(events.NewMessage(pattern=REMOVE_JOKE_PATTERN))
    async def remove_joke(event):
        if event.sender_id not in AUTHORIZED_USERS:
            return
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение с шуткой, которую хотите удалить.")
            return
        reply = await event.get_reply_message()
        joke_text = reply.text
        if not joke_text:
            await event.reply("Сообщение не содержит текста для удаления шутки.")
            return
        try:
            result = jokes_col.delete_one({"text": joke_text})
            if result.deleted_count:
                await event.reply("Шутка успешно удалена из коллекции!")
                logger.info(f"Удалена шутка: {joke_text[:30]}... от пользователя {event.sender_id}")
            else:
                await event.reply("Такая шутка не найдена в коллекции.")
                logger.info(f"Шутка для удаления не найдена: {joke_text[:30]}...")
        except Exception as e:
            await event.reply("Произошла ошибка при удалении шутки.")
            logger.error(f"Ошибка при удалении шутки: {e}")

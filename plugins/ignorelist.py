import re
import logging
import random
import time
from telethon import events
from pymongo import MongoClient

from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME, LOGCHANNEL
from utils.misc import register_help

logger = logging.getLogger(__name__)

IGNORE_CMD_PATTERN = re.compile(r"(?i)^джанки,\s*этого\s+игнорим\s*$")
UNIGNORE_CMD_PATTERN = re.compile(r"(?i)^джанки,\s*этого\s+не\s+игнорим\s*$")

def init(client):
    register_help("ignorelist", {
        "Джанки, этого игнорим": "Добавляет пользователя в список игнорируемых (только для AUTHORIZED_USERS).",
        "Джанки, этого не игнорим": "Удаляет пользователя из списка игнорируемых (только для AUTHORIZED_USERS)."
    })
    
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    ignorelist_col = db['ignorelist']
    jokes_col = db['jokes']
    
    @client.on(events.NewMessage(pattern=IGNORE_CMD_PATTERN))
    async def add_to_ignore(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice([
                "Неа",
                "Иди нахер, кожаный ублюдок",
                "Не положено.",
                "Ты кто такой? Давай, до свидания...",
                "У тебя нет прав на это действие."
            ]))
            return
        
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение пользователя, которого хотите игнорировать.")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        user_id = reply.sender_id
        try:
            result = ignorelist_col.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "added_at": time.time()}},
                upsert=True
            )
            if result.upserted_id:
                await event.reply(f"Пользователь добавлен в список игнорируемых.")
                logger.info(f"Пользователь {user_id} добавлен в ignorelist.")
            else:
                await event.reply("Этот пользователь уже находится в списке игнорируемых.")
                logger.info(f"Попытка добавить уже игнорируемого пользователя {user_id}.")
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя {user_id} в ignorelist: {e}")
            await event.reply("Произошла ошибка при добавлении пользователя в ignorelist.")
    
    @client.on(events.NewMessage(pattern=UNIGNORE_CMD_PATTERN))
    async def remove_from_ignore(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice([
                "Неа",
                "Иди нахер, кожаный ублюдок",
                "Не положено.",
                "Ты кто такой? Давай, до свидания...",
                "У тебя нет прав на это действие."
            ]))
            return
        
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение пользователя, которого хотите удалить из игнорируемых.")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        user_id = reply.sender_id
        try:
            result = ignorelist_col.delete_one({"user_id": user_id})
            if result.deleted_count:
                await event.reply("Пользователь удалён из списка игнорируемых.")
                logger.info(f"Пользователь {user_id} удалён из ignorelist.")
            else:
                await event.reply("Этот пользователь не находится в списке игнорируемых.")
                logger.info(f"Попытка удалить неигнорируемого пользователя {user_id}.")
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {user_id} из ignorelist: {e}")
            await event.reply("Произошла ошибка при удалении пользователя из списка.")
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,.*$")))
    async def handle_ignored_commands(event):
        user_id = event.sender_id
        try:
            is_ignored = ignorelist_col.find_one({"user_id": user_id})
            if is_ignored:
                refusal = random.choice([
                    "Извините, но ваши команды игнорируются.",
                    "Ваши команды не принимаются.",
                    "Не могу выполнить вашу команду.",
                    "Ваш запрос отклонён."
                ])
                await event.reply(refusal)
                event.stop_propagation()
        except Exception as e:
            logger.error(f"Ошибка при проверке ignorelist для пользователя {user_id}: {e}")

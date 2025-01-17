import re
import logging
import random
from telethon import events
from pymongo import MongoClient
from utils.config import MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

def init(client):
    # Инициализируем подключение к MongoDB
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    jokes_col = db["jokes"]

    # Регулярное выражение для команд с обязательным префиксом "Джанки, "
    command_pattern = re.compile(r"(?i)^джанки,\s*(голос|шалом|привет|хай)\s*$")

    @client.on(events.NewMessage(pattern=command_pattern))
    async def voice_handler(event):
        try:
            # Получаем все шутки из коллекции и выбираем случайную
            jokes = list(jokes_col.find({}))
            if jokes:
                chosen_joke = random.choice(jokes)
                msg = chosen_joke.get("text", "Шутка не найдена.")
            else:
                msg = "Нет шуток в базе данных."
        except Exception as e:
            logger.error(f"Ошибка при выборе шутки: {e}")
            msg = "Произошла ошибка при попытке получить шутку."

        await event.reply(msg)

    register_help("ping_echo", {
        "Джанки, голос / шалом / привет / хай":
            "Ответ саркастичной фразой из базы данных."
    })

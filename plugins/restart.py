import re
import os
import sys
import logging
import random
from telethon import events

from utils.config import AUTHORIZED_USERS
from utils.misc import register_help

logger = logging.getLogger(__name__)

# Список грубых ответов для неавторизованных пользователей
RUDE_REPLIES = [
    "Неа",
    "Иди нахер, кожаный ублюдок",
    "Не положено.",
    "Ты кто такой? Давай, до свидания...",
    "У тебя нет прав на это действие."
]

def init(client):
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*рестарт\s*$")))
    async def restart_handler(event):
        # Проверяем, является ли отправитель авторизованным пользователем
        if event.sender_id not in AUTHORIZED_USERS:
            reply = random.choice(RUDE_REPLIES)
            await event.reply(reply)
            logger.warning(f"Пользователь {event.sender_id} попытался выполнить рестарт без прав.")
            return

        # Авторизованный пользователь - выполняем рестарт
        await event.reply("Перезапуск...")
        logger.info("Выполняется рестарт бота по команде от пользователя %s.", event.sender_id)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # Регистрируем команду в справке
    register_help("restart", {
        "Джанки, рестарт": "Перезапускает бота (только для AUTHORIZED_USERS)."
    })

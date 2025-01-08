import re
import logging
from telethon import events
from utils.misc import register_help

logger = logging.getLogger(__name__)

def init(client):
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*пример\s*отправки\s*$")))
    async def example_send(event):
        await event.respond("Это пример отправки нового сообщения!")

    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*пример\s*редактирования\s*$")))
    async def example_edit(event):
        await event.edit("Это пример редактирования сообщения.")

    register_help("example", {
        "Джанки, пример отправки": "Отправляет новое сообщение",
        "Джанки, пример редактирования": "Редактирует текущее сообщение"
    })

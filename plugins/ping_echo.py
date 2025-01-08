import time
import random
import re
import logging
from telethon import events
from utils.misc import register_help

logger = logging.getLogger(__name__)

def init(client):
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*голос\s*$")))
    async def voice_handler(event):
        answers = [
            "Да кто спрашивает?",
            "Голос? Вот тебе голос.",
            "Ладно, ты победил. Голос активирован.",
            "Гав тебя по яйцам. Удовлетворён?",
        ]
        msg = answers[int(time.time()) % len(answers)]
        await event.reply(msg)

    # Регистрируем help
    register_help("ping_echo", {
        "Джанки, голос": "Ответ саркастичной фразой."
    })

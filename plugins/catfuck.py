import re
import logging
import random
from telethon import events
from pymongo import MongoClient

from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

# Регулярки и конфигурации
CATFUCK_PATTERN = re.compile(
    r'''(?xi)
    (?=
      .*?\b
      (?:
        (?:[kк][оo0][tт][aа])
        | (?:.[оo0][tт][aа])
        | (?:[kк].[tт][aа])
        | (?:[kк][оo0].[aа])
        | (?:[kк][оo0][tт].)
        | (?:[kк][оo0][tт][оo0][vв])
        | (?:.[оo0][tт][оo0][vв])
        | (?:[kк].[tт][оo0][vв])
        | (?:[kк][оo0].[оo0][vв])
        | (?:[kк][оo0][tт].[vв])
        | (?:[kк][оo0][tт][оo0].)
      )
      \b
    )
    (?=
      .*?\b
      (?:
        [eе][bб][aа][lл]
        | .[bб][aа][lл]
        | [eе].[aа][lл]
        | [eе][bб].[lл]
        | [eе][bб][aа].
      )
      \b
    )
    .* 
    ''',
    flags=0
)

WYEBAN_PATTERN = re.compile(
    r'''(?xi)
    [вv][ыyиi]?[еe][бb][аa][нn][ыyиiеe]?
    ''',
    flags=0
)

RUDE_REPLIES = [
    "Неа",
    "Иди нахер, кожаный ублюдок",
    "Не положено.",
    "Ты кто такой? Давай, до свидания...",
    "У тебя нет прав на это действие."
]

catfuck_filter_enabled = True
catfuckers_collection = None

def init(client):
    global catfuckers_collection
    register_help("catfuck", {
        "Джанки, ебём котов": "Включает фильтр котоёбства",
        "Джанки, не ебём котов": "Выключает фильтр котоёбства",
        "Джанки, лови котоёба": "Добавляет пользователя в список котоёбов",
        "Джанки, не котоёб": "Удаляет пользователя из списка котоёбов"
    })
    
    # Подключение к MongoDB
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    catfuckers_collection = db['catfuckers']
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*ебём\s+котов\s*$")))
    async def catfuck_on_cmd(event):
        global catfuck_filter_enabled
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice(RUDE_REPLIES))
            return
        catfuck_filter_enabled = True
        await event.reply("Catfuck-фильтр включён!")
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*не\s+ебём\s+котов\s*$")))
    async def catfuck_off_cmd(event):
        global catfuck_filter_enabled
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice(RUDE_REPLIES))
            return
        catfuck_filter_enabled = False
        await event.reply("Catfuck-фильтр выключен!")
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*лови\s+котоёба\s*$")))
    async def add_catfucker(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice(RUDE_REPLIES))
            return
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение «котоёба».")
            return
        rep = await event.get_reply_message()
        if not rep or not rep.sender_id:
            await event.reply("Не вижу отправителя в реплае.")
            return
        target_id = rep.sender_id
        try:
            catfuckers_collection.update_one(
                {"user_id": target_id},
                {"$set": {"user_id": target_id}},
                upsert=True
            )
            await event.reply(f"Пользователь {target_id} добавлен в список котоёбов!")
        except Exception as e:
            logger.error(f"Ошибка при добавлении котоёба: {e}")
            await event.reply("Ошибка при добавлении пользователя в список.")
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*не\s+котоёб\s*$")))
    async def remove_catfucker(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice(RUDE_REPLIES))
            return
        if not event.is_reply:
            await event.reply("Используйте команду ответом на сообщение «бывшего котоёба».")
            return
        rep = await event.get_reply_message()
        if not rep or not rep.sender_id:
            await event.reply("Нет отправителя в реплае.")
            return
        target_id = rep.sender_id
        try:
            result = catfuckers_collection.delete_one({"user_id": target_id})
            if result.deleted_count:
                await event.reply(f"Пользователь {target_id} исключён из списка котоёбов.")
            else:
                await event.reply("Этот пользователь не в списке котоёбов.")
        except Exception as e:
            logger.error(f"Ошибка при удалении котоёба: {e}")
            await event.reply("Ошибка при удалении пользователя из списка.")
    
    @client.on(events.NewMessage())
    async def catfuck_filter(event):
        global catfuck_filter_enabled
        if not catfuck_filter_enabled:
            return
        # Проверка, есть ли пользователь в списке котоёбов
        if not catfuckers_collection.find_one({"user_id": event.sender_id}):
            return
        text = event.raw_text or ""
        if CATFUCK_PATTERN.search(text):
            try:
                await event.delete()
                logger.info(f"Удалил сообщение (catfuck) от {event.sender_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении catfuck-сообщения: {e}")
            return
        if event.is_reply and WYEBAN_PATTERN.search(text):
            try:
                await event.delete()
                logger.info(f"Удалил сообщение (wyeban) от {event.sender_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении wyeban-сообщения: {e}")

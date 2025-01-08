import re
import logging
import random
import time
from telethon import events, functions, types
from pymongo import MongoClient

from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME, LOGCHANNEL
from utils.misc import register_help

logger = logging.getLogger(__name__)

ADD_BIO_PATTERN = re.compile(r"(?i)^джанки,\s*запиши\s+(.+)$")
PIZDBOL_PATTERN = re.compile(r"(?i)^пиздабол$")
NE_PIZDBOL_PATTERN = re.compile(r"(?i)^не\s+пиздабол$")

def init(client):
    register_help("bio_manager", {
        "Джанки, запиши {текст}": "Записывает указанный текст в био пользователя, на сообщение которого сделан реплай (только для AUTHORIZED_USERS).",
        "пиздабол": "Увеличивает карму пользователя (только для AUTHORIZED_USERS).",
        "не пиздабол": "Уменьшает карму пользователя (только для AUTHORIZED_USERS).",
        "Джанки, био": "Выводит информацию о пользователе из био."
    })
    
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    bio_col = db['bio']
    jokes_col = db['jokes']
    
    @client.on(events.NewMessage(pattern=ADD_BIO_PATTERN))
    async def add_bio(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice([
                "У тебя нет прав на это действие."
            ]))
            return
        
        if not event.is_reply:
            await event.reply("Используйте команду реплаем на сообщение пользователя, которому хотите записать био.")
            return
        
        match = ADD_BIO_PATTERN.match(event.raw_text)
        if not match:
            await event.reply("Не удалось распознать текст для записи.")
            return
        
        bio_text = match.group(1).strip()
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        target_id = reply.sender_id
        
        try:
            bio_doc = bio_col.find_one({"user_id": target_id})
            if bio_doc:
                bio_col.update_one(
                    {"user_id": target_id},
                    {"$set": {"bio_text": bio_text, "updated_at": time.time()}}
                )
                await event.reply("Био пользователя успешно обновлено!")
                logger.info(f"Био пользователя {target_id} обновлено.")
            else:
                bio_col.insert_one({
                    "user_id": target_id,
                    "bio_text": bio_text,
                    "karma": 0,
                    "joined_at": time.time(),
                    "created_at": time.time(),
                    "updated_at": time.time()
                })
                await event.reply("Био пользователя успешно записано!")
                logger.info(f"Био пользователя {target_id} добавлено.")
        except Exception as e:
            await event.reply("Произошла ошибка при записи био.")
            logger.error(f"Ошибка при записи био пользователя {target_id}: {e}")
    
    @client.on(events.NewMessage(pattern=PIZDBOL_PATTERN))
    async def add_pizdbol(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice([
                "У тебя нет прав на это действие."
            ]))
            return
        
        if not event.is_reply:
            await event.reply("Используйте команду реплаем на сообщение пользователя, карму которого хотите увеличить.")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        target_id = reply.sender_id
        
        try:
            bio_doc = bio_col.find_one({"user_id": target_id})
            if bio_doc:
                new_karma = bio_doc.get("karma", 0) + 1
                bio_col.update_one(
                    {"user_id": target_id},
                    {"$set": {"karma": new_karma, "updated_at": time.time()}}
                )
            else:
                bio_col.insert_one({
                    "user_id": target_id,
                    "bio_text": "",
                    "karma": 1,
                    "joined_at": time.time(),
                    "created_at": time.time(),
                    "updated_at": time.time()
                })
                new_karma = 1
            
            update_bio_with_karma(bio_col, target_id, new_karma)
            await event.reply(f"Карма пользователя увеличена до {new_karma}.")
            logger.info(f"Карма пользователя {target_id} увеличена до {new_karma}.")
        except Exception as e:
            await event.reply("Произошла ошибка при увеличении кармы.")
            logger.error(f"Ошибка при увеличении кармы пользователя {target_id}: {e}")
    
    @client.on(events.NewMessage(pattern=NE_PIZDBOL_PATTERN))
    async def remove_pizdbol(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply(random.choice([
                "У тебя нет прав на это действие."
            ]))
            return
        
        if not event.is_reply:
            await event.reply("Используйте команду реплаем на сообщение пользователя, карму которого хотите уменьшить.")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        target_id = reply.sender_id
        
        try:
            bio_doc = bio_col.find_one({"user_id": target_id})
            if bio_doc and bio_doc.get("karma", 0) > 0:
                new_karma = bio_doc.get("karma", 0) - 1
                bio_col.update_one(
                    {"user_id": target_id},
                    {"$set": {"karma": new_karma, "updated_at": time.time()}}
                )
            else:
                new_karma = 0
            
            update_bio_with_karma(bio_col, target_id, new_karma)
            await event.reply(f"Карма пользователя уменьшена до {new_karma}.")
            logger.info(f"Карма пользователя {target_id} уменьшена до {new_karma}.")
        except Exception as e:
            await event.reply("Произошла ошибка при уменьшении кармы.")
            logger.error(f"Ошибка при уменьшении кармы пользователя {target_id}: {e}")
    
    def update_bio_with_karma(bio_col, user_id, karma):
        try:
            bio_doc = bio_col.find_one({"user_id": user_id})
            if bio_doc:
                current_bio = bio_doc.get("bio_text", "")
                karma_text = f"Пиздел {karma} раз" if karma > 0 else ""
                # Удаляем предыдущую фразу о карме
                new_bio_lines = [line for line in current_bio.splitlines() if not line.startswith("Пиздел")]
                if karma_text:
                    new_bio_lines.append(karma_text)
                new_bio = "\n".join(new_bio_lines).strip()
                bio_col.update_one(
                    {"user_id": user_id},
                    {"$set": {"bio_text": new_bio, "updated_at": time.time()}}
                )
                logger.debug(f"Био пользователя {user_id} обновлено с кармой {karma}.")
        except Exception as e:
            logger.error(f"Ошибка при обновлении био пользователя {user_id}: {e}")
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*био\s*$")))
    async def show_bio(event):
        if not event.is_reply:
            await event.reply("Используйте команду реплаем на сообщение пользователя, чьё био хотите просмотреть.")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            await event.reply("Не удалось определить пользователя из реплая.")
            return
        
        target_id = reply.sender_id
        try:
            bio_doc = bio_col.find_one({"user_id": target_id})
            if bio_doc:
                bio_text = bio_doc.get("bio_text", "Нет информации о био.")
                await event.reply(bio_text)
            else:
                await event.reply("Я хз, может это бот?")
        except Exception as e:
            await event.reply("Произошла ошибка при получении информации о пользователе.")
            logger.error(f"Ошибка при показе био пользователя {target_id}: {e}")
    
    @client.on(events.ChatAction)
    async def handle_user_join(event):
        if not event.user_joined:
            return

        user_id = event.user_id
        try:
            participant = await client(functions.channels.GetParticipantRequest(
                channel=event.chat_id,
                participant=user_id
            ))
            join_date = getattr(participant.participant, 'date', time.time())

            bio_doc = bio_col.find_one({"user_id": user_id})
            if bio_doc:
                bio_col.update_one(
                    {"user_id": user_id},
                    {"$set": {"joined_at": join_date, "updated_at": time.time()}}
                )
                logger.info(f"Пользователь {user_id} присоединился. Дата: {join_date}")
            else:
                bio_col.insert_one({
                    "user_id": user_id,
                    "bio_text": "",
                    "karma": 0,
                    "joined_at": join_date,
                    "created_at": time.time(),
                    "updated_at": time.time()
                })
                logger.info(f"Новый пользователь {user_id} записан с joined_at: {join_date}.")
        except Exception as e:
            logger.error(f"Ошибка при обработке присоединения пользователя {user_id}: {e}")

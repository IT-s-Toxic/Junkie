import asyncio
import logging
import re
import time
from telethon import events, types, errors, functions
from pymongo import MongoClient
from utils.config import AUTHORIZED_USERS, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

# Регулярные выражения для команд
MONITOR_COMMAND = re.compile(r"(?i)^джанки,\s*мониторим\s*чат\s*$")
STOP_MONITOR_COMMAND = re.compile(r"(?i)^джанки,\s*перестань\s*мониторить\s*чат\s*$")

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[DB_NAME]
states_col = db["states"]
history_col = db["changes_history"]

# В оперативной памяти храним профили участников для мониторинга
monitored_chats = {}  # {chat_id: {user_id: profile_info, ...}, ...}

def serialize_user(user: types.User) -> dict:
    """Сериализует информацию о пользователе для хранения и сравнения."""
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "bio": getattr(user, 'about', None),
        "photo_id": user.photo.photo_id if user.photo else None,
        "username": user.username,
        "premium": getattr(user, 'premium', False)
    }

async def check_user_changes(client, chat_id):
    """Проверяет изменения профилей участников чата и уведомляет об изменениях."""
    if chat_id not in monitored_chats:
        return

    for user_id, old_info in monitored_chats[chat_id].items():
        try:
            user = await client.get_entity(user_id)
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {user_id}: {e}")
            continue

        current_info = serialize_user(user)
        changes = {}
        for field in ["first_name", "last_name", "bio", "photo_id", "username", "premium"]:
            old = old_info.get(field)
            new = current_info.get(field)
            if new != old:
                changes[field] = (old, new)

        if not changes:
            continue

        # Запись в историю изменений
        history_col.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "changes": changes,
            "timestamp": time.time()
        })
        # Обновление сохранённого состояния
        monitored_chats[chat_id][user_id] = current_info

        change_msgs = []
        username_changed = False
        for field, (old, new) in changes.items():
            if field == "photo_id":
                change_msgs.append("сменил аватарку")
            elif field == "first_name":
                change_msgs.append("сменил имя")
            elif field == "last_name":
                change_msgs.append("сменил фамилию")
            elif field == "bio":
                change_msgs.append("сменил био")
            elif field == "username":
                change_msgs.append("сменил юзернейм")
                username_changed = True
            elif field == "premium" and new:
                congrats_msg = f"О, этот мамонт повёлся на скам телеги. Держи значок, что ты дурачок: [Пользователь](tg://user?id={user_id})"
                try:
                    await client.send_message(chat_id, congrats_msg, parse_mode='markdown')
                except Exception as e:
                    logger.error(f"Ошибка отправки премиум уведомления: {e}")
            else:
                change_msgs.append(f"сменил {field} с «{old}» на «{new}»")

        # Специальное уведомление при смене юзернейма
        if username_changed:
            change_msgs.append("Как же вы задолбали менять юзернеймы. Искать вас заебёшься")

        user_mention = f"[{current_info.get('first_name') or 'Юзер'}](tg://user?id={user_id})"
        notification = f"О, а этот поц {user_mention} {', '.join(change_msgs)}."
        try:
            await client.send_message(chat_id, notification, parse_mode='markdown')
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в чат {chat_id}: {e}")

async def periodic_check(client):
    """Периодическая проверка изменений профилей в мониторируемых чатах."""
    logger.info("Запущена периодическая проверка профилей.")
    while True:
        for chat_id in list(monitored_chats.keys()):
            state = states_col.find_one({"chat_id": chat_id})
            if not state or not state.get("is_monitoring"):
                monitored_chats.pop(chat_id, None)
                continue
            await check_user_changes(client, chat_id)
        await asyncio.sleep(10)

def init(client):
    register_help("profile_tracker", {
        "Джанки, мониторим чат": "Запускает мониторинг профилей участников чата (только для AUTHORIZED_USERS).",
        "Джанки, перестань мониторить чат": "Останавливает мониторинг чата (только для AUTHORIZED_USERS)."
    })

    client.loop.create_task(periodic_check(client))

    @client.on(events.NewMessage(pattern=MONITOR_COMMAND))
    async def monitor_chat_handler(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply("Нет прав для запуска мониторинга.")
            return

        chat_id = event.chat_id
        if not chat_id:
            await event.reply("Ошибка определения чата.")
            return

        try:
            participants = await client.get_participants(chat_id)
        except Exception as e:
            logger.error(f"Ошибка получения участников чата {chat_id}: {e}")
            await event.reply("Не удалось получить участников чата.")
            return

        user_info = {}
        for user in participants:
            if isinstance(user, types.User):
                user_info[user.id] = serialize_user(user)

        monitored_chats[chat_id] = user_info

        states_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"is_monitoring": True, "started_at": time.time()}},
            upsert=True
        )

        await event.reply("Сейчас я буду сохранять ВСЕ ПРОФИЛИ ψ(｀∇´)ψ.")

    @client.on(events.NewMessage(pattern=STOP_MONITOR_COMMAND))
    async def stop_monitoring_handler(event):
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply("Нет прав для остановки мониторинга.")
            return

        chat_id = event.chat_id
        states_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"is_monitoring": False}},
            upsert=True
        )
        monitored_chats.pop(chat_id, None)
        await event.reply("Мониторинг чата остановлен.")

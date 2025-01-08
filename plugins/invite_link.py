import re
import logging
import os
import time
from telethon import events, functions
from telethon.errors import (
    ChatAdminRequiredError,
    RPCError,
    ChatWriteForbiddenError
)
from pymongo import MongoClient

from utils.config import LOGCHANNEL, MONGODB_URI, DB_NAME
from utils.misc import register_help

logger = logging.getLogger(__name__)

def init(client):
    register_help("invite_link", {
        "Джанки, ссылку": "Создаёт одноразовую ссылку-приглашение и отправляет её в личные сообщения."
    })
    
    # Подключение к MongoDB через настройки из vars.yaml
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    active_invites_col = db['active_invites']
    
    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*ссылку\s*$")))
    async def create_invite_link(event):
        sender_id = event.sender_id
        chat = await event.get_chat()
        
        try:
            participant = await client(functions.channels.GetParticipantRequest(
                channel=chat,
                participant='me'
            ))
            permissions = participant.participant.admin_rights
            if not (permissions and permissions.invite_users):
                await event.reply("У меня нет прав администратора с возможностью приглашать пользователей.")
                logger.warning(f"Боту не хватает прав для создания приглашений в чате {chat.id}.")
                return
        except ChatAdminRequiredError:
            await event.reply("Бот не является администратором этого чата.")
            logger.error(f"ChatAdminRequiredError в чате {chat.id}.")
            return
        except RPCError as e:
            await event.reply("Ошибка при получении прав администратора.")
            logger.error(f"RPCError: {e}")
            return
        except Exception as e:
            await event.reply("Неизвестная ошибка при проверке прав.")
            logger.error(f"Ошибка: {e}")
            return
        
        try:
            invite = await client(functions.messages.ExportChatInviteRequest(
                peer=chat,
                expire_date=None,
                usage_limit=1
            ))
            invite_link = invite.link
            logger.info(f"Создано приглашение: {invite_link}")
        except Exception as e:
            await event.reply("Ошибка при создании приглашения.")
            logger.error(f"Ошибка создания приглашения: {e}")
            return
        
        active_invites_col.insert_one({
            "invite_link": invite_link,
            "requester_id": sender_id,
            "chat_id": chat.id,
            "created_at": time.time()
        })
        logger.debug(f"Сохранено активное приглашение: {invite_link}")
        
        try:
            user = await client.get_entity(sender_id)
            await client.send_message(user, f"Вот ваша одноразовая ссылка-приглашение: {invite_link}")
            await event.reply(f"Ну что, {user.first_name}, вот твоя волшебная ссылка. Надеюсь, ты её не потеряешь... снова.")
            logger.info(f"Ссылка отправлена пользователю {sender_id}")
        except ChatWriteForbiddenError:
            await event.reply("Не удалось отправить ссылку в личные сообщения. Похоже, ты решил, что я не заслуживаю твоего внимания.")
            logger.error(f"ChatWriteForbiddenError при отправке пользователю {sender_id}.")
            return
        except RPCError as e:
            await event.reply("Не удалось отправить ссылку. Видимо, у меня сегодня неудачный день.")
            logger.error(f"RPCError: {e}")
            return
        except Exception as e:
            await event.reply("Что-то пошло не так. Попробуйте ещё раз.")
            logger.error(f"Неизвестная ошибка: {e}")
            return
        
        if LOGCHANNEL:
            try:
                requester = await client.get_entity(sender_id)
                log_msg = (
                    f"📨 **Запрос ссылки-приглашения**\n"
                    f"Пользователь [{requester.first_name}](tg://user?id={sender_id}) "
                    f"создал одноразовую ссылку-приглашение в чат [{chat.title}](https://t.me/c/{abs(chat.id)}/)."
                )
                await client.send_message(LOGCHANNEL, log_msg, link_preview=False)
                logger.info(f"Логировано создание ссылки {invite_link}")
            except Exception as e:
                logger.error(f"Ошибка логирования: {e}")
    
    @client.on(events.ChatAction)
    async def handle_new_join(event):
        if not event.user_added or not event.user_id:
            return
        
        logger.debug(f"Новое присоединение: пользователь {event.user_id} в чат {event.chat_id}")
        
        active_invite = active_invites_col.find_one({"chat_id": event.chat_id})
        if active_invite:
            used_invite = active_invite["invite_link"]
            requester_id = active_invite["requester_id"]
            try:
                new_user = await client.get_entity(event.user_id)
                requester = await client.get_entity(requester_id)
                log_msg = (
                    f"✅ **Ссылка использована и требует подтверждения**\n"
                    f"Пользователь [{new_user.first_name}](tg://user?id={event.user_id}) "
                    f"попытался присоединиться к чату [{event.chat.title}](https://t.me/c/{abs(event.chat.id)}/) "
                    f"по ссылке, созданной [{requester.first_name}](tg://user?id={requester_id})."
                )
                await client.send_message(LOGCHANNEL, log_msg, link_preview=False)
                logger.info(f"Ссылка {used_invite} использована пользователем {event.user_id}")
                
                await client(functions.messages.DeleteChatInviteRequest(
                    peer=event.chat_id,
                    link=used_invite
                ))
                logger.info(f"Ссылка {used_invite} удалена после использования")
            except Exception as e:
                logger.error(f"Ошибка при обработке использования ссылки: {e}")
            
            active_invites_col.delete_one({"invite_link": used_invite})
            logger.debug(f"Ссылка {used_invite} удалена из базы данных")
        else:
            logger.warning(f"Активная ссылка для чата {event.chat_id} не найдена")

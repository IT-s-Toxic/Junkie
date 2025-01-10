import logging
import os
import re
import time
import io
import base64
import requests
from PIL import Image
from pymongo import MongoClient
from telethon import events, errors, functions, types

# Предполагается, что эти переменные/константы вы где-то храните:
#   MONGODB_URI, DB_NAME, AUTHORIZED_USERS, etc.
#   а также register_help из utils.misc
from utils.config import MONGODB_URI, DB_NAME, AUTHORIZED_USERS
from utils.misc import register_help

logger = logging.getLogger(__name__)

# ------------------- Регэкспы команд -------------------
CREATE_PACK_PATTERN = re.compile(r"(?i)^джанки,\s*создай\s+стикерпак\s*$")
STICKER_CMD_PATTERN = re.compile(r"(?i)^джанки,\s*в\s+стикеры\s*$")
ALL_STICKERS_PATTERN = re.compile(r"(?i)^джанки,\s*все\s+стикеры\s*$")
DELETE_STICKER_PATTERN = re.compile(r"(?i)^джанки,\s*удали\s+стикер\s*$")

# ------------------- Константы ------------------------
MAX_STICKERS_PER_PACK = 120
BASE_DIR = "/root/JunkyUBot"
IMAGES_DIR = os.path.join(BASE_DIR, "images")
STICKER_LOGO_PATH = os.path.join(IMAGES_DIR, "stickerlogo.png")
QUOTES_API_URL = "https://quotes.fl1yd.su/generate"

def init(client):
    """
    Плагин для управления стикерами и генерации цитат:
      - «Джанки, создай стикерпак» (AUTHORIZED_USERS)
      - «Джанки, в стикеры»
      - «Джанки, все стикеры»
      - «Джанки, удали стикер» (AUTHORIZED_USERS)

    Использует MongoDB для хранения/обновления данных о стикерпаке.
    """

    # Регистрируем подсказки (help)
    register_help("sticker_quotes", {
        "Джанки, создай стикерпак": "Создает новый стикерпак (если предыдущие заполнены). Только AUTHORIZED_USERS.",
        "Джанки, в стикеры": "Генерирует цитату через сервис и добавляет стикер в незаполненный пак.",
        "Джанки, все стикеры": "Выводит список всех созданных пакетов.",
        "Джанки, удали стикер": "Удаляет реплайнутый стикер из пака. Только AUTHORIZED_USERS."
    })

    # Подключаемся к Mongo
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    packs_col = db["sticker_packs"]

    @client.on(events.NewMessage(pattern=CREATE_PACK_PATTERN))
    async def create_sticker_pack_handler(event):
        """
        «Джанки, создай стикерпак» — создаём новый пак, если все заполнены.
        1) stickerlogo.png => подгоняем до 512×512 => PNG
        2) /newpack + title + файл + эмодзи + /publish + /skip + short_name
        """
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply("У тебя нет прав для создания нового стикерпакa.")
            return

        existing = packs_col.find_one({"sticker_count": {"$lt": MAX_STICKERS_PER_PACK}})
        if existing:
            left = MAX_STICKERS_PER_PACK - existing["sticker_count"]
            await event.reply(f"Уже есть незаполненный пак. Осталось {left} слотов.")
            return

        next_num = packs_col.count_documents({}) + 1
        title = f"GPL 3.0 IT's Toxic {next_num}"
        short_name = f"itstoxicgpl3_{next_num}"

        if not os.path.isfile(STICKER_LOGO_PATH):
            await event.reply("Не найден stickerlogo.png в /images/.")
            logger.error("Нет stickerlogo.png => прервали создание")
            return

        try:
            with open(STICKER_LOGO_PATH, "rb") as f:
                logo_data = f.read()
            logo_io = io.BytesIO(logo_data)
            logo_io.name = "logo.png"
        except Exception as e:
            logger.error(f"Ошибка чтения stickerlogo.png: {e}")
            await event.reply("Ошибка при чтении stickerlogo.png")
            return

        # fit до 512×512, формат PNG
        logo_ok = fit_sticker_size(logo_io, out_format="PNG", max_size=512)
        if not check_sticker_valid(logo_ok):
            await event.reply("Файл stickerlogo не подходит (PNG/WebP ≤512×512).")
            return

        try:
            await client(functions.contacts.UnblockRequest(id="@Stickers"))
            async with client.conversation("@Stickers") as conv:
                await conv.send_message("/newpack")
                await conv.get_response(timeout=30)

                await conv.send_message(title)
                await conv.get_response(timeout=30)

                await conv.send_file(logo_ok, force_document=True)
                await conv.get_response(timeout=30)

                # Эмодзи
                await conv.send_message("🤔")
                await conv.get_response(timeout=30)

                # /publish
                await conv.send_message("/publish")
                await conv.get_response(timeout=30)

                # /skip
                await conv.send_message("/skip")
                await conv.get_response(timeout=30)

                # short_name
                await conv.send_message(short_name)
                await conv.get_response(timeout=30)

            packs_col.insert_one({
                "title": title,
                "short_name": short_name,
                "sticker_count": 1,
                "created_at": time.time()
            })

            await event.reply(
                f"Создан стикерпак: [{title}](https://t.me/addstickers/{short_name})",
                parse_mode="md"
            )
            logger.info(f"New sticker pack created: short_name={short_name}")
        except errors.RPCError as e:
            logger.error(f"RPCError: {e}")
            await stickers_cancel(client)
            await event.reply(f"Ошибка RPC: {e}")
        except Exception as e:
            logger.error(f"Exception: {e}")
            await stickers_cancel(client)
            await event.reply(f"Ошибка при создании стикерпакa: {e}")

    @client.on(events.NewMessage(pattern=STICKER_CMD_PATTERN))
    async def sticker_quote_handler(event):
        """
        «Джанки, в стикеры»:
          - ищем незаполненный pack
          - генерируем цитату (quotes.fl1yd.su/generate)
          - fit 512x512 => WEBP
          - /addsticker, /done
        """
        if not event.is_reply:
            await event.reply("Ответь на сообщение, которое нужно сделать стикером.")
            return

        pack = packs_col.find_one({"sticker_count": {"$lt": MAX_STICKERS_PER_PACK}},
                                  sort=[("created_at", 1)])
        if not pack:
            await event.reply("Нет незаполненных пакетов. Сначала создай новый.")
            return

        short_name = pack["short_name"]
        title = pack["title"]

        reply_msg = await event.get_reply_message()

        try:
            payload = await make_quote_payload(reply_msg, event.client)
            r = requests.post(QUOTES_API_URL, json=payload, timeout=15)
            if r.status_code != 200:
                await event.reply(f"Quotes API error {r.status_code}\n{r.text}")
                return
            raw_bytes = r.content
            if not raw_bytes:
                await event.reply("Пустой ответ от цитат-сервиса.")
                return
        except requests.exceptions.RequestException as ex:
            logger.error(f"Requests error: {ex}")
            await event.reply(f"Ошибка при обращении к сервису цитат: {ex}")
            return
        except Exception as ex:
            logger.error(f"Exception on make_quote: {ex}")
            await event.reply(f"Ошибка при подготовке JSON/аватара: {ex}")
            return

        try:
            img = Image.open(io.BytesIO(raw_bytes))
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            w, h = img.size
            if w > 512 or h > 512:
                ratio = min(512 / w, 512 / h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)

            out_path = "temp_sticker.webp"
            img.save(out_path, format="WEBP")
        except Exception as e:
            logger.error(f"PIL error: {e}")
            await event.reply("Ошибка при конвертации изображения.")
            return

        try:
            await client(functions.contacts.UnblockRequest(id="@Stickers"))
            async with client.conversation("@Stickers") as conv:
                await conv.send_message("/addsticker")
                await conv.get_response(timeout=20)

                await conv.send_message(short_name)
                r2 = await conv.get_response(timeout=20)
                if ("not find" in r2.text.lower()) or ("no sticker set" in r2.text.lower()):
                    await event.reply("Стикерпак не найден. Убедитесь, что он создан.")
                    return

                with open(out_path, "rb") as f_st:
                    await conv.send_file(f_st, force_document=True,
                                         file_name="quote.webp",
                                         mime_type="image/webp")

                r3 = await conv.get_response(timeout=20)
                if "invalid file type" in r3.text.lower():
                    await event.reply("Telegram отверг файл (ожидали PNG/WebP?).")
                    await stickers_cancel(client)
                    return

                # Эмодзи
                await conv.send_message("🤔")
                await conv.get_response(timeout=20)

                # /done
                await conv.send_message("/done")
                await conv.get_response(timeout=20)

            packs_col.update_one({"short_name": short_name},
                                 {"$inc": {"sticker_count": 1}})
            await event.reply(
                f"Стикер добавлен в [{title}](https://t.me/addstickers/{short_name})",
                parse_mode="md"
            )
            logger.info(f"Sticker added to {short_name}")
        except errors.RPCError as e:
            logger.error(f"[sticker_quote_handler] RPCError: {e}")
            await stickers_cancel(client)
            await event.reply(f"Ошибка RPC: {e}")
        except Exception as e:
            logger.error(f"[sticker_quote_handler] Ex: {e}")
            await stickers_cancel(client)
            await event.reply(f"Ошибка при добавлении стикера: {e}")
        finally:
            if os.path.exists("temp_sticker.webp"):
                os.remove("temp_sticker.webp")

    @client.on(events.NewMessage(pattern=ALL_STICKERS_PATTERN))
    async def list_all_sticker_packs(event):
        """«Джанки, все стикеры» — показываем список пакетов."""
        packs = list(packs_col.find({}))
        if not packs:
            await event.reply("Пока нет созданных стикерпаков.")
            return

        lines = ["**Список всех стикерпаков:**"]
        for p in packs:
            t = p.get("title", "NoTitle")
            sn = p.get("short_name", "???")
            sc = p.get("sticker_count", 0)
            link = f"https://t.me/addstickers/{sn}"
            lines.append(f"• [{t}]({link}) [{sc}/{MAX_STICKERS_PER_PACK}]")

        await event.reply("\n".join(lines), parse_mode="md")

    # --- Удаление стикера ---
    @client.on(events.NewMessage(pattern=DELETE_STICKER_PATTERN))
    async def delete_sticker_handler(event):
        """
        «Джанки, удали стикер» (только для AUTHORIZED_USERS)
          - Проверяем, что реплай на стикер
          - Извлекаем short_name через атрибуты или GetStickerSetRequest
          - /delsticker -> отправляем файл -> /done
          - sticker_count -= 1
        """
        if event.sender_id not in AUTHORIZED_USERS:
            await event.reply("Нет прав для удаления стикера.")
            return

        if not event.is_reply:
            await event.reply("Ответьте на сообщение со стикером, который нужно удалить.")
            return

        msg_st = await event.get_reply_message()
        if not (msg_st and msg_st.document and msg_st.sticker):
            await event.reply("Это не стикер. Нечего удалять.")
            return

        short_n = None
        for attr in msg_st.document.attributes:
            if isinstance(attr, types.DocumentAttributeSticker):
                # A) короткое имя есть напрямую
                if hasattr(attr.stickerset, "short_name") and attr.stickerset.short_name:
                    short_n = attr.stickerset.short_name
                    break

                # B) через ID + access_hash
                if isinstance(attr.stickerset, types.InputStickerSetID):
                    try:
                        # hash обязателен => указываем 0
                        r = await event.client(functions.messages.GetStickerSetRequest(
                            stickerset=types.InputStickerSetID(
                                id=attr.stickerset.id,
                                access_hash=attr.stickerset.access_hash
                            ),
                            hash=0  # <-- важно, иначе ошибка
                        ))
                        short_n = r.set.short_name
                    except errors.RPCError as erpc:
                        await event.reply(f"Ошибка RPC при получении short_name: {erpc}")
                        return
                    except Exception as e2:
                        await event.reply(f"Не удалось извлечь short_name: {e2}")
                        return

                if short_n:
                    break

        if not short_n:
            await event.reply("Не удалось определить short_name стикерпака.")
            return

        try:
            await event.client(functions.contacts.UnblockRequest(id="@Stickers"))
            async with event.client.conversation("@Stickers") as conv:
                await conv.send_message("/delsticker")
                await conv.get_response(timeout=20)

                await conv.send_file(msg_st.document, force_document=True)
                resp_del = await conv.get_response(timeout=20)
                if "sticker not found" in resp_del.text.lower():
                    await event.reply("Стикер не найден (возможно уже удалён).")
                    return

                # /done
                await conv.send_message("/done")
                await conv.get_response(timeout=20)

            # Уменьшаем счётчик
            result = packs_col.update_one(
                {"short_name": short_n, "sticker_count": {"$gt": 0}},
                {"$inc": {"sticker_count": -1}}
            )
            if result.modified_count:
                await event.reply("Стикер успешно удалён, счётчик уменьшен.")
            else:
                await event.reply("Стикер удалён, но счётчик в базе не удалось уменьшить.")
        except errors.RPCError as e:
            logger.error(f"[delete_sticker_handler] RPCError: {e}")
            await stickers_cancel(event.client)
            await event.reply(f"Ошибка RPC: {e}")
        except Exception as e:
            logger.error(f"[delete_sticker_handler] Ex: {e}")
            await stickers_cancel(event.client)
            await event.reply(f"Ошибка при удалении стикера: {e}")


# ---------------- Вспомогательные функции ----------------

async def stickers_cancel(client):
    """ /cancel боту @Stickers, на случай ошибки. """
    try:
        async with client.conversation("@Stickers") as conv:
            await conv.send_message("/cancel")
            await conv.get_response(timeout=10)
    except:
        pass

def check_sticker_valid(file_like: io.BytesIO) -> bool:
    """
    Проверяем, что (PNG или WEBP) и размер <=512×512
    """
    file_like.seek(0)
    try:
        im = Image.open(file_like)
    except:
        return False

    w, h = im.size
    if w > 512 or h > 512:
        return False
    if im.format not in ("PNG", "WEBP"):
        return False
    return True

def fit_sticker_size(input_file: io.BytesIO, out_format="PNG", max_size=512) -> io.BytesIO:
    """
    Конвертируем в RGBA, сжимаем <= max_size, сохраняем в out_format (PNG/WEBP).
    Возвращаем BytesIO.
    """
    input_file.seek(0)
    im = Image.open(input_file)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    w, h = im.size
    if w > max_size or h > max_size:
        ratio = min(max_size / w, max_size / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        im = im.resize((new_w, new_h), Image.LANCZOS)

    out_buf = io.BytesIO()
    im.save(out_buf, format=out_format)
    out_buf.name = f"sticker.{out_format.lower()}"
    out_buf.seek(0)
    return out_buf

async def make_quote_payload(msg: types.Message, client) -> dict:
    """
    Генерируем JSON для https://quotes.fl1yd.su/generate
    При наличии аватарки — кодируем base64 (avatar).
    """
    user_id = msg.sender_id or 0
    user_name = "Anon"
    if msg.sender:
        fn = msg.sender.first_name or ""
        ln = msg.sender.last_name or ""
        user_name = (fn + " " + ln).strip() or "Anon"

    # Загружаем аватарку
    avatar_b64 = ""
    try:
        if msg.sender and msg.sender.photo:
            photo_bytes = await client.download_profile_photo(msg.sender, file=bytes)
            if photo_bytes:
                avatar_b64 = base64.b64encode(photo_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"Не удалось получить аватар {msg.sender_id}: {e}")

    text_str = msg.raw_text or "..."

    # РЕПЛАЙ
    reply_dict = {"id": 0, "name": "", "text": ""}
    if msg.is_reply and msg.reply_to_msg_id:
        try:
            rep_msg = await msg.get_reply_message()
            if rep_msg:
                rid = rep_msg.sender_id or 0
                rname = "Anon"
                if rep_msg.sender:
                    fn2 = rep_msg.sender.first_name or ""
                    ln2 = rep_msg.sender.last_name or ""
                    rname = (fn2 + " " + ln2).strip() or "Anon"
                rtext = rep_msg.raw_text or "..."
                reply_dict = {
                    "id": rid,
                    "name": rname,
                    "text": rtext
                }
        except:
            pass

    return {
        "messages": [
            {
                "text": text_str,
                "media": "",
                "entities": [],
                "author": {
                    "id": user_id,
                    "name": user_name,
                    "avatar": avatar_b64,
                    "rank": "",
                    "via_bot": ""
                },
                "reply": reply_dict
            }
        ],
        "quote_color": "#162330",
        "text_color": "#fff"
    }

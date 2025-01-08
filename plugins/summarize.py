import re
import time
import asyncio
import contextlib
import logging
from telethon import events

from utils.config import OLLAMA_HOST, SUMMARY_MODEL
from utils.misc import register_help, summaries_list

try:
    from ollama import Client as OllamaClient
except ImportError:
    OllamaClient = None

logger = logging.getLogger(__name__)

MAX_RESPONSE_LENGTH = 4096
last_request_time = {}  # {chat_id: timestamp последней суммаризации}

def init(client):
    if not OllamaClient:
        logger.warning("ollama не установлен, плагин summarize будет работать в режиме заглушки.")

    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*суммаризируй\s+(\d+)\s+сообщений\s*$")))
    async def summarize_handler(event):
        match = event.pattern_match
        if not match:
            return

        n = int(match.group(1))
        now = time.time()
        cid = event.chat_id

        # Проверяем лимит 10 минут
        if cid in last_request_time:
            elapsed = now - last_request_time[cid]
            if elapsed < 600:
                remain = int(600 - elapsed)  # остаток в секундах
                mm, ss = divmod(remain, 60)
                remain_str = f"{mm} мин. {ss} сек." if mm else f"{ss} сек."
                await event.reply(f"Слишком часто! Подожди ещё {remain_str} прежде чем делать новую суммаризацию.")
                return

        last_request_time[cid] = now

        if n > 100000:
            await event.reply("Слишком много (макс. 100000).")
            return

        # Собираем последние n сообщений
        msgs_text = []
        async for m in client.iter_messages(cid, limit=n):
            if m.text:
                msgs_text.append(m.text)

        typing_task = asyncio.create_task(_fake_typing(cid, client))

        try:
            summary = await _do_summarize(msgs_text)
        finally:
            typing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await typing_task

        if len(summary) > MAX_RESPONSE_LENGTH:
            summary = summary[:MAX_RESPONSE_LENGTH]

        # Логируем в histories
        summaries_list.append({
            "time": now,
            "chat_id": cid,
            "num": n,
            "summary": summary[:500]  # храним первые 500 символов
        })

        await event.reply(f"Суммаризация последних {n} сообщений:\n{summary}")

    register_help("summarize", {
        "Джанки, суммаризируй N сообщений": (
            "Суммирует последние N сообщений (макс 100000, не чаще чем раз в 10 минут)."
        )
    })

async def _do_summarize(msgs):
    """
    Вызывает Ollama, если возможно, иначе — заглушка.
    Промпт заменён на указанный:
    """
    if not OllamaClient:
        return "ollama не установлен, поэтому заглушка суммаризации."

    combined_text = "\n".join(msgs)
    prompt = (
        "Вы — продвинутая языковая модель. Ваша задача — прочитать приведённый ниже текст на русском языке "
        "и сформировать из него краткую, понятную суммаризацию. Обратите внимание на ключевые идеи, факты и основные детали. "
        "Не добавляйте домыслов и не искажайте содержание.\n\n"
        "Вот текст для суммирования:\n\n"
        f"{combined_text}\n\n"
        "Требуется краткое резюме (не более 300 слов), в котором будут выделены главные аспекты и суть текста, "
        "написанное на естественном русском языке. Если какие-то детали не нужны для понимания сути, опустите их. "
        f"Также не превышайте {MAX_RESPONSE_LENGTH} символов."
    )

    ollama_client = OllamaClient(host=OLLAMA_HOST)
    try:
        response = ollama_client.chat(model=SUMMARY_MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]
    except Exception as e:
        logger.error(f"Ошибка при запросе к Ollama: {e}")
        return f"Ошибка при суммаризации: {e}"

async def _fake_typing(chat_id, client):
    # Заменяем "typing" заглушкой
    while True:
        await asyncio.sleep(4)

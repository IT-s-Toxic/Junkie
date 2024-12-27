import re
import asyncio
import contextlib
import logging
import time
import os
import yaml
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
from utils.misc import modules_help
from ollama import Client as OllamaClient

# Путь к директории, в которой находится текущий модуль
current_dir = os.path.dirname(__file__)

# Загружаем настройки из vars.yaml
vars_file_path = os.path.join(current_dir, "vars.yaml")
with open(vars_file_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

OLLAMA_HOST = config.get("ollama_host", "http://127.0.0.1:11434")
MODEL_NAME = config.get("summary_model", "llama3")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройка Ollama клиента с указанием хоста, берём из vars.yaml
ollama_client = OllamaClient(
    host=OLLAMA_HOST,
    headers={'Content-Type': 'application/json; charset=utf-8'}
)

# Максимальная длина ответа в символах
MAX_RESPONSE_LENGTH = 4096

# Глобальный словарь для хранения времени последнего запроса (по chat_id)
last_request_time = {}

# Функция для суммирования сообщений с использованием Ollama API
async def summarize_messages(messages):
    # Объединяем текст сообщений
    combined_text = "\n".join([msg.text for msg in messages if msg.text])

    # Формируем инструкцию
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

    # Данные для запроса к модели
    request_data = [
        {"role": "user", "content": prompt}
    ]

    # Отправляем запрос к модели Ollama
    try:
        logger.info("Отправка запроса к Ollama: %s (модель=%s)", OLLAMA_HOST, MODEL_NAME)
        response = ollama_client.chat(model=MODEL_NAME, messages=request_data)
        logger.info("Получен ответ от Ollama: %s", response)
        return response['message']['content']
    except Exception as e:
        logger.error("Ошибка при выполнении запроса: %s", e)
        return f"Ошибка при выполнении запроса: {e}"

# Функция для периодической отправки действия "набор текста"
async def send_typing_action(client, chat_id):
    while True:
        await client.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(4)  # Отправляем действие каждые 4 секунды

# Обработчик команды для суммирования сообщений
@Client.on_message(filters.regex(r"Джанки, суммаризируй (\d+) сообщений"))
async def summarize_command(client: Client, message: Message):
    chat_id = message.chat.id
    now = time.time()

    # Проверяем, когда был последний запрос
    if chat_id in last_request_time:
        elapsed = now - last_request_time[chat_id]
        if elapsed < 600:  # 600 секунд = 10 минут
            # Если прошло меньше 10 минут, ругаемся и выходим
            await message.reply("Воу, давай притормози")
            return

    # Запоминаем текущее время как последнее обращение
    last_request_time[chat_id] = now

    match = re.match(r"Джанки, суммаризируй (\d+) сообщений", message.text)
    if match:
        num_messages = int(match.group(1))

        # Проверяем ограничение на кол-во сообщений
        if num_messages > 100000:
            await message.reply("Сорян, но я охренею это всё говно листать")
            return

        # Получаем предыдущие сообщения
        messages_list = []
        async for msg in client.get_chat_history(chat_id, limit=num_messages):
            messages_list.append(msg)

        # Запускаем индикацию "набор текста" в отдельной задаче
        typing_task = asyncio.create_task(send_typing_action(client, chat_id))

        # Суммируем сообщения
        try:
            logger.info("Начало суммирования %d сообщений", num_messages)
            summary = await summarize_messages(messages_list)
        finally:
            # Останавливаем индикацию "набор текста"
            typing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await typing_task

        # Ограничиваем длину ответа при необходимости
        if len(summary) > MAX_RESPONSE_LENGTH:
            summary = summary[:MAX_RESPONSE_LENGTH]

        # Отправляем результат
        logger.info("Отправка результата в чат")
        await message.reply(
            f"Суммаризация последних {num_messages} сообщений:\n{summary}",
            reply_to_message_id=message.id
        )

# Добавляем инструкции для модуля
modules_help["summarize"] = {
    "Джанки, суммаризируй N сообщений": (
        "Суммирует последние N сообщений в чате.\n"
        "Ограничение: не более 100000 сообщений\n"
        "Лимит: один запрос в 10 минут.\n"
        f"Читает настройки модели и хоста из vars.yaml: (host={OLLAMA_HOST}, model={MODEL_NAME})."
    )
}

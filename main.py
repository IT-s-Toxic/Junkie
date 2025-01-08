import asyncio
import logging
import sys
import uvicorn

from telethon import TelegramClient
from utils.config import API_ID, API_HASH
from utils.loader import load_plugins
from web_admin import app as fastapi_app, init_web_admin

SESSION_NAME = "telethon_userbot"
SESSION_FILE = f"{SESSION_NAME}.session"
LOG_FILE = "logs/telethon_userbot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Main")

client: TelegramClient = None

async def start_telethon():
    global client
    client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
    await client.start()
    logger.info("Telethon userbot запущен.")

    # Загружаем плагины
    loaded, failed = load_plugins(client)
    logger.info(f"Загружено {loaded} плагинов, ошибка в {failed}.")
    
    # Инициализируем веб-админку
    init_web_admin(client)

    # Телеграм-клиент ждёт отключения
    await client.run_until_disconnected()

async def run_all():
    telethon_task = asyncio.create_task(start_telethon())

    # Запускаем FastAPI на 0.0.0.0:8000
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    fastapi_task = asyncio.create_task(server.serve())

    await asyncio.gather(telethon_task, fastapi_task)

if __name__ == "__main__":
    asyncio.run(run_all())

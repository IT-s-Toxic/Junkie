import os
import re
import yaml
import logging
import base64
import io
import requests
from PIL import Image
from pymongo import MongoClient
from telethon import events, errors, functions, types
import yandex_music

from utils.misc import register_help

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "/root/JunkyUBot/downloads"
VARS_FILE = "/root/JunkyUBot/vars.yaml"

# Загрузка конфигурации из vars.yaml
with open(VARS_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
YANDEX_TOKEN = config.get("yandex_music_token")

SEARCH_PATTERN = re.compile(r"(?i)^джанки,\s*найди\s+трек:\s*(.+)$")

def get_yandex_client():
    ym_client = yandex_music.Client(token=YANDEX_TOKEN)
    ym_client.init()
    return ym_client

def init(client):
    register_help("yandex_music", {
        "Джанки, найди трек: {название}": "Ищет и отправляет трек с Яндекс.Музыки."
    })

    @client.on(events.NewMessage(pattern=SEARCH_PATTERN))
    async def yandex_music_search_handler(event):
        query_match = SEARCH_PATTERN.search(event.raw_text)
        if not query_match:
            await event.reply("Неправильный формат команды. Используйте: Джанки, найди трек: {название}")
            return

        query = query_match.group(1).strip()
        if not query:
            await event.reply("Укакажи название трека после команды.")
            return

        await event.reply(f"Ищу трек «{query}» на Яндекс.Музыке...")

        try:
            ym_client = get_yandex_client()
            results = ym_client.search(text=query, type_='track')
        except Exception as e:
            logger.error(f"Ошибка при поиске трека: {e}")
            await event.reply("Я не смог ничего найти по твоему запросу, сорян.")
            return

        if not results or not results.tracks or not results.tracks.results:
            await event.reply("Не удалось найти трек.")
            return

        try:
            track = results.tracks.results[0]
            track_obj = ym_client.tracks(track.id)[0]
        except Exception as e:
            logger.error(f"Ошибка при получении трека: {e}")
            await event.reply("Произошла ошибка при получении трека.")
            return

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        file_path = os.path.join(DOWNLOAD_DIR, f"{track_obj.title}.mp3")

        try:
            track_obj.download(filename=file_path)
        except Exception as e:
            logger.error(f"Ошибка при скачивании трека: {e}")
            await event.reply("Произошла ошибка при скачивании трека.")
            return

        caption = f"Вот твой трек: {track_obj.title} - {track_obj.artists[0].name}"
        try:
            await client.send_file(event.chat_id, file_path, caption=caption, reply_to=event.id)
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Ошибка при отправке трека: {e}")
            await event.reply("Произошла ошибка при отправке трека.")

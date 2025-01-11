import os
import time
import base64
import asyncio
import qrcode
import logging
from io import BytesIO
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from utils.config import AUTHORIZED_USERS
from utils.misc import summaries_list

logger = logging.getLogger("WebAdmin")

app = FastAPI(title="Junky Userbot Admin panel", version="1.0.0")
security = HTTPBasic()

client: TelegramClient = None  # Пробросим из main.py

def init_web_admin(telethon_client: TelegramClient):
    global client
    client = telethon_client

def check_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Примитивная BasicAuth: username= user_id (число), password=anything
    """
    try:
        user_id = int(credentials.username)
    except:
        raise HTTPException(status_code=401, detail="Username должен быть числом (ID Telegram).")
    if user_id not in AUTHORIZED_USERS:
        raise HTTPException(status_code=403, detail="Нет прав доступа.")
    return True

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body style="background:#ffffff; color:#000;">
    <h1>TelethonUserbot</h1>
    <p>/admin — панель</p>
    </body></html>
    """

@app.get("/admin", response_class=HTMLResponse)
def admin_main(authorized: bool = Depends(check_admin)):
    return """
    <html><body style="background:#f0f8ff; color:#000;">
    <h2>Админ-панель</h2>
    <ul>
      <li><a href="/admin/qr_login" target="_blank">QR-логин</a></li>
      <li><a href="/admin/stats">Статистика</a></li>
      <li><a href="/admin/log">Лог</a></li>
      <li><a href="/admin/summaries">Суммаризации</a></li>
    </ul>
    </body></html>
    """

@app.get("/admin/qr_login", response_class=HTMLResponse)
async def admin_qr_login(authorized: bool = Depends(check_admin)):
    if not client:
        return "<html><body><h2>Клиент не инициализирован!</h2></body></html>"

    qr_login = await client.qr_login()
    qr_bytes = qr_login.qr_code
    qr_img = qrcode.make(qr_bytes)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    buf.close()

    async def wait_qr():
        logger.info("Ожидание QR-логина...")
        await qr_login.wait()
        logger.info("Успешно залогинились по QR!")

    asyncio.create_task(wait_qr())

    return f"""
    <html><body style="background:#f0f8ff;">
    <h3>Сканируйте QR в Telegram</h3>
    <img src="data:image/png;base64,{b64}" alt="QR" />
    <p>После сканирования — userbot залогинится.</p>
    </body></html>
    """

@app.get("/admin/stats", response_class=HTMLResponse)
def admin_stats(authorized: bool = Depends(check_admin)):
    # Заглушка статистики
    now = time.time()
    uptime_str = time.strftime("%H:%M:%S", time.gmtime(now))
    return f"""
    <html><body style="background:#f0f8ff;">
    <h3>Статистика</h3>
    <p>Uptime (прим.): {uptime_str}</p>
    </body></html>
    """

@app.get("/admin/log", response_class=HTMLResponse)
def admin_log(authorized: bool = Depends(check_admin)):
    log_path = "logs/telethon_userbot.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            data = f.read()[-4000:]  # последние 4000 символов
        escaped = data.replace("<", "&lt;").replace(">", "&gt;")
        return f"<html><body style='white-space: pre-wrap;background:#f0f8ff;'>{escaped}</body></html>"
    else:
        return "<html><body>Лог не найден.</body></html>"

@app.get("/admin/summaries", response_class=HTMLResponse)
def admin_summaries(authorized: bool = Depends(check_admin)):
    """
    Показываем все суммаризации, сохранённые в summaries_list
    """
    rows = ""
    for s in summaries_list[-20:]:  # последние 20
        dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["time"]))
        rows += f"<tr><td>{dt}</td><td>{s['chat_id']}</td><td>{s['num']}</td><td>{s['summary']}</td></tr>\n"

    return f"""
    <html>
    <body style="background:#f0f8ff;">
      <h2>История суммаризаций (последние 20)</h2>
      <table border="1" style="border-collapse:collapse;">
      <tr><th>Время</th><th>Chat ID</th><th>Кол-во</th><th>Текст</th></tr>
      {rows}
      </table>
    </body>
    </html>
    """


import re
import logging
import random
import yaml
import os
from pyrogram import Client, filters
from pyrogram.types import Message

# Импортируем справку
from utils.misc import modules_help

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------- Загрузка AUTHORIZED_USERS из vars.yaml ----------------------
# Предположим, что ваш код уже где-то получает путь к vars.yaml:
current_dir = os.path.dirname(__file__)
vars_file_path = os.path.join(current_dir, "vars.yaml")

with open(vars_file_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

AUTHORIZED_USERS = set(config.get("AUTHORIZED_USERS", []))
# ------------------------------------------------------------------------------------

# Флаг управления фильтром "кота"/"ебал"
catfuck_filter_enabled = False

# Регулярка для "кота/kota/котов/kotov" И "ебал/ebal" (±1 ошибка на каждое слово)
CATFUCK_PATTERN = re.compile(
    r'''(?xi)
    # 1) Lookahead для "кота"/"kota"/"котов"/"kotov" (±1 неверная буква)
    (?=
      .*?\b
      (?:
        # "кота"/"kota" (4 буквы)
        (?:[kк][оo0][tт][aа])
        | (?:.[оo0][tт][aа])
        | (?:[kк].[tт][aа])
        | (?:[kк][оo0].[aа])
        | (?:[kк][оo0][tт].)

        # или "котов"/"kotov" (5 букв)
        | (?:[kк][оo0][tт][оo0][vв])
        | (?:.[оo0][tт][оo0][vв])
        | (?:[kк].[tт][оo0][vв])
        | (?:[kк][оo0].[оo0][vв])
        | (?:[kк][оo0][tт].[vв])
        | (?:[kк][оo0][tт][оo0].)
      )
      \b
    )

    # 2) Lookahead для "ебал"/"ebal" (±1 неверная буква)
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

# Регулярка для "выебан"/"vjeban" и т.д. (частичная/полная транслитерация)
WYEBAN_PATTERN = re.compile(
    r'''(?xi)
    [вv][ыyиi]?[еe][бb][аa][нn][ыyиiеe]?  # "выебан", "vjeban", "выебаны", "vyebani" и т.п.
    ''',
    flags=0
)

# Список «грубых» ответов для неавторизованных пользователей
RUDE_REPLIES = [
    "Неа", 
    "Иди нахер, кожаный ублюдок",
    "Не положено.",
    "Ты кто такой? Давай, до свидания...",
    "У тебя нет прав на это действие."
]

def is_authorized(user_id: int) -> bool:
    """Проверяем, есть ли user_id в списке разрешённых."""
    return user_id in AUTHORIZED_USERS

@Client.on_message(filters.command("catfuckon", prefixes=["."]))
async def catfuck_on_command(client: Client, message: Message):
    global catfuck_filter_enabled
    # Проверяем, авторизован ли пользователь
    if not is_authorized(message.from_user.id):
        await message.reply(random.choice(RUDE_REPLIES))
        return

    catfuck_filter_enabled = True
    reply_text = "Котоебля ЗАПРЕЩЕНА!."
    await message.reply(reply_text)

@Client.on_message(filters.command("catfuckoff", prefixes=["."]))
async def catfuck_off_command(client: Client, message: Message):
    global catfuck_filter_enabled
    # Проверяем, авторизован ли пользователь
    if not is_authorized(message.from_user.id):
        await message.reply(random.choice(RUDE_REPLIES))
        return

    catfuck_filter_enabled = False
    reply_text = "Ладно, ебите своих котов."
    await message.reply(reply_text)

@Client.on_message(filters.text & ~filters.command(["catfuckon", "catfuckoff"], prefixes=["."]))
async def catfuck_filter_check(client: Client, message: Message):
    """
    1) Если фильтр включен (catfuck_filter_enabled == True)
       и текст содержит сразу оба слова (кота/kota/котов/kotov) + (ебал/ebal) (±1 неверная буква):
         - Удаляем сообщение.
    2) Если пользователь отвечает на чьё-то сообщение (message.reply_to_message не None)
       и пишет любую форму "выебан"/"vjeban"/"выебаны" (частичная/полная транслитерация),
         - Удаляем сообщение.
    """
    # 1) Ловим "кота/kota/котов/kotov" + "ебал/ebal"
    if catfuck_filter_enabled and CATFUCK_PATTERN.search(message.text):
        try:
            await message.delete()
            logger.info("Удалено сообщение с запрещёнными словами (кота/ебал): %s", message.text)
        except Exception as e:
            logger.error("Не удалось удалить сообщение: %s", e)
        return  # уже удалили, дальше проверять не имеет смысла

    # 2) Логика для "выебан"/"vjeban" и т.д., но только если это reply-сообщение
    if message.reply_to_message and WYEBAN_PATTERN.search(message.text):
        try:
            await message.delete()
            logger.info("Удалено сообщение с фразой 'выебан' в ответе: %s", message.text)
        except Exception as e:
            logger.error("Не удалось удалить сообщение: %s", e)

# Помощь по модулю
modules_help["catfilter"] = {
    "catfuckon": "Включает фильтр «кота/kota/котов/kotov + ебал/ebal» (±1 ошибка). Сообщения будут удаляться.",
    "catfuckoff": "Выключает фильтр «кота/kota/котов/kotov + ебал/ebal».",
}

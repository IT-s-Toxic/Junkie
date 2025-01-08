import re
import logging
from telethon import events
from utils.misc import plugins_help, register_help

logger = logging.getLogger(__name__)

def init(client):
    # Регистрируем справку для этого плагина
    register_help("help", {
        "Джанки, фичи": "Выводит список всех доступных команд"
    })

    @client.on(events.NewMessage(pattern=re.compile(r"(?i)^джанки,\s*фичи\s*$")))
    async def features_handler(event):
        # Формируем текст помощи, собирая команды из всех плагинов
        lines = ["**📚 Список команд:**\n"]
        for plugin_name, commands in plugins_help.items():
            lines.append(f"**{plugin_name}:**")
            for cmd, desc in commands.items():
                # Оформление команд как инлайн-кода для удобного копирования
                lines.append(f"  • `{cmd}`: {desc}")
            lines.append("")  # пустая строка для разделения плагинов

        help_text = "\n".join(lines)
        await event.reply(help_text, parse_mode='markdown')

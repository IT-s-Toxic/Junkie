import yaml
import os

from utils.config import BASE_DIR

plugins_help = {}
summaries_list = []

def register_help(plugin_name: str, help_dict: dict):
    """
    Регистрация команд для help.
    Пример: register_help("ping_echo", {"Джанки, голос": "Саркастичный ответ."})
    """
    plugins_help[plugin_name] = help_dict

# Путь к файлу для хранения активных приглашений
INVITES_FILE = os.path.join(BASE_DIR, "active_invites.yaml")

def load_active_invites():
    """Загружает активные приглашения из файла."""
    if os.path.exists(INVITES_FILE):
        with open(INVITES_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_active_invites(active_invites):
    """Сохраняет активные приглашения в файл."""
    with open(INVITES_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(active_invites, f, allow_unicode=True)

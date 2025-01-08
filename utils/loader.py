import os
import importlib
import logging

logger = logging.getLogger("TelethonLoader")

def load_plugins(client, plugins_path="plugins"):
    loaded = 0
    failed = 0
    for fname in os.listdir(plugins_path):
        if fname.endswith(".py") and fname != "__init__.py":
            mod_name = fname[:-3]
            try:
                mod = importlib.import_module(f"{plugins_path}.{mod_name}")
                if hasattr(mod, "init"):
                    mod.init(client)
                logger.info(f"Плагин '{mod_name}' загружен.")
                loaded += 1
            except Exception as e:
                logger.error(f"Ошибка загрузки плагина '{mod_name}': {e}", exc_info=True)
                failed += 1
    return loaded, failed

import os
import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARS_PATH = os.path.join(BASE_DIR, "vars.yaml")

with open(VARS_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

API_ID = CONFIG.get("API_ID") or os.getenv("API_ID")
API_HASH = CONFIG.get("API_HASH") or os.getenv("API_HASH")

AUTHORIZED_USERS = CONFIG.get("AUTHORIZED_USERS", [])
OLLAMA_HOST = CONFIG.get("ollama_host", "http://127.0.0.1:11434")
SUMMARY_MODEL = CONFIG.get("summary_model", "tinyllama")
LOGCHANNEL = CONFIG.get("logchannel")

MONGODB_URI = CONFIG.get("mongodb_uri", "mongodb://localhost:27017/")
DB_NAME = CONFIG.get("db_name", "JunkyDB")

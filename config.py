import json
import logging
import os
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TypedDict

from aiogoogle.auth.creds import ServiceAccountCreds
from dotenv import load_dotenv
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)


load_dotenv()

APP_NAME = "mbfc"
MAX_LOG_SIZE = 10_000_000

TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "dev")
DEVELOPER_CHAT_ID = int(os.getenv("DEVELOPER_CHAT_ID", 6085031336))

_gcp_sa_credentials = json.loads(GOOGLE_APPLICATION_CREDENTIALS)
SA_CREDS = ServiceAccountCreds(
    scopes=["https://www.googleapis.com/auth/spreadsheets"], **_gcp_sa_credentials
)


LOG_MSG_FORMAT = "[%(asctime)s] %(levelname)s - %(name)s - %(filename)s:%(lineno)s - %(message)s"
LOG_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / Path("mbfc-telegram-bot.log")
LOG_PATH.touch(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL == "dev" else logging.INFO,
    datefmt=LOG_DATE_FORMAT,
    format=LOG_MSG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_PATH, maxBytes=MAX_LOG_SIZE, backupCount=5),
    ],
)


class AdminConfig(TypedDict):
    question_range: str
    question_set: str

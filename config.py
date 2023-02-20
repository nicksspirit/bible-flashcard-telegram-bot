import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pretty_errors as perr
from aiogoogle.auth.creds import ServiceAccountCreds
from dotenv import load_dotenv

if not perr.terminal_is_interactive:
    perr.mono()

perr.configure(infix="\n⬆️", display_link=True, line_number_first=False)

load_dotenv()

APP_NAME = "mbfc"
MAX_LOG_SIZE = 10_000_000

TOKEN = os.getenv("TELEGRAM_TOKEN")
QA_SET_ID = os.getenv("QA_SET_ID", "ADV-1")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "dev")

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

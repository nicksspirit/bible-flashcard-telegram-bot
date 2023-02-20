import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

APP_NAME = "mbfc"
MAX_LOG_SIZE = 10_000_000

TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")


LOG_MSG_FORMAT = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
LOG_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / Path("mbfc-telegram-bot.log")
LOG_PATH.touch(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    datefmt=LOG_DATE_FORMAT,
    format=LOG_MSG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_PATH, maxBytes=MAX_LOG_SIZE, backupCount=5),
    ],
)

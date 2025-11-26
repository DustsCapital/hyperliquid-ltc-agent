# logger.py - Updated top section
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

# Config
LOG_LEVEL = logging.INFO  # ← Your choice: WARNING hides DEBUG/INFO
LOGS_DIR = "saves/logs"  # New subfolder
LOG_FILE = os.path.join(LOGS_DIR, "bot.log")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# Setup - Create dir if missing
os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("LTCBot")
logger.setLevel(LOG_LEVEL)

# Formatter
formatter = logging.Formatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',  # ← Uses asctime placeholder
    datefmt='%H:%M:%S'  # ← Custom: Hours:Min:Sec only (no date, no ms)
)

# Console
console_handler = logging.StreamHandler()
console_handler.setLevel(LOG_LEVEL)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File - Now in saves/logs/bot.log
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# log_print (unchanged)
def log_print(msg, level="INFO"):
    levels = {"INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "DEBUG": logging.DEBUG}
    logger.log(levels.get(level, logging.INFO), msg)

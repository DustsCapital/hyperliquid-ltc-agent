# logger.py – PERFECT FINAL VERSION (QUIET mode fixed)
import logging
from logging.handlers import RotatingFileHandler
import os
from config import TERMINAL_LOG_MODE

LOGS_DIR = "saves/logs"
LOG_FILE = os.path.join(LOGS_DIR, "bot.log")
os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("LTCBot")
logger.setLevel(logging.DEBUG)
logger.propagate = False
logger.handlers.clear()

# File: always full detail
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s', '%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Terminal: configurable
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

class ConfigurableFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        
        # These always show (critical)
        if record.levelno >= logging.WARNING:
            return True
            
        if TERMINAL_LOG_MODE == "QUIET":
            critical = [
                "BOT STARTED", "Balance", "TREND", "GOLDEN CROSS", "DEATH CROSS",
                "PENDING", "FILLED", "CLOSE", "RATCHET", "FLIPPING"
            ]
            return any(x in msg for x in critical)
            
        elif TERMINAL_LOG_MODE == "NORMAL":
            normal = [
                "BOT STARTED", "Balance", "TREND", "GOLDEN CROSS", "DEATH CROSS",
                "PENDING", "FILLED", "CLOSE", "RATCHET", "FLIPPING",
                "Created new candle file"
            ]
            return any(x in msg for x in normal)
            
        elif TERMINAL_LOG_MODE == "VERBOSE":
            verbose = [
                "BOT STARTED", "Balance", "TREND", "GOLDEN CROSS", "DEATH CROSS",
                "PENDING", "FILLED", "CLOSE", "RATCHET", "FLIPPING",
                "Created new", "Saved"
            ]
            return any(x in msg for x in verbose)
            
        elif TERMINAL_LOG_MODE == "DEBUG":
            return True
            
        return True

console_handler.addFilter(ConfigurableFilter())
console_formatter = logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

def log_print(msg, level="INFO"):
    levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
    logger.log(levels.get(level, logging.INFO), msg)

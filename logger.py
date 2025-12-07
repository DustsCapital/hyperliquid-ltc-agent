# logger.py — FINAL ULTIMATE VERSION (your exact dream formatting) + PnL support
import logging
from logging.handlers import RotatingFileHandler
import os
from config import TERMINAL_LOG_MODE
from utils import color_text
import state
from exchange import get_unrealized_pnl  # NEW: For PnL in price logs

LOGS_DIR = "saves/logs"
LOG_FILE = os.path.join(LOGS_DIR, "bot.log")
os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("LTCBot")
logger.setLevel(logging.DEBUG)
logger.propagate = False
logger.handlers.clear()

# File handler — full detail
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s', '%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Terminal handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

class ConfigurableFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()

        if record.levelno >= logging.WARNING:
            return True

        # TREND → (Downtrend ↓) or (Uptrend ↑)
        if "TREND →" in msg:
            if "Uptrend" in msg:
                record.msg = f"TREND → ({color_text('Uptrend ↑', 'light_green')})"
            elif "Downtrend" in msg:
                record.msg = f"TREND → ({color_text('Downtrend ↓', 'light_red')})"
            return True

        # PRICE + BALANCE + POSITION + PnL (UPDATED FOR NEW FORMAT)
        if "Price $" in msg:
            parts = msg.split(" │ ")
            
            # Robust: Grab trend from last part
            trend_part = parts[-1] if len(parts) > 1 else "Downtrend"
            
            # Extract price/RSI from first two (ignore extras)
            price_part = parts[0] if len(parts) > 0 else "Price $0.000"
            rsi_part = parts[1] if len(parts) > 1 else "RSI 0.0"

            # Extract values
            try:
                price = float(price_part.split("$")[1].split()[0])
                rsi = float(rsi_part.split()[1])
            except:
                price, rsi = 0.0, 0.0

            # Fetch live balance/position/PnL from state/exchange
            balance = state.dashboard_data.get("usdt_balance", 0.0)
            ltc_pos = state.dashboard_data.get("ltc_position", 0.0)
            position_open = getattr(state, 'position_open', False)  # From state

            # Format position
            if abs(ltc_pos) < 0.001:
                pos_str = "0 LTC"
            else:
                pos_str = f"{ltc_pos:.6f}".rstrip("0").rstrip(".") + " LTC"

            # NEW: Fetch PnL
            current_pnl_pct, current_pnl_usd = get_unrealized_pnl() if position_open else (0.0, 0.0)
            pnl_str = f"{current_pnl_pct:+.1f}% (${current_pnl_usd:+.2f})" if position_open else "0% ($0.00)"

            # Build new line
            trend_colored = color_text("Uptrend ↑", 'light_green') if "Uptrend" in trend_part else color_text("Downtrend ↓", 'light_red')
            new_msg = (
                f"Price ${price:.3f} │ "
                f"RSI {rsi:.1f} │ "
                f"Balance: ${balance:.2f} │ "
                f"Position: {pos_str} | "
                f"PnL: {pnl_str} │ "
                f"{trend_colored}"
            )
            record.msg = new_msg
            return True

        # Allow important events
        if TERMINAL_LOG_MODE == "QUIET":
            allowed = ["BOT STARTED", "Balance", "GOLDEN CROSS", "DEATH CROSS",
                      "PENDING", "FILLED", "CLOSE", "RATCHET", "FLIPPING"]
            return any(x in msg for x in allowed)

        elif TERMINAL_LOG_MODE == "NORMAL":
            allowed = ["BOT STARTED", "Balance", "Created new"]
            return any(x in msg for x in allowed) or "TREND →" in msg

        elif TERMINAL_LOG_MODE == "VERBOSE":
            return "Saved" in msg or "TREND →" in msg or any(x in msg for x in ["BOT STARTED", "Balance"])

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
    levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
    logger.log(levels.get(level, logging.INFO), msg)

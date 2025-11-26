# config.py
import os
from dotenv import load_dotenv
from hyperliquid.utils import constants

load_dotenv()

EXCHANGE = "hyperliquid"
NETWORK = "mainnet"
SYMBOL = "LTC"
TRADE_USDT = 15.0
TIMEFRAME = "1m"
MA_SHORT = 50
MA_LONG = 200
TREND_LOOKBACK = 10
RSI_PERIOD = 14
RSI_OVERBOUGHT = 80
RSI_OVERSOLD = 15
FEE_BUFFER_PCT = 0.001
CHECK_INTERVAL = 30
MIN_LTC_SELL = 0.01
MAX_CROSSES = 4


# NEW: Shorting toggle
ALLOW_SHORTS = False          # ← Set False to disable shorts again
USE_RSI_EARLY_EXIT = False     # Optional: exit longs early if RSI >85, shorts if RSI <15

# NEW: Profit protection
PROFIT_RATCHET_ENABLED = True          # ← Turn the whole feature on/off
MIN_PROFIT_TO_ACTIVATE = 0.10           # $0.20 profit → switch to protection mode
PROFIT_PROTECTION_FLOOR = 0.05        # Keep 70% of peak profit (e.g., +$0.40 → close if drops below +$0.24)


# How often to log current price in terminal (in seconds)
PRICE_LOG_INTERVAL = 120   # 300 = 5 minutes (default)
# Examples:
# PRICE_LOG_INTERVAL = 60    # every 1 minute
# PRICE_LOG_INTERVAL = 900   # every 15 minutes
# PRICE_LOG_INTERVAL = 0     # disable price logs





# === KEYS ===
API_WALLET_ADDRESS = os.getenv("HL_WALLET")
API_PRIVATE_KEY = os.getenv("HL_PRIVATE_KEY")
MAIN_WALLET = os.getenv("MAIN_WALLET")

BASE_URL = constants.MAINNET_API_URL

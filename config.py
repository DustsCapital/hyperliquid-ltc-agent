# config.py
import os
from dotenv import load_dotenv
from hyperliquid.utils import constants

load_dotenv()

EXCHANGE = "hyperliquid"
NETWORK = "mainnet"
SYMBOL = "LTC"
TRADE_USDT = 10.0
TIMEFRAME = "1m"
MA_SHORT = 50
MA_LONG = 200
TREND_LOOKBACK = 5
RSI_PERIOD = 14
RSI_OVERBOUGHT = 85
RSI_OVERSOLD = 15
FEE_BUFFER_PCT = 0.001
CHECK_INTERVAL = 30
MIN_LTC_SELL = 0.01
MAX_CROSSES = 4

# NEW: Shorting toggle
ALLOW_SHORTS = True          # ← Set False to disable shorts again
USE_RSI_EARLY_EXIT = True     # Optional: exit longs early if RSI >85, shorts if RSI <15

# === KEYS ===
API_WALLET_ADDRESS = os.getenv("HL_WALLET")
API_PRIVATE_KEY = os.getenv("HL_PRIVATE_KEY")
MAIN_WALLET = os.getenv("MAIN_WALLET")

BASE_URL = constants.MAINNET_API_URL

# exchange.py - CLEAN FINAL VERSION
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
import eth_account
import time
import pandas as pd

from config import API_WALLET_ADDRESS, API_PRIVATE_KEY, SYMBOL, TIMEFRAME, BASE_URL

info = Info(BASE_URL, skip_ws=True)
wallet = eth_account.Account.from_key(API_PRIVATE_KEY)
exchange = Exchange(wallet=wallet, base_url=BASE_URL, account_address=API_WALLET_ADDRESS)

def fetch_ohlcv():
    end_time = int(time.time() * 1000)
    start_time = end_time - 24 * 3600 * 1000
    try:
        raw = info.candles_snapshot(name=SYMBOL, interval=TIMEFRAME, startTime=start_time, endTime=end_time)
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        df = df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return pd.DataFrame()

def get_balance():
    try:
        state = info.user_state(API_WALLET_ADDRESS)
        return float(state.get("withdrawable", "0.0"))
    except:
        return 0.0

def get_ltc_position():
    try:
        state = info.user_state(API_WALLET_ADDRESS)
        for pos in state.get('assetPositions', []):
            if pos.get('position', {}).get('coin') == SYMBOL:
                return abs(float(pos['position'].get('szi', '0')))
        return 0.0
    except:
        return 0.0

# exchange.py
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
import time
import pandas as pd

from config import API_WALLET_ADDRESS, API_PRIVATE_KEY, SYMBOL, TIMEFRAME, MAIN_WALLET, BASE_URL

info = Info(BASE_URL, skip_ws=True)
exchange = Exchange(wallet=API_WALLET_ADDRESS, base_url=BASE_URL)

def fetch_ohlcv():
    end_time = int(time.time() * 1000)
    start_time = end_time - 6 * 3600 * 1000

    try:
        raw = info.candles_snapshot(
            name=SYMBOL,
            interval=TIMEFRAME,
            startTime=start_time,
            endTime=end_time
        )
        if not raw or len(raw) == 0:
            print("No candles returned")
            return pd.DataFrame()

        df = pd.DataFrame(raw)
        df = df.rename(columns={
            't': 'timestamp', 'o': 'open', 'h': 'high',
            'l': 'low', 'c': 'close', 'v': 'volume'
        })
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Candle fetch error: {e}")
        return pd.DataFrame()

def _check_result(result, action: str):
    if not result:
        print(f"{action} FAILED – no response")
        return False
    status = result.get("status")
    if status == "ok":
        return True
    else:
        print(f"{action} FAILED: {result}")
        return False

def place_buy_order(qty):
    result = exchange.market_open(
        is_buy=True,
        sz=qty
    )
    return _check_result(result, "BUY")

def place_sell_order(qty):
    result = exchange.market_close(
        sz=qty
    )
    return _check_result(result, "SELL")

def get_balance():
    try:
        state = info.user_state(API_WALLET_ADDRESS)
        return float(state.get('withdrawable', '0.0'))
    except Exception as e:
        print(f"Balance error: {e}")
        return 0.0

def get_ltc_position():
    try:
        state = info.user_state(API_WALLET_ADDRESS)
        for pos in state.get('assetPositions', []):
            if pos.get('coin') == SYMBOL:
                return abs(float(pos.get('szi', '0')))
        return 0.0
    except Exception as e:
        print(f"Position error: {e}")
        return 0.0

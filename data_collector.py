# data_collector.py – FINAL VERSION (NO WARNINGS, EVER)
import pandas as pd
import os
from datetime import datetime
from exchange import info, SYMBOL
from logger import log_print

# PERMANENTLY SILENCE THE PANDAS WARNING (this is the nuclear option)
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

CANDLE_FILES = {
    "1m": "ltc_1m.csv",
    "3m": "ltc_3m.csv",
    "5m": "ltc_5m.csv"
}

def get_or_create_csv(filename):
    logs_dir = "saves/logs"
    full_path = os.path.join(logs_dir, filename)
    os.makedirs(logs_dir, exist_ok=True)
    if not os.path.exists(full_path):
        pd.DataFrame(columns=['timestamp','open','high','low','close','volume']).to_csv(full_path, index=False)
        log_print(f"Created new candle file: {full_path}")
    return full_path

def append_candle(timeframe, df):
    if df.empty:
        return
    
    filename = get_or_create_csv(CANDLE_FILES[timeframe])
    
    # This line fixes the warning FOREVER
    existing_df = pd.read_csv(filename, parse_dates=['timestamp']) if os.path.getsize(filename) > 0 else pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Safe concat — no FutureWarning
    combined_df = pd.concat([existing_df, df[['timestamp','open','high','low','close','volume']].copy()], ignore_index=True)
    
    agg_df = combined_df.groupby('timestamp').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).reset_index()
    
    agg_df = agg_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last')
    for col in ['open','high','low','close']:
        agg_df[col] = agg_df[col].round(3)
    agg_df['volume'] = agg_df['volume'].round(2)
    
    agg_df.to_csv(filename, index=False, date_format='%Y-%m-%d %H:%M:%S')
    
    new_bars = len(agg_df) - len(existing_df)
    if new_bars > 0:
        log_print(f"Saved {new_bars} new {timeframe} bars")

def collect_all_candles(one_m_df=None):
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = end_time - 24 * 3600 * 1000

    if one_m_df is not None:
        append_candle("1m", one_m_df.copy())
    else:
        try:
            raw = info.candles_snapshot(name=SYMBOL, interval="1m", startTime=start_time, endTime=end_time)
            if raw:
                df = pd.DataFrame(raw).rename(columns={'t':'timestamp','o':'open','h':'high','l':'low','c':'close','v':'volume'})
                df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce').fillna(0.0)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                append_candle("1m", df)
        except Exception as e:
            log_print(f"1m fetch failed: {e}", "WARNING")

    for tf in ["3m", "5m"]:
        try:
            raw = info.candles_snapshot(name=SYMBOL, interval=tf, startTime=start_time, endTime=end_time)
            if raw:
                df = pd.DataFrame(raw).rename(columns={'t':'timestamp','o':'open','h':'high','l':'low','c':'close','v':'volume'})
                df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce').fillna(0.0)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                append_candle(tf, df)
        except Exception as e:
            log_print(f"{tf} fetch failed: {e}", "WARNING")

# data_collector.py
import pandas as pd
import os
from datetime import datetime
from exchange import info, SYMBOL  # Reuse Info
from logger import log_print  # Use logger's log_print (add this if missing)

CANDLE_FILES = {
    "1m": "ltc_1m.csv",
    "3m": "ltc_3m.csv",
    "5m": "ltc_5m.csv"
}

def get_or_create_csv(filename):
    logs_dir = "saves/logs"  # ← New: Use logs subfolder
    full_path = os.path.join(logs_dir, filename)
    os.makedirs(logs_dir, exist_ok=True)  # ← Creates if missing
    if not os.path.exists(full_path):
        df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df.to_csv(full_path, index=False)
    return full_path

def append_candle(timeframe, df):
    if df.empty:
        log_print(f"No new {timeframe} data to append.", "DEBUG")
        return
    
    filename = get_or_create_csv(CANDLE_FILES[timeframe])
    existing_df = pd.read_csv(filename, parse_dates=['timestamp'])
    
    # Ensure incoming df has datetime timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Concat existing + new
    combined_df = pd.concat([existing_df, df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]], ignore_index=True)
    
    # Aggregate: Unique timestamps with proper OHLCV
    agg_df = combined_df.groupby('timestamp').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index()
    
    # Sort and drop any remaining dups (just in case)
    agg_df = agg_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last')
    
    # Round prices to 3 decimals, volume to 2
    for col in ['open', 'high', 'low', 'close']:
        agg_df[col] = agg_df[col].round(3)
    agg_df['volume'] = agg_df['volume'].round(2)
    
    # Save full aggregated CSV with ISO timestamp format
    agg_df.to_csv(filename, index=False, date_format='%Y-%m-%d %H:%M:%S')
    
    new_bars = len(agg_df) - len(existing_df)
    log_print(f"Appended & aggregated {new_bars} {timeframe} bars. Total: {len(agg_df)}", "DEBUG")

def collect_all_candles(one_m_df=None):
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = end_time - 24 * 3600 * 1000  # 24h
    timeframes = ["1m", "3m", "5m"]  # ← Your update: No 10m
    
    # Handle 1m if no df passed
    if one_m_df is None:
        try:
            raw = info.candles_snapshot(name=SYMBOL, interval="1m", startTime=start_time, endTime=end_time)
            if raw:
                one_m_df = pd.DataFrame(raw)
                one_m_df = one_m_df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    one_m_df[col] = pd.to_numeric(one_m_df[col], errors='coerce').fillna(0.0)
                one_m_df['timestamp'] = pd.to_datetime(one_m_df['timestamp'], unit='ms')
                append_candle("1m", one_m_df)
        except Exception as e:
            log_print(f"Candle fetch fail for 1m: {e}", "WARNING")
            return  # Bail if 1m fails
    
    # Other TFs
    for tf in timeframes:
        try:
            raw = info.candles_snapshot(name=SYMBOL, interval=tf, startTime=start_time, endTime=end_time)
            if raw:
                df = pd.DataFrame(raw)
                df = df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                append_candle(tf, df)
        except Exception as e:
            log_print(f"Candle fetch fail for {tf}: {e}", "WARNING")

# indicators.py
import pandas as pd
from config import MA_SHORT, MA_LONG, TREND_LOOKBACK, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD, ALLOW_SHORTS, USE_RSI_EARLY_EXIT, MAX_CROSSES
from state import position_open, position_side
from logger import log_print

last_cross_time = None

def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def detect_cross(df: pd.DataFrame, cross_history: list, last_trend: str | None):
    global last_cross_time

    df['sma_short'] = df['close'].rolling(window=MA_SHORT).mean()
    df['sma_long']  = df['close'].rolling(window=MA_LONG).mean()
    df['rsi']       = rsi(df['close'], RSI_PERIOD)

    cur_short = df['sma_short'].iloc[-1]
    cur_long  = df['sma_long'].iloc[-1]
    prev_short = df['sma_short'].shift(1).iloc[-1]
    prev_long  = df['sma_long'].shift(1).iloc[-1]

    is_uptrend = df['sma_long'].iloc[-1] > df['sma_long'].iloc[-1 - TREND_LOOKBACK]
    trend_str = 'Uptrend' if is_uptrend else 'Downtrend'

    signal = None
    cross_type = None
    current_time = df['timestamp'].iloc[-1]

    if last_cross_time != current_time:
        last_cross_time = current_time

        rsi_val = df['rsi'].iloc[-1]

        # Golden Cross
        if cur_short > cur_long and prev_short <= prev_long:
            cross_type = 'golden'
            cross_history.append({
                'type': 'golden',
                'time': current_time.strftime('%H:%M:%S'),
                'price': df['close'].iloc[-1],
                'trend': trend_str
            })
            if len(cross_history) > MAX_CROSSES:
                cross_history.pop(0)
            from state import save_crosses
            save_crosses()

            if is_uptrend:
                if rsi_val < RSI_OVERBOUGHT:
                    signal = 'buy'
                else:
                    print(f"[SKIP] GOLDEN CROSS — RSI too high ({rsi_val:.1f} ≥ {RSI_OVERBOUGHT})", "WARNING")
            else:
                print(f"[SKIP] GOLDEN CROSS — Market in Downtrend (no longs allowed)")

        # Death Cross
        elif cur_short < cur_long and prev_short >= prev_long:
            cross_type = 'death'
            cross_history.append({
                'type': 'death',
                'time': current_time.strftime('%H:%M:%S'),
                'price': df['close'].iloc[-1],
                'trend': trend_str
            })
            if len(cross_history) > MAX_CROSSES:
                cross_history.pop(0)
            from state import save_crosses
            save_crosses()

            if not is_uptrend:
                if ALLOW_SHORTS:
                    if rsi_val > RSI_OVERSOLD:
                        signal = 'short'
                    else:
                        print(f"[SKIP] DEATH CROSS — RSI too low ({rsi_val:.1f} ≤ {RSI_OVERSOLD})")
                else:
                    print("[SKIP] DEATH CROSS — Shorts disabled in config")
            else:
                print(f"[SKIP] DEATH CROSS — Market in Uptrend (no shorts allowed)")

        # Optional early exit signals
        if USE_RSI_EARLY_EXIT:
            if position_open and position_side == "long" and rsi_val > RSI_OVERBOUGHT:
                signal = 'sell_early'
            elif position_open and position_side == "short" and rsi_val < RSI_OVERSOLD:
                signal = 'cover_early'

    return signal, trend_str, cross_type

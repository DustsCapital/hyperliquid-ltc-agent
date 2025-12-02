# indicators.py
import pandas as pd
from config import MA_SHORT, MA_LONG, TREND_LOOKBACK, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD, ALLOW_SHORTS, USE_RSI_EARLY_EXIT
from state import position_open, position_side, save_crosses  # ← MOVED TO TOP!
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

        # === GOLDEN CROSS ===
        if cur_short > cur_long and prev_short <= prev_long:
            cross_type = 'golden'
            log_print(f"GOLDEN CROSS DETECTED @ ${df['close'].iloc[-1]:.3f} | RSI {rsi_val:.1f}", "INFO")
            
            cross_history.append({
                'type': 'golden',
                'time': current_time.strftime('%H:%M:%S'),
                'price': df['close'].iloc[-1],
                'trend': trend_str
            })
            if len(cross_history) > 4:
                cross_history.pop(0)
            save_crosses()  # ← NOW ALWAYS CALLED

            if is_uptrend and rsi_val < RSI_OVERBOUGHT:
                signal = 'buy'
                log_print("GOLDENaf CROSS → ENTERING LONG", "INFO")
            else:
                reason = "RSI too high" if rsi_val >= RSI_OVERBOUGHT else "Not in uptrend"
                log_print(f"[SKIPPED] GOLDEN CROSS — {reason}", "WARNING")

        # === DEATH CROSS ===
        elif cur_short < cur_long and prev_short >= prev_long:
            cross_type = 'death'
            log_print(f"DEATH CROSS DETECTED @ ${df['close'].iloc[-1]:.3f} | RSI {rsi_val:.1f}", "INFO")
            
            cross_history.append({
                'type': 'death',
                'time': current_time.strftime('%H:%M:%S'),
                'price': df['close'].iloc[-1],
                'trend': trend_str
            })
            if len(cross_history) > 4:
                cross_history.pop(0)
            save_crosses()  # ← NOW ALWAYS CALLED

            if not is_uptrend and ALLOW_SHORTS and rsi_val > RSI_OVERSOLD:
                signal = 'short'
                log_print("DEATH CROSS → ENTERING SHORT", "INFO")
            else:
                reason = "Shorts disabled" if not ALLOW_SHORTS else "RSI too low" if rsi_val <= RSI_OVERSOLD else "In uptrend"
                log_print(f"[SKIPPED] DEATH CROSS — {reason}", "WARNING")

        # Early exit
        if USE_RSI_EARLY_EXIT and position_open:
            if position_side == "long" and rsi_val > 85:
                signal = 'sell_early'
            elif position_side == "short" and rsi_val < 15:
                signal = 'cover_early'

    return signal, trend_str, cross_type

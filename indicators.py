# indicators.py
import pandas as pd
from config import MA_SHORT, MA_LONG, TREND_LOOKBACK, RSI_PERIOD, RSI_OVERBOUGHT, MAX_CROSSES

def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def detect_cross(df: pd.DataFrame, cross_history: list, last_trend: str | None):
    df['sma_short'] = df['close'].rolling(window=MA_SHORT).mean()
    df['sma_long']  = df['close'].rolling(window=MA_LONG).mean()
    df['rsi']       = rsi(df['close'], RSI_PERIOD)

    cur_short = df['sma_short'].iloc[-1]
    cur_long  = df['sma_long'].iloc[-1]
    prev_short = df['sma_short'].shift(1).iloc[-1]
    prev_long  = df['sma_long'].shift(1).iloc[-1]

    is_uptrend = df['sma_long'].iloc[-1] > df['sma_long'].iloc[-1 - TREND_LOOKBACK]
    trend_str = 'Uptrend' if is_uptrend else 'Downtrend'

    cross_type = None
    signal = None

    if cur_short > cur_long and prev_short <= prev_long:
        cross_type = 'death'
        cross_history.append({
            'type': 'golden',
            'time': df['timestamp'].iloc[-1].strftime('%H:%M:%S'),
            'price': df['close'].iloc[-1]
        })
        if len(cross_history) > MAX_CROSSES:
            cross_history.pop(0)
        from state import save_crosses
        save_crosses()
        
        if is_uptrend and df['rsi'].iloc[-1] < RSI_OVERBOUGHT:
            signal = 'buy'

 # Death Cross
    elif cur_short < cur_long and prev_short >= prev_long:
        cross_type = 'death'
        cross_history.append({
            'type': 'death',
            'time': df['timestamp'].iloc[-1].strftime('%H:%M:%S'),
            'price': df['close'].iloc[-1]
        })
        if len(cross_history) > MAX_CROSSES:
            cross_history.pop(0)
        from state import save_crosses
        save_crosses()

        if not is_uptrend and df['rsi'].iloc[-1] > RSI_OVERBOUGHT:
            signal = 'sell'

    return signal, trend_str, cross_type

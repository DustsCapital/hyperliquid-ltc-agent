# main.py — FINAL VERSION: FLIPPING + 1% TRAILING STOP (Dec 2025)
import threading
import time
import signal
import math
import pandas as pd
from datetime import datetime, timezone, timedelta

from dashboard import app
from config import *
import state
from exchange import get_balance, get_ltc_position, fetch_ohlcv, exchange
from indicators import detect_cross
from data_collector import collect_all_candles
from logger import log_print

from state import total_profit, position_open, position_side, last_signal, cross_history, dashboard_data

stop_event = threading.Event()
pending_trade = None
last_price_log = datetime.now(timezone.utc)

def signal_handler(sig, frame):
    log_print("Bot stopped by user.", "INFO")
    stop_event.set()
    import os
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def enough_usdt(required):
    free = get_balance()
    needed = required * (1 + FEE_BUFFER_PCT)
    return free >= needed, free

def calculate_dynamic_qty(current_price):
    if current_price <= 0:
        return 0.01
    rounded_price = math.ceil(current_price)
    qty = TRADE_USDT / rounded_price
    return math.ceil(qty * 100) / 100

def place_long(qty):
    try:
        result = exchange.market_open(name=SYMBOL, is_buy=True, sz=qty)
        if result.get("status") == "ok":
            for status in result["response"]["data"]["statuses"]:
                if "filled" in status:
                    filled = status["filled"]
                    entry_px = float(filled["avgPx"])
                    log_print(f"BUY LONG FILLED: {qty:.4f} LTC @ ${entry_px:.3f}", "INFO")
                    state.last_buy_price = entry_px
                    state.position_open = True
                    state.position_side = "long"
                    state.save_state()
                    state.save_trade("buy", qty, entry_px)
                    return True
        log_print(f"LONG FAILED: {result}", "ERROR")
        return False
    except Exception as e:
        log_print(f"LONG EXCEPTION: {e}", "ERROR")
        return False

def place_short(qty):
    try:
        result = exchange.market_open(name=SYMBOL, is_buy=False, sz=qty)
        if result.get("status") == "ok":
            for status in result["response"]["data"]["statuses"]:
                if "filled" in status:
                    filled = status["filled"]
                    entry_px = float(filled["avgPx"])
                    log_print(f"SHORT FILLED: {qty:.4f} LTC @ ${entry_px:.3f}", "INFO")
                    state.last_buy_price = entry_px
                    state.position_open = True
                    state.position_side = "short"
                    state.save_state()
                    state.save_trade("short", qty, entry_px)
                    return True
        log_print(f"SHORT FAILED: {result}", "ERROR")
        return False
    except Exception as e:
        log_print(f"SHORT EXCEPTION: {e}", "ERROR")
        return False

def close_position():
    qty = get_ltc_position()
    if qty < MIN_LTC_SELL:
        return False
    try:
        result = exchange.market_close(name=SYMBOL, is_buy=state.position_side == "short", sz=qty)
        if result.get("status") == "ok":
            for status in result["response"]["data"]["statuses"]:
                if "filled" in status:
                    filled = status["filled"]
                    exit_px = float(filled["avgPx"])
                    pnl = (exit_px - state.last_buy_price) * qty if state.position_side == "long" else (state.last_buy_price - exit_px) * qty
                    log_print(f"POSITION CLOSED: {qty:.4f} LTC @ ${exit_px:.3f} | PnL: ${pnl:+.2f}", "INFO")
                    state.total_profit += pnl
                    state.save_trade("close", qty, exit_px)
                    state.position_open = False
                    state.position_side = None
                    state.save_state()
                    # Reset trailing peaks
                    for attr in ['highest_price', 'lowest_price']:
                        if hasattr(state, attr):
                            delattr(state, attr)
                    return True
        return False
    except Exception as e:
        log_print(f"CLOSE EXCEPTION: {e}", "ERROR")
        return False

def run_bot():
    global last_price_log, pending_trade

    while not stop_event.is_set():
        try:
            df = fetch_ohlcv()
            if df.empty or len(df) < MA_LONG + 20:
                time.sleep(CHECK_INTERVAL)
                continue

            collect_all_candles(one_m_df=df)
            current_price = df['close'].iloc[-1]
            signal, trend_str, cross_type = detect_cross(df, cross_history, state.last_trend)

            if getattr(state, 'last_trend', None) != trend_str:
                log_print(f"TREND → {trend_str}", "INFO")
                state.last_trend = trend_str

            if PRICE_LOG_INTERVAL > 0:
                now = datetime.now(timezone.utc)
                if (now - last_price_log).total_seconds() >= PRICE_LOG_INTERVAL:
                    rsi_val = df['rsi'].iloc[-1] if 'rsi' in df.columns else 0.0
                    log_print(f"Price ${current_price:.3f} │ RSI {rsi_val:.1f} │ {trend_str}")
                    last_price_log = now

            # ==================== TRAILING STOP ====================
            if TRAILING_STOP_ENABLED and state.position_open and state.last_buy_price:
                qty = get_ltc_position()
                if qty >= MIN_LTC_SELL:
                    if state.position_side == "long":
                        peak = max(current_price, getattr(state, 'highest_price', current_price))
                        state.highest_price = peak
                        if current_price <= peak * (1 - TRAILING_STOP_PCT / 100):
                            log_print(f"TRAILING STOP HIT ({TRAILING_STOP_PCT}%)! Closing LONG @ ${current_price:.3f}", "INFO")
                            close_position()
                    else:  # short
                        peak = min(current_price, getattr(state, 'lowest_price', current_price))
                        state.lowest_price = peak
                        if current_price >= peak * (1 + TRAILING_STOP_PCT / 100):
                            log_print(f"TRAILING STOP HIT ({TRAILING_STOP_PCT}%)! Closing SHORT @ ${current_price:.3f}", "INFO")
                            close_position()
            # ==========================================================

            old_side = state.position_side if state.position_open else None

            # Close on opposite cross
            if state.position_open:
                if (state.position_side == "long" and signal == "short") or \
                   (state.position_side == "short" and signal == "buy"):
                    close_position()

            # Open new position (or flip)
            if not state.position_open:
                if signal == "buy":
                    qty = calculate_dynamic_qty(current_price)
                    pending_trade = {"type": "long", "qty": qty, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print(f"{'FLIP → ' if old_side else ''}GOLDEN CROSS — PENDING LONG {qty:.4f} LTC", "INFO")
                elif signal == "short" and ALLOW_SHORTS:
                    qty = calculate_dynamic_qty(current_price)
                    pending_trade = {"type": "short", "qty": qty, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print(f"{'FLIP → ' if old_side else ''}DEATH CROSS — PENDING SHORT {qty:.4f} LTC", "INFO")

            # Execute pending
            if pending_trade and datetime.now(timezone.utc) < pending_trade["expires"]:
                qty = pending_trade["qty"]
                if pending_trade["type"] == "long" and not state.position_open and enough_usdt(TRADE_USDT)[0]:
                    place_long(qty)
                    pending_trade = None
                elif pending_trade["type"] == "short" and not state.position_open and enough_usdt(TRADE_USDT)[0]:
                    place_short(qty)
                    pending_trade = None
            elif pending_trade:
                log_print("PENDING TRADE EXPIRED", "WARNING")
                pending_trade = None

            state.dashboard_data.update({
                "last_update": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "price": current_price,
                "trend": trend_str,
                "usdt_balance": get_balance(),
                "ltc_position": get_ltc_position(),
            })
            state.last_signal = signal or "None"

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            log_print(f"CRASH: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    log_print("=== HYPERLIQUID LTC BOT STARTED — FLIPPING + TRAILING STOP ===", "INFO")
    log_print(f"Startup USDC Balance: ${get_balance():.2f}", "INFO")

    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000, threaded=True)

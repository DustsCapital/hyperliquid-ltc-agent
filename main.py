# main.py
import threading
import time
import signal
import math  # For ceil
from datetime import datetime, timezone, timedelta
from dashboard import app
from config import *
import state
from exchange import get_balance, get_ltc_position, fetch_ohlcv, exchange
from indicators import detect_cross
from data_collector import collect_all_candles
from logger import log_print
from utils import color_text
from state import total_profit, position_open, position_side, last_signal, cross_history, dashboard_data
from signal import SIGTERM

stop_event = threading.Event()
pending_trade = None
last_price_log = datetime.now(timezone.utc)

# Profit Ratchet
profit_ratchet_active = False
peak_unrealized_profit = 0.0

def signal_handler(sig, frame):
    log_print("Bot stopped by user.", "INFO")
    stop_event.set()
    import os
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(SIGTERM, signal_handler)

def enough_usdt(required):
    free = get_balance()
    needed = required * (1 + FEE_BUFFER_PCT)
    return free >= needed, free

def calculate_dynamic_qty(current_price):
    """Dynamic LTC qty: $TRADE_USDT worth, price ceiled, qty ceiled to ensure >$15 exposure."""
    if current_price <= 0:
        log_print("WARNING: Invalid price for sizing—fallback to 0.01 LTC", "WARNING")
        return 0.01
    
    rounded_price = math.ceil(current_price)  # Ceil to next whole number (e.g., 83.4 → 84, 83.1 → 84)
    qty = TRADE_USDT / rounded_price
    qty_rounded = math.ceil(qty * 100) / 100  # Ceil to 2 decimals (e.g., 0.178 → 0.18)
    
    actual_value = qty_rounded * current_price
    log_print(f"DYNAMIC SIZING: Price ${current_price:.3f} → Ceiled ${rounded_price} → Qty {qty_rounded} LTC (>${actual_value:.2f} exposure)", "DEBUG")
    return qty_rounded

def place_long(qty):
    try:
        result = exchange.market_open(name=SYMBOL, is_buy=True, sz=qty)
        if result.get("status") == "ok":
            for status in result["response"]["data"]["statuses"]:
                if "filled" in status:
                    filled = status["filled"]
                    entry_px = float(filled["avgPx"])
                    log_print(f"BUY LONG FILLED: {qty} LTC @ ${entry_px:.3f}", "INFO")
                    state.last_buy_price = entry_px
                    state.position_open = True
                    state.position_side = "long"
                    state.save_state()
                    state.save_trade("buy", qty, entry_px)
                    return True
            log_print(f"LONG FAILED: {result}", "ERROR")
            return False
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
                    log_print(f"SHORT FILLED: {qty} LTC @ ${entry_px:.3f}", "INFO")
                    state.last_buy_price = entry_px
                    state.position_open = True
                    state.position_side = "short"
                    state.save_state()
                    state.save_trade("short", qty, entry_px)
                    return True
            log_print(f"SHORT FAILED: {result}", "ERROR")
            return False
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
                    state.total_profit += pnl
                    log_print(f"CLOSED {state.position_side.upper()}: {qty} LTC @ ${exit_px:.3f} | PnL: ${pnl:.2f}", "INFO")
                    state.position_open = False
                    state.position_side = None
                    state.last_buy_price = None
                    state.save_state()
                    state.save_trade("close", qty, exit_px)
                    return True
            log_print(f"CLOSE FAILED: {result}", "ERROR")
            return False
        log_print(f"CLOSE FAILED: {result}", "ERROR")
        return False
    except Exception as e:
        log_print(f"CLOSE EXCEPTION: {e}", "ERROR")
        return False

def run_bot():
    global pending_trade, last_price_log, profit_ratchet_active, peak_unrealized_profit
    while not stop_event.is_set():
        try:
            
            df = fetch_ohlcv()
            if df.empty or len(df) < MA_LONG + 20:
                log_print("Not enough data yet, waiting...", "DEBUG")
                time.sleep(CHECK_INTERVAL)
                continue

            # ──────── ADD THIS ENTIRE BLOCK HERE (every 30 sec) ────────
            try:
                # Save 1m, 3m, 5m candles to CSV — this is what creates your files
                collect_all_candles(one_m_df=df)  # we already have fresh 1m data → reuse it
            except Exception as e:
                log_print(f"Candle collection failed: {e}", "WARNING")
            # ──────────────────────────────────────────────────────────────

            current_price = df['close'].iloc[-1]
            signal, trend_str, cross_type = detect_cross(df, state.cross_history, state.last_trend)

            # Price logging
            now = datetime.now(timezone.utc)
            if (now - last_price_log).total_seconds() > PRICE_LOG_INTERVAL:
                log_print(f"PRICE: ${current_price:.3f} | USDC: ${get_balance():.2f} | Pos: {get_ltc_position():.4f} LTC", "INFO")
                last_price_log = now

            # Profit Ratchet (if enabled)
            if PROFIT_RATCHET_ENABLED and state.position_open:
                unrealized = (current_price - state.last_buy_price) * get_ltc_position() if state.position_side == "long" else (state.last_buy_price - current_price) * get_ltc_position()
                if unrealized > MIN_PROFIT_TO_ACTIVATE:
                    profit_ratchet_active = True
                    peak_unrealized_profit = max(peak_unrealized_profit, unrealized)
                    floor = peak_unrealized_profit * (1 - (1 - PROFIT_PROTECTION_FLOOR))  # e.g., keep 70% of peak
                    if unrealized < floor:
                        log_print(f"RATCHET CLOSE: Below floor ${floor:.2f} (peak ${peak_unrealized_profit:.2f})", "INFO")
                        close_position()
                        profit_ratchet_active = False
                        peak_unrealized_profit = 0.0

            # Pending trade execution
            if pending_trade and datetime.now(timezone.utc) > pending_trade["expires"]:
                log_print("Trade expired", "INFO")
                pending_trade = None
            elif pending_trade and not state.position_open:
                qty = pending_trade["qty"]
                success = place_long(qty) if pending_trade["type"] == "long" else place_short(qty)
                if success:
                    pending_trade = None

            # Trend change
            if state.last_trend != trend_str:
                trend_word = "uptrend" if trend_str == "Uptrend" else "downtrend"
                color = "light_green" if trend_str == "Uptrend" else "light_red"
                colored_trend = f"({color_text(trend_word, color)})"
                log_print(f"TREND → {colored_trend}", "INFO")
                state.last_trend = trend_str

            # Signals — DYNAMIC SIZING
            if signal == "buy" and not state.position_open and not pending_trade:
                if enough_usdt(TRADE_USDT)[0]:
                    qty = calculate_dynamic_qty(current_price)
                    pending_trade = {"type": "long", "qty": qty, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print(f"GOLDEN CROSS — PENDING LONG {qty} LTC (>${TRADE_USDT:.2f})", "INFO")

            elif signal == "short" and ALLOW_SHORTS and not state.position_open and not pending_trade:
                if enough_usdt(TRADE_USDT)[0]:
                    qty = calculate_dynamic_qty(current_price)
                    pending_trade = {"type": "short", "qty": qty, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print(f"DEATH CROSS — PENDING SHORT {qty} LTC (>${TRADE_USDT:.2f})", "INFO")

            # Flip — DYNAMIC SIZING
            if state.position_open and ((state.position_side == "long" and signal == "sell") or (state.position_side == "short" and signal == "buy")):
                close_position()
                qty = calculate_dynamic_qty(current_price)
                is_uptrend = df["sma_long"].iloc[-1] > df["sma_long"].iloc[-1 - TREND_LOOKBACK]
                if signal == "sell" and not is_uptrend and ALLOW_SHORTS:
                    log_print(f"FLIPPING TO SHORT {qty} LTC", "INFO")
                    place_short(qty)
                elif signal == "buy" and is_uptrend:
                    log_print(f"FLIPPING TO LONG {qty} LTC", "INFO")
                    place_long(qty)

            # Dashboard
            state.dashboard_data.update({
                "last_update": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "price": current_price,
                "trend": trend_str,
                "usdt_balance": get_balance(),
                "ltc_position": abs(get_ltc_position()),
                "crosses": list(reversed(state.cross_history))
            })
            state.last_signal = signal or "None"

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            log_print(f"CRASH: {e}", "ERROR")
            time.sleep(10)

# START
if __name__ == "__main__":
    log_print("=== HYPERLIQUID LTC BOT STARTED — LIVE TRADING ===", "INFO")
    usdt_balance = get_balance()
    log_print(f"Startup USDC Balance: ${usdt_balance:.2f}", "INFO")
    
    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000, threaded=True)

# main.py - FINAL LIVE VERSION - FIXED SIZE - NO MORE "invalid size" - NOV 2025
import threading
import time
import signal
from datetime import datetime, timezone, timedelta
from dashboard import app
from config import *
import state
from exchange import get_balance, get_ltc_position, fetch_ohlcv, exchange
from indicators import detect_cross
from data_collector import collect_all_candles
from logger import log_print
from utils import color_text

stop_event = threading.Event()
pending_trade = None
last_price_log = datetime.now(timezone.utc)

# Profit Ratchet
profit_ratchet_active = False
peak_unrealized_profit = 0.0

def signal_handler(sig, frame):
    log_print("Bot stopped by user.", "INFO")  # ← Swap print
    stop_event.set()
    import os
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def enough_usdt(required):
    free = get_balance()
    needed = required * (1 + FEE_BUFFER_PCT)
    return free >= needed, free

# FIXED SIZE — NO MORE FLOATING POINT GARBAGE
FIXED_QTY = 0.20  # Configure for yourself

# FINAL WORKING ORDER FUNCTIONS — BULLETPROOF
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
            # No filled status found (partial? rare)
            log_print(f"LONG FAILED: {result}", "ERROR")
            return False
        # Status not "ok"
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
            # No filled status found
            log_print(f"SHORT FAILED: {result}", "ERROR")
            return False
        # Status not "ok"
        log_print(f"SHORT FAILED: {result}", "ERROR")
        return False
    except Exception as e:
        log_print(f"SHORT EXCEPTION: {e}", "ERROR")
        return False

def close_position():
    qty = get_ltc_position()
    if qty < 0.01:
        return False
    try:
        result = exchange.market_close(name=SYMBOL, sz=qty)
        if result.get("status") == "ok":
            current_price = fetch_ohlcv().iloc[-1]["close"]
            profit = (current_price - state.last_buy_price) * qty if state.position_side == "long" else (state.last_buy_price - current_price) * qty
            state.total_profit += profit
            side_msg = "SELL LONG" if state.position_side == "long" else "COVER SHORT"
            log_print(f"{side_msg}: {qty} LTC @ ${current_price:.3f} | Profit: ${profit:.2f} | Total: ${state.total_profit:.2f}", "INFO")
            state.last_buy_price = None
            action = "sell" if state.position_side == "long" else "cover"  # Capture first
            state.save_trade(action, qty, current_price)
            state.position_open = False
            state.position_side = None
            state.save_state()
            return True
        log_print(f"CLOSE FAILED: {result}", "ERROR")
        return False
    except Exception as e:
        log_print(f"CLOSE EXCEPTION: {e}", "ERROR")
        return False

# MAIN LOOP
def run_bot():
    global pending_trade, last_price_log, peak_unrealized_profit, profit_ratchet_active

    while not stop_event.is_set():
        try:
            df = fetch_ohlcv()
            collect_all_candles(one_m_df=df)
            if df.empty or len(df) < MA_LONG:
                time.sleep(CHECK_INTERVAL)
                continue

            current_price = df["close"].iloc[-1]
            signal, trend_str, _ = detect_cross(df, state.cross_history, state.last_trend)

            # Price logging
            if PRICE_LOG_INTERVAL > 0 and (datetime.now(timezone.utc) - last_price_log).total_seconds() >= PRICE_LOG_INTERVAL:
                log_print(f"Current price: ${current_price:.3f}", "INFO")  # set to DEBUG, INFO or warning.
                last_price_log = datetime.now(timezone.utc)

            # Profit ratchet
            if PROFIT_RATCHET_ENABLED and state.position_open:
                qty = get_ltc_position()
                if qty > 0:
                    unrealized = (current_price - state.last_buy_price) * qty if state.position_side == "long" else (state.last_buy_price - current_price) * qty
                    if unrealized > peak_unrealized_profit:
                        peak_unrealized_profit = unrealized
                        if not profit_ratchet_active and unrealized >= MIN_PROFIT_TO_ACTIVATE:
                            profit_ratchet_active = True
                            log_print(f"RATCHET ACTIVATED — Peak: ${peak_unrealized_profit:.2f}", "INFO")
                    if profit_ratchet_active and unrealized <= peak_unrealized_profit * 0.70:
                        log_print(f"RATCHET TRIGGERED — Closing at ${unrealized:.2f}", "INFO")
                        close_position()
                        continue

            # Pending trade execution
            if pending_trade and datetime.now(timezone.utc) > pending_trade["expires"]:
                log_print("Trade expired", "INFO")
                pending_trade = None
            elif pending_trade and not state.position_open:
                success = place_long(pending_trade["qty"]) if pending_trade["type"] == "long" else place_short(pending_trade["qty"])
                if success:
                    pending_trade = None

            # Trend change
            if state.last_trend != trend_str:
                trend_word = "uptrend" if trend_str == "Uptrend" else "downtrend"
                color = "light_green" if trend_str == "Uptrend" else "light_red"
                colored_trend = f"({color_text(trend_word, color)})"
                log_print(f"TREND → {colored_trend}", "INFO")  # ← f-string fixes literal; INFO for visibility
                state.last_trend = trend_str

            # Signals — FIXED SIZE
            if signal == "buy" and not state.position_open and not pending_trade:
                if enough_usdt(15.0)[0]:
                    pending_trade = {"type": "long", "qty": FIXED_QTY, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print("GOLDEN CROSS — PENDING LONG", "INFO")

            elif signal == "short" and ALLOW_SHORTS and not state.position_open and not pending_trade:
                if enough_usdt(15.0)[0]:
                    pending_trade = {"type": "short", "qty": FIXED_QTY, "expires": datetime.now(timezone.utc) + timedelta(minutes=2)}
                    log_print("DEATH CROSS — PENDING SHORT", "INFO")

            # Flip — FIXED SIZE
            if state.position_open and ((state.position_side == "long" and signal == "sell") or (state.position_side == "short" and signal == "buy")):
                close_position()
                is_uptrend = df["sma_long"].iloc[-1] > df["sma_long"].iloc[-1 - TREND_LOOKBACK]
                if signal == "sell" and not is_uptrend and ALLOW_SHORTS:
                    log_print("FLIPPING TO SHORT", "INFO")
                    place_short(FIXED_QTY)
                elif signal == "buy" and is_uptrend:
                    log_print("FLIPPING TO LONG", "INFO")
                    place_long(FIXED_QTY)

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

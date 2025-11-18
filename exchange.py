# main.py
import threading
import time
import signal
from datetime import datetime, timezone, timedelta
from dashboard import app
from config import *
from state import (
    total_profit, last_buy_price, position_open, position_side,
    cross_history, last_signal, last_trend, dashboard_data,
    save_state, save_trade
)
from exchange import get_balance, get_ltc_position, fetch_ohlcv
from indicators import detect_cross

# Import the exchange instance so we can call market_open directly
from exchange import exchange

# PRICE LOG TIMER (every 5 minutes)
last_price_log = datetime.now(timezone.utc)

# Trailing Stop-loss
trail_stop_price = None

# SHUTDOWN CONTROL
stop_event = threading.Event()

# PENDING TRADE (2-minute window)
pending_trade = None

def signal_handler(sig, frame):
    print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Bot stopped by user.")
    stop_event.set()
    import os
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log_print(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")

# ------------------------------------------------------------------ helpers
def enough_usdt(required):
    free = get_balance()
    needed = required * (1 + FEE_BUFFER_PCT)
    return free >= needed, free

def place_long(qty):
    global last_buy_price, trail_stop_price
    result = exchange.market_open(name=SYMBOL, is_buy=True, sz=qty)
    if result and result.get("status") == "ok":
        last_buy_price = fetch_ohlcv().iloc[-1]['close']
        trail_stop_price = last_buy_price * 0.98
        log_print(f"BUY LONG: {qty:.6f} LTC @ ~${last_buy_price:.2f} | TRAIL: ${trail_stop_price:.2f}")
        save_state()
        save_trade("buy", qty, last_buy_price)
        return True
    else:
        log_print(f"LONG FAILED: {result}")
    return False

def place_short(qty):
    global last_buy_price, trail_stop_price
    result = exchange.market_open(name=SYMBOL, is_buy=False, sz=qty)
    if result and result.get("status") == "ok":
        last_buy_price = fetch_ohlcv().iloc[-1]['close']
        trail_stop_price = last_buy_price * 1.02
        log_print(f"OPEN SHORT: {qty:.6f} LTC @ ~${last_buy_price:.2f} | TRAIL: ${trail_stop_price:.2f}")
        save_state()
        save_trade("short", qty, last_buy_price)
        return True
    else:
        log_print(f"SHORT FAILED: {result}")
    return False

def close_position():
    global total_profit, last_buy_price, trail_stop_price
    qty = get_ltc_position()
    if qty < MIN_LTC_SELL:
        return False

    result = exchange.market_close(name=SYMBOL, sz=qty)
    if result and result.get("status") == "ok":
        current_price = fetch_ohlcv().iloc[-1]['close']
        if position_side == "long":
            profit = (current_price - last_buy_price) * qty
            log_print(f"SELL LONG: {qty:.6f} LTC @ ~${current_price:.2f} | Profit: ${profit:.2f} | Total: ${total_profit + profit:.2f}")
        else:
            profit = (last_buy_price - current_price) * qty
            log_print(f"COVER SHORT: {qty:.6f} LTC @ ~${current_price:.2f} | Profit: ${profit:.2f} | Total: ${total_profit + profit:.2f}")
        total_profit += profit
        last_buy_price = None
        trail_stop_price = None
        save_state()
        save_trade("sell" if position_side == "long" else "cover", qty, current_price)
        return True
    else:
        log_print(f"CLOSE FAILED: {result}")
    return False

# ------------------------------------------------------------------ bot loop
def run_bot():
    global position_open, position_side, last_signal, last_trend, pending_trade, trail_stop_price, last_price_log

    log_print("=== HYPERLIQUID LTC BOT STARTED (LONGS + SHORTS ENABLED) ===")
    log_print(f"API Wallet: {API_WALLET_ADDRESS}")
    log_print(f"Initial USDC: ${get_balance():.2f}")

    # Recover position
    actual_ltc = get_ltc_position()
    if actual_ltc > 0.001:
        position_open = True
        position_side = "long"
        last_buy_price = fetch_ohlcv().iloc[-1]['close']
        trail_stop_price = last_buy_price * 0.98
        log_print(f"RECOVERED LONG: {actual_ltc:.6f} LTC")

    while not stop_event.is_set():
        try:
            df = fetch_ohlcv()
            if df.empty or len(df) < MA_LONG:
                time.sleep(CHECK_INTERVAL)
                continue

            current_price = float(df['close'].iloc[-1])
            signal, trend_str, cross_type = detect_cross(df, cross_history, last_trend)

            # ←←← NEW: LOG EVERY CROSS WITH POSITION STATUS ←←←
            if cross_type == 'golden':
                status = "OPEN" if position_open else "FLAT"
                log_print(f"GOLDEN CROSS — Position: {status}")
            elif cross_type == 'death':
                status = "OPEN" if position_open else "FLAT"
                log_print(f"DEATH CROSS — Position: {status}")

            # Trailing stop
            if position_open and trail_stop_price:
                if position_side == "long":
                    new_trail = current_price * 0.98
                    if new_trail > trail_stop_price:
                        trail_stop_price = new_trail
                    if current_price <= trail_stop_price:
                        close_position()
                        position_open = False
                        position_side = None
                        trail_stop_price = None
                else:  # short
                    new_trail = current_price * 1.02
                    if new_trail < trail_stop_price:
                        trail_stop_price = new_trail
                    if current_price >= trail_stop_price:
                        close_position()
                        position_open = False
                        position_side = None
                        trail_stop_price = None

            # Price log
            if (datetime.now(timezone.utc) - last_price_log).total_seconds() >= 300:
                log_print(f"Current price: ${current_price:.2f}")
                last_price_log = datetime.now(timezone.utc)

            # Pending trade handling
            if pending_trade:
                if datetime.now(timezone.utc) > pending_trade['expires']:
                    log_print("Trade window expired")
                    pending_trade = None
                elif pending_trade['type'] == 'long' and signal == 'sell':
                    log_print("Death cross — canceling pending long")
                    pending_trade = None
                elif pending_trade['type'] == 'short' and signal == 'buy':
                    log_print("Golden cross — canceling pending short")
                    pending_trade = None
                elif not position_open:
                    qty = pending_trade['qty']
                    success = place_long(qty) if pending_trade['type'] == 'long' else place_short(qty)
                    if success:
                        position_open = True
                        position_side = pending_trade['type']
                        pending_trade = None

            # Trend change
            if last_trend != trend_str:
                color = "\033[93m" if trend_str == "Downtrend" else "\033[92m"
                reset = "\033[0m"
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] TREND CHANGE → {color}{trend_str}{reset}")
                last_trend = trend_str

            # New signals
            if signal == 'buy' and not position_open and not pending_trade:
                qty = round(TRADE_USDT / current_price, 6)
                if enough_usdt(TRADE_USDT)[0]:
                    pending_trade = {
                        'type': 'long',
                        'qty': qty,
                        'expires': datetime.now(timezone.utc) + timedelta(minutes=2)
                    }
                    log_print("GOLDEN CROSS — PENDING LONG")

            elif signal == 'short' and ALLOW_SHORTS and not position_open and not pending_trade:
                qty = round(TRADE_USDT / current_price, 6)
                if enough_usdt(TRADE_USDT)[0]:
                    pending_trade = {
                        'type': 'short',
                        'qty': qty,
                        'expires': datetime.now(timezone.utc) + timedelta(minutes=2)
                    }
                    log_print("DEATH CROSS — PENDING SHORT")

            # Opposite cross closes position
            if position_open:
                if (position_side == "long" and signal == 'sell') or (position_side == "short" and signal == 'buy'):
                    close_position()
                    position_open = False
                    position_side = None

            # Dashboard
            dashboard_data.update({
                'last_update': datetime.now(timezone.utc).strftime('%H:%M:%S'),
                'price': current_price,
                'trend': trend_str,
                'usdt_balance': get_balance(),
                'ltc_position': abs(get_ltc_position()),
                'crosses': list(reversed(cross_history))
            })
            last_signal = signal or "None"

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            if not stop_event.is_set():
                log_print(f"CRASH: {e}")
            time.sleep(10)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=5000, threaded=True)

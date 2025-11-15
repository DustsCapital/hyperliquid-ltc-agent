# main.py
import threading
import time
import signal
from datetime import datetime, timezone, timedelta
from dashboard import app
from config import *
from state import (
    total_profit, last_buy_price, position_open,
    cross_history, last_signal, last_trend, dashboard_data,
    save_state, save_trade
)
from exchange import (
    get_balance, get_ltc_position, place_buy_order,
    place_sell_order, fetch_ohlcv
)
from indicators import detect_cross

# PRICE LOG TIMER (every 5 minutes)
last_price_log = datetime.now(timezone.utc)

# SHUTDOWN CONTROL
stop_event = threading.Event()

# PENDING TRADE (2-minute window)
pending_trade = None  # {'type': 'buy', 'qty': 0.1, 'price': 97.0, 'expires': datetime}

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

def place_buy(qty):
    global last_buy_price
    if place_buy_order(qty):
        last_buy_price = fetch_ohlcv().iloc[-1]['close']
        log_print(f"BUY: {qty:.6f} LTC @ ~${last_buy_price:.2f}")
        save_state()
        save_trade("buy", qty, last_buy_price)
        return True
    return False

def place_sell(qty):
    global total_profit, last_buy_price
    if place_sell_order(qty):
        sell_price = fetch_ohlcv().iloc[-1]['close']
        profit = (sell_price - last_buy_price) * qty
        total_profit += profit
        log_print(f"SELL: {qty:.6f} LTC @ ~${sell_price:.2f} | Profit: ${profit:.2f} | Total: ${total_profit:.2f}")
        last_buy_price = None
        save_state()
        save_trade("sell", qty, sell_price)
        return True
    return False

# ------------------------------------------------------------------ bot loop
def run_bot():
    global position_open, last_signal, last_trend, pending_trade, last_price_log

    log_print("=== HYPERLIQUID LTC BOT STARTED ===")
    log_print(f"API Wallet: {API_WALLET_ADDRESS}")
    log_print(f"Initial USDC: ${get_balance():.2f}")

    # RECOVER POSITION
    actual_ltc = get_ltc_position()
    if actual_ltc > 0.001 and not position_open:
        log_print(f"RECOVERED OPEN POSITION: {actual_ltc:.6f} LTC")
        position_open = True
        last_buy_price = fetch_ohlcv().iloc[-1]['close']
    elif actual_ltc == 0 and position_open:
        log_print("CLOSED POSITION DETECTED — resetting")
        position_open = False
        last_buy_price = None
        save_state()

    while not stop_event.is_set():
        try:
            df = fetch_ohlcv()
            if df.empty or len(df) < MA_LONG:
                log_print("Waiting for sufficient candle data...")
                time.sleep(CHECK_INTERVAL)
                continue

            current_price = float(df['close'].iloc[-1])

            # PRICE LOG EVERY 5 MINUTES
            if (datetime.now(timezone.utc) - last_price_log).total_seconds() >= 300:
                log_print(f"Current price: ${current_price:.2f}")
                last_price_log = datetime.now(timezone.utc)

            signal, trend_str, cross_type = detect_cross(df, cross_history, last_trend)

            # LOG EVERY CROSS
            if signal == 'buy':
                log_print("GOLDEN CROSS")
            elif signal == 'sell':
                log_print("DEATH CROSS")

            # PENDING TRADE: retry every 30s for 2 min
            if pending_trade:
                if datetime.now() > pending_trade['expires']:
                    log_print("Trade window expired")
                    pending_trade = None
                elif signal == 'sell' and pending_trade['type'] == 'buy':
                    log_print("Death cross — canceling pending buy")
                    pending_trade = None
                elif not position_open and pending_trade['type'] == 'buy':
                    qty = pending_trade['qty']
                    if enough_usdt(TRADE_USDT)[0] and place_buy(qty):
                        position_open = True
                        pending_trade = None

            # TREND CHANGE
            if last_trend != trend_str:
                color = "\033[93m" if trend_str == "Downtrend" else "\033[92m"
                reset = "\033[0m"
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] TREND CHANGE → {color}{trend_str}{reset}")
                last_trend = trend_str

            # NEW BUY SIGNAL
            if signal == 'buy' and not position_open and not pending_trade:
                qty = TRADE_USDT / current_price
                if enough_usdt(TRADE_USDT)[0]:
                    pending_trade = {
                        'type': 'buy',
                        'qty': qty,
                        'price': current_price,
                        'expires': datetime.now() + timedelta(minutes=2)
                    }
                    log_print(f"GOLDEN CROSS — PENDING BUY in 2 min window")
                else:
                    log_print("BUY signal but low USDC")

            # SELL SIGNAL
            elif signal == 'sell' and position_open:
                qty = get_ltc_position()
                if qty >= MIN_LTC_SELL and place_sell(qty):
                    position_open = False

            # DASHBOARD UPDATE
            dashboard_data.update({
                'last_update': datetime.now(timezone.utc).strftime('%H:%M:%S'),
                'price': current_price,
                'trend': trend_str,
                'usdt_balance': get_balance(),
                'ltc_position': get_ltc_position(),
                'crosses': list(reversed(cross_history))  # ← REVERSE HERE
            })
            last_signal = signal or "None"

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            if not stop_event.is_set():
                log_print(f"CRASH: {e}")
            time.sleep(10)

# ------------------------------------------------------------------ entry
if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    try:
        # SILENCE FLASK "GET /" LOGS
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Bot stopped by user.")
        stop_event.set()
        bot_thread.join(timeout=2)
        print("Process terminated.")
        import os
        os._exit(0)

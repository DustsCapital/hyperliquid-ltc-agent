# main.py — (December 2025)

import threading
import time
import signal
import math
import pandas as pd
from datetime import datetime, timezone, timedelta

from dashboard import app
from config import *
import state
from exchange import get_balance, get_position, fetch_ohlcv, exchange, get_unrealized_pnl
from indicators import detect_cross
from data_collector import collect_all_candles
from logger import log_print

from state import total_profit, position_open, position_side, last_signal, cross_history, dashboard_data

# === NEW: Info instance to read metadata & leverage ===
from hyperliquid.info import Info
info = Info(BASE_URL, skip_ws=True)

# === FETCH ASSET PRECISION ONCE AT START ===
meta = info.meta()
asset_info = next(a for a in meta['universe'] if a['name'] == SYMBOL)
SZ_DECIMALS = int(asset_info['szDecimals'])           # e.g. 2 for LTC, 5 for BTC
MIN_SIZE = float(asset_info.get('minSize', 0.001))

# === DYNAMIC LEVERAGE DETECTION ===
def get_current_leverage():
    """Reads the actual leverage you have set in Hyperliquid (no hardcoding)"""
    try:
        user_state = info.user_state(API_WALLET_ADDRESS)
        # If position exists → use position-specific leverage
        for pos in user_state.get("assetPositions", []):
            if pos["position"]["coin"] == SYMBOL:
                return int(pos["position"]["leverage"]["value"])
        # Otherwise use account-wide cross leverage
        acc_lev = user_state.get("marginSummary", {}).get("accountLeverage")
        return int(acc_lev) if acc_lev else 1
    except:
        return 1

current_leverage = get_current_leverage()
log_print(f"Detected current leverage: {current_leverage}× (from Hyperliquid)", "INFO")

# === CORRECTED FUNCTIONS ===
def enough_usdt(required_notional):
    """Check if we have enough margin using REAL leverage"""
    free = get_balance()
    needed_margin = (required_notional / current_leverage) * (1 + FEE_BUFFER_PCT)
    enough = free >= needed_margin
    if not enough:
        log_print(f"Insufficient margin: need ${needed_margin:.2f}, have ${free:.2f} @ {current_leverage}×", "WARNING")
    return enough, free

def calculate_dynamic_qty(current_price):
    """Round quantity to correct decimals using asset metadata"""
    if current_price <= 0:
        return MIN_SIZE
    raw_qty = TRADE_USDT / current_price
    qty = round(raw_qty, SZ_DECIMALS)
    return max(MIN_SIZE, qty)

def place_long(qty):
    result = exchange.market_open(SYMBOL, True, qty)
    if result and result.get("status") == "ok":
        for s in result["response"]["data"]["statuses"]:
            if "filled" in s:
                entry_px = float(s["filled"]["avgPx"])
                log_print(f"LONG OPENED ✅ {qty} {SYMBOL} @ ${entry_px:.3f}", "INFO")
                state.last_buy_price = entry_px
                state.position_open = True
                state.position_side = "long"
                state.save_state()
                state.save_trade("buy", qty, entry_px)
                return True
    log_print(f"LONG FAILED: {result}", "ERROR")
    return False

def place_short(qty):
    result = exchange.market_open(SYMBOL, False, qty)
    if result and result.get("status") == "ok":
        for s in result["response"]["data"]["statuses"]:
            if "filled" in s:
                entry_px = float(s["filled"]["avgPx"])
                log_print(f"SHORT OPENED ✅ {qty} {SYMBOL} @ ${entry_px:.3f}", "INFO")
                state.last_buy_price = entry_px
                state.position_open = True
                state.position_side = "short"
                state.save_state()
                state.save_trade("short", qty, entry_px)
                return True
    log_print(f"SHORT FAILED: {result}", "ERROR")
    return False

def close_position():
    result = exchange.market_close(SYMBOL)
    if result and result.get("status") == "ok":
        for s in result["response"]["data"]["statuses"]:
            if "filled" in s:
                exit_px = float(s["filled"]["avgPx"])
                qty = float(s["filled"]["totalSz"])
                pnl = (exit_px - state.last_buy_price) * qty if state.position_side == "long" else (state.last_buy_price - exit_px) * qty

                if pnl > 0:
                    log_print(f"POSITION CLOSED ✅ {qty} {SYMBOL} @ ${exit_px:.3f} → PROFIT ${pnl:+.2f} 🎉", "INFO")
                else:
                    log_print(f"POSITION CLOSED ❌ {qty} {SYMBOL} @ ${exit_px:.3f} → ${pnl:+.2f}", "INFO")

                state.total_profit += pnl
                state.save_trade("close", qty, exit_px)
                state.position_open = False
                state.position_side = None
                state.save_state()
                return True
    log_print(f"CLOSE FAILED: {result}", "ERROR")
    return False

# === REST OF BOT (unchanged except tiny fixes) ===
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

            # Price log
            if PRICE_LOG_INTERVAL > 0 and (datetime.now(timezone.utc) - last_price_log).total_seconds() >= PRICE_LOG_INTERVAL:
                rsi_val = df['rsi'].iloc[-1] if 'rsi' in df.columns else 0.0
                pnl_pct, pnl_usd = get_unrealized_pnl() if state.position_open else (0.0, 0.0)
                log_print(f"Price ${current_price:.3f} │ RSI {rsi_val:.1f} │ Balance: ${get_balance():.2f} │ Pos: {get_position():.4f} {SYMBOL} │ PnL: {pnl_pct:+.1f}% │ {trend_str}")
                last_price_log = datetime.now(timezone.utc)

            # Trailing PnL stop (unchanged)
            if TRAILING_PNL_ENABLED and state.position_open:
                qty = get_position()
                if qty >= MIN_SIZE:
                    current_pnl_pct, _ = get_unrealized_pnl()
                    if not hasattr(state, 'peak_pnl_pct') or current_pnl_pct > state.peak_pnl_pct:
                        state.peak_pnl_pct = current_pnl_pct
                    if current_pnl_pct <= state.peak_pnl_pct + TRAILING_PNL_PCT:
                        log_print(f"TRAILING STOP HIT @ {current_pnl_pct:+.1f}%", "INFO")
                        close_position()

            # Close on opposite signal
            if state.position_open:
                if (state.position_side == "long" and signal == "short") or \
                   (state.position_side == "short" and signal == "buy"):
                    close_position()

            # Open new position
            if not state.position_open and signal in ("buy", "short"):
                qty = calculate_dynamic_qty(current_price)
                side = "long" if signal == "buy" else "short"
                pending_trade = {
                    "type": side,
                    "qty": qty,
                    "expires": datetime.now(timezone.utc) + timedelta(minutes=2)
                }
                log_print(f"GOLDEN/DEATH CROSS — PENDING {side.upper()} {qty} {SYMBOL}", "INFO")

            # Execute pending trade instantly if possible
            if pending_trade and datetime.now(timezone.utc) < pending_trade["expires"]:
                qty = pending_trade["qty"]
                if pending_trade["type"] == "long" and enough_usdt(TRADE_USDT)[0]:
                    place_long(qty)
                    pending_trade = None
                elif pending_trade["type"] == "short" and enough_usdt(TRADE_USDT)[0]:
                    place_short(qty)
                    pending_trade = None
            elif pending_trade:
                log_print("PENDING TRADE EXPIRED", "WARNING")
                pending_trade = None

            # Dashboard update
            state.dashboard_data.update({
                "last_update": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "price": current_price,
                "trend": trend_str,
                "usdt_balance": get_balance(),
                "ltc_position": get_position(),
            })
            state.last_signal = signal or "None"

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            log_print(f"CRASH: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    log_print("=== HYPERLIQUID BOT STARTED — UNIVERSAL + DYNAMIC LEVERAGE ===", "INFO")
    log_print(f"Startup Balance: ${get_balance():.2f} | Leverage: {current_leverage}× | Symbol: {SYMBOL}", "INFO")

    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000, threaded=True)

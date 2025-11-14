# state.py
import json
import os
from datetime import datetime

SAVES_DIR = "saves"
STATE_FILE = os.path.join(SAVES_DIR, "state.json")
TRADES_FILE = os.path.join(SAVES_DIR, "trades.json")
CROSS_FILE = os.path.join(SAVES_DIR, "crosses.json")

# Load crosses
if os.path.exists(CROSS_FILE):
    with open(CROSS_FILE, 'r') as f:
        cross_history = json.load(f)
else:
    cross_history = []

# Save crosses
def save_crosses():
    # Always save full list (or last MAX_CROSSES)
    data_to_save = cross_history[-MAX_CROSSES:] if len(cross_history) > MAX_CROSSES else cross_history
    with open(CROSS_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=2)

os.makedirs(SAVES_DIR, exist_ok=True)

default_state = {
    "position_open": False,
    "last_buy_price": None,
    "total_profit": 0.0
}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, 'r') as f:
        data = json.load(f)
    total_profit = data.get("total_profit", 0.0)
    last_buy_price = data.get("last_buy_price")
    position_open = data.get("position_open", False)
else:
    total_profit = 0.0
    last_buy_price = None
    position_open = False
    with open(STATE_FILE, 'w') as f:
        json.dump(default_state, f, indent=2)

if os.path.exists(TRADES_FILE):
    with open(TRADES_FILE, 'r') as f:
        trades = json.load(f)
else:
    trades = []
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def save_state():
    state = {
        "position_open": position_open,
        "last_buy_price": last_buy_price,
        "total_profit": total_profit
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def save_trade(action, qty, price):
    trade = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "ltc": round(qty, 6),
        "price": round(price, 2),
        "value_usd": round(qty * price, 2)
    }
    trades.append(trade)
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

cross_history = []
last_signal = "None"
last_trend = None

dashboard_data = {
    'last_update': None,
    'price': 0.0,
    'trend': 'Unknown',
    'usdt_balance': 0.0,
    'ltc_position': 0.0,
}

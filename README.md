# HyperLiquid LTC Bot

Live LTC/USDT perp trading bot with:
- $10 trades (configurable)
- 1x leverage
- SMA50/200 + RSI + Trend filter
- Persistent state (`saves/state.json`)
- Trade history (`saves/trades.json`)
- Real-time dashboard
- Clean shutdown

## Setup

```bash
git clone https://github.com/DustsCapital/hyperliquid-ltc-agent
cd hyperliquid-ltc-agent
python run.py
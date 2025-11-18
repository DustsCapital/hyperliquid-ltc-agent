# dashboard.py
from flask import Flask, render_template_string, request
import subprocess
from state import total_profit, position_open, last_signal, cross_history, dashboard_data, cross_history, position_side

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html><head><title>LTC Bot</title>
<meta http-equiv="refresh" content="30">
<style>
  body {
    font-family: 'Courier New', monospace;
    margin: 2rem;
    background: #000000;
    color: #ffffff;
    line-height: 1.6;
  }
  .card {
    background: #111111;
    padding: 1.2rem;
    margin: 1.5rem 0;
    border-radius: 10px;
    border: 1px solid #333333;
    box-shadow: 0 4px 12px rgba(255, 255, 255, 0.1);
  }
  h1 {
    color: #ffffff; /* ← AQUA → WHITE */
    text-align: center;
    font-size: 2.2rem;
    font-weight: bold;
  }
  p {
    margin: 0.6rem 0;
    font-size: 1.1rem;
    color: #ffffff;
  }
  strong {
    color: #ffffff; /* ← ALL LABELS WHITE */
  }
  /* STATUS & PROFIT KEEP COLORS */
  span[style*="green"], span[style*="red"] {
    font-weight: bold;
  }
  /* TREND COLORS */
  span[style*="#00FFFF"], span[style*="#FFFF00"] {
    font-weight: bold;
  }
  /* REFRESH BUTTON: GREY + BLACK TEXT */
  button {
    background: #666666;
    color: #000000;
    border: 1px solid #888888;
    padding: 0.7rem 1.5rem;
    font-size: 1rem;
    font-weight: bold;
    border-radius: 6px;
    cursor: pointer;
    transition: 0.3s;
  }
  button:hover {
    background: #888888;
    border-color: #aaaaaa;
  }
  ul {
    padding-left: 1.5rem;
  }
  li {
    margin: 0.4rem 0;
    color: #cccccc;
  }
</style>
</head><body>
<div class="card"><h1>LTC/USDT Bot</h1></div>

<div class="card">
  <p><strong>Status:</strong> <span style="color:{{ 'green' if status=='RUNNING' else 'red' }};">{{ status }}</span></p>
  <p><strong>Price:</strong> ${{ (price|round(2)) if price else '-.--' }}</p>
  <p><strong>Trend:</strong> <span style="color: {{ '#00FFFF' if trend == 'Uptrend' else '#FFFF00' }}; font-weight: bold;">{{ trend }}</span></p>
  <p><strong>USDC Balance:</strong> ${{ (usdt_balance|round(2)) if usdt_balance is not none else '0.00' }}</p>
  <p><strong>LTC Position:</strong> {{ (ltc_position|round(6)) if ltc_position else '0.000000' }} LTC</p>
  <p><strong>Position:</strong> {{ position }}</p>
  <p><strong>Total Profit:</strong> <span style="color:{{ 'green' if profit>=0 else 'red' }};">${{ (profit|round(2)) if profit is not none else '0.00' }}</span></p>
  <p><strong>Last Signal:</strong> {{ signal }}</p>
  <p><strong>Last Update:</strong> {{ last_update }} UTC</p>
</div>

<div class="card"><h2>Recent Crosses</h2>
<ul>
{% for c in crosses %}
  <li>
    <strong>{{ c.type|capitalize }}</strong> 
    @ {{ c.time }} — ${{ (c.price|round(2)) if c.price else '-.--' }}
    <span style="color: {{ '#00FFFF' if c.trend == 'Uptrend' else '#FFFF00' }}; font-weight: bold;">
      ({{ c.trend }})
    </span>
  </li>
{% endfor %}
</ul></div>

<button onclick="location.reload()">Refresh Now</button>
</body></html>
"""

@app.route('/')
def index():
    try:
        ps_output = subprocess.check_output(['ps', 'aux']).decode()
        is_running = 'main.py' in ps_output
    except:
        is_running = False
    status = "RUNNING" if is_running else "STOPPED"
    pos = "LONG" if position_open and position_side == "long" else \
      "SHORT" if position_open and position_side == "short" else "FLAT"

# REVERSE CROSSES: NEWEST AT TOP
    crosses = list(reversed(cross_history))

    return render_template_string(
        HTML,
        status=status,
        profit=total_profit,
        position=pos,
        signal=last_signal,
        **dashboard_data
    )

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ADD THIS EXACT BLOCK AT THE END OF THE FILE
@app.route('/shutdown', methods=['GET'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

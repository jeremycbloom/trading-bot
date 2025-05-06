import os
import json
import time
from datetime import datetime, timezone
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

# Load Binance credentials from environment
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# Config
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_1MINUTE
rsi_period = 14
rsi_buy_threshold = 30
stop_loss_pct = 0.10
take_profit_pct = 0.05
trade_amount_usdt = 100
daily_limit_usdt = 1000
quantity = 0.001  # Adjust to your desired BTC size
log_file = "streamlit-dashboard/trade_log.json"

# State
state = "ready_to_buy"
buy_price = None
daily_spend = 0

# Utils
def get_closes():
    klines = client.get_klines(symbol=symbol, interval=interval, limit=100)
    return [float(k[4]) for k in klines]

def calculate_rsi(closes):
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-rsi_period:]) / rsi_period
    avg_loss = sum(losses[-rsi_period:]) / rsi_period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def place_buy_order(amount):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    return float(order["fills"][0]["price"])

def place_partial_sell_order(price, pct):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    return float(order["fills"][0]["price"])

def log_trade(trade_data):
    try:
        with open(log_file, "r") as f:
            trades = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        trades = []
    trades.append(trade_data)
    with open(log_file, "w") as f:
        json.dump(trades, f, indent=4)

# Main loop
while True:
    closes = get_closes()
    current_price = closes[-1]
    rsi = calculate_rsi(closes)

    print(f"🕒 {datetime.now(timezone.utc).isoformat()} | Price: ${current_price:.2f} | RSI: {rsi:.2f} | State: {state}", flush=True)
    print(f"💰 24hr Spend Total: ${daily_spend:.2f}", flush=True)

    if state == "ready_to_buy" and rsi < rsi_buy_threshold and (daily_spend + trade_amount_usdt) <= daily_limit_usdt:
        buy_price = place_buy_order(trade_amount_usdt)
        daily_spend += trade_amount_usdt
        state = "holding"
        print(f"🟢 Bought at ${buy_price}", flush=True)

    elif state == "holding":
        if current_price <= buy_price * (1 - stop_loss_pct):
            sell_price = place_partial_sell_order(buy_price, 1)
            profit = (sell_price - buy_price) * (trade_amount_usdt / buy_price)
            log_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit": round(profit, 2)
            })
            state = "ready_to_buy"
            print(f"🔻 Stop-loss triggered. Sold at ${sell_price}", flush=True)

        elif current_price >= buy_price * (1 + take_profit_pct):
            sell_price = place_partial_sell_order(buy_price, take_profit_pct)
            profit = (sell_price - buy_price) * (trade_amount_usdt / buy_price)
            log_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit": round(profit, 2)
            })
            state = "ready_to_buy"
            print(f"🚀 Take-profit triggered. Sold at ${sell_price}", flush=True)

        else:
            print("📊 Holding position...", flush=True)

    time.sleep(60)

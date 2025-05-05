import ccxt
import pandas as pd
import time
import os
from dotenv import load_dotenv
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# Connect to Binance.US
exchange = ccxt.binanceus({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
})

# Bot configuration
symbol = "BTC/USDT"
rsi_buy = 30
timeframe = "1h"
limit = 200
trade_usdt_amount = 100
daily_usdt_limit = 1000
stop_loss_pct = 0.10
take_profit_pct = 0.05
check_interval = 60  # in seconds

# Track USDT spent over the last 24 hours
trade_log = []

# Functions
def current_spend():
    cutoff = datetime.utcnow() - timedelta(hours=24)
    return sum(t["amount"] for t in trade_log if t["timestamp"] > cutoff)

def log_trade(usdt_amount):
    trade_log.append({
        "timestamp": datetime.utcnow(),
        "amount": usdt_amount
    })

def fetch_price():
    return exchange.fetch_ticker(symbol)['last']

def place_buy(usdt_amount):
    price = fetch_price()
    amount = round(usdt_amount / price, 6)
    order = exchange.create_market_buy_order(symbol, amount)
    print(f"✅ BUY: {amount} BTC @ ${price:.2f}")
    log_trade(usdt_amount)
    return amount, price

def place_partial_sell(btc_total, entry_price, current_price):
    gain_pct = (current_price - entry_price) / entry_price
    if gain_pct < take_profit_pct:
        return False

    profit_usdt = trade_usdt_amount * gain_pct
    sell_amount = round(profit_usdt / current_price, 6)
    sell_amount = min(sell_amount, btc_total)

    if sell_amount < 0.00001:
        print("⚠️ Profit too small to sell.")
        return False

    exchange.create_market_sell_order(symbol, sell_amount)
    print(f"💰 TAKE-PROFIT: Sold {sell_amount} BTC (≈ ${profit_usdt:.2f})")
    return sell_amount

def fetch_ohlcv():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def stop_loss_hit(entry, current):
    return current <= entry * (1 - stop_loss_pct)

# Main loop
print("🚀 Starting RSI Bot — Live Trading w/ Stop-Loss, Profit-Take & 24hr Cap")
state = "ready_to_buy"
btc_balance = 0
entry_price = 0

while True:
    try:
        df = fetch_ohlcv()
        rsi = RSIIndicator(close=df['close'], window=14).rsi().iloc[-1]
        current_price = df['close'].iloc[-1]
        print(f"\n⏱ {datetime.utcnow().isoformat()} | Price: ${current_price:.2f} | RSI: {rsi:.2f} | State: {state}")

        spent_today = current_spend()
        print(f"📊 24hr Spend Total: ${spent_today:.2f}")

        if state == "ready_to_buy":
            if spent_today + trade_usdt_amount > daily_usdt_limit:
                print("⛔ Skipping buy — 24hr spend limit reached.")
            elif rsi < rsi_buy:
                btc_balance, entry_price = place_buy(trade_usdt_amount)
                state = "holding"
            else:
                print("⏸ No buy signal...")

        elif state == "holding":
            if stop_loss_hit(entry_price, current_price):
                exchange.create_market_sell_order(symbol, btc_balance)
                print(f"🛑 STOP-LOSS: Sold {btc_balance} BTC @ ${current_price:.2f}")
                btc_balance = 0
                state = "ready_to_buy"
            else:
                sold = place_partial_sell(btc_balance, entry_price, current_price)
                if sold:
                    btc_balance -= sold

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    time.sleep(check_interval)
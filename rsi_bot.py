from datetime import datetime, timedelta, timezone
import time
import os
import ccxt
import pytz

# Load environment variables
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

exchange = ccxt.binanceus({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

symbol = 'BTC/USDT'
timeframe = '1m'
rsi_period = 14
check_interval = 60
trade_amount_usdt = 100
stop_loss_pct = 0.10
take_profit_pct = 0.05
daily_limit_usdt = 1000

trade_log = []

def fetch_rsi():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
    closes = [x[4] for x in ohlcv]
    deltas = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    avg_gain = sum(gains[-rsi_period:]) / rsi_period
    avg_loss = sum(losses[-rsi_period:]) / rsi_period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_current_price():
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']

def place_buy_order(amount):
    print(f"🟢 Placing buy for ${amount} USDT of BTC", flush=True)
    order = exchange.create_market_buy_order(symbol, amount / get_current_price())
    return get_current_price()

def place_partial_sell_order(buy_price, take_profit_pct):
    sell_amount = trade_amount_usdt * take_profit_pct / get_current_price()
    print(f"🔼 Selling ${trade_amount_usdt * take_profit_pct:.2f} profit (partial) at profit target", flush=True)
    order = exchange.create_market_sell_order(symbol, sell_amount)
    return order

def get_total_spent_24h():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return sum([amt for ts, amt in trade_log if ts > cutoff])

def main():
    print("🚀 Starting RSI Bot — Live Trading w/ Stop-Loss, Profit-Take & 24hr Cap", flush=True)
    state = 'ready_to_buy'
    buy_price = 0.0

    while True:
        try:
            current_price = get_current_price()
            rsi = fetch_rsi()
            spend_total = get_total_spent_24h()
            print(f"\n⏱ {datetime.now(timezone.utc).isoformat()} | Price: ${current_price:.2f} | RSI: {rsi:.2f} | State: {state}", flush=True)
            print(f"📊 24hr Spend Total: ${spend_total:.2f}", flush=True)

            if state == 'ready_to_buy' and rsi < 30 and spend_total + trade_amount_usdt <= daily_limit_usdt:
                buy_price = place_buy_order(trade_amount_usdt)
                trade_log.append((datetime.now(timezone.utc), trade_amount_usdt))
                state = 'holding'
            elif state == 'holding':
                if current_price <= buy_price * (1 - stop_loss_pct):
                    print(f"🔻 Price dropped to stop-loss level (${current_price:.2f}) — exiting position", flush=True)
                    state = 'ready_to_buy'
                elif current_price >= buy_price * (1 + take_profit_pct):
                    place_partial_sell_order(buy_price, take_profit_pct)
                    state = 'ready_to_buy'
                else:
                    print("⏳ Holding position...", flush=True)
            else:
                print("⏸ No buy signal...", flush=True)

            time.sleep(check_interval)
        except Exception as e:
            print(f"❌ Error: {str(e)}", flush=True)
            time.sleep(10)

main()

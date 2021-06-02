
import ccxt
import config
import schedule
import time
import numpy as np
import pandas as pd
pd.set_option("display.max_rows", None)

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime

exchange_id = 'binance'
exchange_class = getattr(ccxt, exchange_id)
exchange = exchange_class({
    'apiKey': config.BINANCE_API_KEY,
    'secret': config.BINANCE_SECRET_KEY,
})

balance = exchange.fetch_balance()

def tr(df):
    df['previous_close'] = df['close'].shift(1)
    df['high-low'] = df['high'] - df['low']
    df['high-pc'] = abs(df['high'] - df['previous_close'])
    df['low-pc'] = abs(df['low'] - df['previous_close'])
    tr = df[['high-low', 'high-pc', 'low-pc']].max(axis=1)
    return tr

def atr(df, period):
    df['tr'] = tr(df)
    the_atr = df['tr'].rolling(period).mean()
    return the_atr


#basic upper band = (high + low) / 2) + (multiplier * atr)
#basic upper band = (high + low) / 2) - (multiplier * atr)
def supertrend(df, period=7, mulitplier=3):
    highLowHalf = (df['high'] + df['low'])
    df['atr'] = atr(df, period)
    df['upperband'] = highLowHalf + (mulitplier * df['atr'])
    df['lowerband'] = highLowHalf - (mulitplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]
            
            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]

    return df

in_position = False

def check_buy_sell_signals(df):
    global in_position

    print("checking for buy and sell signals")
    print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("change to uptrend, buy")
        if not in_position:
            order = exchange.create_market_buy_order('ETH/USDT', 0.01)
            print(order)
            in_position = True
        else:
            print("already in position, nothing to do")

    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("change to downtrend, sell")
            order = exchange.create_market_sell_order('ETH/USDT', 0.01)
            print(order)
            in_position = False
        else:
            print("You aren't in position, nothing to sell")

def run():
    print(f"Fetching new bars for {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv('ETH/USDT', timeframe='1m', limit=100)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    supertrend_data = supertrend(df)
    check_buy_sell_signals(supertrend_data)

schedule.every(10).seconds.do(run)

while True:
    schedule.run_pending()
    time.sleep(1)
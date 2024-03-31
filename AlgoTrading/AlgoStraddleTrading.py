import os
os.chdir(r'C:\Users\Xzavier\Documents\SpringIEOR\PersonalProject'.replace('\\', '/'))
import sys
sys.path.append(os.getcwd())

import numpy as np
import pandas as pd
import re
from datetime import datetime, timedelta

from tensorflow.keras.models import load_model

from alpaca.data.historical.option import *
from alpaca.trading.client import *
from alpaca.trading.requests import *
from alpaca.data import StockHistoricalDataClient, TimeFrame
from alpaca.data.requests import StockQuotesRequest, StockBarsRequest

import config
from Greeks import *
from OptionPortfolio import OptionPortfolio

import schedule
import time

api_key = config.API_KEY
secret_key = config.SECRET_KEY

paper = True
trade_client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper, url_override=None)
data_client = StockHistoricalDataClient(api_key, secret_key)
option_historical_data_client = OptionHistoricalDataClient(api_key, secret_key, url_override=None)

all_straddles = []

def sell_old_straddles():
    # Sell straddles older than day limit
    for straddle in all_straddles:
        straddle['days_left'] -= 1
        
        if straddle['days_left'] == 0:
            req = MarketOrderRequest(
            symbol=straddle['call_id'],
            qty=1,
            side=OrderSide.SELL,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            )
            res = trade_client.submit_order(req)

            req = MarketOrderRequest(
                symbol=straddle['put_id'],
                qty=1,
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )
            res = trade_client.submit_order(req)

def predict_vol():
    # get data for prediction

    st = datetime.today() - timedelta(days = 21)
    et = datetime.today()
    request_params = StockBarsRequest(
        symbol_or_symbols=['NVDA'],
        timeframe = TimeFrame.Day,
        start = st,
        end = et
        )

    bars_df = data_client.get_stock_bars(request_params).df.tz_convert('America/New_York', level=1)
    new_df = bars_df.reset_index(['symbol', 'timestamp'])
    new_df['timestamp'] = new_df['timestamp'].astype(str)
    new_df['return'] = 100*new_df['close'].pct_change()
    new_df['vol'] = new_df['return'].rolling(window=7).std()

    # load pretrained model
    model1 = load_model(r'C:\Users\Xzavier\Documents\SpringIEOR\PersonalProject\Models\LSTM_3dayVol.keras'.replace('\\', '/'))

    # make vol prediction
    past_vol = np.expand_dims(new_df['vol'].tail(7), axis=0)
    pred_vol = np.sqrt(365)*model1.predict(past_vol).flatten()[0]

    return pred_vol

def get_option_chain():
    
    req = OptionChainRequest(underlying_symbol='NVDA')
    chain = option_historical_data_client.get_option_chain(req)

    return chain

def identify_undervalued_straddles(pred_vol, chain):

    calls = [call for call in list(chain.keys()) if call[10] == 'C']
    st = datetime.today() - timedelta(days = 7)
    et = datetime.today()
    request_params = StockBarsRequest(
        symbol_or_symbols=['NVDA'],
        timeframe = TimeFrame.Minute,
        start = st,
        end = et
        )

    bars_df = data_client.get_stock_bars(request_params).df.tz_convert('America/New_York', level=1)
    S = list(bars_df.close)[-1]
    r = 0.0533
    q = 0
    today_string = datetime.strftime(datetime.today(), '%Y/%m/%d')

    contracts = list(chain.keys())

    undervalued_straddles = []
    min_expiry = datetime.today()+timedelta(days = 3)
    for call in calls:
        put = call[:10] + 'P' + call[11:]
        if put not in contracts:
            continue

        strike = int(call[-8:])/1000
        if np.abs((strike-S)/S) > .01:
            continue

        expiry = datetime.strptime(call[4:10], '%y%m%d')
        if min_expiry > expiry:
            continue

        call_price = chain[call].latest_quote.ask_price
        put_price = chain[put].latest_quote.ask_price
        try:
            port = OptionPortfolio('NVDA', S, r, q, today_string)
            port.add_option(call, call_price, 'Buy')
            port.add_option(put, put_price, 'Buy')
        except Exception as e:
            if np.abs(strike/S - 1) < .5:
                print(call, e)
                print('Moneyness:', strike/S)
                print('Price:', call_price)

        #print(port.option_greeks)
        call_vol = port.option_greeks['Implied Vol'][0]
        put_vol = port.option_greeks['Implied Vol'][1]
        if (call_vol < pred_vol/1) and (put_vol < pred_vol/1):
            undervalued_straddles.append({'call_id': call, 'put_id': put, 'call_price': call_price, 
                                            'put_price': put_price,'greeks': port.portfolio_greeks,
                                            'days_left': 3})
    return undervalued_straddles

def buy_target_straddles(target_straddles):
    # put in market orders for given straddles

    for straddle in target_straddles:

        req = MarketOrderRequest(
            symbol=straddle['call_id'],
            qty=1,
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
        res = trade_client.submit_order(req)

        req = MarketOrderRequest(
            symbol=straddle['put_id'],
            qty=1,
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
        res = trade_client.submit_order(req)

def straddle_trading():
    sell_old_straddles()
    pred_vol = predict_vol()
    chain = get_option_chain()
    undervalued_straddles = identify_undervalued_straddles(pred_vol, chain)

    # filter out straddles with large deltas
    target_straddles = [strad for strad in undervalued_straddles if np.abs(strad['greeks'][1]*1e3) < 10]
    print('Predicted Vol:', pred_vol)
    print('Put in market orders for:', target_straddles)
    buy_target_straddles(target_straddles)

schedule.every().day.at("05:16").do(straddle_trading)

while True:
    schedule.run_pending()
    time.sleep(60) # wait one minute
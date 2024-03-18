from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.stream import TradingStream
import config
from collections import deque
from alpaca.data.live import CryptoDataStream
import threading

# This was an exercise for a class to build a trading algorithm
# That could listen to a data stream and execute trades (via Alpaca)
# Based onn some naive strategy using live data

# In this case, we're trading BTC based on signals from two moving averages

client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
account = dict(client.get_account())

current_cash = float(account['cash'])
init_port_val = float(account['portfolio_value'])
cash_spent = 0 # by buying
cash_received = 0 # from selling
qty_owned_this_session = 0
print("Initial cash:", current_cash)
print("Initial portfolio value:", init_port_val)

short_memory = 10
long_memory = 100
short_mem_bid = deque(maxlen=short_memory)
long_mem_bid = deque(maxlen=long_memory)
short_mem_ask = deque(maxlen=short_memory)
long_mem_ask = deque(maxlen=long_memory)

def algo_trader():
    print('Listening for prices...')
    async def quote_data_handler(data):
        # quote data will arrive here
        print("ask price:",data.ask_price, "bid price:", data.bid_price)
        current_ask = data.ask_price
        current_bid = data.bid_price
        global short_mem_ask
        global long_mem_ask
        global short_mem_bid
        global long_mem_ask
        global current_cash

        # Calculate indicators
        short_mem_bid.append(data.bid_price)
        long_mem_bid.append(data.bid_price)
        short_mem_ask.append(data.ask_price)
        long_mem_ask.append(data.ask_price)

        ma_sm_bid = sum(short_mem_bid)/len(short_mem_bid)
        ma_lm_bid = sum(long_mem_bid)/len(long_mem_bid)
        ma_sm_ask = sum(short_mem_ask)/len(short_mem_ask)
        ma_lm_ask = sum(long_mem_ask)/len(long_mem_ask)

        # Logic of strategy
        # Note: The less volatile and the smaller the MA windows, the less likely a trade will occur

        if (.02*current_ask < current_cash) & (.02*current_ask < .02*ma_sm_bid < .02*ma_lm_bid):
            size = .02
            action = OrderSide.BUY
        elif (.01*current_ask < current_cash) & (.01*current_ask < .01*ma_sm_bid):
            size = .01
            action = OrderSide.BUY
        elif (.01*current_bid > .01*ma_sm_ask) & (.01*current_bid > .01*ma_lm_ask):
            size = .01
            action = OrderSide.SELL
        else:
            action = False
            print("No Trade Made")

        # Put in order if strategy gives the signal
        if action:
            order_details = MarketOrderRequest(
            symbol= "BTC/USD",
            qty = size,
            side = action,
            time_in_force = TimeInForce.IOC
            )

            order = client.submit_order(order_data= order_details)
            print("Made Trade")
    
    wss_client = CryptoDataStream(config.API_KEY, config.SECRET_KEY)
    wss_client.subscribe_quotes(quote_data_handler, "BTC/USD")
    wss_client.run()

def trade_results():
    print('Listening for trade updates...')
    async def trade_status(data):
        global cash_spent
        global cash_received
        global qty_owned_this_session

        status = data.event

        # If order is filled, update global variables and print rough PnL
        if status == 'fill':
            price = float(data.order.filled_avg_price)
            qty = float(data.order.filled_qty)
            side = data.order.side.value

            if side == 'buy':
                cash_spent += qty*price
                qty_owned_this_session += qty
            elif side == 'sell':
                cash_received += qty*price
                qty_owned_this_session -= qty
            
            print("Estimated Pnl:", cash_received - cash_spent + qty_owned_this_session*price)
            
    trades = TradingStream(config.API_KEY, config.SECRET_KEY, paper=True)
    trades.subscribe_trade_updates(trade_status)
    trades.run()

# Two threads, one for prices and one for trade updates
t1 = threading.Thread(target=algo_trader)
t2 = threading.Thread(target=trade_results)
t1.start()
t2.start()
t1.join()
t2.join()

# To exit, terminal must be manually killed for now

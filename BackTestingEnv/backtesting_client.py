import socket
import pandas as pd
import re
from io import StringIO
from algo_trading_strat_1 import Trader
import time

HOST, PORT = "localhost", 9999

# types: singlerows - will receive single rows, dataframes - will receive whole dfs
type = 'singlerows'

# parameters sent to server upon connection
data_structure = 'multi files linked' # 1 if reading single file, 0 if reading several files
cycle = .001 # interval of time between server outputs in seconds
directory = r"E:/Stocks/AAPL/".replace("\\","/") 
regex = '^([A-z]{1,5})(_)([A-z]{0,10})(_)([0-9-; ]{0,25})(.[A-z]{0,10})'
regex_last_bar = "^({[\s\S]*})*({[^{}]*})$"
date_form = '%Y-%m-%d %H;%M;%S'

# depending on the cycle length, the trader may miss some of the data sent by the server
# this counts rows lost
total_lost = 0

t1 = time.time()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

    # connect and send parameters to server
    sock.connect((HOST, PORT))
    config = str({'data_structure': data_structure, 'cycle': cycle, 'directory': directory, 'regex': regex, 'date_form': date_form})
    sock.sendall(bytes(config, "utf-8"))
    print("sent info")

    # create trader
    # see algo_trading_strat_1 for this class in AlgoTrading
    trader = Trader(10000, 'AAPL', 5, 90)

    i = 0
    while True:
        if i % 10000 == 0:
            print(trader.get_wealth())
        i += 1
        try:
            if type == 'dataframes':
                received = str(sock.recv(8192), "utf-8")
                a = pd.read_json(StringIO(received))
        
            elif type == 'singlerows':
                received = str(sock.recv(8192), "utf-8")
                matches = re.findall(regex_last_bar, received)
                last_bar = matches[0][-1]
                lost = len(matches[0]) - 2 if len(matches[0][0]) == 0 else len(matches[0]) - 1
                total_lost += lost
                a = pd.read_json(StringIO(last_bar), typ='series')
                a = a.to_frame()

                # here data is given to the trader to make a decision
                trader.generate_signal(a.T)

        except Exception as e:
            # these prints are for debugging
            print(e)
            print(received)
            print(matches)
            break

# time it took to complete
t2 = time.time()
print(t2-t1)

# Cash + value of holdings by the end of simulation
print(trader.get_wealth())

print(total_lost)
    

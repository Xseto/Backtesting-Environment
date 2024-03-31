import numpy as np
import pandas as pd
from datetime import datetime
import re
from Greeks import get_greeks

class OptionPortfolio:

    def __init__(self, ticker, spot, rate, div, today):
        self.ticker = ticker
        self.s = spot
        self.r = rate
        self.q = div
        self.portfolio = {}
        self.portfolio_greeks = np.zeros((7,))
        self.option_greeks = pd.DataFrame()
        self.today = datetime.strptime(today, '%Y/%m/%d')

    def op_contract_dec(self, contract_string):
    # parses option contract names
        option_regex = r"^([A-z]{1,5})(\d{6})([CPcp])([\d.]+)"
        matches = re.findall(option_regex, contract_string)

        return {'id': contract_string,'ticker':matches[0][0], 'date':datetime.strptime(matches[0][1], '%y%m%d'), 
                'type':matches[0][2], 'strike':float(matches[0][3])/1000}

    def update_portfolio_greeks(self):
        self.portfolio_greeks = np.zeros((7,))
        option_greeks_list = []
        options = list(self.portfolio.keys())
        for opt in options:
            V = self.portfolio[opt]['price']
            S = self.s
            K = self.portfolio[opt]['strike']
            r = self.r
            q = self.q
            T = self.portfolio[opt]['tte']
            expiration = self.portfolio[opt]['exp']
            typ = self.portfolio[opt]['type']
            if self.portfolio[opt]['side'] == 'Buy':
                greeks = get_greeks(V, S, K, r, q, T, expiration, typ)
                self.portfolio_greeks += greeks
                op_greeks = [opt] + list(greeks)
            else:
                greeks = get_greeks(V, S, K, r, q, T, expiration, typ)
                self.portfolio_greeks -= greeks
                op_greeks = [opt] + list(-1*greeks)
            option_greeks_list.append(op_greeks)
        columns = ['Contract','Implied Vol', 'Delta', 'Gamme', 'Vega', 'Volga', 'Vanna', 'Theta']
        self.option_greeks = pd.DataFrame(option_greeks_list, columns=columns)

    def add_option(self, id, price, side):
        profile = self.op_contract_dec(id)
        tte = (profile['date'] - self.today).days/365
        self.portfolio[id] = {'price': price, 'strike': profile['strike'], 'tte': tte, 'exp': profile['date'], 
                              'side': side, 'type': profile['type']}
        
        self.update_portfolio_greeks()

    def remove_option(self, id):
        del self.portfolio[id]

        self.update_portfolio_greeks()

        
import numpy as np
import pandas as pd
from scipy.stats import norm
import matplotlib.pyplot as plt
import re
from datetime import datetime
from scipy import optimize

class OptionChain:
    '''
    Calculates Implied Volatility and Greeks of European and American Options
    Assumes risk free rate is constant
    Dividend yields are continuously compounded
    Assumes option chain is a dataframe formatted like Yahoo Finance option chains
        and all contracts are either American or European and Puts or Calls
    '''

    def __init__(self, spot, rfr, div, start_date, data, type='E'):
        '''
        spot - price of underlying when option chain was captured
        rfr - annual risk free rate as decimal
        div - annual dividend yield as decimal
        start_date - day when option chain was captured
        data - dataframe of option chain of single tenor
        type - type of option ('E' for European, 'A' for American)
        '''
        self.data = data
        self.type = type
        self.s = spot
        self.r = rfr
        self.q = div
        self.start_date = start_date

        name = self.data['Contract Name'][0]
        self.style = self.op_contract_dec(name, False)['type'] # checks if contracts are calls or puts
        self.T = (self.op_contract_dec(name, False)['date'] - self.start_date).days/252 # time to maturity

    def op_contract_dec(self, contract_string, as_string):
    # parses option contract names
        option_regex = r"^([A-z]{1,5})(\d{6})([CPcp])([\d.]+)"
        matches = re.findall(option_regex, contract_string)
        if as_string:
            return {'id': contract_string, 'ticker':matches[0][0], 'date':matches[0][1], 'type':matches[0][2], 'strike':matches[0][3]}
        else:
            return {'id': contract_string,'ticker':matches[0][0], 'date':datetime.strptime(matches[0][1], '%y%m%d'), 'type':matches[0][2], 'strike':float(matches[0][3])/1000}

    def d1(self, S, K, r, q, vol, T):
        return (np.log(S/K)+(r-q+.5*vol**2)*T)/(vol*np.sqrt(T))

    def d2(self, S, K, r, q, vol, T, D1 = None):
        if D1:
            return D1 - vol*np.sqrt(T)
        else:
            return self.d1(S, K, r, q, vol, T) - vol*np.sqrt(T)

    def ec_price(self, S, K, r, q, vol, T):
        D1 = self.d1(self.s, K, self.r, self.q, vol, T)
        D2 = self.d2(self.s, K, self.r, self.q, vol, T, D1)
        return S*np.exp(-q*T)*norm.cdf(D1) - K*np.exp(-r*T)*norm.cdf(D2)
    
    def ep_price(self, S, K, r, q, vol, T):
        D1 = self.d1(self.s, K, self.r, self.q, vol, T)
        D2 = self.d2(self.s, K, self.r, self.q, vol, T, D1)
        return -S*np.exp(-q*T)*norm.cdf(-D1) + K*np.exp(-r*T)*norm.cdf(-D2)
    
    def vega(self, vol, S, K, r, q, T, op_price, op_style):
        # edited version of euro_vega to accept same paramters
        # as zero functions for use with scipy.optimize
        D1 = self.d1(S, K, r, q, vol, T)
        return S*np.exp(-q*T)*norm.pdf(D1)*np.sqrt(T)

    def american_crr_tree(self, S, K, r, div, vol, T, N, op_style):
        # Computes price of American option on dividend paying stock
        # Using CRR binomial tree

        #precompute values
        dt = T/N
        u = np.exp(vol*np.sqrt(dt))
        d = 1/u
        q = (np.exp((r-div)*dt) - d)/(u-d)
        disc = np.exp(-r*dt)

        # initialise stock prices at maturity
        S_prices = S * d**(np.arange(N,-1,-1)) * u**(np.arange(0,N+1,1))

        # option payoff
        if op_style == 'P':
            C = np.maximum(0, K - S_prices)
        else:
            C = np.maximum(0, S_prices - K)

        # backward recursion through the tree
        for i in np.arange(N-1,-1,-1):
            S_prices = S * d**(np.arange(i,-1,-1)) * u**(np.arange(0,i+1,1))
            C[:i+1] = disc * ( q*C[1:i+2] + (1-q)*C[0:i+1] )
            C = C[:-1]
            if op_style == 'P':
                C = np.maximum(C, K - S_prices)
            else:
                C = np.maximum(C, S_prices - K)

        return C[0]
    
    def american_delta(self, K, vol):
        # finite difference for American delta
        ds = .001*self.s
        plus = self.american_crr_tree(self.s+ds, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        minus = self.american_crr_tree(self.s-ds, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        return (plus-minus)/(2*ds)

    def ec_delta(self, S, K, r, q, vol, T):
        # euro call delta
        D1 = self.d1(S, K, r, q, vol, T)
        return np.exp(-q*T)*norm.cdf(D1)

    def ep_delta(self, S, K, r, q, vol, T):
        # euro put delta
        D1 = self.d1(S, K, r, q, vol, T)
        return -np.exp(-q*T)*norm.cdf(-D1)
    
    def euro_delta(self, K, vol):
        # calls correct delta function
        if self.style == 'C':
            return self.ec_delta(self.s, K, self.r, self.q, vol, self.T)
        elif self.style == 'P':
            return self.ep_delta(self.s, K, self.r, self.q, vol, self.T)
        
    def american_gamma(self, K, vol):
        # finite difference for American gamma
        ds = .001*self.s
        plus = self.american_crr_tree(self.s+ds, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        minus = self.american_crr_tree(self.s-ds, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        atm = self.american_crr_tree(self.s, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        return (minus - 2*atm + plus)/(ds**2)
    
    def euro_gamma(self, S, K, r, q, vol, T):
        # euro gamma
        D1 = self.d1(S, K, r, q, vol, T)
        return np.exp(-q*T)*norm.pdf(D1)/(S*vol*np.sqrt(T))
    
    def american_vega(self, K, vol):
        # finite difference for American vega
        dvol = .001*vol
        plus = self.american_crr_tree(self.s, K, self.r, self.q, vol+dvol, self.T, N=1000, op_style=self.style)
        minus = self.american_crr_tree(self.s, K, self.r, self.q, vol-dvol, self.T, N=1000, op_style=self.style)
        return (plus-minus)/(2*dvol)

    def euro_vega(self, S, K, r, q, vol, T):
        # euro vega
        D1 = self.d1(S, K, r, q, vol, T)
        return S*np.exp(-q*T)*norm.pdf(D1)*np.sqrt(T)
    
    def american_volga(self, K, vol):
        # finite difference for American volga
        dvol = .001*vol
        plus = self.american_crr_tree(self.s, K, self.r, self.q, vol+dvol, self.T, N=1000, op_style=self.style)
        minus = self.american_crr_tree(self.s, K, self.r, self.q, vol-dvol, self.T, N=1000, op_style=self.style)
        atm = self.american_crr_tree(self.s, K, self.r, self.q, vol, self.T, N=1000, op_style=self.style)
        return (minus - 2*atm + plus)/(dvol**2)
    
    def euro_volga(self, S, K, r, q, vol, T):
        # euro volga
        D1 = self.d1(S, K, r, q, vol, T)
        D2 = self.d2(S, K, r, q, vol, T, D1)
        return S*np.exp(-q*T)*np.sqrt(T)*norm.pdf(D1)*D1*D2/vol

    def american_vanna(self, K, vol):
        # finite difference for American vanna
        ds = .001*self.s
        dvol = .001*vol
        pp = self.american_crr_tree(self.s+ds, K, self.r, self.q, vol+dvol, self.T, N=1000, op_style=self.style)
        pm = self.american_crr_tree(self.s+ds, K, self.r, self.q, vol-dvol, self.T, N=1000, op_style=self.style)
        mp = self.american_crr_tree(self.s-ds, K, self.r, self.q, vol+dvol, self.T, N=1000, op_style=self.style)
        mm = self.american_crr_tree(self.s-ds, K, self.r, self.q, vol-dvol, self.T, N=1000, op_style=self.style)

        return (pp-pm-mp+mm)/(4*ds*dvol)
    
    def euro_vanna(self, S, K, r, q, vol, T):
        # euro vanna
        D1 = self.d1(S, K, r, q, vol, T)
        D2 = self.d2(S, K, r, q, vol, T, D1)
        return -np.exp(-q*T)*norm.pdf(D1)*D2/vol

    def zero_euro(self, vol, S, K, r, q, T, op_price, op_style):
        # Find 0 of this function to find implied vol for euro options
        if op_style == 'C':
            return self.ec_price(S, K, r, q, vol, T) - op_price
        if op_style == 'P':
            return self.ep_price(S, K, r, q, vol, T) - op_price

    def zero_amer(self, vol, S, K, r, q, T, op_price, op_style):
        # Find 0 of this function to find implied vol for American options
        return self.american_crr_tree(S, K, r, q, vol, T, N=1000, op_style=op_style) - op_price

    def implied_vol(self, S, K, r, q, T, op_price, op_style):
        # Calculated implied vol using Newton's method
        if self.type == 'A':
            # init = np.sqrt((2*np.log(S*np.exp(r*T)/K))/(T))
            try:
                imp_vol = optimize.newton(self.zero_amer, 2, args = (S, K, r, q, T, op_price, op_style))
            except Exception as e:
                print(e)
                imp_vol = 0

        elif self.type == 'E':
            try:
                imp_vol = optimize.newton(self.zero_euro, 2, self.vega, args = (S, K, r, q, T, op_price, op_style))
            except Exception as e:
                print(e)
                imp_vol = 0

        return imp_vol
    
    def iv_adder(self):
        # adds implied vol column to data
        if self.style == 'C':
            self.data['imp_vol'] = self.data.apply(lambda x: self.implied_vol(self.s, x.Strike, self.r, self.q, self.T, .5*(x.Bid+x.Ask), 'C'), axis=1)
        elif self.style == 'P':
            self.data['imp_vol'] = self.data.apply(lambda x: self.implied_vol(self.s, x.Strike, self.r, self.q, self.T, .5*(x.Bid+x.Ask), 'P'), axis=1)

    def delta_adder(self,vol=None):
        # adds delta column to data
        if vol:
            if self.type == 'A':
                self.data['delta'] = self.data.apply(lambda x: self.american_delta(x.Strike, vol))
            elif self.type == 'E':
                self.data['delta'] = self.data.apply(lambda x: self.euro_delta(x.Strike, vol))
        else:
            try:
                if self.type == 'A':
                    self.data['delta'] = self.data.apply(lambda x: self.american_delta(x.Strike, x.imp_vol), axis=1)
                elif self.type == 'E':
                    self.data['delta'] = self.data.apply(lambda x: self.euro_delta(x.Strike, x.imp_vol), axis=1)
            except Exception as e:
                print(e)

    def gamma_adder(self):
        # adds gamma column to data
        if self.type == 'A':
            self.data['gamma'] = self.data.apply(lambda x: self.american_gamma(x.Strike, x.imp_vol), axis=1)
        elif self.type == 'E':
            self.data['gamma'] = self.data.apply(lambda x: self.euro_gamma(self.s, x.Strike, self.r, self.q, x.imp_vol, self.T), axis=1)

    def vega_adder(self):
        # adds vega column to data
        if self.type == 'A':
            self.data['vega'] = self.data.apply(lambda x: self.american_vega(x.Strike, x.imp_vol), axis=1)
        elif self.type == 'E':
            self.data['vega'] = self.data.apply(lambda x: self.euro_vega(self.s, x.Strike, self.r, self.q, x.imp_vol, self.T), axis=1)

    def volga_adder(self):
        # adds volga column to data
        if self.type == 'A':
            self.data['volga'] = self.data.apply(lambda x: self.american_volga(x.Strike, x.imp_vol), axis=1)
        elif self.type == 'E':
            self.data['volga'] = self.data.apply(lambda x: self.euro_volga(self.s, x.Strike, self.r, self.q, x.imp_vol, self.T), axis=1)

    def vanna_adder(self):
        # adds vanna column to data
        if self.type == 'A':
            self.data['vanna'] = self.data.apply(lambda x: self.american_vanna(x.Strike, x.imp_vol), axis=1)
        elif self.type == 'E':
            self.data['vanna'] = self.data.apply(lambda x: self.euro_vanna(self.s, x.Strike, self.r, self.q, x.imp_vol, self.T), axis=1)

    def greeks_adder(self):
        # adds greek columns to data by calling all adder functions
        self.delta_adder()
        self.gamma_adder()
        self.vega_adder()
        self.volga_adder()
        self.vanna_adder()

    


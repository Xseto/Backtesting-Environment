import numpy as np
import pandas as pd
from datetime import datetime
from OptionChainCalculator import OptionChain

class VolSurface:
    '''
    Class that calculates implied volatility and local volatility surface
        given dictionary of option chains
    '''
    def __init__(self, spot, rfr, div, start_date, data, type='E', style='C'):
        '''
        spot - price of underlying when option chain was captured
        rfr - annual risk free rate as decimal
        div - annual dividend yield as decimal
        start_date - day when option chain was captured
        data - dictionary of option chains for all tenors
        type - type of option ('E' for European, 'A' for American)
        style - style of option ('C' for call, 'P' for put)
        '''

        self.data = data
        self.tenors = list(self.data.keys()) # dictionary keys are dates
        self.s = spot
        self.r = rfr
        self.q = div
        self.start_date = start_date
        self.type = type
        self.style = style

        self.iv_surface = pd.DataFrame()

        self.iv_surface_interpolated = pd.DataFrame()
        self.lv_surface_interpolated = pd.DataFrame()

        self.iv_surface_filled = pd.DataFrame()
        self.lv_surface_filled = pd.DataFrame()

    def dupires_formula(self, strike_tenor_grid, times_to_maturity, strikes):
        # Calculate local vol using Dupires formula 
        # Finite differences are used to calculate derivatives

        dt = np.append(np.diff(times_to_maturity), np.diff(times_to_maturity)[-1])
        dk = np.append(np.diff(strikes), np.diff(strikes)[-1])

        Dt = np.diff(strike_tenor_grid, axis=1)
        Dt = np.hstack((Dt, Dt[:, -1][:, None]))/dt
        Dk = np.diff(strike_tenor_grid, axis=0)
        Dk = (np.vstack((Dk, Dk[-1])).T/dk).T
        D2Dk = np.diff(Dk, axis=0)
        D2Dk = (np.vstack((D2Dk, D2Dk[-1])).T/dk).T

        return np.sqrt((Dt + self.q*strike_tenor_grid + (self.r-self.q)*(Dk.T*strikes).T)/(.5*(D2Dk.T*strikes**2).T))

    def implied_vol_surface(self):
        # Calculate implied vol surface with and without linear interpolation

        # Use OptionChain class to calculate implied vols for each tenor
        list_of_ivs = []
        for tenor in self.tenors:
            df = self.data[tenor]
            option_chain = OptionChain(self.s, self.r, self.q, self.start_date, df, self.type)
            option_chain.iv_adder()
            self.data[tenor] = option_chain.data

            df_temp = option_chain.data[['Strike', 'imp_vol']]
            df_temp = df_temp.set_index('Strike')
            df_temp = df_temp.rename(columns={"imp_vol": tenor})

            list_of_ivs.append(df_temp)

        # Combine tenors into implied vol surface
        self.iv_surface = pd.concat(list_of_ivs, axis=1)
        self.iv_surface.sort_index(inplace=True)

        # Fill in nans using interpolation 
        self.iv_surface_interpolated = self.iv_surface.interpolate(method='linear', limit_direction='forward', axis=0)
        self.iv_surface_interpolated = self.iv_surface.interpolate(method='linear', limit_direction='backward', axis=0)

        # FIll in remaining nans
        self.iv_surface_filled = self.iv_surface_interpolated.fillna(method='ffill').fillna(method='bfill')

    def local_vol_surface(self):
        # Calculate local vol surface

        # Construct 2d grid of option prices of each tenor and strike
        list_of_option_prices = []
        for tenor in self.tenors:
            df = self.data[tenor]
            df_temp = pd.DataFrame(index=df.Strike, data={tenor:(.5*(df.Bid+df.Ask)).to_list()})
            list_of_option_prices.append(df_temp)

        strike_tenor_grid = pd.concat(list_of_option_prices, axis=1)
        strike_tenor_grid.sort_index(inplace=True)

        # Fill in nans using interpolation
        strike_tenor_grid = strike_tenor_grid.interpolate(method='spline', order=2, limit_direction='forward', axis=0)
        strike_tenor_grid = strike_tenor_grid.interpolate(method='spline', order=2, limit_direction='backward', axis=0)

        # Construct time to maturity and strike vectors for use in Dupires formula
        times_to_maturity = []
        for tenor in self.tenors:
            times_to_maturity.append(datetime.strptime(tenor, '%B %d, %Y'))
        times_to_maturity = np.array([(ttm - self.start_date).days/252 for ttm in times_to_maturity])
        strikes = np.array(strike_tenor_grid.index)

        # If given put prices, use put-call parity to change into calls for Dupire's formula
        if self.style == 'P':
            S_term = self.s*np.exp(-self.q*times_to_maturity)
            K_matrix = np.array([[K*np.exp(-self.r*ttm) for ttm in times_to_maturity] for K in strikes])

            strike_tenor_grid = strike_tenor_grid + S_term - K_matrix
        
        # Calcluate local vol
        self.lv_surface_interpolated = self.dupires_formula(strike_tenor_grid, times_to_maturity, strikes)

        # Fill in nans
        self.lv_surface_filled = self.lv_surface_interpolated.fillna(method='ffill').fillna(method='bfill')

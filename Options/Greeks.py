import numpy as np
from scipy.stats import norm
from QuantLib import *

def d1(S, K, r, q, vol, T):
        return (np.log(S/K)+(r-q+.5*vol**2)*T)/(vol*np.sqrt(T))

def d2(S, K, r, q, vol, T, D1 = None):
    if D1:
        return D1 - vol*np.sqrt(T)
    else:
        return d1(S, K, r, q, vol, T) - vol*np.sqrt(T)
    
def ec_price(S, K, r, q, vol, T):
    D1 = d1(S, K, r, q, vol, T)
    D2 = d2(S, K, r, q, vol, T, D1)
    return S*np.exp(-q*T)*norm.cdf(D1) - K*np.exp(-r*T)*norm.cdf(D2)

def ep_price(S, K, r, q, vol, T):
    D1 = d1(S, K, r, q, vol, T)
    D2 = d2(S, K, r, q, vol, T, D1)
    return -S*np.exp(-q*T)*norm.cdf(-D1) + K*np.exp(-r*T)*norm.cdf(-D2)

def ec_delta(S, K, r, q, vol, T):
    # euro call delta
    D1 = d1(S, K, r, q, vol, T)
    return np.exp(-q*T)*norm.cdf(D1)

def ep_delta(S, K, r, q, vol, T):
    # euro put delta
    D1 = d1(S, K, r, q, vol, T)
    return -np.exp(-q*T)*norm.cdf(-D1)

def euro_gamma(S, K, r, q, vol, T):
    # euro gamma
    D1 = d1(S, K, r, q, vol, T)
    return np.exp(-q*T)*norm.pdf(D1)/(S*vol*np.sqrt(T))

def euro_vega(S, K, r, q, vol, T):
    # euro vega
    D1 = d1(S, K, r, q, vol, T)
    return S*np.exp(-q*T)*norm.pdf(D1)*np.sqrt(T)

def euro_volga(S, K, r, q, vol, T):
    # euro volga
    D1 = d1(S, K, r, q, vol, T)
    D2 = d2(S, K, r, q, vol, T, D1)
    return S*np.exp(-q*T)*np.sqrt(T)*norm.pdf(D1)*D1*D2/vol

def euro_vanna(S, K, r, q, vol, T):
    # euro vanna
    D1 = d1(S, K, r, q, vol, T)
    D2 = d2(S, K, r, q, vol, T, D1)
    return -np.exp(-q*T)*norm.pdf(D1)*D2/vol

def euro_theta(S, K, r, q, vol, T, type):
    D1 = d1(S, K, r, q, vol, T)
    D2 = d2(S, K, r, q, vol, T, D1)

    c = 1 if type == 'C' else -1
    one = S*vol*np.exp(-q*T)*norm.pdf(D1)/(2*np.sqrt(T))
    two = r*K*np.exp(-r*T)*norm.cdf(c*D2)
    three = q*S*np.exp(-q*T)*norm.cdf(c*D1)

    return -one - c*(two - three)

def implied_vol(V, S, K, r, q, expiration, type):
    if type == 'C':
        po = Option.Call
    else:
        po = Option.Put
    exercise = EuropeanExercise(Date(expiration.day,expiration.month,expiration.year))
    payoff = PlainVanillaPayoff(po, K)
    option = EuropeanOption(payoff,exercise)

    S = QuoteHandle(SimpleQuote(S))
    r = YieldTermStructureHandle(FlatForward(0, TARGET(), r, Actual360()))
    q = YieldTermStructureHandle(FlatForward(0, TARGET(), q, Actual360()))
    sigma = BlackVolTermStructureHandle(BlackConstantVol(0, TARGET(), 0.20, Actual360()))
    process = BlackScholesMertonProcess(S,q,r,sigma)
    
    return option.impliedVolatility(V, process, 1.0e-4, 1000, 1e-7, 10)

def get_greeks(V, S, K, r, q, T, expiration, type, as_array=True):

    imp_vol = implied_vol(V, S, K, r, q, expiration, type)
    delta = ec_delta(S, K, r, q, imp_vol, T) if type == 'C' else ep_delta(S, K, r, q, imp_vol, T)
    gamma = euro_gamma(S, K, r, q, imp_vol, T)
    vega = euro_vega(S, K, r, q, imp_vol, T)
    volga = euro_volga(S, K, r, q, imp_vol, T)
    vanna = euro_vanna(S, K, r, q, imp_vol, T)
    theta = euro_theta(S, K, r, q, imp_vol, T, type)

    if as_array:
        return np.array([imp_vol, delta, gamma, vega, volga, vanna, theta])
    else:
        output = {'IV': imp_vol, 'delta': delta, 'gamma': gamma, 'vega': vega, 'volga': volga, 'vanna': vanna, 'theta': theta}
        return output
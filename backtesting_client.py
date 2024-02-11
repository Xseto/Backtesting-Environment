import socket
import sys
import pandas as pd
from datetime import datetime
import re
from io import StringIO

HOST, PORT = "localhost", 9999

def opt_contract_dec(contract_string,as_string):
    # Used for parsing an options contract name
    option_regex = r"^([A-z]{1,5})(\d{6})([CPcp])([\d.]+)"
    matches = re.findall(option_regex, contract_string)
    if as_string:
        return {'ticker':matches[0][0], 'date':matches[0][1], 'type':matches[0][2], 'strike':matches[0][3]}
    else:
        return {'ticker':matches[0][0], 'date':datetime.strptime(matches[0][1], '%y%m%d'), 'type':matches[0][2], 'strike':float(matches[0][3])/1000}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((HOST, PORT))

    while True:
        try:
            received = str(sock.recv(8192), "utf-8")
            a = pd.read_json(StringIO(received))
            
            contracts = opt_contract_dec(a['Contract Name'][0],False)['date'].strftime('%m/%d/%Y')

            # For debugging
            '''print('received {} {} contracts'.format(contracts, opt_contract_dec(a['Contract Name'][0],False)['type']))
            print(a)
            print('\n')
            print('*******************************************************************************')'''
        except Exception as e:
            print(e)
            break
    

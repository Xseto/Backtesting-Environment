import socketserver
import time
import pandas as pd
import os
import re
from datetime import datetime
import algo_trading_strat_1

# provide a directory of files that will be used simulate real time data
# for now, file names must include ticker, type, date in that order
# for now, files must be xlsx
# use regex to specify format
# specify interval between sent data in seconds in cycle

symbols = '{}()[].,:;+-*/&|<>=~$1234567890_'


class MyTCPHandler(socketserver.BaseRequestHandler):
    # Mimics an exchange streaming market data
    
    def fname_parser(self, fn, regex, as_string, date_form):
        # parses filenames
        matches = re.findall(regex, fn)
        matches = [m for m in matches[0] if m not in symbols]
        if as_string:
            return {'fn':fn, 'ticker':matches[0], 'date':matches[2], 'type':matches[1], 'file_ext':matches[3]}
        else:
            return {'fn':fn, 'ticker':matches[0], 'date':datetime.strptime(matches[2], date_form), 'type':matches[1], 'file_ext':matches[3]}

    def handle(self):
        config = self.request.recv(1024).strip()
        config_dict = eval(config)
        cycle = config_dict['cycle']
        data_structure = config_dict['data_structure']
        directory = config_dict['directory']
        regex = config_dict['regex']
        date_form = config_dict['date_form']

        if data_structure == 'one file':
            # data is in one file, delivered row by row
            dir = os.listdir(directory)
            dir = [file for file in dir if file[0] != '~']
            fn = dir[0]
            fn_path = directory + '/' + fn
            data = pd.read_excel(fn_path)
            for i in data.index:
                row = data.loc[i].to_json()
                df_json = bytes(row, 'utf-8')
                self.request.sendall(df_json)
                time.sleep(cycle)

        elif data_structure == 'multi files linked':
            # data is in multiple files in single directory
            # delivered row by row
            dir = os.listdir(directory)
            dir = [file for file in dir if file[0] != '~']
            dir_parsed = [self.fname_parser(fn, regex, False, date_form) for fn in dir]
            dir_parsed.sort(key=lambda x: x['date'])

            for file in dir_parsed:
                fn = file['fn']
                fn_path = directory + '/' + fn
                data = pd.read_excel(fn_path)
                for i in data.index:
                    row = data.loc[i].to_json()
                    df_json = bytes(row, 'utf-8')
                    self.request.sendall(df_json)
                    time.sleep(cycle)

        elif data_structure == 'multi files separate':
            # data is in multiple files
            # full dataframes delivered sheet by sheet
            dir = os.listdir(directory)
            dir = [file for file in dir if file[0] != '~']
            dir_parsed = [self.fname_parser(fn, regex, False, date_form) for fn in dir]
            dir_parsed.sort(key=lambda x: x['date'])

            for file in dir_parsed:
                fn = file['fn']
                fn_path = directory + '/' + fn
                try:
                    xls = pd.ExcelFile(fn_path)
                    for sheet in xls.sheet_names:
                        df = pd.read_excel(xls, sheet).drop(columns=['Unnamed: 0', 'Last Trade Date', 'Change', '% Change'])
                        df_json = bytes(df.to_json(), 'utf-8')
                        self.request.sendall(df_json)
                        time.sleep(.01)
                except:
                    break
                time.sleep(cycle)

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999 #localhost or 127.0.0.1
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        server.serve_forever()

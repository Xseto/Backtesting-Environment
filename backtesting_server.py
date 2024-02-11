import socketserver
import time
import pandas as pd
import os
import re
from datetime import datetime

# provide a directory of files that will be used simulate real time data
# for now, file names must include ticker, type, date in that order
# for now, files must be xlsx
# use regex to specify format
# specify interval between sent data in seconds in cycle

cycle = 60
directory = r"C:\Users\Xzavier\Documents\Data\Options\Citi".replace("\\","/")
regex = r"^([A-z]{1,5})(_)([A-z]{1,5})(_)([0-9]{2}_[0-9]{2}_[0-9]{4})(.)([A-z]{1,5}$)"
symbols = '{}()[].,:;+-*/&|<>=~$1234567890_'

def fname_parser(fn, regex, as_string):

    matches = re.findall(regex, fn)

    matches = [m for m in matches[0] if m not in symbols]

    if as_string:
        return {'fn':fn, 'ticker':matches[0], 'date':matches[2], 'type':matches[1], 'file_ext':matches[3]}
    else:
        return {'fn':fn, 'ticker':matches[0], 'date':datetime.strptime(matches[2], '%m_%d_%Y'), 'type':matches[1], 'file_ext':matches[3]}

class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        '''# self.request is the TCP socket connected to the client'''
        dir = os.listdir(directory)
        dir = [file for file in dir if file[0] != '~']
        dir_parsed = [fname_parser(fn, regex, False) for fn in dir]
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

                #break #remove later

            except:
                break
            time.sleep(cycle)

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999 #localhost or 127.0.0.1

    # Create the server, binding to localhost on port 9999
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()
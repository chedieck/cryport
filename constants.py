from pycoingecko import CoinGeckoAPI
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

PORTFOLIOS_DIR = 'portfolios/'
CG = CoinGeckoAPI()
STYLE = ['.-', 'o-', 'v-', '^-', '<-', '>-', '1-', '2-', '3-', '4-', '8-', 's-', 'p-', 'P-', '*-', 'H-', '+-', 'x-', 'X-', 'D-']

class Date:
    NOW = datetime.now()
    ONE_MONTH_AGO = NOW - relativedelta(months=1)

class PortfolioInfoType:
    VALUE = 'value'
    PERCENTAGE = 'percentage'
    PRICE = 'price'

    ALL = [VALUE, PERCENTAGE, PRICE]

class TradeAction:
    SELL = 'SELL'
    BUY = 'BUY'

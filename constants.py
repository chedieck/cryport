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

class ConditionType:
    VALUE_MIN = PortfolioInfoType.VALUE + '_min'
    PERCENTAGE_MIN = PortfolioInfoType.PERCENTAGE + '_min'
    PRICE_MIN = PortfolioInfoType.PRICE + '_min'

    VALUE_MAX = PortfolioInfoType.VALUE + '_max'
    PERCENTAGE_MAX = PortfolioInfoType.PERCENTAGE + '_max'
    PRICE_MAX = PortfolioInfoType.PRICE + '_max'

    ALL = [VALUE_MAX, PERCENTAGE_MAX, PRICE_MAX, VALUE_MIN, PERCENTAGE_MIN, PRICE_MIN]

class TradeAction:
    SELL = 'SELL'
    BUY = 'BUY'

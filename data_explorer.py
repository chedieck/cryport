from constants import CG
import json
from core import Portfolio, PortfolioMonitor
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from constants import STYLE, TradeAction
from typing import Callable
import random
import numpy as np


def create_windowed_dataframe(results_dict, window_size=relativedelta(hours=1)):
    oldest_date = min([v[0][0] for v in results_dict.values()])
    start = datetime.fromtimestamp(oldest_date / 1000)
    new_df = pd.DataFrame(columns=set(results_dict.keys()) | {'date'})

    now = datetime.now()
    loop_counter = 0
    while start < now:
        row_data = {}
        for k, v in results_dict.items():
            for ts, value in v:
                if start <= datetime.fromtimestamp(ts / 1000):
                    row_data[k] = value
                    break

        new_df = new_df.append({
            'date': start,
            **row_data
        }, ignore_index=True)

        start += window_size
        loop_counter += 1
    return new_df.set_index('date')


class CoinInfo:
    def __init__(self, raw_response):
        self.raw_response = raw_response

def get_coins_info(coin_id_list):
    # update list of coins
    return_dict = dict()
    for coin in coin_id_list:
        coin_info = CoinInfo(CG.get_coin_by_id(coin))
        return_dict[coin] = coin_info
    
    return return_dict

class HistoricalPortfolio(Portfolio):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.days = None
        self._cached_first_prices = None
        self._cached_price_normalized_evolution = None

    def update_history(self, days=30):
        """Get historical data of each portfolio asset.

        Does not support custom granularity, as this is the CoinGecko API behavior. Granularity
        is determined automatic, as mentioned by CoinGecko API docs:
            days = 1 ----------> 5 minute interval data
            1 < days <= days --> hourly data
            days > 90 ---------> daily data (00:00 UTC)
        """
        self.days = days
        results_dict = {}
        first_values_dict = {}
        for coin_id in self.assets.index:
            historical_data = CG.get_coin_market_chart_by_id(coin_id,
                                                             self.quote,
                                                             days=days)
            first_value = historical_data['prices'][0][1]  # used to normalize data
            first_values_dict[coin_id] = first_value
            results_dict[coin_id] = list(map(
                lambda xy: (xy[0], xy[1]/first_value),
                historical_data['prices']
            ))

        # this refers to the default coingecko API behavior
        match days:
            case 1:
                window_size = relativedelta(minutes=5)
            case days if 1 < days <= 90:
                window_size = relativedelta(hours=1)
            case _:
                window_size = relativedelta(days=1)

        performance_df = create_windowed_dataframe(results_dict,
                                                   window_size=window_size).dropna()
        self._cached_first_prices = pd.Series(first_values_dict)
        self._cached_price_normalized_evolution = performance_df
        return performance_df, pd.Series(first_values_dict)

    @property
    def historical_normalized_prices(self):
        if self._cached_first_prices is None:
            self.update_history()
        return self._cached_price_normalized_evolution

    @property
    def historical_prices(self):
        return self.historical_normalized_prices.mul(self._cached_first_prices, axis=1)

    @property
    def historical_values(self):
        return self.historical_prices.mul(self.assets)

    @property
    def historical_percentages(self):
        return self.historical_values.div(self.historical_values.sum(axis=1), axis=0)

    @property
    def historical_totals(self):
        return self.historical_values.sum(axis=1)

    def plot_price_evolution(self):
        markevery = len(self.historical_normalized_prices) // 16
        self.historical_normalized_prices.plot(style=STYLE,
                                             markevery=markevery)
        plt.title(f'Price evolution of portfolio assets on the last {self.days} days.')
        plt.axhline(y=1, color='black', linestyle='--', label='CONSTANT')
        plt.show()

    def plot_percentages_evolution(self):
        markevery = len(self.historical_normalized_prices) // 16
        self.historical_percentages.plot(style=STYLE,
                                       markevery=markevery)
        plt.title(f'(% of portfolio) evolution of assets on the last {self.days} days.')
        plt.show()

    def plot_total_evolution(self):
        self.historical_totals.plot()
        plt.title(f'Total value of portfolio (in {self.quote.upper()}) evolution on the last {self.days} days.')
        plt.show()


class BackTestStrategyMixin():
    def _decorator(foo):
        def magic(self, *args, **kwargs) :
            strategy_result = foo(self, *args, **kwargs)
            match strategy_result:
                case TradeAction.BUY:
                    print('buy link')
                case TradeAction.SELL:
                    print('sell link')
        return magic

    def hodl_strategy(self, assets, percentages, values, prices, loop_counter):
        if loop_counter == 0:
            print('hodl buy link')
            new_total = values.sum() * 0.999  # 0.1% fee
            assets.chainlink = new_total / prices.chainlink
            assets.bitcoin = 0
            action = TradeAction.BUY

    def default_strategy(self, assets, percentages, values, prices, loop_counter):
        action = None
        new_total = values.sum() * 0.999  # 0.1% fee
        buy_link_threshold = self.strategy_params ['buy_link_threshold']
        sell_link_threshold = self.strategy_params ['sell_link_threshold']
        buy_link_target = self.strategy_params ['buy_link_target']
        sell_link_target = self.strategy_params ['sell_link_target']
        match percentages.chainlink:
            case percentages.chainlink if percentages.chainlink < buy_link_threshold:
                print('buy link', percentages.chainlink, end='')
                assets.chainlink = new_total * buy_link_target / prices.chainlink
                assets.bitcoin = new_total * (1 - buy_link_target) / prices.bitcoin
                action = TradeAction.BUY
                print('-->', percentages.chainlink)
            case percentages.chainlink if sell_link_threshold < percentages.chainlink:
                print('sell link', percentages.chainlink, end='')
                assets.chainlink = new_total * sell_link_target / prices.chainlink
                assets.bitcoin = new_total * (1 - sell_link_target) / prices.bitcoin
                action = TradeAction.SELL
                print('-->', percentages.chainlink)

        return action

    def random_strategy(self, assets, percentages, values, prices, loop_counter):
        self.strategy_params['buy_link_threshold'] = random.random() / 2
        self.strategy_params['sell_link_threshold'] = 1 - random.random() / 2
        self.strategy_params['buy_link_target'] = 1 - random.random() / 2
        self.strategy_params['sell_link_target'] = random.random() / 2
        return self.default_strategy(assets, percentages, values, prices, loop_counter)

        



class PortfolioBackTest(HistoricalPortfolio, BackTestStrategyMixin):
    def __init__(self, *args,
                 strategy: Callable = None,
                 strategy_params: dict = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.strategy = strategy or self.default_strategy
        self.strategy_params = strategy_params or dict()

        self.backtest_values = None

    def run(self):
        self.backtest_values = pd.DataFrame()
        self.backtest_values.name = 'Strategy'
        initial_assets = self.assets.copy()

        strategy_actions = []
        for loop_counter, (date, prices) in enumerate(self.historical_prices.iterrows()):
            values = self.assets * prices
            percentages = values / values.sum()

            values.name = date
            self.backtest_values = self.backtest_values.append(values)
            strategy_actions.append((date, self.strategy(self.assets, percentages, values, prices, loop_counter)))
        self.assets = initial_assets
        self.backtest_actions = pd.DataFrame(strategy_actions).set_index(0)[1].astype('bool')
        self.backtest_actions.name = 'Action performed'

        self.update_prices()
        return strategy_actions

    @property
    def backtest_totals(self):
        return self.backtest_values.sum(axis=1)

    def __truediv__(self, other):
        return (
            (
                self.backtest_values.iloc[-1].sum() / other.backtest_values.iloc[-1].sum()
            ) - 1
        )

    def plot_difference(self, other):
        this_strategy = self.backtest_totals
        this_strategy.name = 'Strategy main'
        other_strategy = other.backtest_totals
        other_strategy.name = 'Strategy other'

        performance = self / other * 100
        better_or_worse = 'better' if performance >= 0 else 'worse'
        performance_str = f'{performance:.2f}% {better_or_worse}.'

        pd.concat([this_strategy, other_strategy], axis=1).plot()
        has_changed_index = this_strategy.index[self.backtest_actions]
        plt.scatter(has_changed_index,
                    this_strategy[has_changed_index].values,
                    c='black',
                    marker='X')
        # c = ['yellow' if x else 'red' for x in other.backtest_actions]
        # plt.scatter(other_strategy.index, other_strategy, c=c)
        this_params_str = '\n'.join([f'{k:<20} {100* v:<5.2f}' for k, v in self.strategy_params.items()])
        other_params_str = '\n'.join([f'{k:<20} {100* v:<5.2f}' for k, v in other.strategy_params.items()])
        plt.title(f'This strategy:\n {this_params_str}\nOther strategy: {other_params_str}\n' + performance_str)
        plt.show()

    def test_all_strategies(self, hodl, n):
        for blth in np.arange(0, 0.50, 0.05):
            for slth in np.arange(0.5, 1, 0.05):
                for blta in np.arange(0.5, 1, 0.05):
                    for slta in np.arange(0, 0.5, 0.05):
                        self.strategy_params['buy_link_threshold'] = blth
                        self.strategy_params['sell_link_threshold'] = slth

                        self.strategy_params['buy_link_target'] = blta
                        self.strategy_params['sell_link_target'] = slta
                        self.run()
                        row = [blth, slth, blta, slta, self.plot_differenceprofit]
                        with open ('result.csv', 'a') as f:
                                   f.write(','.join(map(lambda x: str(x), row)) + '\n')

            # p.plot_difference()



if __name__ == '__main__':
    # coins_info = get_coins_info()
    #p = HistoricalPortfolio('main', 'usd')
    #exit()
    hodl = PortfolioBackTest('temp', 'usd', strategy=None)
    hodl.update_history(days=365)
    hodl.strategy = hodl.hodl_strategy
    hodl.run()
    p = PortfolioBackTest('temp', 'usd', strategy=None)
    p.update_history(days=365)
    p.strategy = p.random_strategy
    p.strategy_params['buy_link_threshold'] = 0.55
    p.strategy_params['sell_link_threshold'] = 0.85

    p.strategy_params['buy_link_target'] = 0.7
    p.strategy_params['sell_link_target'] = 0.3
    while 1:
        p.run()
        p.plot_difference(hodl)

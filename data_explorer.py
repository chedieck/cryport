from constants import CG
import json
from core import Portfolio, PortfolioMonitor, AssetCondition
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from constants import STYLE, TradeAction, PortfolioInfoType, ConditionType
from typing import Callable
import random
import numpy as np


def create_windowed_dataframe(results_dict, window_size):
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
    """Portfolio containing historical data for the assets.

    Attributes
    ----------

    days : pd.DataFrame
        DataFrame with alert conditions.
    _cached_first_prices : pd.Series
        Series with the first prices for each portfolio asset (prices `self.days` ago)
    _cached_price_normalized_evolution : pd.DataFrame
        Dataframe with the normalized price evolution of each asset (always starts at 1).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.days = None
        self._cached_first_prices = None
        self._cached_price_normalized_evolution = None

    def update_history(self, days=30):
        """Get historical data of each portfolio asset.

        Does not support custom granularity, as this is the CoinGecko API behavior.
        Granularity is determined automatic, as mentioned by CoinGecko API docs:
            days = 1         => 5 minute interval data
            1 < days <= days => hourly data
            days > 90        => daily data (00:00 UTC)
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
                lambda xy: (xy[0], xy[1] / first_value),
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

    @property
    def _markevery(self):
        return len(self.historical_normalized_prices) // 16

    def plot_price_evolution(self, normalized=True, show=True):
        if normalized:
            self.historical_normalized_prices.plot(style=STYLE,
                                                   markevery=self._markevery)
        else:
            self.historical_prices.plot(style=STYLE,
                                        markevery=self._markevery)
        plt.title(f'Price evolution of portfolio assets on the last {self.days} days.')
        plt.axhline(y=1, color='black', linestyle='--', label='CONSTANT')
        if show:
            plt.show()

    def plot_percentages_evolution(self, show=True):
        self.historical_percentages.plot(style=STYLE,
                                       markevery=self._markevery)
        plt.title(f'(% of portfolio) evolution of assets on the last {self.days} days.')
        if show:
            plt.show()

    def plot_total_evolution(self, show=True):
        self.historical_totals.plot()
        plt.title(f'Total value of portfolio (in {self.quote.upper()}) evolution on the last {self.days} days.')
        if show:
            plt.show()


class BackTestStrategyMixin():
    def validate(strategy):
        def wrapper(self, *args, **kwargs) :
            total = self.total

            strategy_result = strategy(self, *args, **kwargs)
            assert self.total <= total, f"{self.total} > {total}"
            match strategy_result:
                case TradeAction.BUY:
                    pass
                case TradeAction.SELL:
                    pass
            return strategy_result
        return wrapper

    def default_strategy(self, loop_counter):
        new_total = self.total * 0.999  # 0.1% fee
        boundary_delta = (self.alerts[ConditionType.PERCENTAGE_MAX].chainlink
                          - self.alerts[ConditionType.PERCENTAGE_MIN].chainlink)
        random_middle = random.random() * boundary_delta
        target = random_middle + self.alerts[ConditionType.PERCENTAGE_MIN].chainlink / self.alerts[ConditionType.PERCENTAGE_MAX].chainlink

        action = None
        for asset_condition in self.violated_asset_conditions:
            match asset_condition:
                case AssetCondition(asset='chainlink', condition=ConditionType.PERCENTAGE_MIN):
                    self.assets.chainlink = new_total * target / self.prices.chainlink
                    self.assets.bitcoin = new_total * (1 - target) / self.prices.bitcoin
                    action = TradeAction.BUY
                case AssetCondition(asset='chainlink', condition=ConditionType.PERCENTAGE_MAX):
                    self.assets.chainlink = new_total * target / self.prices.chainlink
                    self.assets.bitcoin = new_total * (1 - target) / self.prices.bitcoin
                    action = TradeAction.SELL
        return action

    @property
    def template_strategy_index(self):
        multiindex_tuples = []
        for condition in self.triggered_alerts.columns:
            for asset in self.triggered_alerts.index:
                multiindex_tuples.append((condition, asset))
        return pd.MultiIndex.from_tuples(multiindex_tuples)

    @validate
    def _DEPRECATED_default_strategy(self, loop_counter):
        action = None
        new_total = self.total * 0.999  # 0.1% fee
        buy_link_threshold = self.strategy_params ['buy_link_threshold']
        sell_link_threshold = self.strategy_params ['sell_link_threshold']
        buy_link_target = self.strategy_params ['buy_link_target']
        sell_link_target = self.strategy_params ['sell_link_target']
        link_percentage = self.percentages.chainlink
        match link_percentage:
            case link_percentage if link_percentage < buy_link_threshold:
                print('buy link', link_percentage, end='')
                self.assets.chainlink = new_total * buy_link_target / self.prices.chainlink
                self.assets.bitcoin = new_total * (1 - buy_link_target) / self.prices.bitcoin
                action = TradeAction.BUY
                print('-->', self.percentages.chainlink)
            case self.percentages.chainlink if sell_link_threshold < self.percentages.chainlink:
                print('sell link', link_percentage, end='')
                self.assets.chainlink = new_total * sell_link_target / self.prices.chainlink
                self.assets.bitcoin = new_total * (1 - sell_link_target) / self.prices.bitcoin
                action = TradeAction.SELL
                print('-->', self.percentages.chainlink)

        return action



class PortfolioBackTest(HistoricalPortfolio, PortfolioMonitor, BackTestStrategyMixin):
    """HistoricalPortfolio with backtest capabilities.

    Attributes
    ----------

    strategy : Callable
        Strategy to be used on backtest. Receives only the `loop_counter` as argument.
    strategy_params : dict
        Parameters to be used by the strategy.
    _cached_first_prices : pd.Series
        Series with the first prices for each portfolio asset (prices `self.days` ago)
    _cached_price_normalized_evolution : pd.DataFrame
        Dataframe with the normalized price evolution of each asset (always starts at 1).
    """
    def __init__(self, *args,
                 strategy: Callable = None,
                 strategy_params: dict = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.strategy = strategy or self.default_strategy
        self.strategy_params = strategy_params or dict()

        self.backtest_values = None
        self.backtest_actions = None

    def run(self):
        """Run the backtest.
        """
        self.backtest_values = pd.DataFrame()
        self.backtest_values.name = 'Strategy'
        initial_assets = self.assets.copy()

        try:
            strategy_actions = []
            for loop_counter, (date, prices) in enumerate(self.historical_prices.iterrows()):
                self.update_prices(prices_df=prices)

                values = self.values
                values.name = date
                self.backtest_values = self.backtest_values.append(values)
                self.update_triggered_alerts()
                strategy_action = self.strategy(loop_counter)  # changes assets
                strategy_actions.append((date, strategy_action))
            self.backtest_actions = pd.DataFrame(strategy_actions).set_index(0)[1]
            self.backtest_actions.name = 'Action performed'

        finally:
            self.update_prices()
            self.assets = initial_assets
            self.update_triggered_alerts()

        return strategy_actions

    @property
    def backtest_totals(self):
        return self.backtest_values.sum(axis=1)

    @property
    def profit(self):
        chainlink_profit = self.historical_normalized_prices['chainlink'].iloc[-1]
        bitcoin_profit = self.historical_normalized_prices['bitcoin'].iloc[-1]
        self_profit = self.backtest_totals.iloc[-1] / self.backtest_totals.iloc[0]
        return {'chainlink': self_profit / chainlink_profit - 1,
                'bitcoin': self_profit / bitcoin_profit - 1}


    def __truediv__(self, other):
        return (
            (
                self.backtest_values.iloc[-1].sum() / other.backtest_values.iloc[-1].sum()
            ) - 1
        )

    def plot_profit(self):
        this_strategy = self.backtest_totals
        this_strategy.name = 'Strategy'
        hodl_link = self.historical_normalized_prices.chainlink * self.historical_totals.iloc[0]
        hodl_bitcoin = self.historical_normalized_prices.bitcoin * self.historical_totals.iloc[0]
        hodl_link.name = 'HODL LINK'
        hodl_bitcoin.name = 'HODL BITCOIN'


        profit_bitcoin, profit_chainlink = self.profit['bitcoin'], self.profit['chainlink']
        better_or_worse_chainlink = 'better' if profit_chainlink >= 0 else 'worse'
        better_or_worse_bitcoin = 'better' if profit_bitcoin >= 0 else 'worse'
        performance_str = f'{profit_chainlink*100:.2f}% {better_or_worse_chainlink} than link HODL,'
        performance_str += f'{profit_bitcoin*100:.2f}% {better_or_worse_bitcoin} than bitcoin HODL.'

        pd.concat([this_strategy, hodl_link, hodl_bitcoin], axis=1).plot()
        has_bought_index = this_strategy.index[self.backtest_actions == TradeAction.BUY]
        has_sold_index = this_strategy.index[self.backtest_actions == TradeAction.SELL]
        plt.scatter(has_bought_index,
                    this_strategy[has_bought_index].values,
                    c='green',
                    marker='o', zorder=3)
        plt.scatter(has_sold_index,
                    this_strategy[has_sold_index].values,
                    c='red',
                    marker='X', zorder=3)
        this_params_str = '\n'.join([f'{k:<20} {100* v:<5.2f}%' for k, v in self.active_conditions.items()])
        plt.title(f'This strategy:\n {this_params_str}\n' + performance_str)
        plt.show()

    def test_all_strategies(self):
        with open ('result.csv', 'a') as f:
            for blth in np.arange(0, 0.50, 0.05):
                for slth in np.arange(0.5, 1, 0.05):
                    for blta in np.arange(0.5, 1, 0.05):
                        for slta in np.arange(0, 0.5, 0.05):
                            self.strategy_params['buy_link_threshold'] = blth
                            self.strategy_params['sell_link_threshold'] = slth

                            self.strategy_params['buy_link_target'] = blta
                            self.strategy_params['sell_link_target'] = slta
                            self.run()
                            row = [blth, slth, blta, slta, self.profit]
                            f.write(','.join(map(lambda x: str(x), row)) + '\n')

    def test_strategies_random(self):
        results_df = pd.DataFrame(columns=set(self.strategy_params.keys()) | {'profit'})
        while 1:
            self.randomize_params()
            self.run()
            row_dict = self.strategy_params.copy()
            row_dict.update({'profit': self.profit })
            results_df = results_df.append(row_dict, ignore_index=True)
            results_df.to_csv('results.csv')

            # p.plot_profit()



if __name__ == '__main__':
    # coins_info = get_coins_info()
    #exit()
    p = HistoricalPortfolio('main',
                         quote='usd')

    p = PortfolioBackTest('temp', 'usd', strategy=None)
    p.update_history(days=365)

    p.strategy_params['buy_link_target'] = 0.7
    p.strategy_params['sell_link_target'] = 0.3
    while 1:
        p.run()

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

    def plot_price_evolution(self, normalized=True, show=True, exclude_assets=None):
        exclude_assets = exclude_assets or []
        if normalized:
            to_plot_df = self.historical_normalized_prices.drop(exclude_assets, axis=1)
        else:
            to_plot_df = self.historical_prices.drop(exclude_assets, axis=1)

        to_plot_df.plot(style=STYLE,
                        markevery=self._markevery)
        plt.title(f'Price evolution of portfolio assets on the last {self.days} days.')
        if normalized:
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


if __name__ == '__main__':
    p = HistoricalPortfolio('example',
                            quote='usd')

    p.update_history(days=365)
    p.update_prices(show=True)

    print(p.values)
    print(p.percentages)
    print(p.total)

    p.plot_price_evolution()
    p.plot_percentages_evolution()
    p.plot_total_evolution()


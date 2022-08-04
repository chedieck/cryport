import pandas as pd
import json
from constants import (
    CG,
    USD_BRL,
    PORTFOLIOS_DIR,
    PortfolioInfoType,
    ConditionType,
    AGGREGATE_DUST_THRESHOLD,
    STYLE,
)
from termcolor import colored
from dataclasses import dataclass
from typing import List
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from scripts import create_windowed_dataframe


pd.options.display.float_format = '{:.8f}'.format


def update_src():
    # update list of coins
    coins_list = CG.get_coins_list()
    with open('src/coins.list', 'w') as f:
        json.dump(coins_list, f)

    quotes_list = CG.get_supported_vs_currencies()
    with open('src/quotes.list', 'w') as f:
        json.dump(quotes_list, f)


class Portfolio:
    """Portfolio, information about each asset being holded.

    Attributes
    ----------
    name: str
        Name of the portfolio.
    quote: str
        Currency on which information about assets value will be displayed.
    assets: pd.Series
        Series, how much of each asset is in the portfolio.

    self._cached_prices: None, pd.Series
        The price of each asset in the `quote` currency.
        Should be accessed through the `prices` property.
    """

    def __init__(self, name: str, quote='usd'):
        """Class constructor.

        Parameters
        ----------
        name : str
            Name of the CSV to read information from. Should be under `PORTFOLIOS_DIR`
            directory.
        quote: str
            Currency to weight the portfolio assets value upon.
            A full list of supported currencies can be founded on `./src/quotes.list`.
        """
        self.name = name
        self.quote = quote

        self.assets = pd.read_csv(f'{PORTFOLIOS_DIR}{name}.csv',
                                  index_col=0).amount
        self.assets.name = 'Assets'

        # values to be set
        self._cached_prices = None

    def __str__(self):
        return f'{self.name} ${self.quote}'

    def __repr__(self):
        return self.__str__()

    def delete_cache(self):
        """Reset cached values to `None`.
        """
        self._cached_prices = None

    def update_prices(self, prices_df=None, show=False):
        """Send request to CoinGecko and update price information. Deletes the cache.

        If `prices_df` is passed, use it instead to set as the prices.
        """
        self.delete_cache()

        if prices_df is not None:
            self._cached_prices = prices_df
        else:
            portfolio_coins_str = ','.join(self.assets.index)

            self._cached_prices = pd.DataFrame.from_dict(
                CG.get_price(portfolio_coins_str,
                             self.quote)
            ).transpose()[self.quote]
        self._cached_prices.name = 'Prices'
        if show:
            print(self.prices)

    @property
    def prices(self):
        if self._cached_prices is None:
            self.update_prices()
        return self._cached_prices.sort_values(
            ascending=False
        )

    @property
    def values(self):
        values_df = (self.prices * self.assets)
        values_df.name = 'Values'
        return values_df.sort_values(
            ascending=False
        )

    @property
    def percentages(self):
        percentages_df = self.values / self.values.sum()
        percentages_df.name = 'Percentages'
        return percentages_df.sort_values(
            ascending=False
        )

    def set_quote(self, quote):
        """Change the portfolio quote.
        """
        self.delete_cache()
        self.quote = quote

    @property
    def total_brl(self):
        return self.values.sum() * USD_BRL

    @property
    def total(self):
        return self.values.sum()

    def pie(self):
        values = list(self.values[self.percentages >= AGGREGATE_DUST_THRESHOLD].values)
        labels = list(self.values[self.percentages >= AGGREGATE_DUST_THRESHOLD].index)
        other = self.values[self.percentages < AGGREGATE_DUST_THRESHOLD]
        if len(other.index) != 0:
            values.append(other.sum())
            labels.append(', '.join(other.index))

        plt.pie(values, labels=labels, autopct='%1.1f%%', pctdistance=0.85, labeldistance=1.05)
        plt.title(f"Portfolio `{self.name}` total value: {self.total:.4f} {self.quote.upper()}")
        plt.show()


@dataclass
class AssetCondition:
    asset: str
    condition: ConditionType
    value: float = None

    def __str__(self):
        value_str = f': {self.value}' if self.value is not None else ''
        return f'{self.asset}-{self.condition}{value_str}'

    def __repr__(self):
        return f"<AssetCondition: {self.__str__()}>"

    def get_info_type(self) -> PortfolioInfoType:
        return self.condition.rsplit('_')[0]

    def get_side(self):
        """0 if lower boundary, 1 if upper.
        """
        return self.condition.rsplit('_')[-1]


class PortfolioMonitor(Portfolio):
    """Monitor to verify if portfolio assets has met conditions.

    Attributes
    ----------

    conditions : pd.DataFrame
        DataFrame with conditions.
    triggered_conditions : pd.DataFrame
        Boolean DataFrame indicating whether or not conditions have been violated.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        none_list = [None] * len(self.assets)
        aux_dict = {
            condition_type: none_list for condition_type in ConditionType.ALL
        }
        base_df = pd.DataFrame(
            aux_dict,
            index=self.assets.index
        )

        self.conditions = base_df.copy()
        self.triggered_conditions = base_df.copy().fillna(value=False)

    def add_condition_list(self, asset_condition_list: List[AssetCondition]):
        """Create an condition on an asset.

        Parameters
        ----------

        asset_condition: AssetCondition
            AssetCondition, with the `coin_id` asset and the condition to create.
        """
        for asset_condition in asset_condition_list:
            self.conditions.at[asset_condition.asset,
                               asset_condition.condition] = asset_condition.value

    def _get_asset_state(self, asset, info_type):
        """Return the price, value or percentage of asset on portfolio

        Parameters
        ----------
        asset: str
            Name (`coin_id`) of the asset to get state.
        info_type: PortfolioInfoType
            State to get: value, price or percentage.
        """
        match info_type:
            case PortfolioInfoType.PRICE:
                return self.prices.loc[asset]
            case PortfolioInfoType.PERCENTAGE:
                return self.percentages.loc[asset]
            case PortfolioInfoType.VALUE:
                return self.values.loc[asset]
            case _:
                raise ValueError("Invalid info_type")

    @property
    def active_conditions(self):
        return_list = []
        for (asset, condition), value in zip(self.conditions.stack().index,
                                             self.conditions.stack().values):
            return_list.append(
                AssetCondition(asset=asset, condition=condition, value=value)
            )
        return return_list

    @property
    def triggered_active_conditions(self):
        return_list = []
        for (asset, condition), value in zip(self.conditions[self.triggered_conditions].stack().index,
                                             self.conditions[self.triggered_conditions].stack().values):
            return_list.append(
                AssetCondition(asset=asset, condition=condition, value=value)
            )
        return return_list

    def _get_asset_boundary(self, asset, info_type):
        """Return the condition boundary of the asset.

        Parameters
        ----------
        asset: str
            Name (`coin_id`) of the asset to get boundary.
        info_type: PortfolioInfoType
            Boundary to get: value, price or percentage.
        """
        return (
            self.conditions.loc[asset, f'{info_type}_min'],
            self.conditions.loc[asset, f'{info_type}_max']
        )

    def update_triggered_conditions(self):
        """Trigger conditions that had their conditions met.

        If a condition, defined on `self.conditions` has been met,
        updates the same cell on `self.triggered_conditions` to True.
        """
        for ac in self.active_conditions:
            side = ac.get_side()
            state = self._get_asset_state(ac.asset, ac.get_info_type())
            match side:
                case 'min':
                    self.triggered_conditions.at[ac.asset, ac.condition] = state < ac.value
                case 'max':
                    self.triggered_conditions.at[ac.asset, ac.condition] = ac.value < state

    def _render_triggered_condition_string(self, asset_condition):
        state = self._get_asset_state(asset_condition.asset, asset_condition.get_info_type())
        side = asset_condition.get_side()
        match side:
            case 'min':
                condition_str = colored(f'{state:<20f} < {asset_condition.value:>20f}', 'red')
            case 'max':
                condition_str = colored(f'{state:<20f} > {asset_condition.value:>20f}', 'red')

        return f'{asset_condition.asset.upper():<20} {asset_condition.condition:<20} {condition_str}'

    def __str__(self):
        display = super().__str__()
        for ac in self.triggered_active_conditions:
            display += '\n' + self._render_triggered_condition_string(ac)
        return display


class PortfolioEqualizer(PortfolioMonitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name = args[0]
        self._cached_mutable_goals_percentages = None
        self._cached_defined_percentage = None
        self._cached_total_defined_value = None

        try:
            self.raw_goals = pd.read_csv(f'{PORTFOLIOS_DIR}{name}.eq.csv',
                                         index_col=0).goal
            self.goals = self._parse_goals()
            self.goals.name = 'Goals'
        except FileNotFoundError:
            self.goals = None

    def delete_cache(self):
        """Reset cached values to `None`.
        """
        super().delete_cache()
        self._cached_mutable_goals_percentages = None
        self._cached_defined_percentage = None
        self._cached_total_defined_value = None

    @property
    def mutable_goals_percentages(self) -> pd.Series:
        """The percentages of the assets that were marked as mutable (lines start with '%').
        This should always sum up to 100.
        """
        if self._cached_mutable_goals_percentages is None:
            self._cached_mutable_goals_percentages = self.raw_goals[
                self.raw_goals.str.startswith('%')
            ].apply(
                lambda x: float(x[1:]) if x != '%-' else self.each_remainder_percentage
            )
        return self._cached_mutable_goals_percentages

    @property
    def mutable_goals(self) -> pd.Series:
        """Same as `self.assets`, but the goals for each asset.
        """
        return self.goals[self.mutable_goals_percentages.index]

    @property
    def mutable_total(self) -> float:
        """Return the total value of the assets that were marked as mutable (lines start with '%')
        """
        return self.values[self.mutable_goals_percentages.index].sum()

    @property
    def defined_percentage(self):
        """Return the total percentage that was explicitally defined ('%-' rows not included)
        """
        if self._cached_defined_percentage is None:
            self._cached_defined_percentage = sum([
                float(x[1:]) for x in self.raw_goals if (
                    x.startswith('%') and not x.startswith('%-')
                )
            ])
        return self._cached_defined_percentage

    @property
    def defined_total(self):
        if self._cached_total_defined_value is None:
            self._cached_total_defined_value = self.defined_percentage * self.mutable_total
        return self._cached_total_defined_value

    @property
    def each_remainder_percentage(self):
        if self.defined_percentage > 100:
            raise ValueError('Total percentage on equalized CSV exceeds 100%.')
        return (100 - self.defined_percentage) / self.raw_goals[self.raw_goals == '%-'].count()

    @property
    def diff(self):
        diff = self.goals - self.assets
        return diff[diff != 0]

    @property
    def has_goal(self):
        return self.goals is not None

    def get_asset_amount_from_percentage(self, percentage: float, asset: str):
        return self.mutable_total * percentage / self.prices[asset]

    def _parse_goals(self):
        def parse_single_goal(goal: pd.Series):
            goal_str = goal.goal
            if goal_str.startswith('%'):
                if goal_str == '%-':
                    goal_str = f'%{self.each_remainder_percentage}'
                percentage = float(goal_str[1:]) / 100
                return self.get_asset_amount_from_percentage(percentage, goal.name)
            elif goal_str.startswith('#'):
                return float(goal_str[1:])

        return pd.DataFrame(self.raw_goals).apply(
            parse_single_goal, axis=1
        )

    def goals_pie(self):
        goals = list(self.mutable_goals_percentages[self.mutable_goals_percentages >= AGGREGATE_DUST_THRESHOLD].values)
        labels = list(self.mutable_goals_percentages[self.mutable_goals_percentages >= AGGREGATE_DUST_THRESHOLD].index)
        other = self.mutable_goals_percentages[self.mutable_goals_percentages < AGGREGATE_DUST_THRESHOLD]
        if len(other.index) != 0:
            goals.append(other.sum())
            labels.append(', '.join(other.index))

        plt.pie(goals, labels=labels, autopct='%1.1f%%', pctdistance=0.85, labeldistance=1.05)
        plt.title(f"Portfolio `{self.name}` mutable goals: {self.mutable_total:.4f} {self.quote.upper()}")
        plt.show()


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
            try:
                historical_data = CG.get_coin_market_chart_by_id(coin_id,
                                                                 self.quote,
                                                                 days=days)
            except ValueError as e:
                print('coin_id falhou', coin_id)
                raise e
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


"""
class Pf(PortfolioMonitor, HistoricalPortfolio):
    def __init__(self):
        super(PortfolioMonitor).__init__()
        super(HistoricalPortfolio).__init__()
"""
Pf = type('Pf', (PortfolioEqualizer, HistoricalPortfolio), dict(pf='pf'))


def main(pf):
    # will alert if:
    pf.add_condition_list([
        AssetCondition(asset='chainlink', condition=ConditionType.VALUE_MAX, value=6000),  # total link value on portfolio > 6000 USD
        AssetCondition(asset='hathor', condition=ConditionType.PERCENTAGE_MAX, value=0.1),  # hathor occupies > 10% of portfolio
        AssetCondition(asset='bitcoin', condition=ConditionType.PRICE_MAX, value=30000),  # bitcoin price > 70000 USD
        AssetCondition(asset='bitcoin', condition=ConditionType.PRICE_MIN, value=20000),  # bitcoin price < 60000 USD
    ])

    pf.update_triggered_conditions()
    print(pf)


if __name__ == '__main__':
    e = Pf('example',
           quote='usd')
    main(e)

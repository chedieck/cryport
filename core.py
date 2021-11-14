import pandas as pd
import json
from constants import (
    CG,
    PORTFOLIOS_DIR,
    PortfolioInfoType,
    ConditionType,
    AGGREGATE_DUST_THRESHOLD,
)
from termcolor import colored
from dataclasses import dataclass
from typing import List
import matplotlib.pyplot as plt


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

    def get_info_type(self):
        """0 if lower boundary, 1 if upper.
        """
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
                AssetCondition(asset=asset,condition=condition, value=value)
            )
        return return_list

    @property
    def triggered_active_conditions(self):
        return_list = []
        for (asset, condition), value in zip(self.conditions[self.triggered_conditions].stack().index,
                                             self.conditions[self.triggered_conditions].stack().values):
            return_list.append(
                AssetCondition(asset=asset,condition=condition, value=value)
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



if __name__ == '__main__':
    p = PortfolioMonitor('example',
                         quote='usd')
    # will alert if:
    p.add_condition_list([
        AssetCondition(asset='chainlink', condition=ConditionType.VALUE_MAX, value=6000),  # total link value on portfolio > 6000 USD
        AssetCondition(asset='hathor', condition=ConditionType.PERCENTAGE_MAX, value=0.1),  # hathor occupies > 10% of portfolio
        AssetCondition(asset='bitcoin', condition=ConditionType.PRICE_MAX, value=70000),  # bitcoin price > 70000 USD
        AssetCondition(asset='bitcoin', condition=ConditionType.PRICE_MIN, value=60000),  # bitcoin price < 60000 USD
    ])

    p.update_triggered_conditions()
    print(p)

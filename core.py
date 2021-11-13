import pandas as pd
import json
from constants import CG, PORTFOLIOS_DIR, PortfolioInfoType
from constants import ConditionType
pd.options.display.float_format = '{:.8f}'.format
from termcolor import colored
from dataclasses import dataclass



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


@dataclass
class AssetCondition:
    asset: str
    condition: ConditionType
    value: int = None

    def __str__(self):
        value_str = f': {self.value}' if self.value is not None else ''
        return f'{self.asset}-{self.condition}{value_str}'


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

    def add_condition(self, asset_condition: str, boundary: tuple):
        """Create an condition on an asset.

        Parameters
        ----------

        asset_condition: AssetCondition
            AssetCondition, with the `coin_id` asset and the condition to create.
        boundary: tuple (float, float)
            The boundary (a, b) on which the asset price, value or percentage has to remain
            before triggering the condition.
            
        """
        self.conditions.at[asset, f'{info_type}_min'] = boundary[0]
        self.conditions.at[asset, f'{info_type}_max'] = boundary[1]
       
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
        conditions = dict()
        for asset in self.assets.index:
            for condition_type in ConditionType.ALL:
                if (condition_value := self.conditions.loc[asset, condition_type]):
                    conditions[str(AssetCondition(asset, condition_type))] = condition_value

        return conditions

    @property
    def violated_asset_conditions(self):
        conditions = []
        for asset in self.assets.index:
            for condition_type in ConditionType.ALL:
                if self.triggered_conditions.loc[asset, condition_type]:
                    conditions.append(AssetCondition(asset, condition_type))
        return conditions


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
        def trigger_asset_conditions(row):
            asset = row.name
            for info_type in PortfolioInfoType.ALL:
                state = self._get_asset_state(asset, info_type)
                boundary = self._get_asset_boundary(asset, info_type)
                match boundary:
                    case (None, None):
                        continue
                    case (None, b):
                        self.triggered_conditions.loc[asset, f'{info_type}_max'] = b < state
                    case (a, None):
                        self.triggered_conditions.at[asset, f'{info_type}_min'] = state < a
                    case (a, b):
                        self.triggered_conditions.at[asset, f'{info_type}_min'] = state < a
                        self.triggered_conditions.at[asset, f'{info_type}_max'] = b < state
                    case _:
                        raise ValueError("Invalid boundary")
        self.conditions.apply(trigger_asset_conditions,
                          axis=1)

    def _render_condition_string(self, asset, info_type, violated_side):
        violated_value = self._get_asset_boundary(asset, info_type)[violated_side]
        state = self._get_asset_state(asset, info_type)
        match violated_side:
            case 0:
                condition_str = colored(f'{state} < {violated_value}', 'red')
            case 1:
                condition_str = colored(f'{state} > {violated_value}', 'red')

        return f'{asset.upper():<20} condition {info_type} boundary: current {info_type} {condition_str}.'

    def __str__(self):
        display = ''
        def show_asset_triggered_conditions(row):
            asset = row.name
            for info_type in PortfolioInfoType.ALL:
                if self.triggered_conditions.loc[asset, f'{info_type}_min']:
                    display += self._render_condition_string(asset, info_type, 0) + '\n'
                if self.triggered_conditions.loc[asset, f'{info_type}_max']:
                    display += self._render_condition_string(asset, info_type, 1) + '\n'

        self.triggered_conditions.apply(show_asset_triggered_conditions,
                                    axis=1)
        return display



if __name__ == '__main__':
    p.add_condition('chainlink', PortfolioInfoType.PRICE, (26, 30))
    # p.add_condition('chainlink', PortfolioInfoType.PERCENTAGE, (None, 50))
    # p.add_condition('ark', PortfolioInfoType.PERCENTAGE, (10, None))
    # p.add_condition('render-token', PortfolioInfoType.VALUE, (10, 1000))

    p.update_triggered_conditions()

import pandas as pd
import json
from constants import CG, PORTFOLIOS_DIR, PortfolioInfoType
from constants import Date
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

    def delete_cache(self):
        """Reset cached values to `None`.
        """
        self._cached_prices = None

    def update_prices(self):
        """Send request to CoinGecko and update price information. Deletes the cache.
        """
        self.delete_cache()

        portfolio_coins_str = ','.join(self.assets.index)

        self._cached_prices = pd.DataFrame.from_dict(
            CG.get_price(portfolio_coins_str,
                         self.quote)
        ).transpose()[self.quote]
        self._cached_prices.name = 'Prices'

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

    def get_historic_percentages(self,
                                 quote: str,
                                 start=Date.ONE_MONTH_AGO,
                                 end=Date.NOW):
        """Return Dataframe containing the historic percentages of the portfolio each asset would occupy

        Does not support custom granularity, as this is the CoinGecko API behavior. Granularity
        is determined automatic, as mentioned by CoinGecko API docs:
            1 day from query time = 5 minute interval data
            1 - 90 days from query time = hourly data
            above 90 days from query time = daily data (00:00 UTC)
        """
        pass


class PortfolioMonitor(Portfolio):
    """Monitor to verify if portfolio assets has met conditions.

    Attributes
    ----------

    alerts : pd.DataFrame
        DataFrame with alert conditions.
    triggered_alerts : pd.DataFrame
        Boolean DataFrame indicating whether or not alert conditions have been violated.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        none_list = [None] * len(self.assets)
        aux_dict = {
            f'{info_type}_a': none_list for info_type in PortfolioInfoType.ALL
        }
        aux_dict.update({
            f'{info_type}_b': none_list for info_type in PortfolioInfoType.ALL
        })
        base_df = pd.DataFrame(
            aux_dict,
            index=self.assets.index
        )

        self.alerts = base_df.copy()
        self.triggered_alerts = base_df.copy().fillna(value=False)

    def add_alert(self, asset: str, info_type: PortfolioInfoType, boundary: tuple):
        """Create an alert condition.

        Parameters
        ----------

        asset: str
            Name (`coin_id`) of the asset to create the condition on.
        info_type: PortfolioInfoType
            Type of the alert: price, value or percentage, see `PortfolioInfoType`.
        boundary: tuple (float, float)
            The boundary (a, b) on which the asset price, value or percentage has to remain
            before triggering the alert.
            
        """
        self.alerts.at[asset, f'{info_type}_a'] = boundary[0]
        self.alerts.at[asset, f'{info_type}_b'] = boundary[1]
       
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
            self.alerts.loc[asset, f'{info_type}_a'],
            self.alerts.loc[asset, f'{info_type}_b']
        ) 

    def update_triggered_alerts(self):
        """Trigger alerts that had their conditions met.

        If an alert condition, defined on `self.alerts` has been met,
        updates the same cell on `self.triggered_alerts` to True.
        """
        def trigger_asset_alerts(row):
            asset = row.name
            for info_type in PortfolioInfoType.ALL:
                state = self._get_asset_state(asset, info_type)
                boundary = self._get_asset_boundary(asset, info_type)
                match boundary:
                    case (None, None):
                        continue
                    case (None, b):
                        self.triggered_alerts.loc[asset, f'{info_type}_b'] = b < state
                    case (a, None):
                        self.triggered_alerts.at[asset, f'{info_type}_a'] = state < a
                    case (a, b):
                        self.triggered_alerts.at[asset, f'{info_type}_a'] = state < a
                        self.triggered_alerts.at[asset, f'{info_type}_b'] = b < state
                    case _:
                        raise ValueError("Invalid boundary")
        self.alerts.apply(trigger_asset_alerts,
                          axis=1)

if __name__ == '__main__':
    update_src()
    p = Portfolio('example',
                  quote='usd')
    p.add_alert('chainlink', PortfolioInfoType.PRICE, (26, 30))
    # p.add_alert('chainlink', PortfolioInfoType.PERCENTAGE, (None, 50))
    p.update_triggered_alerts()


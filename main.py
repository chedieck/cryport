import pandas as pd
import json
from constants import CG, PORTFOLIOS_DIR, AlertType
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

    self._cached_values: None, pd.Series
        How much each asset values on the `quote` currency.
        Should be accessed through the `values` property.
    self._cached_percentages: None, pd.Series
        The percentage of the whole portfolio that each asset occupies.
        Should be accessed through the `percentages` property.
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
        self._cached_values = None
        self._cached_percentages = None
        self._cached_prices = None

    def delete_cache(self):
        """Reset cached values to `None`.
        """
        self._cached_values = None
        self._cached_percentages = None
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
        return self._cached_prices

    def _calculate_values(self):
        self._cached_values = self.prices.loc[self.assets.index] * self.assets.values
        self._cached_values.name = 'Values'

    def _calculate_percentages(self):
        self._cached_percentages = self.values / self.values.sum() * 100
        self._cached_percentages.name = 'Percentages'

    @property
    def values(self):
        if self._cached_values is None:
            self._calculate_values()
        return self._cached_values

    @property
    def percentages(self):
        if self._cached_percentages is None:
            self._calculate_percentages()
        return self._cached_percentages

    def set_quote(self, quote):
        """Change the portfolio quote.
        """
        self.delete_cache()
        self.quote = quote

    def get_total(self):
        return self.values.sum()

    def get_sorted_values(self, ascending=False):
        """Sorted `self.values` series.

        Parameters
        ----------

        ascending: bool, optional
            If the result should be in ascending order of value, instead of descending.

        Return
        ------
        pd.Series
            How much each asset values, in `quote`.
        """
        return self.values.sort_values(
            ascending=ascending
        )

    def get_sorted_percentages(self, ascending=False):
        """Sorted `self.percentages` series.

        Parameters
        ----------

        ascending: bool, optional
            If the result should be in ascending order of percentage, instead of descending.

        Return
        ------
        pd.Series
            The percentage of the portfolio that each asset occupies, in `quote`.
        """
        return self.percentages.sort_values(
            ascending=ascending
        )

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
            f'{alert_type}_a': none_list for alert_type in AlertType.ALL
        }
        aux_dict.update({
            f'{alert_type}_b': none_list for alert_type in AlertType.ALL
        })
        base_df = pd.DataFrame(
            aux_dict,
            index=self.assets.index
        )

        self.alerts = base_df.copy()
        self.triggered_alerts = base_df.copy().fillna(value=False)

    def add_alert(self, asset: str, alert_type: AlertType, boundary: tuple):
        """Create an alert condition.

        Parameters
        ----------

        asset: str
            Name (`coin_id`) of the asset to create the condition on.
        alert_type: AlertType
            Type of the alert: price, value or percentage, see `AlertType`.
        boundary: tuple (float, float)
            The boundary (a, b) on which the asset price, value or percentage has to remain
            before triggering the alert.
            
        """
        self.alerts.at[asset, f'{alert_type}_a'] = boundary[0]
        self.alerts.at[asset, f'{alert_type}_b'] = boundary[1]
       
    def _get_asset_state(self, asset, alert_type):
        """Return the price, value or percentage of asset on portfolio

        Parameters
        ----------
        asset: str
            Name (`coin_id`) of the asset to get state.
        alert_type: AlertType
            State to get: value, price or percentage.
            
        """
        match alert_type:
            case AlertType.PRICE:
                return self.prices.loc[asset]
            case AlertType.PERCENTAGE:
                return self.percentages.loc[asset]
            case AlertType.VALUE:
                return self.values.loc[asset]
            case _:
                raise ValueError("Invalid alert_type")

    def _get_asset_boundary(self, asset, alert_type):
        return (
            self.alerts.loc[asset, f'{alert_type}_a'],
            self.alerts.loc[asset, f'{alert_type}_b']
        ) 

    def update_triggered_alerts(self):
        """Trigger alerts that had their conditions met.

        If an alert condition, defined on `self.alerts` has been met,
        updates the same cell on `self.triggered_alerts` to True.
        """
        def trigger_asset_alerts(row):
            asset = row.name
            for alert_type in AlertType.ALL:
                state = self._get_asset_state(asset, alert_type)
                boundary = self._get_asset_boundary(asset, alert_type)
                match boundary:
                    case (None, None):
                        continue
                    case (None, b):
                        self.triggered_alerts.loc[asset, f'{alert_type}_b'] = b < state
                    case (a, None):
                        self.triggered_alerts.at[asset, f'{alert_type}_a'] = state < a
                    case (a, b):
                        self.triggered_alerts.at[asset, f'{alert_type}_a'] = state < a
                        self.triggered_alerts.at[asset, f'{alert_type}_b'] = b < state
                    case _:
                        raise ValueError("Invalid boundary")
        self.alerts.apply(trigger_asset_alerts,
                          axis=1)
if __name__ == '__main__':
    update_src()
    p = Portfolio('example',
                  quote='usd')

    print(p.values)
    print(p.percentages)

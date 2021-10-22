import pandas as pd
import json
from constants import CG, PORTFOLIOS_DIR
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


if __name__ == '__main__':
    update_src()
    p = Portfolio('example',
                  quote='usd')

    print(p.values)
    print(p.percentages)

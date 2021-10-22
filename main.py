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
    quote_currencies: iterable
        Currencies on which information about assets value will be displayed.
    assets_df: pd.DataFrame
        DataFrame, rows are assets and contains two columns: `coin_id` (assets)
        and `amount` (how much of each asset). Main portfolio dataframe.

    self._cached_values_df: None, pd.DataFrame
        Cached values for each asset (rows) on each of the quote currencies (columns).
    self._cached_percentages_df: None, pd.DataFrame
        Cached values for the percentage of the whole portfolio that each asset (rows)
        occupies, according to each of the quote currencies (columns).
    self._cached_prices_df: None, pd.DataFrame
        Cached prices for each asset (rows) in each of the quote currencies.
    """

    def __init__(self, name: str, quote_currencies=('usd',)):
        """Class constructor.
        
        Parameters
        ----------
        name : str
            Name of the CSV to read information from. Should be under `PORTFOLIOS_DIR`
            directory.
        quote_currencies : iterable
            Currencies to weight the portfolio assets value upon. A full list of
            supported currencies can be founded on src/quotes.list.
        """
        self.name = name
        self.quote_currencies = quote_currencies

        self.assets_df = pd.read_csv(f'{PORTFOLIOS_DIR}{name}.csv',
                              index_col=0)

        # values to be set
        self._cached_values_df = None
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def delete_cache(self):
        """Reset cached values to `None`.
        """
        self._cached_values_df = None
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def update_prices(self):
        """Send request to CoinGecko and update price information. Resets the cache.
        """
        self.delete_cache()

        portfolio_coins_str = ','.join(self.assets_df.index)
        quote_currencies_str = ','.join(self.quote_currencies)

        self._cached_prices_df = pd.DataFrame.from_dict(
            CG.get_price(portfolio_coins_str,
                         quote_currencies_str)
        ).transpose()

    @property
    def prices_df(self):
        if self._cached_prices_df is None:
            self.update_prices()
        return self._cached_prices_df

    def _calculate_values(self):
        self._cached_values_df = self.prices_df.loc[self.assets_df.index] * self.assets_df.values

    def _calculate_percentages(self):
        self._cached_percentages_df = self.values_df / self.values_df.sum() * 100

    @property
    def values_df(self):
        if self._cached_values_df is None:
            self._calculate_values()
        return self._cached_values_df

    @property
    def percentages_df(self):
        if self._cached_percentages_df is None:
            self._calculate_percentages()
        return self._cached_percentages_df

    def set_quote_currencies(self, quote_currencies):
        self.quote_currencies = quote_currencies

    def get_totals(self):
        return self.values_df.sum()

    def get_sorted_values(self, quote: str, ascending=False):
        """Return dataframe containing how much each asset values, in `quote`.

        Parameters
        ----------

        quote: str
            The currency to check the value upon. Must be one of `self.quote_currencies`
        ascending: bool, optional
            If the result should be in ascending order of value, instead of descending.

        Return
        ------
        pd.DataFrame
            How much each asset values, in `quote`.
        """
        quote_values_df = self.values_df[quote]
        return quote_values_df.sort_values(
            ascending=ascending
        )

    def get_sorted_percentages(self, quote, ascending=False):
        """Return dataframe containing the percentage of the portfolio that each asset occupies.

        Parameters
        ----------

        quote: str
            The currency to check the value upon. Must be one of `self.quote_currencies`
        ascending: bool, optional
            If the result should be in ascending order of percentage, instead of descending.

        Return
        ------
        pd.DataFrame
            The percentage of the portfolio that each asset occupies, in `quote`.
        """
        quote_percentages_df = self.percentages_df[quote]
        return quote_percentages_df.sort_values(
            ascending=ascending
        )


if __name__ == '__main__':
    update_src()
    p = Portfolio('example',
                  quote_currencies=['usd', 'eth', 'btc'])
    print(p.values_df)
    print(p.percentages_df)

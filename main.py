import pandas as pd
import json
from constants import CG, PORTFOLIOS_DIR


def update_src():
    # update list of coins
    coins_list = CG.get_coins_list()
    with open('src/coins.list', 'w') as f:
        json.dump(coins_list, f)

    quotes_list = CG.get_supported_vs_currencies()
    with open('src/quotes.list', 'w') as f:
        json.dump(quotes_list, f)


class Portfolio:
    """Portfolio, information about the amount of each currency being holded.

    Parameters
    ----------
    name : str
        Name of the CSV to read information from. Should be under `PORTFOLIOS_DIR`
        directory.
    quote_currencies : iterable
        Currencies to weight portfolio value upon. A full list of supported currencies
        can be founded on src/quotes.list
    """

    def __init__(self, name: str, quote_currencies=('usd',)):
        self.name = name
        self.quote_currencies = quote_currencies

        self.df = pd.read_csv(f'{PORTFOLIOS_DIR}{name}.csv',
                              index_col=0)

        # values to be set
        self._cached_amounts_df = None
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def reset_cache(self):
        self._cached_amounts_df = None
        """Reset cached values to `None`.
        """
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def update_prices(self):
        """Send request to CoinGecko and update price information. Resets the cache.
        """
        self.reset_cache()
        portfolio_coins_str = ','.join(self.df.index)
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

    def _calculate_amounts(self):
        self._cached_amounts_df = self.prices_df.loc[self.df.index] * self.df.values

    def _calculate_percentages(self):
        self._cached_percentages_df = self.amounts_df / self.amounts_df.sum() * 100

    @property
    def amounts_df(self):
        if self._cached_amounts_df is None:
            self._calculate_amounts()
        return self._cached_amounts_df

    @property
    def percentages_df(self):
        if self._cached_percentages_df is None:
            self._calculate_percentages()
        return self._cached_percentages_df

    def set_quote_currencies(self, quote_currencies):
        self.quote_currencies = quote_currencies

    def get_sorted_amounts(self, quote, ascending=False):
        quote_amounts_df = self.amounts_df[quote]
        return quote_amounts_df.sort_values(
        """Return dict containing how much each holding values, in `quote`.

        Parameters
        ----------

        quote: str
            The currency to check the value upon. Must be one of `self.quote_currencies`
        ascending: bool, optional
            If the result should be in ascending order of value, instead of descending.

        Return
        ------
        dict
            How much each holding values, in `quote`.
        """
            ascending=ascending
        ).to_dict()

    def get_sorted_percentages(self, quote, ascending=False):
        """Return dict containing the percentage of the portfolio that each holding occupies.

        Parameters
        ----------

        quote: str
            The currency to check the value upon. Must be one of `self.quote_currencies`
        ascending: bool, optional
            If the result should be in ascending order of percentage, instead of descending.

        Return
        ------
        dict
            The percentage of each holding values, in `quote`.
        """
        quote_percentages_df = self.percentages_df[quote]
        return quote_percentages_df.sort_values(
            ascending=ascending
        ).to_dict()


if __name__ == '__main__':
    update_src()
    p = Portfolio('example',
                  quote_currencies=['usd', 'eth', 'btc'])
    print(p.amounts_df)
    print(p.percentages_df)

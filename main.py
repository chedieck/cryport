import pandas as pd
import json
from constants import CG


def update_src():
    # update list of coins
    coins_list = CG.get_coins_list()
    with open('src/coins.list', 'w') as f:
        json.dump(coins_list, f)

    quotes_list = CG.get_supported_vs_currencies()
    with open('src/quotes.list', 'w') as f:
        json.dump(quotes_list, f)


class Portfolio:
    def __init__(self, name, quote_currencies=('usd',)):
        self.name = name
        self.quote_currencies = quote_currencies

        self.df = pd.read_csv(f'portfolios/{name}.csv',
                              index_col=0)

        # values to be set
        self._cached_amounts_df = None
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def reset_cache(self):
        self._cached_amounts_df = None
        self._cached_percentages_df = None
        self._cached_prices_df = None

    def update_prices(self):
        self.reset_cache()
        # CoinGeckoAPI.get_price expects string of ids joined by comma
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
            ascending=ascending
        ).to_dict()

    def get_sorted_percentages(self, quote, ascending=False):
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

from unittest.mock import patch, Mock
from main import Portfolio
import pytest
import pandas as pd

mock_cg_get_price = {'chainlink': {'usd': 18.78, 'eth': 0.00713439, 'btc': 0.00047071}, 'bitcoin': {'usd': 61163, 'eth': 15.163804, 'btc': 1.0}, 'hathor': {'usd': 0.756956, 'eth': 0.00018768, 'btc'
: 1.238e-05}}

class TestPortfolio:
    @staticmethod
    def test_update_prices():
        with patch('pycoingecko.CoinGeckoAPI.get_price', Mock(return_value=mock_cg_get_price)):
            portfolio = Portfolio('example')
            mock_prices_df = pd.DataFrame.from_dict(mock_cg_get_price).transpose()
            assert portfolio.prices_df.to_string() == mock_prices_df.to_string() 

# Cryport
## Python portfolio manager for cryptocurrencies
---
Requires `pandas`, [pycoingecko](https://github.com/man-c/pycoingecko), **and Python 3.10**.

`pip install -r requirements.txt`

Simple portfolio manager, to start just create a csv file of your portoflio in the `portfolio/` folder (see [portfolios/example.csv](https://github.com/chedieck/cryport/blob/master/portfolios/example.csv). Running `python -i data_explorer` shows the basic functionality of the `Portfolio` and the `HistoricalPortfolio` classes. Running `python -i core.py` shows the basic functionality of the `PortfolioMonitor` class.

The CSV must have the header indicating the two columns: `coin_id, amount`. The `coin_id` usually can be found browsing in coingecko: is the last subdirectory that appears on the URL (example: the bitcoin URL is https://www.coingecko.com/pt/moedas/bitcoin, so the `coin_id` for bitcoin is `bitcoin`). **However, this is not always the case.**

 BNB, for example, has `binance-coin` as the end of the website URL: [https://www.coingecko.com/pt/moedas/binance-coin](https://www.coingecko.com/pt/moedas/binance-coin), but it's `coin_id` is actually `binancecoin`. For that reason, you might want to check [CoinGecko Token API List](https://docs.google.com/spreadsheets/d/1wTTuxXt8n9q7C4NDXqQpI3wpKu1_5bGVmP9Xz0XGSyU/edit#gid=0) on google sheets. A list with this information is also available on the repository, under [src/coins.list](https://github.com/chedieck/cryport/blob/master/src/coins.list).

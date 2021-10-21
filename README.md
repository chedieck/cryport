# Cryport
## Python portfolio manager for cryptocurrencies
---
Requires `pandas` and [pycoingecko](https://github.com/man-c/pycoingecko).

Simple portfolio manager, to start just create a csv file of your portoflio in the `portfolio/` folder (see [portfolios/example.csv](https://github.com/chedieck/cryport/blob/master/portfolios/example.csv).

The CSV must have the header indicating the two columns: `coin_id, amount`. The `coin_id` can be found browsing in coingecko: is the last subdirectory that appears on the URL (example: the bitcoin URL is https://www.coingecko.com/pt/moedas/bitcoin, so the `coin_id` for bitcoin is `bitcoin`).

Running `main.py` directly provides the user with an example of the software current functionality.

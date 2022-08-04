# Cryport
## Python portfolio manager for cryptocurrencies
---
Requires `pandas`, [pycoingecko](https://github.com/man-c/pycoingecko), **and Python 3.10**.

`pip install -r requirements.txt`

Simple portfolio manager, to start just create a csv file of your portoflio in the `portfolios/` folder (see [portfolios/example.csv](https://github.com/chedieck/cryport/blob/master/portfolios/example.csv). Running `python -i core.py` shows the basic functionality of the `Pf` class.

The CSV must have the header indicating the two columns: `coin_id, amount`. The `coin_id` usually can be found browsing in coingecko: is the last subdirectory that appears on the URL (example: the bitcoin URL is https://www.coingecko.com/pt/moedas/bitcoin, so the `coin_id` for bitcoin is `bitcoin`). **However, this is not always the case.**

 BNB, for example, has `binance-coin` as the end of the website URL: [https://www.coingecko.com/pt/moedas/binance-coin](https://www.coingecko.com/pt/moedas/binance-coin), but it's `coin_id` is actually `binancecoin`. For that reason, you might want to check [CoinGecko Token API List](https://docs.google.com/spreadsheets/d/1wTTuxXt8n9q7C4NDXqQpI3wpKu1_5bGVmP9Xz0XGSyU/edit#gid=0) on google sheets. A list with this information is also available on the repository, under [src/coins.list](https://github.com/chedieck/cryport/blob/master/src/coins.list).

Equilizer
---------

This feature allows you to find out the amounts you should have for each asset to achieve a specific portfolio balancing. Example: Suppose the following portfolio:
```
<example.csv>

coin_id,amount
chainlink,300
bitcoin,0.1234444
ecash,3000000
```

Then let's say that those Bitcoins are in a cold wallet, and I don't want to do anything with it. But I want to keep a 70/30 split between Ethereum and Chainlink. Then it suffices to create the following file also in the `portfolios/` folder, with the same `coin_id`s as the `example.csv` file:
```
<example.eq.csv>

coin_id,goal
chainlink,%70
bitcoin,#0.1234444
ecash,%30
```

Then you can access: 
```
>>>example = Pf('example', 'usd')
>>>example.goals
chainlink        222.54541724
bitcoin            0.1234444
ecash       15965262.19372567
```

Not that the bitcoin amount is  the same, but the other two have changed. The fixed amount specified by the prefix '#' in the `.eq.csv` indicates that this quantity is not mutable. The other lines, prefixed by '%', indicate the percentage goal for each of the assets:

```
>>>example.mutable_goals_percentages
coin_id
chainlink   70.00000000
ecash       30.00000000
```

Furthermore, one could leave a goal blank: blank goals are indicated with '%-', and the remainder percentange will be split between then. Example:

```
<example.csv>

coin_id,amount
bitcoin,0.1
ecash,0
hathor,50
chainlink,123
ethereum,1
render-token,0
```
```
<example.eq.csv>

coin_id,goal
bitcoin,%50
ecash,%20
hathor,%-
chainlink,#123
ethereum,%-
render-token,%-
```

Will give us:
```
>>>example = Pf('example', 'usd')
>>> example.mutable_goals_percentages
coin_id
bitcoin        50.00000000
ecash          20.00000000
hathor         10.00000000
ethereum       10.00000000
render-token   10.00000000
>>>example.goals
bitcoin               0.08555589
ecash          17684167.20183486
hathor             2806.41807831
chainlink           123.00000000
ethereum              0.24165967
render-token        574.18436194

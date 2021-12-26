from constants import CG
from datetime import datetime
import pandas as pd
import json


class CoinInfo:
    def __init__(self, raw_response):
        self.raw_response = raw_response


def get_coins_info(coin_id_list):
    # update list of coins
    return_dict = dict()
    for coin in coin_id_list:
        coin_info = CoinInfo(CG.get_coin_by_id(coin))
        return_dict[coin] = coin_info

    return return_dict


def update_src():
    # update list of coins
    coins_list = CG.get_coins_list()
    with open('src/coins.list', 'w') as f:
        json.dump(coins_list, f)

    quotes_list = CG.get_supported_vs_currencies()
    with open('src/quotes.list', 'w') as f:
        json.dump(quotes_list, f)


def create_windowed_dataframe(results_dict, window_size):
    oldest_date = min([v[0][0] for v in results_dict.values()])
    start = datetime.fromtimestamp(oldest_date / 1000)
    new_df = pd.DataFrame(columns=set(results_dict.keys()) | {'date'})

    now = datetime.now()
    loop_counter = 0
    while start < now:
        row_data = {}
        for k, v in results_dict.items():
            for ts, value in v:
                if start <= datetime.fromtimestamp(ts / 1000):
                    row_data[k] = value
                    break

        new_df = new_df.append({
            'date': start,
            **row_data
        }, ignore_index=True)

        start += window_size
        loop_counter += 1
    return new_df.set_index('date')

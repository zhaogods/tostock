#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import logging
import concurrent.futures
import pandas as pd
import os.path
import sys
import datetime

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
import instock.core.backtest.rate_stats as rate
import instock.core.stockfetch as stf

__author__ = 'myh '
__date__ = '2023/3/10 '


def _date_start_for_backtest(date_value):
    if hasattr(date_value, 'strftime'):
        date_value = date_value.strftime('%Y-%m-%d')
    tmp_year, tmp_month, tmp_day = str(date_value).split('-')
    date_end = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day))
    return (date_end + datetime.timedelta(days=-(365 * 3))).strftime('%Y%m%d')


def load_hist_data(stocks, workers=8):
    data = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_stock = {
                executor.submit(stf.fetch_stock_hist, stock, _date_start_for_backtest(stock[0]), True): stock
                for stock in stocks
            }
            for future in concurrent.futures.as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    hist = future.result()
                    if hist is not None:
                        data[stock[1]] = hist
                except Exception as e:
                    logging.error(f"backtest_data_daily_job.load_hist_data处理异常：{stock[1]}代码{e}")
    except Exception as e:
        logging.error(f"backtest_data_daily_job.load_hist_data处理异常：{e}")
    if not data:
        return None
    return data


# 股票策略回归测试。
def prepare():
    tables = [tbs.TABLE_CN_STOCK_INDICATORS_BUY, tbs.TABLE_CN_STOCK_INDICATORS_SELL]
    tables.extend(tbs.TABLE_CN_STOCK_STRATEGIES)
    backtest_columns = list(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
    backtest_columns.insert(0, 'code')
    backtest_columns.insert(0, 'date')
    backtest_column = backtest_columns

    # 回归测试表
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for table in tables:
            executor.submit(process, table, backtest_column)


def process(table, backtest_column):
    table_name = table['name']
    if not mdb.checkTableIsExist(table_name):
        return

    column_tail = tuple(table['columns'])[-1]
    now_date = datetime.datetime.now().date()
    sql = f"SELECT * FROM `{table_name}` WHERE `date` < '{now_date}' AND `{column_tail}` is NULL"
    try:
        data = pd.read_sql(sql=sql, con=mdb.engine())
        if data is None or len(data.index) == 0:
            return

        subset = data[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
        subset = subset.astype({'date': 'string'})
        stocks = [tuple(x) for x in subset.values]

        load_subset = subset.sort_values('date').drop_duplicates(subset='code', keep='first')
        load_stocks = [tuple(x) for x in load_subset.values]
        stocks_data = load_hist_data(load_stocks)
        if stocks_data is None:
            return

        results = run_check(stocks, stocks_data, backtest_column)
        if results is None:
            return

        data_new = pd.DataFrame(results.values())
        mdb.update_db_from_df(data_new, table_name, ('date', 'code'))

    except Exception as e:
        logging.error(f"backtest_data_daily_job.process处理异常：{table}表{e}")


def run_check(stocks, data_all, backtest_column, workers=40):
    data = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_data = {executor.submit(rate.get_rates, stock,
                                              data_all.get(stock[1]), backtest_column,
                                              len(backtest_column) - 1): stock for stock in stocks}
            for future in concurrent.futures.as_completed(future_to_data):
                stock = future_to_data[future]
                try:
                    _data_ = future.result()
                    if _data_ is not None:
                        data[stock] = _data_
                except Exception as e:
                    logging.error(f"backtest_data_daily_job.run_check处理异常：{stock[1]}代码{e}")
    except Exception as e:
        logging.error(f"backtest_data_daily_job.run_check处理异常：{e}")
    if not data:
        return None
    else:
        return data


def main():
    prepare()


# main函数入口
if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging

import pandas as pd


RATE_FIELDS = ('rate_5', 'rate_10', 'rate_20')


def _safe_mean(series):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if values.empty:
        return None
    return round(float(values.mean()), 4)


def _safe_win_rate(series):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if values.empty:
        return None
    return round(float((values > 0).mean() * 100), 4)


def _safe_max(series):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if values.empty:
        return None
    return round(float(values.max()), 4)


def _safe_min(series):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if values.empty:
        return None
    return round(float(values.min()), 4)


def build_strategy_rank(date=None):
    import instock.core.tablestructure as tbs
    import instock.lib.database as mdb

    if date is None:
        date = datetime.date.today()
    rows = []
    for strategy in tbs.TABLE_CN_STOCK_STRATEGIES:
        table_name = strategy['name']
        try:
            if not mdb.checkTableIsExist(table_name):
                continue
            sql = f"SELECT {', '.join('`%s`' % f for f in RATE_FIELDS)} FROM `{table_name}` WHERE `date` <= %s AND `rate_20` IS NOT NULL"
            data = pd.read_sql(sql=sql, con=mdb.engine(), params=(date,))
        except Exception as exc:
            logging.error(f"leaderboard.build_strategy_rank处理异常：{table_name}{exc}")
            continue
        if data is None or data.empty:
            continue
        row = {
            'date': date,
            'strategy_name': strategy['cn'],
            'strategy_table': table_name,
            'sample_count': int(len(data.index)),
            'avg_rate_5': _safe_mean(data['rate_5']),
            'avg_rate_10': _safe_mean(data['rate_10']),
            'avg_rate_20': _safe_mean(data['rate_20']),
            'win_rate_5': _safe_win_rate(data['rate_5']),
            'win_rate_10': _safe_win_rate(data['rate_10']),
            'win_rate_20': _safe_win_rate(data['rate_20']),
            'best_rate_20': _safe_max(data['rate_20']),
            'worst_rate_20': _safe_min(data['rate_20']),
            'updated_at': datetime.datetime.now(),
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=list(tbs.TABLE_CN_STOCK_STRATEGY_BACKTEST_RANK['columns']))


def save_strategy_rank(date=None):
    import instock.core.tablestructure as tbs
    import instock.lib.database as mdb

    data = build_strategy_rank(date)
    if data is None or data.empty:
        return 0
    table = tbs.TABLE_CN_STOCK_STRATEGY_BACKTEST_RANK
    table_name = table['name']
    if mdb.checkTableIsExist(table_name):
        mdb.executeSql(f"DELETE FROM `{table_name}` where `date` = %s", (date or datetime.date.today(),))
        cols_type = None
    else:
        cols_type = tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`strategy_table`")
    return len(data.index)

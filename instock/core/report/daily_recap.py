#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os

import pandas as pd

from instock.lib import config


def _modules():
    import instock.core.tablestructure as tbs
    import instock.lib.database as mdb
    return tbs, mdb


def _read_sql(sql, params=None):
    _, mdb = _modules()
    try:
        return pd.read_sql(sql=sql, con=mdb.engine(), params=params)
    except Exception as exc:
        logging.error(f'daily_recap._read_sql处理异常：{exc}')
        return pd.DataFrame()


def _stock_overview(date):
    tbs, mdb = _modules()
    table = tbs.TABLE_CN_STOCK_SPOT['name']
    if not mdb.checkTableIsExist(table):
        return {'total': 0, 'up': 0, 'down': 0, 'flat': 0}
    sql = f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN `change_rate` > 0 THEN 1 ELSE 0 END) AS up_count,
               SUM(CASE WHEN `change_rate` < 0 THEN 1 ELSE 0 END) AS down_count,
               SUM(CASE WHEN `change_rate` = 0 THEN 1 ELSE 0 END) AS flat_count
        FROM `{table}` WHERE `date` = %s
    """
    data = _read_sql(sql, (date,))
    if data.empty:
        return {'total': 0, 'up': 0, 'down': 0, 'flat': 0}
    row = data.iloc[0]
    return {
        'total': int(row.get('total') or 0),
        'up': int(row.get('up_count') or 0),
        'down': int(row.get('down_count') or 0),
        'flat': int(row.get('flat_count') or 0),
    }


def _top_rows(table_name, columns, order_by, date, limit=5):
    _, mdb = _modules()
    if not mdb.checkTableIsExist(table_name):
        return pd.DataFrame(columns=columns)
    sql = f"SELECT {', '.join('`%s`' % c for c in columns)} FROM `{table_name}` WHERE `date` = %s ORDER BY `{order_by}` DESC LIMIT {int(limit)}"
    return _read_sql(sql, (date,))


def _strategy_rank(date):
    tbs, mdb = _modules()
    table = tbs.TABLE_CN_STOCK_STRATEGY_BACKTEST_RANK['name']
    if not mdb.checkTableIsExist(table):
        return pd.DataFrame()
    sql = f"SELECT `strategy_name`,`sample_count`,`avg_rate_20`,`win_rate_20` FROM `{table}` WHERE `date` = %s ORDER BY `avg_rate_20` DESC"
    return _read_sql(sql, (date,))


def _format_table(data):
    if data is None or data.empty:
        return '暂无数据\n'
    lines = []
    columns = list(data.columns)
    lines.append('| ' + ' | '.join(columns) + ' |')
    lines.append('| ' + ' | '.join(['---'] * len(columns)) + ' |')
    for _, row in data.iterrows():
        lines.append('| ' + ' | '.join(str(row.get(col, '')) for col in columns) + ' |')
    return '\n'.join(lines) + '\n'


def build_report_content(date=None):
    if date is None:
        date = datetime.date.today()
    tbs, _ = _modules()
    overview = _stock_overview(date)
    industry = _top_rows(tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY['name'], ['name', 'change_rate', 'fund_amount'], 'fund_amount', date)
    concept = _top_rows(tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT['name'], ['name', 'change_rate', 'fund_amount'], 'fund_amount', date)
    ranks = _strategy_rank(date)

    total = overview['total']
    up_ratio = round(overview['up'] / total * 100, 2) if total else 0
    down_ratio = round(overview['down'] / total * 100, 2) if total else 0
    title = f'{date} 每日市场复盘'
    summary = f"股票样本 {total} 只，上涨 {overview['up']} 只（{up_ratio}%），下跌 {overview['down']} 只（{down_ratio}%）。"

    content = [
        f'# {title}',
        '',
        '## 市场概览',
        '',
        summary,
        '',
        '## 行业资金流 Top 5',
        '',
        _format_table(industry),
        '## 概念资金流 Top 5',
        '',
        _format_table(concept),
        '## 策略回测排行',
        '',
        _format_table(ranks),
        '## 观察提示',
        '',
        '- 优先关注资金流与策略排行同时靠前的方向。',
        '- 若市场上涨占比偏低，降低追涨仓位，优先等待回踩确认。',
        '- 本报告为规则化复盘，不构成投资建议。',
        '',
    ]
    return title, summary, '\n'.join(content)


def generate_daily_report(date=None):
    if date is None:
        date = datetime.date.today()
    title, summary, content = build_report_content(date)
    report_dir = config.project_root() / 'reports' / 'daily'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f'{date}.md'
    report_path.write_text(content, encoding='utf-8')
    return {'date': date, 'title': title, 'summary': summary, 'report_path': os.fspath(report_path)}


def save_daily_report(date=None):
    tbs, mdb = _modules()
    result = generate_daily_report(date)
    table = tbs.TABLE_DAILY_MARKET_REPORT
    table_name = table['name']
    data = pd.DataFrame([{**result, 'created_at': datetime.datetime.now()}], columns=list(table['columns']))
    if mdb.checkTableIsExist(table_name):
        mdb.executeSql(f"DELETE FROM `{table_name}` where `date` = %s", (result['date'],))
        cols_type = None
    else:
        cols_type = tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`")
    return 1

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging


SKIP_TABLES = {
    'job_run_log',
    'data_quality_log',
    'daily_market_report',
}

PRICE_COLUMNS = {
    'new_price', 'open_price', 'high_price', 'low_price', 'pre_close_price',
    'close', 'open', 'high', 'low', 'total_market_cap', 'free_cap',
}
VOLUME_COLUMNS = {'volume', 'deal_amount', 'amount'}


def _result(check_name, level, passed, issue_count, message):
    return {
        'check_name': check_name,
        'level': level,
        'passed': bool(passed),
        'issue_count': int(issue_count),
        'message': str(message)[:1800],
    }


def validate_dataframe(table_name, data):
    if table_name in SKIP_TABLES:
        return []

    results = []
    if data is None:
        return [_result('dataframe_present', 'error', False, 1, 'DataFrame 为 None')]

    row_count = len(data.index)
    results.append(_result('row_count', 'error' if row_count == 0 else 'info', row_count > 0, 0 if row_count > 0 else 1,
                           f'行数：{row_count}'))

    if row_count == 0:
        return results

    if 'date' in data.columns:
        null_count = int(data['date'].isna().sum())
        results.append(_result('date_not_null', 'error' if null_count else 'info', null_count == 0, null_count,
                               f'date 空值数：{null_count}'))

    for column in sorted((PRICE_COLUMNS | VOLUME_COLUMNS) & set(data.columns)):
        series = data[column]
        numeric = series.dropna()
        try:
            negative_count = int((numeric < 0).sum())
        except TypeError:
            results.append(_result(f'{column}_numeric', 'warning', False, len(numeric), f'{column} 存在非数值内容'))
            continue
        if negative_count:
            results.append(_result(f'{column}_non_negative', 'warning', False, negative_count,
                                   f'{column} 负值数：{negative_count}'))

    key_columns = [col for col in ('date', 'code', 'name') if col in data.columns]
    for column in key_columns:
        null_count = int(data[column].isna().sum())
        if null_count:
            results.append(_result(f'{column}_not_null', 'warning', False, null_count,
                                   f'{column} 空值数：{null_count}'))

    return results


def record_quality_results(table_name, results, run_date=None):
    if not results:
        return
    try:
        from instock.lib import database as mdb
    except Exception as exc:
        logging.error(f'data_quality.record_quality_results导入数据库异常：{exc}')
        return

    if run_date is None:
        run_date = datetime.date.today()
    created_at = datetime.datetime.now()
    sql = (
        "INSERT INTO `data_quality_log` "
        "(`run_date`,`table_name`,`check_name`,`level`,`passed`,`issue_count`,`message`,`created_at`) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    for item in results:
        try:
            mdb.executeSql(sql, (
                run_date,
                table_name,
                item['check_name'],
                item['level'],
                1 if item['passed'] else 0,
                item['issue_count'],
                item['message'],
                created_at,
            ))
        except Exception as exc:
            logging.error(f"data_quality.record_quality_results处理异常：{table_name}{exc}")

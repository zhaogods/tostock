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

    if '_quality' in data.columns:
        partial_count = int((data['_quality'] == 'partial_basic_missing').sum())
        if partial_count > 0:
            results.append(_result('data_quality_flag', 'warning', False, partial_count,
                                 f'{partial_count}行数据缺少basic字段'))

    critical_zero_fields = {'turnoverrate', 'pe', 'pb'}
    for col in critical_zero_fields & set(data.columns):
        zero_count = int((data[col] == 0).sum())
        if zero_count > len(data) * 0.8:
            results.append(_result(f'{col}_mostly_zero', 'error', False, zero_count,
                                 f'{col}字段{zero_count}行为0，疑似数据源问题'))

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


def _row_value(row, index, key=None, default=0):
    if row is None:
        return default
    try:
        if key is not None and hasattr(row, 'get'):
            return row.get(key, default)
    except Exception:
        pass
    try:
        return row[index]
    except Exception:
        return default


def summarize_quality_log(table_name, run_date=None):
    """汇总 data_quality_log 中某表某日的质量结果，供资产门禁复用。"""
    if run_date is None:
        run_date = datetime.date.today()
    try:
        from instock.lib import database as mdb
    except Exception as exc:
        logging.error(f'data_quality.summarize_quality_log导入数据库异常：{exc}')
        return {
            'table_name': table_name,
            'run_date': run_date,
            'total_checks': 0,
            'failed_checks': 0,
            'error_count': 0,
            'warning_count': 0,
            'issue_count': 0,
            'latest_message': '',
        }

    sql = (
        "SELECT COUNT(*) AS total_checks, "
        "SUM(CASE WHEN `passed` = 0 THEN 1 ELSE 0 END) AS failed_checks, "
        "SUM(CASE WHEN `passed` = 0 AND `level` = 'error' THEN 1 ELSE 0 END) AS error_count, "
        "SUM(CASE WHEN `passed` = 0 AND `level` = 'warning' THEN 1 ELSE 0 END) AS warning_count, "
        "SUM(CASE WHEN `passed` = 0 THEN IFNULL(`issue_count`, 0) ELSE 0 END) AS issue_count "
        "FROM `data_quality_log` WHERE `table_name` = %s AND `run_date` = %s"
    )
    try:
        rows = mdb.executeSqlFetch(sql, (table_name, run_date)) or []
    except Exception as exc:
        logging.error(f"data_quality.summarize_quality_log统计异常：{table_name}{exc}")
        rows = []
    row = rows[0] if rows else None

    message = ''
    try:
        message_rows = mdb.executeSqlFetch(
            "SELECT `message` FROM `data_quality_log` "
            "WHERE `table_name`=%s AND `run_date`=%s AND `passed`=0 "
            "ORDER BY `created_at` DESC LIMIT 1",
            (table_name, run_date),
        ) or []
        if message_rows:
            message = str(_row_value(message_rows[0], 0, 'message', '') or '')
    except Exception as exc:
        logging.error(f"data_quality.summarize_quality_log消息异常：{table_name}{exc}")

    return {
        'table_name': table_name,
        'run_date': run_date,
        'total_checks': int(_row_value(row, 0, 'total_checks', 0) or 0),
        'failed_checks': int(_row_value(row, 1, 'failed_checks', 0) or 0),
        'error_count': int(_row_value(row, 2, 'error_count', 0) or 0),
        'warning_count': int(_row_value(row, 3, 'warning_count', 0) or 0),
        'issue_count': int(_row_value(row, 4, 'issue_count', 0) or 0),
        'latest_message': message,
    }

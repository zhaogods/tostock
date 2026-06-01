#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import time


RUNNING = 'running'
SUCCESS = 'success'
FAILED = 'failed'


def _short_message(message):
    if message is None:
        return ''
    return str(message)[:1800]


def _insert_log(run_date, job_name, start_time, end_time, status, duration_seconds, rows_written=None, message=''):
    try:
        from instock.lib import database as mdb
    except Exception as exc:
        logging.error(f'job_monitor._insert_log导入数据库异常：{exc}')
        return

    sql = (
        "INSERT INTO `job_run_log` "
        "(`run_date`,`job_name`,`start_time`,`end_time`,`status`,`duration_seconds`,`rows_written`,`message`,`created_at`) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    try:
        mdb.executeSql(sql, (
            run_date,
            job_name,
            start_time,
            end_time,
            status,
            duration_seconds,
            rows_written,
            _short_message(message),
            datetime.datetime.now(),
        ))
    except Exception as exc:
        logging.error(f'job_monitor._insert_log处理异常：{job_name}{exc}')


def run_job(job_name, func, run_date=None, *args, **kwargs):
    if run_date is None:
        run_date = datetime.date.today()
    start_time = datetime.datetime.now()
    start = time.time()
    _insert_log(run_date, job_name, start_time, None, RUNNING, 0, None, '')
    try:
        result = func(*args, **kwargs)
        duration = time.time() - start
        rows_written = result if isinstance(result, int) else None
        _insert_log(run_date, job_name, start_time, datetime.datetime.now(), SUCCESS, duration, rows_written, '')
        return result
    except Exception as exc:
        duration = time.time() - start
        _insert_log(run_date, job_name, start_time, datetime.datetime.now(), FAILED, duration, None, exc)
        logging.exception(f'job_monitor.run_job处理异常：{job_name}')
        raise

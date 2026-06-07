#!/usr/local/bin/python
# -*- coding: utf-8 -*-


import logging
import datetime
import concurrent.futures
import os
import sys
import time
import instock.lib.trade_time as trd
from instock.lib import config
from instock.core.eastmoney_fetcher import reset_circuit

__author__ = 'myh '
__date__ = '2023/3/10 '

_JOB_BATCH_DELAY = int(os.environ.get('JOB_BATCH_DELAY', '2'))


def _parse_date(value):
    tmp_year, tmp_month, tmp_day = value.split("-")
    return datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day)).date()


def _invoke_run_fun(run_fun, run_date, *args):
    reset_circuit()
    if run_fun.__name__.startswith('save_nph'):
        return run_fun(run_date, False, *args)
    return run_fun(run_date, *args)


def _run_dates(run_fun, dates, *args):
    if not dates:
        return
    workers = config.get_job_date_workers()
    if workers <= 1:
        for index, run_date in enumerate(dates):
            _invoke_run_fun(run_fun, run_date, *args)
            if index < len(dates) - 1 and _JOB_BATCH_DELAY > 0:
                time.sleep(_JOB_BATCH_DELAY)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for run_date in dates:
            futures.append(executor.submit(_invoke_run_fun, run_fun, run_date, *args))
            if _JOB_BATCH_DELAY > 0:
                time.sleep(_JOB_BATCH_DELAY)
        for future in concurrent.futures.as_completed(futures):
            future.result()


# 通用函数，获得日期参数，支持批量作业。
def run_with_args(run_fun, *args):
    if len(sys.argv) == 3:
        # 区间作业 python xxx.py 2023-03-01 2023-03-21
        start_date = _parse_date(sys.argv[1])
        end_date = _parse_date(sys.argv[2])
        run_date = start_date
        dates = []
        while run_date <= end_date:
            if trd.is_trade_date(run_date):
                dates.append(run_date)
            run_date += datetime.timedelta(days=1)
        try:
            _run_dates(run_fun, dates, *args)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
            raise
    elif len(sys.argv) == 2:
        # N个时间作业 python xxx.py 2023-03-01,2023-03-02
        try:
            dates = []
            for date in sys.argv[1].split(','):
                run_date = _parse_date(date)
                if trd.is_trade_date(run_date):
                    dates.append(run_date)
            _run_dates(run_fun, dates, *args)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
            raise
    else:
        # 当前时间作业 python xxx.py
        try:
            run_date, run_date_nph = trd.get_trade_date_last()
            if run_fun.__name__.startswith('save_nph'):
                run_fun(run_date_nph, False)
            elif run_fun.__name__.startswith('save_after_close'):
                run_fun(run_date, *args)
            else:
                run_fun(run_date_nph, *args)
        except Exception as e:
            logging.error(f"run_template.run_with_args处理异常：{run_fun}{sys.argv}{e}")
            raise

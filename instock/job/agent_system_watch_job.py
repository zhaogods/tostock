#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

from instock.core.agent import system_watch


__author__ = 'Kiro'
__date__ = '2026/06/10'


def _parse_date(value):
    tmp_year, tmp_month, tmp_day = value.split('-')
    return datetime.date(int(tmp_year), int(tmp_month), int(tmp_day))


def _iter_dates():
    if len(sys.argv) == 3:
        start_date = _parse_date(sys.argv[1])
        end_date = _parse_date(sys.argv[2])
        date_value = start_date
        while date_value <= end_date:
            yield date_value
            date_value += datetime.timedelta(days=1)
        return
    if len(sys.argv) == 2:
        for token in sys.argv[1].split(','):
            token = token.strip()
            if token:
                yield _parse_date(token)
        return
    yield datetime.date.today()


def run_agent_system_watch(date):
    try:
        return system_watch.run_system_watch(date)
    except Exception as e:
        logging.error(f"agent_system_watch_job.run_agent_system_watch处理异常：{e}")
        return 0


def main():
    for date_value in _iter_dates():
        run_agent_system_watch(date_value)


if __name__ == '__main__':
    main()

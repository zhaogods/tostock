#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import logging
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

import instock.lib.run_template as runt
from instock.core.report import daily_recap


__author__ = 'myh '
__date__ = '2026/6/1 '


def save_daily_market_report(date):
    try:
        return daily_recap.save_daily_report(date)
    except Exception as e:
        logging.error(f"daily_report_job.save_daily_market_report处理异常：{e}")
        return 0


def main():
    runt.run_with_args(save_daily_market_report)


if __name__ == '__main__':
    main()

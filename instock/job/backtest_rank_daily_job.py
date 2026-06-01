#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

import instock.lib.run_template as runt
from instock.core.backtest import leaderboard


__author__ = 'myh '
__date__ = '2026/6/1 '


def save_strategy_backtest_rank(date):
    try:
        return leaderboard.save_strategy_rank(date)
    except Exception as e:
        logging.error(f"backtest_rank_daily_job.save_strategy_backtest_rank处理异常：{e}")
        return 0


def main():
    runt.run_with_args(save_strategy_backtest_rank)


if __name__ == '__main__':
    main()

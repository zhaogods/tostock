#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
历史数据回填脚本
专门用于批量回填历史交易日数据，支持断点续传和进度报告

用法:
    python instock/job/backfill_job.py 2026-05-08 2026-06-06        # 日期区间
    python instock/job/backfill_job.py 2026-05-08,2026-05-09        # 逗号分隔
    python instock/job/backfill_job.py 2026-05-08 2026-06-06 --skip-existing  # 跳过已有数据
"""

import time
import datetime
import logging
import os.path
import sys
import argparse

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(
    format='%(asctime)s %(message)s',
    filename=os.path.join(log_path, 'stock_backfill_job.log'),
    level=logging.INFO
)

import instock.lib.trade_time as trd
import instock.lib.database as mdb

# 导入各个job模块
import init_job as bj
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import indicators_data_daily_job as gdj
import strategy_data_daily_job as sdj
import backtest_data_daily_job as bdj
import backtest_rank_daily_job as brdj
import daily_report_job as drj
import klinepattern_data_daily_job as kdj
import selection_data_daily_job as sddj
import instock.lib.job_monitor as jm
import concurrent.futures


def execute_single_date(run_date):
    """执行单个日期的完整数据管线"""
    jm.run_job('init_job', bj.main, run_date)
    jm.run_job('basic_data_daily_job', hdj.main, run_date)
    time.sleep(5)
    jm.run_job('selection_data_daily_job', sddj.main, run_date)
    time.sleep(3)
    jm.run_job('basic_data_after_close_daily_job', acdj.main, run_date)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(jm.run_job, 'basic_data_other_daily_job', hdtj.main, run_date),
            executor.submit(jm.run_job, 'indicators_data_daily_job', gdj.main, run_date),
            executor.submit(jm.run_job, 'klinepattern_data_daily_job', kdj.main, run_date),
            executor.submit(jm.run_job, 'strategy_data_daily_job', sdj.main, run_date),
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    jm.run_job('backtest_data_daily_job', bdj.main, run_date)
    jm.run_job('backtest_rank_daily_job', brdj.main, run_date)
    jm.run_job('daily_report_job', drj.save_daily_market_report, run_date, run_date)


def check_date_exists(date):
    """检查指定日期的数据是否已存在"""
    count = mdb.executeSqlCount(
        "SELECT COUNT(*) FROM cn_stock_spot WHERE date = %s", (date,)
    )
    return count > 0


def backfill_date_range(start_date, end_date, skip_existing=False):
    """回填日期区间的数据"""
    dates = []
    current = start_date
    while current <= end_date:
        if trd.is_trade_date(current):
            dates.append(current)
        current += datetime.timedelta(days=1)

    total = len(dates)
    logging.info(f"========== 开始回填任务 ==========")
    logging.info(f"日期区间: {start_date} 至 {end_date}")
    logging.info(f"交易日数量: {total}")
    logging.info(f"跳过已有数据: {skip_existing}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for idx, run_date in enumerate(dates, 1):
        print(f"\n[{idx}/{total}] 处理日期: {run_date}")
        logging.info(f"[{idx}/{total}] 开始处理日期: {run_date}")

        if skip_existing and check_date_exists(run_date):
            print(f"  → 数据已存在，跳过")
            logging.info(f"日期 {run_date} 数据已存在，跳过")
            skip_count += 1
            continue

        try:
            execute_single_date(run_date)
            success_count += 1
            print(f"  ✓ 完成")
            logging.info(f"日期 {run_date} 处理成功")
        except Exception as e:
            fail_count += 1
            print(f"  ✗ 失败: {e}")
            logging.error(f"日期 {run_date} 处理失败: {e}")

        # 进度报告
        if idx % 5 == 0 or idx == total:
            progress = idx / total * 100
            print(f"\n--- 进度: {progress:.1f}% ({idx}/{total}) ---")
            print(f"    成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")

    logging.info(f"========== 回填任务完成 ==========")
    logging.info(f"总计: {total}, 成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")
    print(f"\n========== 回填完成 ==========")
    print(f"总计: {total}, 成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")


def main():
    parser = argparse.ArgumentParser(description='历史数据回填工具')
    parser.add_argument('dates', nargs='+', help='日期参数：单日期、逗号分隔、或起止日期')
    parser.add_argument('--skip-existing', action='store_true',
                       help='跳过已有数据的日期')

    args = parser.parse_args()

    if len(args.dates) == 2 and ',' not in args.dates[0]:
        # 日期区间模式
        start_date = datetime.datetime.strptime(args.dates[0], '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(args.dates[1], '%Y-%m-%d').date()
        backfill_date_range(start_date, end_date, args.skip_existing)
    elif len(args.dates) == 1 and ',' in args.dates[0]:
        # 逗号分隔模式
        date_list = [datetime.datetime.strptime(d.strip(), '%Y-%m-%d').date()
                     for d in args.dates[0].split(',')]
        date_list = [d for d in date_list if trd.is_trade_date(d)]
        if date_list:
            backfill_date_range(min(date_list), max(date_list), args.skip_existing)
    else:
        print("错误: 参数格式不正确")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

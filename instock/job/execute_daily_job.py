#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import datetime
import concurrent.futures
import logging
import os.path
import sys
import pandas as pd
# pandas 3.0 Copy-on-Write 导致 .values 赋值报 read-only 错误
pd.options.mode.copy_on_write = False

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(format='%(asctime)s %(message)s', filename=os.path.join(log_path, 'stock_execute_job.log'))
logging.getLogger().setLevel(logging.INFO)
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

__author__ = 'myh '
__date__ = '2023/3/10 '


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("######## 任务执行时间: %s #######" % _start.strftime("%Y-%m-%d %H:%M:%S.%f"))
    run_date = _start.date()
    # 第1步创建数据库
    jm.run_job('init_job', bj.main, run_date)
    # 第2.1步创建股票基础数据表
    jm.run_job('basic_data_daily_job', hdj.main, run_date)
    time.sleep(5)  # push2 实时行情完成后等待冷却
    # 第2.2步创建综合股票数据表
    jm.run_job('selection_data_daily_job', sddj.main, run_date)
    time.sleep(3)  # xuangu API 完成后等待
    # # # # 第7步创建股票闭盘后才有的数据——必须先下载历史K线缓存，
    # # # # 否则指标/形态/策略阶段读到空缓存生成空结果
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

    # # # # 第6步创建股票回测
    # bdj.main()

    jm.run_job('backtest_rank_daily_job', brdj.main, run_date)
    jm.run_job('daily_report_job', drj.main, run_date)

    logging.info("######## 完成任务, 使用时间: %s 秒 #######" % (time.time() - start))


# main函数入口
if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：插入模拟策略回测数据
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from instock.lib import database

# 模拟策略回测数据
test_data = [
    ('海龟交易法则', 'cn_stock_strategy_turtle_trade', 45, 2.3, 2.8, 3.5, 65.2, 68.1, 71.3, 8.5, -2.1),
    ('均线多头', 'cn_stock_strategy_keep_increasing', 67, 1.8, 2.1, 2.6, 58.7, 61.2, 64.5, 6.2, -1.5),
    ('突破平台', 'cn_stock_strategy_breakthrough_platform', 32, 2.1, 2.5, 3.2, 62.5, 65.6, 68.9, 7.8, -1.8),
    ('放量上涨', 'cn_stock_strategy_enter', 54, 1.5, 1.9, 2.3, 55.6, 58.3, 61.7, 5.9, -1.3),
    ('停机坪', 'cn_stock_strategy_parking_apron', 28, 1.2, 1.6, 2.1, 52.1, 55.4, 58.2, 5.1, -1.1),
    ('回踩年线', 'cn_stock_strategy_backtrace_ma250', 19, 0.9, 1.3, 1.8, 48.9, 51.2, 54.6, 4.3, -0.9),
    ('无大幅回撤', 'cn_stock_strategy_low_backtrace_increase', 41, 1.6, 2.0, 2.7, 57.3, 60.1, 63.8, 6.5, -1.4),
    ('高而窄的旗形', 'cn_stock_strategy_high_tight_flag', 15, 0.8, 1.1, 1.5, 46.7, 49.3, 52.1, 3.8, -0.8),
    ('放量跌停', 'cn_stock_strategy_climax_limitdown', 23, -0.5, 0.2, 0.8, 42.1, 45.6, 48.9, 2.5, -3.2),
    ('低ATR成长', 'cn_stock_strategy_low_atr', 36, 1.4, 1.7, 2.2, 54.2, 57.8, 61.2, 5.6, -1.2),
]

today = date.today()

sql_template = """
INSERT INTO cn_stock_strategy_backtest_rank
(date, strategy_name, strategy_table, sample_count,
 avg_rate_5, avg_rate_10, avg_rate_20,
 win_rate_5, win_rate_10, win_rate_20,
 best_rate_20, worst_rate_20, updated_at)
VALUES ('{date}', '{name}', '{table}', {count},
 {rate5}, {rate10}, {rate20},
 {win5}, {win10}, {win20},
 {best}, {worst}, NOW())
"""

print(f"插入模拟数据到 cn_stock_strategy_backtest_rank (日期: {today})")

for data in test_data:
    sql = sql_template.format(
        date=today,
        name=data[0],
        table=data[1],
        count=data[2],
        rate5=data[3],
        rate10=data[4],
        rate20=data[5],
        win5=data[6],
        win10=data[7],
        win20=data[8],
        best=data[9],
        worst=data[10]
    )
    try:
        database.executeSql(sql)
        print(f"  ✓ {data[0]}")
    except Exception as e:
        print(f"  ✗ {data[0]}: {e}")

print(f"\n完成！共插入 {len(test_data)} 条策略回测数据")

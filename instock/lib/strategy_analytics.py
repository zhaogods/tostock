#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略分析模块
计算策略表现指标
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
import pandas as pd

from instock.lib import database

__author__ = 'Kiro'
__date__ = '2026/06/07'


@dataclass
class StrategyPerformance:
    """策略表现"""
    key: str
    name: str
    sample_count: int
    avg_return_7d: float
    win_rate_7d: float
    trend: str
    updated_at: Optional[str] = None


def calculate_trend(history_df: pd.DataFrame) -> str:
    """
    计算趋势
    比较近3天 vs 前3天的平均收益率
    """
    if history_df is None or len(history_df) < 6:
        return 'flat'

    recent_3 = history_df.head(3)['avg_rate_10'].mean()
    prev_3 = history_df.iloc[3:6]['avg_rate_10'].mean()

    diff = recent_3 - prev_3
    if diff > 0.5:
        return 'up'
    elif diff < -0.5:
        return 'down'
    else:
        return 'flat'


def get_strategy_performance(strategy_key: str, strategy_name: str, days: int = 7) -> StrategyPerformance:
    """获取单个策略表现"""
    from_date = date.today() - timedelta(days=days)

    sql = f"""
    SELECT
        AVG(avg_rate_10) as avg_return,
        AVG(win_rate_10) as win_rate,
        SUM(sample_count) as total_samples,
        MAX(date) as last_date
    FROM cn_stock_strategy_backtest_rank
    WHERE strategy_table = '{strategy_key}'
      AND date >= '{from_date}'
    """

    try:
        df = database.executeSql(sql)
        if df is None or len(df) == 0:
            return StrategyPerformance(
                key=strategy_key,
                name=strategy_name,
                sample_count=0,
                avg_return_7d=0.0,
                win_rate_7d=0.0,
                trend='flat',
                updated_at=None
            )

        row = df.iloc[0]
        avg_return = row['avg_return'] if pd.notna(row['avg_return']) else 0.0
        win_rate = row['win_rate'] if pd.notna(row['win_rate']) else 0.0
        sample_count = int(row['total_samples']) if pd.notna(row['total_samples']) else 0
        last_date = row['last_date'].strftime('%Y-%m-%d') if pd.notna(row['last_date']) else None

        history_sql = f"""
        SELECT date, avg_rate_10
        FROM cn_stock_strategy_backtest_rank
        WHERE strategy_table = '{strategy_key}'
          AND date >= DATE_SUB(CURDATE(), INTERVAL 10 DAY)
        ORDER BY date DESC
        LIMIT 10
        """
        history_df = database.executeSql(history_sql)
        trend = calculate_trend(history_df) if history_df is not None else 'flat'

        return StrategyPerformance(
            key=strategy_key,
            name=strategy_name,
            sample_count=sample_count,
            avg_return_7d=round(avg_return, 2),
            win_rate_7d=round(win_rate, 2),
            trend=trend,
            updated_at=last_date
        )
    except Exception as e:
        logging.error(f"strategy_analytics.get_strategy_performance处理异常：{strategy_key} {e}")
        return StrategyPerformance(
            key=strategy_key,
            name=strategy_name,
            sample_count=0,
            avg_return_7d=0.0,
            win_rate_7d=0.0,
            trend='flat',
            updated_at=None
        )


def get_all_strategies_performance(days: int = 7) -> list[StrategyPerformance]:
    """获取所有策略表现"""
    from instock.lib import strategy_manager

    performances = []
    for strategy in strategy_manager.get_all_strategies():
        try:
            perf = get_strategy_performance(strategy.key, strategy.name, days)
            performances.append(perf)
        except Exception as e:
            logging.error(f"strategy_analytics.get_all_strategies_performance处理异常：{strategy.key} {e}")
    return performances

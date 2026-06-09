#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略分析模块
计算策略表现指标
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
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
    avg_return_10d: float
    win_rate_10d: float
    trend: str
    updated_at: Optional[str] = None


def _read_sql(sql, params=None):
    try:
        return pd.read_sql(sql=sql, con=database.engine(), params=params)
    except Exception as exc:
        logging.error(f"strategy_analytics._read_sql处理异常：{exc}")
        return pd.DataFrame()


def _format_date(value):
    if pd.isna(value):
        return None
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _to_date(value):
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _safe_mean(series):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if values.empty:
        return 0.0
    return round(float(values.mean()), 2)


def calculate_trend(history_df: pd.DataFrame) -> str:
    """
    计算趋势
    比较近3天 vs 前3天的平均收益率
    """
    if history_df is None or len(history_df) < 6:
        return 'flat'

    recent_3 = pd.to_numeric(history_df.head(3)['avg_rate_10'], errors='coerce').mean()
    prev_3 = pd.to_numeric(history_df.iloc[3:6]['avg_rate_10'], errors='coerce').mean()

    diff = recent_3 - prev_3
    if diff > 0.5:
        return 'up'
    elif diff < -0.5:
        return 'down'
    else:
        return 'flat'


def _empty_performance(strategy_key: str, strategy_name: str, updated_at=None) -> StrategyPerformance:
    return StrategyPerformance(
        key=strategy_key,
        name=strategy_name,
        sample_count=0,
        avg_return_10d=0.0,
        win_rate_10d=0.0,
        trend='flat',
        updated_at=updated_at,
    )


def _build_performance(strategy_key: str, strategy_name: str, latest_row, history_df: pd.DataFrame,
                       days: int = 7) -> StrategyPerformance:
    latest_date = _to_date(latest_row['date'])
    latest_date_text = _format_date(latest_row['date'])
    if latest_date is None or latest_date_text is None:
        return _empty_performance(strategy_key, strategy_name)

    from_date = latest_date - timedelta(days=days)
    strategy_history = history_df[history_df['strategy_table'] == strategy_key].copy()
    if not strategy_history.empty:
        strategy_history.loc[:, 'date_value'] = pd.to_datetime(strategy_history['date']).dt.date
        period_history = strategy_history[
            (strategy_history['date_value'] >= from_date) &
            (strategy_history['date_value'] <= latest_date)
        ]
        trend_history = strategy_history[
            (strategy_history['date_value'] >= latest_date - timedelta(days=10)) &
            (strategy_history['date_value'] <= latest_date)
        ].sort_values('date_value', ascending=False)
    else:
        period_history = pd.DataFrame()
        trend_history = pd.DataFrame()

    sample_count = int(latest_row['sample_count']) if pd.notna(latest_row['sample_count']) else 0
    return StrategyPerformance(
        key=strategy_key,
        name=strategy_name,
        sample_count=sample_count,
        avg_return_10d=_safe_mean(period_history['avg_rate_10']) if not period_history.empty else 0.0,
        win_rate_10d=_safe_mean(period_history['win_rate_10']) if not period_history.empty else 0.0,
        trend=calculate_trend(trend_history),
        updated_at=latest_date_text,
    )


def get_strategy_performance(strategy_key: str, strategy_name: str, days: int = 7) -> StrategyPerformance:
    """获取单个策略表现"""
    try:
        latest_sql = """
        SELECT `strategy_table`, `date`, `sample_count`
        FROM `cn_stock_strategy_backtest_rank`
        WHERE `strategy_table` = %s
        ORDER BY `date` DESC
        LIMIT 1
        """
        latest_df = _read_sql(latest_sql, (strategy_key,))
        if latest_df is None or latest_df.empty:
            return _empty_performance(strategy_key, strategy_name)

        latest_date = _to_date(latest_df.iloc[0]['date'])
        if latest_date is None:
            return _empty_performance(strategy_key, strategy_name)

        from_date = latest_date - timedelta(days=max(days, 10))
        history_sql = """
        SELECT `strategy_table`, `date`, `avg_rate_10`, `win_rate_10`
        FROM `cn_stock_strategy_backtest_rank`
        WHERE `strategy_table` = %s
          AND `date` >= %s
          AND `date` <= %s
        ORDER BY `date` DESC
        """
        history_df = _read_sql(history_sql, (strategy_key, from_date, _format_date(latest_df.iloc[0]['date'])))
        return _build_performance(strategy_key, strategy_name, latest_df.iloc[0], history_df, days)
    except Exception as e:
        logging.error(f"strategy_analytics.get_strategy_performance处理异常：{strategy_key} {e}")
        return _empty_performance(strategy_key, strategy_name)


def get_all_strategies_performance(days: int = 7) -> list[StrategyPerformance]:
    """获取所有策略表现"""
    from instock.lib import strategy_manager

    strategies = strategy_manager.get_all_strategies()
    if not strategies:
        return []

    keys = [strategy.key for strategy in strategies]
    placeholders = ','.join(['%s'] * len(keys))
    try:
        latest_sql = f"""
        SELECT r.`strategy_table`, r.`date`, r.`sample_count`
        FROM `cn_stock_strategy_backtest_rank` r
        INNER JOIN (
            SELECT `strategy_table`, MAX(`date`) AS max_date
            FROM `cn_stock_strategy_backtest_rank`
            WHERE `strategy_table` IN ({placeholders})
            GROUP BY `strategy_table`
        ) latest
          ON r.`strategy_table` = latest.`strategy_table`
         AND r.`date` = latest.max_date
        WHERE r.`strategy_table` IN ({placeholders})
        """
        latest_df = _read_sql(latest_sql, tuple(keys + keys))
        if latest_df is None or latest_df.empty:
            return [_empty_performance(strategy.key, strategy.name) for strategy in strategies]

        latest_df.loc[:, 'date_value'] = pd.to_datetime(latest_df['date']).dt.date
        valid_dates = latest_df['date_value'].dropna()
        if valid_dates.empty:
            return [_empty_performance(strategy.key, strategy.name) for strategy in strategies]

        min_date = valid_dates.min() - timedelta(days=max(days, 10))
        max_date = valid_dates.max()
        history_sql = f"""
        SELECT `strategy_table`, `date`, `avg_rate_10`, `win_rate_10`
        FROM `cn_stock_strategy_backtest_rank`
        WHERE `strategy_table` IN ({placeholders})
          AND `date` >= %s
          AND `date` <= %s
        ORDER BY `strategy_table`, `date` DESC
        """
        history_df = _read_sql(history_sql, tuple(keys) + (min_date, max_date))
        latest_map = {row['strategy_table']: row for _, row in latest_df.iterrows()}

        performances = []
        for strategy in strategies:
            latest_row = latest_map.get(strategy.key)
            if latest_row is None:
                performances.append(_empty_performance(strategy.key, strategy.name))
                continue
            performances.append(_build_performance(strategy.key, strategy.name, latest_row, history_df, days))
        return performances
    except Exception as e:
        logging.error(f"strategy_analytics.get_all_strategies_performance处理异常：{e}")
        return [_empty_performance(strategy.key, strategy.name) for strategy in strategies]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略管理模块
定义策略注册表和策略档案
"""

from dataclasses import dataclass
from typing import Optional

__author__ = 'Kiro'
__date__ = '2026/06/07'


@dataclass
class StrategyProfile:
    """策略档案"""
    key: str              # 策略表名
    name: str             # 中文名称
    description: str      # 策略说明
    category: str = '趋势'  # 分类


# 策略注册表
STRATEGY_ENTER = StrategyProfile(
    key='cn_stock_strategy_enter',
    name='放量上涨',
    description='成交量放大并伴随价格上涨',
    category='量价'
)

STRATEGY_KEEP_INCREASING = StrategyProfile(
    key='cn_stock_strategy_keep_increasing',
    name='均线多头',
    description='多条均线呈多头排列',
    category='趋势'
)

STRATEGY_PARKING_APRON = StrategyProfile(
    key='cn_stock_strategy_parking_apron',
    name='停机坪',
    description='横盘整理后突破',
    category='突破'
)

STRATEGY_BACKTRACE_MA250 = StrategyProfile(
    key='cn_stock_strategy_backtrace_ma250',
    name='回踩年线',
    description='股价回踩250日均线后反弹',
    category='趋势'
)

STRATEGY_BREAKTHROUGH_PLATFORM = StrategyProfile(
    key='cn_stock_strategy_breakthrough_platform',
    name='突破平台',
    description='突破前期平台整理区域',
    category='突破'
)

STRATEGY_LOW_BACKTRACE_INCREASE = StrategyProfile(
    key='cn_stock_strategy_low_backtrace_increase',
    name='无大幅回撤',
    description='上涨过程中回撤幅度小',
    category='成长'
)

STRATEGY_TURTLE_TRADE = StrategyProfile(
    key='cn_stock_strategy_turtle_trade',
    name='海龟交易法则',
    description='基于唐奇安通道的趋势跟踪策略',
    category='趋势'
)

STRATEGY_HIGH_TIGHT_FLAG = StrategyProfile(
    key='cn_stock_strategy_high_tight_flag',
    name='高而窄的旗形',
    description='强势上涨后的短暂整理形态',
    category='形态'
)

STRATEGY_CLIMAX_LIMITDOWN = StrategyProfile(
    key='cn_stock_strategy_climax_limitdown',
    name='放量跌停',
    description='放量跌停后的反弹机会',
    category='反转'
)

STRATEGY_LOW_ATR = StrategyProfile(
    key='cn_stock_strategy_low_atr',
    name='低ATR成长',
    description='波动率低且稳健成长',
    category='成长'
)

# 所有策略列表
_ALL_STRATEGIES = [
    STRATEGY_ENTER,
    STRATEGY_KEEP_INCREASING,
    STRATEGY_PARKING_APRON,
    STRATEGY_BACKTRACE_MA250,
    STRATEGY_BREAKTHROUGH_PLATFORM,
    STRATEGY_LOW_BACKTRACE_INCREASE,
    STRATEGY_TURTLE_TRADE,
    STRATEGY_HIGH_TIGHT_FLAG,
    STRATEGY_CLIMAX_LIMITDOWN,
    STRATEGY_LOW_ATR,
]


def get_all_strategies() -> list:
    """获取所有策略"""
    return _ALL_STRATEGIES


def get_strategy(key: str) -> Optional[StrategyProfile]:
    """根据key获取策略"""
    for strategy in _ALL_STRATEGIES:
        if strategy.key == key:
            return strategy
    return None

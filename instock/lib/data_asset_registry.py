#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import instock.core.tablestructure as tbs
from instock.lib.data_asset_manager import DataAsset


# 个股日线行情
ASSET_STOCK_DAILY = DataAsset(
    key='stock_daily',
    name='个股日线行情',
    source='tushare',
    table=tbs.TABLE_CN_STOCK_SPOT['name'],
    update_frequency='daily',
    expected_count=5500,
    quality_checks=['new_price > 0', 'volume >= 0'],
    description='全A股日线行情数据，包含价格、成交量、PE/PB/ROE等',
    task_key='basic_data_daily_job',
    expected_ready_time='17:30',
)

# ETF行情
ASSET_ETF_DAILY = DataAsset(
    key='etf_daily',
    name='ETF行情',
    source='akshare',
    table=tbs.TABLE_CN_ETF_SPOT['name'],
    update_frequency='daily',
    expected_count=800,
    quality_checks=['new_price > 0'],
    description='ETF日线行情数据',
    task_key='basic_data_daily_job',
    expected_ready_time='17:30',
)

# 综合选股数据
ASSET_SELECTION = DataAsset(
    key='selection_data',
    name='综合选股数据',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_SELECTION['name'],
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='东方财富综合选股页面数据（200+字段）',
    depends_on=['stock_daily'],
    task_key='selection_data_daily_job',
    expected_ready_time='17:40',
)

# 收盘后大宗交易
ASSET_BLOCKTRADE = DataAsset(
    key='blocktrade',
    name='大宗交易',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_BLOCKTRADE['name'],
    update_frequency='daily',
    expected_count=0,
    quality_checks=[],
    description='股票大宗交易数据',
    depends_on=['selection_data'],
    task_key='basic_data_after_close_daily_job',
    expected_ready_time='17:50',
)

# 尾盘抢筹
ASSET_CHIP_RACE_END = DataAsset(
    key='chip_race_end',
    name='尾盘抢筹',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_CHIP_RACE_END['name'],
    update_frequency='daily',
    expected_count=0,
    quality_checks=[],
    description='尾盘委托/抢筹数据',
    depends_on=['selection_data'],
    task_key='basic_data_after_close_daily_job',
    expected_ready_time='17:50',
)

# 个股资金流向
ASSET_STOCK_MONEYFLOW = DataAsset(
    key='stock_moneyflow',
    name='个股资金流向',
    source='tushare/eastmoney',
    table=tbs.TABLE_CN_STOCK_FUND_FLOW['name'],
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='个股主力资金流向数据',
    depends_on=['stock_daily'],
    task_key='basic_data_other_daily_job',
    expected_ready_time='18:00',
)

# 行业资金流向
ASSET_INDUSTRY_MONEYFLOW = DataAsset(
    key='industry_moneyflow',
    name='行业资金流向',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY['name'],
    update_frequency='daily',
    expected_count=80,
    quality_checks=[],
    description='行业板块主力资金流向数据',
    task_key='basic_data_other_daily_job',
    expected_ready_time='18:00',
)

# 概念资金流向
ASSET_CONCEPT_MONEYFLOW = DataAsset(
    key='concept_moneyflow',
    name='概念资金流向',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT['name'],
    update_frequency='daily',
    expected_count=300,
    quality_checks=[],
    description='概念板块主力资金流向数据',
    task_key='basic_data_other_daily_job',
    expected_ready_time='18:00',
)

# 龙虎榜
ASSET_LHB = DataAsset(
    key='lhb',
    name='龙虎榜',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_LHB['name'],
    update_frequency='daily',
    expected_count=0,
    quality_checks=[],
    description='每日龙虎榜数据',
    task_key='basic_data_other_daily_job',
    expected_ready_time='18:00',
)

# 分红配送
ASSET_DIVIDEND = DataAsset(
    key='dividend',
    name='分红配送',
    source='eastmoney',
    table=tbs.TABLE_CN_STOCK_BONUS['name'],
    update_frequency='daily',
    expected_count=0,
    quality_checks=[],
    description='股票分红配送数据',
    task_key='basic_data_other_daily_job',
    expected_ready_time='18:00',
)

# 技术指标
ASSET_INDICATORS = DataAsset(
    key='indicators',
    name='技术指标',
    source='talib',
    table=tbs.TABLE_CN_STOCK_INDICATORS['name'],
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='TA-Lib计算的技术指标（MACD/KDJ/BOLL等）',
    depends_on=['stock_daily'],
    task_key='indicators_data_daily_job',
    expected_ready_time='18:20',
)

# 指标买入信号
ASSET_INDICATORS_BUY = DataAsset(
    key='indicators_buy',
    name='指标买入信号',
    source='talib',
    table=tbs.TABLE_CN_STOCK_INDICATORS_BUY['name'],
    update_frequency='daily',
    expected_count=1,
    quality_checks=[],
    description='技术指标买入信号筛选结果',
    depends_on=['indicators'],
    task_key='indicators_data_daily_job',
    expected_ready_time='18:20',
)

# K线形态
ASSET_PATTERNS = DataAsset(
    key='patterns',
    name='K线形态',
    source='talib',
    table=tbs.TABLE_CN_STOCK_KLINE_PATTERN['name'],
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='K线形态识别（晨星/三乌鸦等）',
    depends_on=['stock_daily'],
    task_key='klinepattern_data_daily_job',
    expected_ready_time='18:20',
)

# 策略回测排行
ASSET_BACKTEST_RANK = DataAsset(
    key='backtest_rank',
    name='策略回测排行',
    source='backtest',
    table=tbs.TABLE_CN_STOCK_STRATEGY_BACKTEST_RANK['name'],
    update_frequency='daily',
    expected_count=10,
    quality_checks=[],
    description='策略平均收益、胜率和最佳/最差收益排行',
    task_key='backtest_rank_rebuild',
    expected_ready_time='19:30',
)

# 每日复盘报告
ASSET_DAILY_REPORT = DataAsset(
    key='daily_report',
    name='每日复盘报告',
    source='report',
    table=tbs.TABLE_DAILY_MARKET_REPORT['name'],
    update_frequency='daily',
    expected_count=1,
    quality_checks=[],
    description='每日复盘 Markdown 报告索引',
    depends_on=['stock_daily', 'backtest_rank'],
    task_key='daily_report_rebuild',
    page_table=tbs.TABLE_DAILY_MARKET_REPORT['name'],
    expected_ready_time='19:40',
)

# 所有数据资产
_ALL_ASSETS = [
    ASSET_STOCK_DAILY,
    ASSET_ETF_DAILY,
    ASSET_SELECTION,
    ASSET_BLOCKTRADE,
    ASSET_CHIP_RACE_END,
    ASSET_STOCK_MONEYFLOW,
    ASSET_INDUSTRY_MONEYFLOW,
    ASSET_CONCEPT_MONEYFLOW,
    ASSET_LHB,
    ASSET_DIVIDEND,
    ASSET_INDICATORS,
    ASSET_INDICATORS_BUY,
    ASSET_PATTERNS,
    ASSET_BACKTEST_RANK,
    ASSET_DAILY_REPORT,
]

_ASSETS_BY_KEY = {asset.key: asset for asset in _ALL_ASSETS}
_ASSETS_BY_TABLE = {asset.table: asset for asset in _ALL_ASSETS if asset.table}


def get_all_assets() -> list:
    """获取所有数据资产"""
    return _ALL_ASSETS


def get_asset(key: str):
    """根据key获取数据资产"""
    return _ASSETS_BY_KEY.get(key)


def get_asset_by_table(table_name: str):
    """根据表名获取数据资产"""
    return _ASSETS_BY_TABLE.get(table_name)


def assets_by_task(task_key: str) -> list:
    """获取某任务产出的资产"""
    return [asset for asset in _ALL_ASSETS if asset.task_key == task_key]

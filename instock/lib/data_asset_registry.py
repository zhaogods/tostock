#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from instock.lib.data_asset_manager import DataAsset

# 个股日线行情
ASSET_STOCK_DAILY = DataAsset(
    key='stock_daily',
    name='个股日线行情',
    source='tushare',
    table='cn_stock_spot',
    update_frequency='daily',
    expected_count=5500,
    quality_checks=['new_price > 0', 'volume >= 0'],
    description='全A股日线行情数据，包含价格、成交量、PE/PB/ROE等',
)

# 个股资金流向
ASSET_STOCK_MONEYFLOW = DataAsset(
    key='stock_moneyflow',
    name='个股资金流向',
    source='tushare',
    table='cn_stock_fund_flow',
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='个股主力资金流向数据',
)

# ETF行情
ASSET_ETF_DAILY = DataAsset(
    key='etf_daily',
    name='ETF行情',
    source='akshare',
    table='cn_etf_spot',
    update_frequency='daily',
    expected_count=800,
    quality_checks=['new_price > 0'],
    description='ETF日线行情数据',
)

# 龙虎榜
ASSET_LHB = DataAsset(
    key='lhb',
    name='龙虎榜',
    source='eastmoney',
    table='cn_stock_lhb',
    update_frequency='daily',
    expected_count=50,
    quality_checks=[],
    description='每日龙虎榜数据',
)

# 大宗交易
ASSET_BLOCKTRADE = DataAsset(
    key='blocktrade',
    name='大宗交易',
    source='eastmoney',
    table='cn_stock_blocktrade',
    update_frequency='daily',
    expected_count=100,
    quality_checks=[],
    description='股票大宗交易数据',
)

# 分红配送
ASSET_DIVIDEND = DataAsset(
    key='dividend',
    name='分红配送',
    source='eastmoney',
    table='cn_stock_bonus',
    update_frequency='daily',
    expected_count=50,
    quality_checks=[],
    description='股票分红配送数据',
)

# 综合选股数据
ASSET_SELECTION = DataAsset(
    key='selection_data',
    name='综合选股数据',
    source='eastmoney',
    table='cn_stock_selection',
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='东方财富综合选股页面数据（200+字段）',
)

# 技术指标
ASSET_INDICATORS = DataAsset(
    key='indicators',
    name='技术指标',
    source='talib',
    table='cn_stock_indicators',
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='TA-Lib计算的技术指标（MACD/KDJ/BOLL等）',
    depends_on=['stock_daily'],
)

# K线形态
ASSET_PATTERNS = DataAsset(
    key='patterns',
    name='K线形态',
    source='talib',
    table='cn_stock_pattern',
    update_frequency='daily',
    expected_count=5500,
    quality_checks=[],
    description='K线形态识别（晨星/三乌鸦等）',
    depends_on=['stock_daily'],
)

# 所有数据资产
_ALL_ASSETS = [
    ASSET_STOCK_DAILY,
    ASSET_STOCK_MONEYFLOW,
    ASSET_ETF_DAILY,
    ASSET_LHB,
    ASSET_BLOCKTRADE,
    ASSET_DIVIDEND,
    ASSET_SELECTION,
    ASSET_INDICATORS,
    ASSET_PATTERNS,
]

_ASSETS_BY_KEY = {asset.key: asset for asset in _ALL_ASSETS}


def get_all_assets() -> list:
    """获取所有数据资产"""
    return _ALL_ASSETS


def get_asset(key: str):
    """根据key获取数据资产"""
    return _ASSETS_BY_KEY.get(key)

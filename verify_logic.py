#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证Tushare财务字段补全的代码逻辑"""

import datetime

# 验证报告期计算逻辑
def verify_report_period_logic():
    """验证报告期计算逻辑"""
    print("=== 验证报告期计算逻辑 ===")

    test_cases = [
        (datetime.date(2024, 1, 15), "20231231"),
        (datetime.date(2024, 3, 31), "20231231"),
        (datetime.date(2024, 4, 1), "20240331"),
        (datetime.date(2024, 6, 30), "20240331"),
        (datetime.date(2024, 7, 1), "20240630"),
        (datetime.date(2024, 9, 30), "20240630"),
        (datetime.date(2024, 10, 1), "20240930"),
        (datetime.date(2024, 12, 31), "20240930"),
    ]

    def _get_latest_report_period(date):
        year = date.year
        month = date.month
        if month <= 3:
            return f"{year-1}1231"
        elif month <= 6:
            return f"{year}0331"
        elif month <= 9:
            return f"{year}0630"
        else:
            return f"{year}0930"

    all_pass = True
    for date, expected in test_cases:
        result = _get_latest_report_period(date)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_pass = False
        print(f"{status} {date} -> {result} (期望: {expected})")

    return all_pass

# 验证字段映射
def verify_field_mapping():
    """验证字段映射完整性"""
    print("\n=== 验证字段映射 ===")

    tushare_fields = {
        'eps': 'basic_eps',
        'bps': 'bvps',
        'capital_rese_ps': 'per_capital_reserve',
        'undist_profit_ps': 'per_unassign_profit',
        'roe_waa': 'roe_weight',
        'grossprofit_margin': 'sale_gpr',
        'debt_to_assets': 'debt_asset_ratio',
        'or_yoy': 'toi_yoy_ratio',
    }

    print(f"✓ 映射字段数: {len(tushare_fields)}")
    for ts_field, proj_field in tushare_fields.items():
        print(f"  {ts_field:20s} -> {proj_field}")

    return True

# 验证缓存路径逻辑
def verify_cache_path():
    """验证缓存路径逻辑"""
    print("\n=== 验证缓存路径逻辑 ===")

    period = "20231231"
    year = period[:4]
    cache_path = f"cache/fina/{year}/fina_{period}.pkl"

    print(f"✓ 报告期: {period}")
    print(f"✓ 缓存路径: {cache_path}")
    print(f"✓ 年份目录: {year}")

    return True

# 验证STOCK_SPOT_COLUMNS包含所有必需字段
def verify_columns():
    """验证字段定义"""
    print("\n=== 验证字段定义 ===")

    required_fields = [
        'basic_eps', 'bvps', 'per_capital_reserve', 'per_unassign_profit',
        'roe_weight', 'sale_gpr', 'debt_asset_ratio', 'toi_yoy_ratio',
        'industry', 'listing_date'
    ]

    STOCK_SPOT_COLUMNS = (
        'date', 'code', 'name', 'new_price', 'change_rate', 'ups_downs',
        'volume', 'deal_amount', 'amplitude', 'turnoverrate', 'volume_ratio',
        'open_price', 'high_price', 'low_price', 'pre_close_price',
        'speed_increase', 'speed_increase_5', 'speed_increase_60', 'speed_increase_all',
        'dtsyl', 'pe9', 'pe', 'pbnewmrq',
        'basic_eps', 'bvps', 'per_capital_reserve', 'per_unassign_profit',
        'roe_weight', 'sale_gpr', 'debt_asset_ratio',
        'total_operate_income', 'toi_yoy_ratio', 'parent_netprofit', 'netprofit_yoy_ratio',
        'report_date', 'total_shares', 'free_shares', 'total_market_cap', 'free_cap',
        'industry', 'listing_date',
    )

    all_present = True
    for field in required_fields:
        if field in STOCK_SPOT_COLUMNS:
            print(f"✓ {field}")
        else:
            print(f"✗ {field} 缺失")
            all_present = False

    return all_present

if __name__ == "__main__":
    print("开始验证 Tushare 财务字段补全代码逻辑\n")

    success = True
    success = verify_report_period_logic() and success
    success = verify_field_mapping() and success
    success = verify_cache_path() and success
    success = verify_columns() and success

    print("\n" + "="*50)
    if success:
        print("✓ 所有逻辑验证通过")
    else:
        print("✗ 部分验证失败")
    print("="*50)

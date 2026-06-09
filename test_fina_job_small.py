#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '/data/tostock')

import datetime
import pandas as pd
from instock.core.tushare_provider import TushareProvider

provider = TushareProvider()
date = datetime.date(2024, 1, 15)
period = provider._get_latest_report_period(date)

print(f"报告期: {period}")

# 仅测试前10只股票
stock_info = provider._get_stock_info()
codes = list(stock_info.keys())[:10]
print(f"测试股票数: {len(codes)}")

results = []
success_count = 0
fail_count = 0

for i, code in enumerate(codes, 1):
    ts_code = provider.to_ts_code(code)
    print(f"{i}. {code} ({ts_code})...", end=" ")

    try:
        result = provider._call_with_retry(
            'fina_indicator',
            f'fina_{ts_code}',
            lambda tc=ts_code, p=period: provider.pro.fina_indicator(ts_code=tc, period=p)
        )

        if result.is_success and result.data is not None and not result.data.empty:
            df = result.data.head(1).copy()
            df['code'] = code
            results.append(df)
            success_count += 1
            print(f"✓")
        else:
            fail_count += 1
            print(f"✗ {result.message}")
    except Exception as e:
        fail_count += 1
        print(f"✗ {e}")

print(f"\n总结: 成功 {success_count}/{len(codes)}")

if results:
    all_df = pd.concat(results, ignore_index=True)

    field_mapping = {
        'eps': 'basic_eps',
        'bps': 'bvps',
        'capital_rese_ps': 'per_capital_reserve',
        'undist_profit_ps': 'per_unassign_profit',
        'roe_waa': 'roe_weight',
        'grossprofit_margin': 'sale_gpr',
        'debt_to_assets': 'debt_asset_ratio',
        'or_yoy': 'toi_yoy_ratio',
    }

    result_df = pd.DataFrame()
    result_df['code'] = all_df['code']
    for ts_field, proj_field in field_mapping.items():
        if ts_field in all_df.columns:
            result_df[proj_field] = pd.to_numeric(all_df[ts_field], errors='coerce').fillna(0.0)
        else:
            result_df[proj_field] = 0.0

    print(f"\n最终数据:\n{result_df}")

    cache_file = f"/tmp/fina_{period}_test.pkl"
    result_df.to_pickle(cache_file)
    print(f"\n已保存到: {cache_file}")
else:
    print("\n没有成功获取任何数据")

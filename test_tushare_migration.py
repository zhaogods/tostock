#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试Tushare版本分红配送和大宗交易接口"""

import sys
sys.path.insert(0, '/home/docker/tostock')

import datetime
from instock.core.tushare_provider import TushareProvider

provider = TushareProvider()
test_date = datetime.date(2024, 1, 15)

print("=" * 80)
print("测试1：分红配送接口")
print("=" * 80)

try:
    dividend_df = provider.fetch_dividend(test_date)
    if dividend_df is not None and not dividend_df.empty:
        print(f"✓ 获取成功: {len(dividend_df)} 条记录")
        print(f"\n字段列表({len(dividend_df.columns)}个):")
        for col in dividend_df.columns:
            print(f"  - {col}")

        print(f"\n前3条样例数据:")
        sample = dividend_df.head(3)
        for idx, row in sample.iterrows():
            print(f"\n  [{row['code']}] {row['name']}")
            print(f"    送股: {row['convertible_rate']:.2f}")
            print(f"    转增: {row['convertible_transfer_rate']:.2f}")
            print(f"    派现: {row['bonusaward_rate']:.2f}")
            print(f"    EPS: {row['basic_eps']:.4f}")
            print(f"    除权日: {row['ex_dividend_date']}")
    else:
        print("✗ 返回空数据")
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n\n" + "=" * 80)
print("测试2：大宗交易接口")
print("=" * 80)

try:
    blocktrade_df = provider.fetch_block_trade(test_date)
    if blocktrade_df is not None and not blocktrade_df.empty:
        print(f"✓ 获取成功: {len(blocktrade_df)} 条记录")
        print(f"\n字段列表({len(blocktrade_df.columns)}个):")
        for col in blocktrade_df.columns:
            print(f"  - {col}")

        print(f"\n前3条样例数据:")
        sample = blocktrade_df.head(3)
        for idx, row in sample.iterrows():
            print(f"\n  [{row['code']}] {row['name']}")
            print(f"    收盘价: {row['new_price']:.2f}")
            print(f"    成交均价: {row['average_price']:.2f}")
            print(f"    折溢率: {row['overflow_rate']:.2f}%")
            print(f"    成交量: {row['sum_volume']:.2f}万股")
            print(f"    成交额: {row['sum_turnover']:.2f}万元")
    else:
        print("✗ 返回空数据")
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整集成测试：验证财务指标获取和fetch_stock_spot集成"""

import sys
sys.path.insert(0, '/data/tostock')

import datetime
from instock.core.tushare_provider import TushareProvider

provider = TushareProvider()
date = datetime.date(2024, 1, 15)

print("=" * 60)
print("步骤1: 测试财务缓存读取")
print("=" * 60)

fina_df = provider.get_fina_indicator_cached(date)
if fina_df is not None and not fina_df.empty:
    print(f"✓ 缓存读取成功: {len(fina_df)} 条记录")
    print(f"  字段: {list(fina_df.columns)}")
else:
    print("✗ 缓存读取失败")
    sys.exit(1)

print("\n" + "=" * 60)
print("步骤2: 测试fetch_stock_spot集成")
print("=" * 60)

result = provider.fetch_stock_spot(date)
if not result.is_success:
    print(f"✗ fetch_stock_spot失败: {result.message}")
    sys.exit(1)

df = result.data
print(f"✓ 获取成功: {len(df)} 条记录")

# 验证缓存中的股票数据
test_codes = ['000001', '000002', '000004']
for code in test_codes:
    row = df[df['code'] == code]
    if row.empty:
        print(f"  ✗ {code} 未找到")
        continue

    row = row.iloc[0]
    print(f"\n  {code} ({row['name']}):")
    print(f"    basic_eps: {row['basic_eps']:.4f}")
    print(f"    bvps: {row['bvps']:.4f}")
    print(f"    roe_weight: {row['roe_weight']:.4f}")
    print(f"    sale_gpr: {row['sale_gpr']:.4f}")
    print(f"    industry: {row['industry']}")

    # 验证值非零
    if row['basic_eps'] != 0 or row['bvps'] != 0:
        print(f"    ✓ 财务数据已正确加载")
    else:
        print(f"    ✗ 财务数据为0")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

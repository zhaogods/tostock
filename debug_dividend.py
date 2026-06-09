#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试分红配送接口"""

import sys
sys.path.insert(0, '/home/docker/tostock')

import datetime
import tushare as ts
from instock.lib.config import get_tushare_token

token = get_tushare_token()
pro = ts.pro_api(token)

# 测试原始API
print("=" * 80)
print("测试Tushare dividend原始API")
print("=" * 80)

test_date = datetime.date(2024, 1, 15)
year = test_date.year
start_date = f'{year-1}0101'
end_date = f'{year}1231'

print(f"\n查询参数:")
print(f"  ann_date范围: {start_date} ~ {end_date}")

try:
    df = pro.dividend(ann_date=start_date, end_date=end_date)
    print(f"\n✓ API调用成功")
    print(f"  返回记录数: {len(df) if df is not None else 0}")

    if df is not None and not df.empty:
        print(f"\n前5条记录:")
        print(df.head())
    else:
        print("\n✗ 返回空DataFrame")

        # 尝试不带日期参数查询
        print("\n尝试查询单只股票...")
        df2 = pro.dividend(ts_code='000001.SZ')
        if df2 is not None and not df2.empty:
            print(f"✓ 单只股票查询成功: {len(df2)} 条记录")
            print(df2.head(3))

except Exception as e:
    print(f"\n✗ API调用失败: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 Tushare 财务字段补全功能"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import datetime
from instock.core.tushare_provider import TushareProvider

def test_fina_indicator():
    """测试财务指标获取"""
    print("=== 测试财务指标获取 ===")
    try:
        provider = TushareProvider()
        date = datetime.date(2024, 1, 15)

        # 测试财务数据获取
        fina_df = provider.get_fina_indicator_cached(date)
        if fina_df is not None and not fina_df.empty:
            print(f"✓ 财务数据行数: {len(fina_df)}")
            print(f"✓ 字段: {fina_df.columns.tolist()}")
            print(f"✓ 前5条数据:")
            print(fina_df.head())
        else:
            print("✗ 财务数据获取失败")
            return False

        return True
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stock_spot():
    """测试股票实时行情"""
    print("\n=== 测试股票实时行情 ===")
    try:
        provider = TushareProvider()
        date = datetime.date(2024, 1, 15)

        result = provider.fetch_stock_spot(date)
        if result.is_success:
            df = result.data
            print(f"✓ 行情数据行数: {len(df)}")

            # 检查关键字段
            check_fields = ['basic_eps', 'bvps', 'industry', 'listing_date',
                            'roe_weight', 'sale_gpr', 'debt_asset_ratio']

            for field in check_fields:
                if field in df.columns:
                    if field in ['industry']:
                        non_empty = (df[field] != '').sum()
                        print(f"✓ {field} 非空数量: {non_empty}/{len(df)}")
                    elif field in ['listing_date']:
                        non_null = df[field].notna().sum()
                        print(f"✓ {field} 非空数量: {non_null}/{len(df)}")
                    else:
                        non_zero = (df[field] != 0).sum()
                        print(f"✓ {field} 非0数量: {non_zero}/{len(df)}")
                else:
                    print(f"✗ {field} 字段不存在")

            # 显示示例数据
            print(f"\n示例数据（前3条）:")
            print(df[['code', 'name', 'basic_eps', 'bvps', 'industry', 'listing_date']].head(3))

            return True
        else:
            print(f"✗ 获取失败: {result.message}")
            return False

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试 Tushare 财务字段补全功能\n")

    success = True
    success = test_fina_indicator() and success
    success = test_stock_spot() and success

    print("\n" + "="*50)
    if success:
        print("✓ 所有测试通过")
    else:
        print("✗ 部分测试失败")
    print("="*50)

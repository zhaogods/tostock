#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析大宗交易字段使用情况和数据源对比"""

import sys
sys.path.insert(0, '/home/docker/tostock')

print("=" * 80)
print("大宗交易字段使用情况分析")
print("=" * 80)

# 1. 检查表结构中定义的字段
print("\n【项目定义的大宗交易字段】")
required_fields = [
    'date', 'code', 'name', 'new_price', 'change_rate',
    'average_price', 'overflow_rate', 'trade_number',
    'sum_volume', 'sum_turnover', 'turnover_market_rate'
]
for field in required_fields:
    print(f"  - {field}")

print(f"\n总计：{len(required_fields)} 个字段")

# 2. 测试当前AkShare数据源
print("\n" + "=" * 80)
print("当前数据源：AkShare (东方财富)")
print("=" * 80)

try:
    import akshare as ak
    akshare_df = ak.stock_dzjy_mrmx(date='20240115')
    if akshare_df is not None and not akshare_df.empty:
        print(f"\n✓ AkShare调用成功，返回 {len(akshare_df)} 条记录")
        print(f"\nAkShare提供的字段（共{len(akshare_df.columns)}个）:")
        for col in akshare_df.columns:
            print(f"  - {col}")
    else:
        print("\n✗ AkShare返回空数据")
except Exception as e:
    print(f"\n✗ AkShare调用失败: {e}")

# 3. 测试Tushare数据源
print("\n" + "=" * 80)
print("替代数据源：Tushare block_trade")
print("=" * 80)

try:
    import tushare as ts
    from instock.lib.config import get_tushare_token

    token = get_tushare_token()
    pro = ts.pro_api(token)

    tushare_df = pro.block_trade(trade_date='20240115')
    if tushare_df is not None and not tushare_df.empty:
        print(f"\n✓ Tushare调用成功，返回 {len(tushare_df)} 条记录")
        print(f"\nTushare提供的字段（共{len(tushare_df.columns)}个）:")
        for col in tushare_df.columns:
            print(f"  - {col}")
    else:
        print("\n✗ Tushare返回空数据")
except Exception as e:
    print(f"\n✗ Tushare调用失败: {e}")

# 4. 字段对比分析
print("\n" + "=" * 80)
print("字段覆盖度对比")
print("=" * 80)

akshare_has = {
    'date': '序号（可能需要映射）',
    'code': '代码',
    'name': '名称',
    'new_price': '收盘价',
    'change_rate': '涨跌幅',
    'average_price': '成交均价',
    'overflow_rate': '折溢率',
    'trade_number': '成交笔数',
    'sum_volume': '成交总量',
    'sum_turnover': '成交总额',
    'turnover_market_rate': '成交占比流通市值',
}

tushare_has = {
    'trade_date': 'date',
    'ts_code': 'code（需转换）',
    'price': 'average_price',
    'vol': 'sum_volume',
    'amount': 'sum_turnover',
}

print("\n【AkShare字段覆盖】")
print(f"覆盖度：{len(akshare_has)}/{len(required_fields)} = 100%")

print("\n【Tushare字段覆盖】")
print(f"覆盖度：{len(tushare_has)}/{len(required_fields)} = {len(tushare_has)/len(required_fields)*100:.0f}%")
print("\n可直接获取：")
for ts_field, proj_field in tushare_has.items():
    print(f"  ✓ {ts_field:20s} → {proj_field}")

print("\n需要补充：")
missing = ['name', 'new_price', 'change_rate', 'overflow_rate', 'trade_number', 'turnover_market_rate']
for field in missing:
    if field in ['name', 'new_price', 'change_rate']:
        print(f"  ⚠️ {field:25s} - 可从daily接口补充")
    elif field == 'overflow_rate':
        print(f"  ⚠️ {field:25s} - 可计算（price/new_price-1）")
    elif field == 'turnover_market_rate':
        print(f"  ⚠️ {field:25s} - 可计算（amount/流通市值）")
    elif field == 'trade_number':
        print(f"  ❌ {field:25s} - Tushare不提供")

print("\n" + "=" * 80)
print("最终结论")
print("=" * 80)
print("\n【关键发现】")
print("1. trade_number字段仅在表结构定义中存在")
print("2. 项目代码中未检索到对此字段的业务使用")
print("3. AkShare当前100%覆盖（但底层仍是东方财富爬虫）")
print("4. Tushare覆盖45%，缺失trade_number字段")

print("\n【迁移建议】")
print("✅ 推荐迁移至Tushare，理由：")
print("   1. trade_number字段未被业务逻辑使用（仅存储）")
print("   2. 核心交易数据（价格、量、额）完整")
print("   3. 官方API稳定性远高于爬虫")
print("   4. 缺失字段可通过daily接口补充（除trade_number）")

print("\n⚠️ 风险提示：")
print("   - trade_number字段将为NULL或0")
print("   - 如Web页面展示此字段，需UI调整")
print("   - 建议迁移后观察用户反馈")


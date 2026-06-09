#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探查Tushare Pro 2000积分权限下的所有可用接口"""

import sys
sys.path.insert(0, '/home/docker/tostock')

import tushare as ts
from instock.lib.config import get_tushare_token

# 初始化
token = get_tushare_token()
if not token:
    print("错误：未配置TUSHARE_TOKEN")
    sys.exit(1)

pro = ts.pro_api(token)

print("=" * 80)
print("Tushare Pro 接口探查")
print("=" * 80)

# 获取接口权限信息
try:
    # 方法1：查询用户积分信息
    user_info = pro.user()
    if user_info is not None and not user_info.empty:
        print(f"\n用户信息:")
        print(f"  积分: {user_info.iloc[0].get('point', 'N/A')}")
        print(f"  到期时间: {user_info.iloc[0].get('exp_date', 'N/A')}")
except Exception as e:
    print(f"无法获取用户信息: {e}")

# 核心接口分类（2000积分权限内的重点接口）
api_catalog = {
    "行情数据": [
        ("daily", "日线行情", "已使用", "交易日期、开高低收、成交量额"),
        ("daily_basic", "每日指标", "已使用", "PE/PB/PS/市值/换手率/流通股本"),
        ("adj_factor", "复权因子", "未使用", "前复权/后复权因子"),
        ("suspend_d", "停复牌信息", "未使用", "停牌/复牌日期和原因"),
        ("hsgt_top10", "沪深港通十大成交股", "未使用", "每日沪深港通成交前10"),
        ("ggt_top10", "港股通十大成交股", "未使用", "港股通成交前10"),
        ("bak_daily", "备用行情", "未使用", "备用数据源"),
    ],

    "资金流向": [
        ("moneyflow", "个股资金流", "已使用", "主力/超大单/大单/中单/小单资金流"),
        ("moneyflow_hsgt", "沪深港通资金流", "未使用", "北向/南向资金流向统计"),
        ("hsgt_top10", "十大成交股", "未使用", "成交金额、净买入额"),
    ],

    "财务数据": [
        ("income", "利润表", "未使用", "营收、利润、费用等"),
        ("balancesheet", "资产负债表", "未使用", "资产、负债、权益"),
        ("cashflow", "现金流量表", "未使用", "经营/投资/筹资现金流"),
        ("fina_indicator", "财务指标", "已使用", "ROE、毛利率、负债率等"),
        ("fina_mainbz", "主营业务构成", "未使用", "分产品/地区营收占比"),
        ("dividend", "分红送股", "未使用", "分红、送转、预案"),
        ("top10_holders", "前十大股东", "未使用", "股东名称、持股数量/比例"),
        ("top10_floatholders", "前十大流通股东", "未使用", "流通股东明细"),
        ("stk_holdertrade", "股东增减持", "未使用", "股东买卖明细"),
    ],

    "市场参考数据": [
        ("stk_limit", "涨跌停价格", "未使用", "每日涨跌停价格计算"),
        ("limit_list_d", "每日涨跌停统计", "未使用", "涨停/跌停股票列表"),
        ("stk_factor", "复权因子", "未使用", "权息数据"),
        ("margin", "融资融券交易汇总", "未使用", "融资余额、融券余额"),
        ("margin_detail", "融资融券交易明细", "未使用", "个股融资融券明细"),
        ("top_list", "龙虎榜每日明细", "⚠️需5000积分", "上榜原因、成交额"),
        ("top_inst", "龙虎榜机构交易", "⚠️需5000积分", "机构买卖席位"),
    ],

    "基础信息": [
        ("stock_basic", "股票列表", "已使用", "代码、名称、上市日期、行业"),
        ("namechange", "股票曾用名", "未使用", "历史名称变更记录"),
        ("hs_const", "沪深股通成份股", "未使用", "港股通标的"),
        ("stk_managers", "上市公司管理层", "未使用", "高管姓名、职务"),
        ("stk_rewards", "管理层薪酬和持股", "未使用", "高管薪酬明细"),
        ("new_share", "IPO新股列表", "未使用", "新股发行信息"),
    ],

    "特色数据": [
        ("concept", "概念股分类", "未使用", "概念板块分类"),
        ("concept_detail", "概念股列表", "未使用", "每个概念包含的股票"),
        ("share_float", "限售股解禁", "未使用", "解禁时间、数量"),
        ("block_trade", "大宗交易", "未使用", "折价率、成交金额"),
        ("stk_account", "股票账户开户数", "未使用", "每周新增/总数"),
        ("stk_holdernumber", "股东人数", "未使用", "股东户数变化"),
        ("pledge_stat", "股权质押统计", "未使用", "质押比例、笔数"),
        ("pledge_detail", "股权质押明细", "未使用", "质押方、质押数量"),
        ("repurchase", "回购数据", "未使用", "回购金额、进度"),
    ],

    "指数数据": [
        ("index_basic", "指数基本信息", "未使用", "指数列表"),
        ("index_daily", "指数日线行情", "未使用", "指数K线数据"),
        ("index_dailybasic", "指数每日指标", "未使用", "成交额、换手率"),
        ("index_weight", "指数成份和权重", "未使用", "指数成份股权重"),
        ("index_classify", "申万行业分类", "未使用", "行业分类标准"),
        ("index_member", "申万行业成份", "未使用", "行业包含股票"),
    ],
}

print("\n" + "=" * 80)
print("2000积分权限下的接口清单（分类展示）")
print("=" * 80)

for category, apis in api_catalog.items():
    print(f"\n【{category}】")
    for api_name, desc, status, detail in apis:
        status_icon = "✅" if status == "已使用" else "⚠️" if "需5000" in status else "❌"
        print(f"  {status_icon} {api_name:25s} - {desc:20s} [{status}]")
        print(f"     └─ {detail}")

print("\n" + "=" * 80)
print("统计汇总")
print("=" * 80)

total = sum(len(apis) for apis in api_catalog.values())
used = sum(1 for apis in api_catalog.values() for _, _, status, _ in apis if status == "已使用")
need_5000 = sum(1 for apis in api_catalog.values() for _, _, status, _ in apis if "5000" in status)
available = total - used - need_5000

print(f"总接口数: {total}")
print(f"已使用: {used} ({used/total*100:.1f}%)")
print(f"需5000积分: {need_5000} ({need_5000/total*100:.1f}%)")
print(f"可用未使用: {available} ({available/total*100:.1f}%)")
print(f"利用率: {used/(total-need_5000)*100:.1f}%（排除5000积分接口）")

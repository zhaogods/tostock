#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析项目中易受反爬影响的接口"""

import sys
sys.path.insert(0, '/home/docker/tostock')

# 基于代码分析和东方财富反爬特征
eastmoney_interfaces = {
    "高风险（频繁被封）": [
        {
            "接口": "综合选股页面",
            "文件": "stock_selection.py",
            "URL": "datacenter-web.eastmoney.com",
            "调用频率": "每日1次",
            "数据量": "200+字段 × 5000+股票",
            "反爬特征": "大数据量单次请求，容易触发限流",
        },
        {
            "接口": "龙虎榜明细",
            "文件": "stock_lhb_em.py",
            "URL": "datacenter-web.eastmoney.com/securities/api",
            "调用频率": "每日1次",
            "数据量": "全市场龙虎榜",
            "反爬特征": "高价值数据，严格反爬",
        },
    ],

    "中风险（偶尔限流）": [
        {
            "接口": "个股资金流向",
            "文件": "stock_fund_em.py",
            "URL": "push2.eastmoney.com",
            "调用频率": "每日1次",
            "数据量": "主力/大单/中单/小单",
            "反爬特征": "已迁移到Tushare，风险解除",
            "状态": "✅ 已迁移",
        },
        {
            "接口": "分红配送",
            "文件": "stock_fhps_em.py",
            "URL": "data.eastmoney.com/DataCenter_V3",
            "调用频率": "每日1次",
            "数据量": "全年分红数据",
            "反爬特征": "使用AkShare包装，有一定防护",
        },
    ],

    "低风险（较稳定）": [
        {
            "接口": "大宗交易",
            "文件": "stock_dzjy_em.py",
            "URL": "datacenter-web.eastmoney.com",
            "调用频率": "每日1次",
            "数据量": "当日大宗交易",
            "反爬特征": "数据量小，风险较低",
        },
        {
            "接口": "涨停原因揭密",
            "文件": "stock_limitup_reason.py",
            "URL": "datacenter-web.eastmoney.com",
            "调用频率": "每日1次",
            "数据量": "涨停股票列表",
            "反爬特征": "实时性要求高，可能有限流",
        },
    ],
}

print("=" * 80)
print("东方财富接口反爬风险分析")
print("=" * 80)

for risk_level, interfaces in eastmoney_interfaces.items():
    print(f"\n【{risk_level}】")
    for item in interfaces:
        status = item.get('状态', '')
        status_icon = status if status else ""
        print(f"\n  {item['接口']} {status_icon}")
        print(f"    文件: {item['文件']}")
        print(f"    URL: {item['URL']}")
        print(f"    调用频率: {item['调用频率']}")
        print(f"    数据量: {item['数据量']}")
        print(f"    反爬特征: {item['反爬特征']}")

print("\n\n" + "=" * 80)
print("反爬缓解措施")
print("=" * 80)

mitigation = {
    "代码中已实现": [
        "代理池轮换（proxy_fetcher.py）",
        "Cookie注入（eastmoney_cookie.txt）",
        "请求重试机制",
        "User-Agent伪装",
    ],
    "配置文件": [
        "config/proxy.txt - 代理列表",
        "config/eastmoney_cookie.txt - Cookie",
        ".env - XIEQU_API_URL（携趣代理）",
    ],
}

for category, items in mitigation.items():
    print(f"\n【{category}】")
    for item in items:
        print(f"  • {item}")

print("\n\n" + "=" * 80)
print("建议")
print("=" * 80)
print("\n1. 监控高风险接口的失败率")
print("2. 定期更新代理池和Cookie")
print("3. 优先迁移到官方API（Tushare）")
print("4. 对于无法迁移的接口，增加降级方案")
print("5. 记录反爬失败日志，分析触发模式")


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精准匹配：当前项目东方财富接口 vs Tushare 2000积分替代方案"""

import sys
sys.path.insert(0, '/home/docker/tostock')

# 当前项目中使用东方财富的数据接口
CURRENT_EASTMONEY_USAGE = {
    "stock_fhps_em.py": {
        "name": "分红配送",
        "data": "分红、送股、转增、预案",
        "table": "stock_dividend",
        "job": "basic_data_other_daily_job.py",
        "tushare_match": "dividend",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐ 低",
        "data_coverage": "100%",
        "recommendation": "✅ 强烈推荐迁移",
    },

    "stock_dzjy_em.py": {
        "name": "大宗交易",
        "data": "成交价、成交量、买方/卖方席位",
        "table": "stock_blocktrade",
        "job": "basic_data_after_close_daily_job.py",
        "tushare_match": "block_trade",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐ 低",
        "data_coverage": "100%（额外提供折价率）",
        "recommendation": "✅ 强烈推荐迁移",
    },

    "stock_lhb_em.py": {
        "name": "龙虎榜",
        "data": "上榜原因、买入/卖出金额、营业部",
        "table": "stock_billboard",
        "job": "basic_data_other_daily_job.py",
        "tushare_match": "top_list + top_inst",
        "tushare_permission": "⚠️ 需5000积分",
        "migration_difficulty": "❌ 无法迁移",
        "data_coverage": "0%（权限不足）",
        "recommendation": "❌ 保留东方财富或使用AkShare",
    },

    "stock_fund_em.py": {
        "name": "个股资金流向",
        "data": "主力/超大单/大单/中单/小单净流入",
        "table": "stock_fund_flow",
        "job": "basic_data_other_daily_job.py",
        "tushare_match": "moneyflow",
        "tushare_permission": "2000积分",
        "migration_difficulty": "✅ 已迁移",
        "data_coverage": "100%",
        "recommendation": "✅ 已使用Tushare",
    },

    "stock_limitup_reason.py": {
        "name": "涨停原因揭密",
        "data": "涨停时间、原因文字描述、封板强度",
        "table": "stock_limitup_reason",
        "job": "basic_data_other_daily_job.py",
        "tushare_match": "limit_list_d（仅统计，无文字描述）",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐⭐ 中",
        "data_coverage": "60%（缺少原因文字）",
        "recommendation": "⚠️ 部分迁移：统计数据用Tushare，原因文字保留东方财富",
    },

    "stock_selection.py": {
        "name": "综合选股页面（200+字段）",
        "data": "财务+技术+机构+人气综合数据",
        "table": "stock_web_selection_data",
        "job": "selection_data_daily_job.py",
        "tushare_match": "无（需组合多个接口）",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐⭐⭐⭐⭐ 极高",
        "data_coverage": "30%（需组合20+接口）",
        "recommendation": "❌ 不建议迁移（工作量过大，保留东方财富）",
    },

    "stock_cpbd.py": {
        "name": "筹码分布/早盘抢筹",
        "data": "筹码集中度、成本分布",
        "table": "stock_chip",
        "job": "basic_data_other_daily_job.py",
        "tushare_match": "cyq_*系列接口",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐⭐⭐ 中",
        "data_coverage": "80%",
        "recommendation": "⚠️ 可选迁移",
    },

    "fund_etf_em.py": {
        "name": "ETF行情",
        "data": "ETF价格、规模、成交量",
        "table": "stock_fund_daily",
        "job": "basic_data_daily_job.py",
        "tushare_match": "fund_daily（部分）",
        "tushare_permission": "2000积分",
        "migration_difficulty": "⭐⭐⭐ 中",
        "data_coverage": "70%",
        "recommendation": "⚠️ 已使用AkShare，可考虑双源验证",
    },
}

# Tushare接口补充（当前项目未使用，但可增强现有功能）
TUSHARE_ENHANCEMENT = {
    "suspend_d": {
        "name": "停复牌信息",
        "data": "停牌/复牌日期、原因",
        "enhance": "可为现有行情数据添加停牌标记",
        "priority": "⭐⭐ 中",
    },
    "adj_factor": {
        "name": "复权因子",
        "data": "前复权/后复权因子",
        "enhance": "优化K线复权计算",
        "priority": "⭐⭐⭐ 高",
    },
    "moneyflow_hsgt": {
        "name": "沪深港通资金流",
        "data": "北向/南向资金流向",
        "enhance": "增强资金流向分析维度",
        "priority": "⭐⭐ 中",
    },
    "margin + margin_detail": {
        "name": "融资融券",
        "data": "融资余额、融券余量",
        "enhance": "新增市场情绪指标",
        "priority": "⭐⭐ 中",
    },
}

print("=" * 100)
print("当前项目东方财富接口 vs Tushare 2000积分迁移对比")
print("=" * 100)

print("\n【可立即迁移的接口】")
migratable = [(k, v) for k, v in CURRENT_EASTMONEY_USAGE.items()
              if "强烈推荐" in v["recommendation"]]
for file, info in migratable:
    print(f"\n✅ {info['name']} ({file})")
    print(f"   当前表: {info['table']}")
    print(f"   Tushare接口: {info['tushare_match']}")
    print(f"   数据覆盖: {info['data_coverage']}")
    print(f"   迁移难度: {info['migration_difficulty']}")
    print(f"   作业文件: {info['job']}")

print("\n\n【部分迁移的接口】")
partial = [(k, v) for k, v in CURRENT_EASTMONEY_USAGE.items()
           if "部分迁移" in v["recommendation"] or "可选迁移" in v["recommendation"]]
for file, info in partial:
    print(f"\n⚠️ {info['name']} ({file})")
    print(f"   当前表: {info['table']}")
    print(f"   Tushare接口: {info['tushare_match']}")
    print(f"   数据覆盖: {info['data_coverage']}")
    print(f"   建议: {info['recommendation']}")

print("\n\n【无法迁移的接口】")
no_migrate = [(k, v) for k, v in CURRENT_EASTMONEY_USAGE.items()
              if "不建议迁移" in v["recommendation"] or "保留东方财富" in v["recommendation"]]
for file, info in no_migrate:
    print(f"\n❌ {info['name']} ({file})")
    print(f"   原因: {info['tushare_permission']}")
    print(f"   数据覆盖: {info['data_coverage']}")
    print(f"   建议: {info['recommendation']}")

print("\n\n【已完成迁移的接口】")
migrated = [(k, v) for k, v in CURRENT_EASTMONEY_USAGE.items()
            if "已迁移" in v["migration_difficulty"] or "已使用" in v["recommendation"]]
for file, info in migrated:
    print(f"\n✅ {info['name']} - {info['tushare_match']}")

print("\n\n" + "=" * 100)
print("统计汇总")
print("=" * 100)

total = len(CURRENT_EASTMONEY_USAGE)
can_migrate = len(migratable)
partial_migrate = len(partial)
cannot_migrate = len(no_migrate)
already_migrated = len(migrated)

print(f"东方财富接口总数: {total}")
print(f"✅ 可立即迁移: {can_migrate} ({can_migrate/total*100:.1f}%)")
print(f"⚠️ 部分迁移: {partial_migrate} ({partial_migrate/total*100:.1f}%)")
print(f"❌ 无法迁移: {cannot_migrate} ({cannot_migrate/total*100:.1f}%)")
print(f"✅ 已完成: {already_migrated} ({already_migrated/total*100:.1f}%)")

print("\n迁移潜力: ", end="")
if can_migrate > 0:
    print(f"立即迁移{can_migrate}个接口，可减少{can_migrate/(total-already_migrated)*100:.0f}%的东方财富依赖")
else:
    print("当前无立即可迁移接口")

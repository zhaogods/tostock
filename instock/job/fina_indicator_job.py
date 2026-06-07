#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务指标数据获取作业
逐股票获取fina_indicator数据并缓存

作者: Claude
日期: 2026-06-07
说明: 由于Tushare fina_indicator接口要求必须提供ts_code参数，
     本作业逐个股票获取财务数据并缓存，供fetch_stock_spot使用
"""

import sys
import os
import datetime
import pandas as pd
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from instock.core.tushare_provider import TushareProvider
from instock.lib.run_template import run_with_args

pd.options.mode.copy_on_write = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def fetch_fina_indicators(date):
    """获取指定日期的财务指标数据

    Args:
        date: 交易日期
    """
    provider = TushareProvider()

    # 计算报告期
    period = provider._get_latest_report_period(date)

    # 检查缓存
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'fina', period[:4])
    cache_file = os.path.join(cache_dir, f"fina_{period}_all.pkl")

    if os.path.exists(cache_file):
        logging.info(f"财务数据缓存已存在: {cache_file}")
        return

    # 获取股票列表
    stock_info = provider._get_stock_info()
    codes = list(stock_info.keys())

    logging.info(f"开始获取 {len(codes)} 只股票的财务指标，报告期: {period}")
    logging.info(f"预计耗时: {len(codes) / 160:.1f} 分钟 (限流160次/分钟)")

    results = []
    success_count = 0
    fail_count = 0

    for i, code in enumerate(codes, 1):
        ts_code = provider.to_ts_code(code)

        try:
            result = provider._call_with_retry(
                'fina_indicator',
                f'fina_indicator({ts_code},{period})',
                lambda tc=ts_code, p=period: provider.pro.fina_indicator(ts_code=tc, period=p)
            )

            if result.is_success and result.data is not None and not result.data.empty:
                df = result.data.head(1).copy()
                df['code'] = code
                results.append(df)
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            logging.warning(f"获取 {code} 财务数据失败: {e}")
            fail_count += 1

        # 每100只股票输出一次进度
        if i % 100 == 0 or i == len(codes):
            progress_pct = i / len(codes) * 100
            logging.info(f"进度: {i}/{len(codes)} ({progress_pct:.1f}%) 成功:{success_count} 失败:{fail_count}")

    # 合并并缓存
    if results:
        all_df = pd.concat(results, ignore_index=True)

        # 字段映射
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

        # 保存缓存
        os.makedirs(cache_dir, exist_ok=True)
        result_df.to_pickle(cache_file)
        logging.info(f"财务数据已缓存: {cache_file}, 共 {len(result_df)} 条记录")
        logging.info(f"成功率: {success_count}/{len(codes)} ({success_count/len(codes)*100:.1f}%)")
    else:
        logging.error("未获取到任何财务数据")


def main():
    """主函数"""
    run_with_args(fetch_fina_indicators)


if __name__ == '__main__':
    main()

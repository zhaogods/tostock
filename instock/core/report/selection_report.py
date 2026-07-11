#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
每日选股报告

基于策略命中、策略近期表现、资金流、技术信号、K 线形态和数据资产门禁，
生成可复现的规则化选股报告；LLM 只做可选解释增强。
"""

import datetime
import json
import logging
import os

import pandas as pd

from instock.lib import config
from instock.lib import database as mdb


__author__ = 'Kiro'
__date__ = '2026/06/10'


_POSITIVE_PATTERNS = {
    'morning_star', 'morning_doji_star', 'three_white_soldiers', 'hammer', 'inverted_hammer',
    'piercing_pattern', 'dragonfly_doji', 'ladder_bottom', 'matching_low', 'homing_pigeon',
    'belt_hold', 'breakaway', 'kicking', 'unique_3_river', 'three_inside_up_down',
}
_NEGATIVE_PATTERNS = {
    'three_black_crows', 'evening_star', 'evening_doji_star', 'shooting_star', 'hanging_man',
    'dark_cloud_cover', 'advance_block', 'stalled_pattern', 'gravestone_doji', 'two_crows',
    'tow_crows', 'upside_gap_two_crows', 'bearish_engulfing', 'black_cloud_tops',
}
_CRITICAL_ASSET_KEYS = {'stock_daily', 'selection_data', 'stock_moneyflow', 'indicators_buy', 'patterns', 'backtest_rank'}


def _modules():
    import instock.core.tablestructure as tbs
    return tbs


def _normalize_date(value=None):
    if value is None or value == '':
        return datetime.date.today()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except Exception:
        return datetime.date.today()


def _read_sql(sql, params=None):
    try:
        return pd.read_sql(sql=sql, con=mdb.engine(), params=params)
    except Exception as exc:
        logging.error(f"selection_report._read_sql处理异常：{exc}")
        return pd.DataFrame()


def _table_columns(table):
    return list((table or {}).get('columns') or {})


def _existing_columns(table_name, desired):
    if not desired:
        return []
    cols = ','.join(['%s'] * len(desired))
    rows = mdb.executeSqlFetch(
        f"""
        SELECT `column_name`
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name IN ({cols})
        """,
        tuple([table_name] + list(desired)),
    ) or []
    existing = {row[0] for row in rows}
    return [col for col in desired if col in existing]


def _read_daily_table(table, date_value, columns):
    table_name = table['name'] if isinstance(table, dict) else table
    if not mdb.checkTableIsExist(table_name):
        return pd.DataFrame(columns=columns)
    columns = _existing_columns(table_name, columns)
    if not columns:
        return pd.DataFrame()
    col_sql = ','.join(f'`{col}`' for col in columns)
    return _read_sql(f"SELECT {col_sql} FROM `{table_name}` WHERE `date`=%s", (date_value,))


def _safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def _short_text(value, max_chars=1800):
    text = '' if value is None else str(value)
    return text[:max_chars]


def _format_number(value, digits=2, suffix=''):
    if value is None or value == '':
        return '-'
    try:
        value = float(value)
    except Exception:
        return str(value)
    return f"{value:.{digits}f}{suffix}"


def _format_amount(value):
    value = _safe_float(value)
    if abs(value) >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if abs(value) >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.0f}"


def _strategy_performance_map():
    try:
        from instock.lib import strategy_analytics
        perfs = strategy_analytics.get_all_strategies_performance(7)
        return {item.key: item for item in perfs}
    except Exception as exc:
        logging.error(f"selection_report._strategy_performance_map处理异常：{exc}")
        return {}


def _asset_status_context(date_value):
    try:
        from instock.lib import data_asset_manager
        statuses = data_asset_manager.get_all_assets_status(date_value)
    except Exception as exc:
        logging.error(f"selection_report._asset_status_context处理异常：{exc}")
        statuses = []
    assets = []
    blocked = []
    warning = []
    for status in statuses:
        item = {
            'key': status.key,
            'name': status.name,
            'table': status.table,
            'gate_status': status.gate_status,
            'gate_message': status.gate_message,
            'actual': status.actual,
            'expected': status.expected,
            'completeness': status.completeness,
            'quality_score': status.quality_score,
        }
        assets.append(item)
        if status.gate_status == 'block':
            blocked.append(item)
        elif status.gate_status == 'warning':
            warning.append(item)
    critical_blocked = [item for item in blocked if item.get('key') in _CRITICAL_ASSET_KEYS]
    return {
        'assets': assets,
        'blocked': blocked,
        'warning': warning,
        'critical_blocked': critical_blocked,
        'gate_ok': not critical_blocked,
    }


def _strategy_candidates(date_value):
    tbs = _modules()
    perf_map = _strategy_performance_map()
    rows = []
    for strategy in tbs.TABLE_CN_STOCK_STRATEGIES:
        table_name = strategy['name']
        if not mdb.checkTableIsExist(table_name):
            continue
        try:
            data = _read_sql(
                f"SELECT `date`,`code`,`name` FROM `{table_name}` WHERE `date`=%s",
                (date_value,),
            )
        except Exception as exc:
            logging.error(f"selection_report._strategy_candidates处理异常：{table_name}{exc}")
            continue
        if data is None or data.empty:
            continue
        perf = perf_map.get(table_name)
        for _, row in data.iterrows():
            rows.append({
                'code': row.get('code'),
                'name': row.get('name'),
                'strategy_key': table_name,
                'strategy_name': strategy.get('cn') or table_name,
                'strategy_avg_return_10d': getattr(perf, 'avg_return_10d', 0.0) if perf else 0.0,
                'strategy_win_rate_10d': getattr(perf, 'win_rate_10d', 0.0) if perf else 0.0,
                'strategy_trend': getattr(perf, 'trend', 'flat') if perf else 'flat',
            })
    if not rows:
        return pd.DataFrame()
    data = pd.DataFrame(rows)
    grouped = []
    for code, group in data.groupby('code'):
        name_values = [item for item in group['name'].dropna().tolist() if item]
        strategies = []
        for _, row in group.iterrows():
            strategies.append({
                'key': row.get('strategy_key'),
                'name': row.get('strategy_name'),
                'avg_return_10d': _safe_float(row.get('strategy_avg_return_10d')),
                'win_rate_10d': _safe_float(row.get('strategy_win_rate_10d')),
                'trend': row.get('strategy_trend') or 'flat',
            })
        grouped.append({
            'code': code,
            'name': name_values[0] if name_values else '',
            'strategy_count': len(strategies),
            'strategies': strategies,
            'strategy_names': '、'.join(item.get('name') or item.get('key') for item in strategies),
            'strategy_avg_return_10d': round(sum(item.get('avg_return_10d', 0.0) for item in strategies) / len(strategies), 2) if strategies else 0.0,
            'strategy_win_rate_10d': round(sum(item.get('win_rate_10d', 0.0) for item in strategies) / len(strategies), 2) if strategies else 0.0,
        })
    return pd.DataFrame(grouped)


def _pattern_summary(date_value):
    tbs = _modules()
    pattern_columns = list(tbs.STOCK_KLINE_PATTERN_DATA['columns'])
    columns = ['code', 'name'] + pattern_columns
    data = _read_daily_table(tbs.TABLE_CN_STOCK_KLINE_PATTERN, date_value, columns)
    if data is None or data.empty:
        return pd.DataFrame(columns=['code', 'pattern_positive_count', 'pattern_negative_count', 'pattern_positive_names', 'pattern_negative_names'])
    fields = [col for col in pattern_columns if col in data.columns]
    cn_map = {col: tbs.get_field_cn(col, tbs.STOCK_KLINE_PATTERN_DATA) for col in fields}
    rows = []
    for _, row in data.iterrows():
        positive = []
        negative = []
        for col in fields:
            value = _safe_float(row.get(col))
            if value > 0 and (col in _POSITIVE_PATTERNS or len(positive) < 3):
                positive.append(cn_map.get(col) or col)
            elif value < 0 and (col in _NEGATIVE_PATTERNS or len(negative) < 3):
                negative.append(cn_map.get(col) or col)
        rows.append({
            'code': row.get('code'),
            'pattern_positive_count': len(positive),
            'pattern_negative_count': len(negative),
            'pattern_positive_names': '、'.join(positive[:5]),
            'pattern_negative_names': '、'.join(negative[:5]),
        })
    return pd.DataFrame(rows)


def collect_selection_candidates(date=None):
    date_value = _normalize_date(date)
    tbs = _modules()
    candidates = _strategy_candidates(date_value)
    asset_context = _asset_status_context(date_value)
    context = {
        'date': date_value.strftime('%Y-%m-%d'),
        'assets': asset_context,
        'gate_ok': asset_context.get('gate_ok'),
    }
    if candidates is None or candidates.empty:
        return pd.DataFrame(), context

    spot_cols = ['code', 'name', 'new_price', 'change_rate', 'volume', 'deal_amount', 'turnoverrate', 'volume_ratio', 'industry', 'total_market_cap', 'free_cap']
    spot = _read_daily_table(tbs.TABLE_CN_STOCK_SPOT, date_value, spot_cols)
    if spot is not None and not spot.empty:
        candidates = candidates.merge(spot.drop_duplicates('code'), on='code', how='left', suffixes=('', '_spot'))
        candidates['name'] = candidates.get('name_spot', candidates.get('name')).fillna(candidates.get('name'))

    fund_cols = ['code', 'fund_amount', 'fund_rate', 'fund_amount_super', 'fund_rate_super', 'fund_amount_large', 'fund_rate_large', 'fund_amount_3', 'fund_rate_3', 'fund_amount_5', 'fund_rate_5']
    fund = _read_daily_table(tbs.TABLE_CN_STOCK_FUND_FLOW, date_value, fund_cols)
    if fund is not None and not fund.empty:
        candidates = candidates.merge(fund.drop_duplicates('code'), on='code', how='left')

    indicator_buy = _read_daily_table(tbs.TABLE_CN_STOCK_INDICATORS_BUY, date_value, ['code'])
    buy_codes = set(indicator_buy['code'].astype(str)) if indicator_buy is not None and not indicator_buy.empty else set()
    candidates['indicator_buy'] = candidates['code'].astype(str).isin(buy_codes)

    patterns = _pattern_summary(date_value)
    if patterns is not None and not patterns.empty:
        candidates = candidates.merge(patterns, on='code', how='left')

    selection_cols = ['code', 'concept', 'style', 'popularity_rank', 'rank_change', 'org_rating', 'org_survey_3m', 'volume_ratio']
    selection = _read_daily_table(tbs.TABLE_CN_STOCK_SELECTION, date_value, selection_cols)
    if selection is not None and not selection.empty:
        candidates = candidates.merge(selection.drop_duplicates('code'), on='code', how='left', suffixes=('', '_selection'))

    lhb = _read_daily_table(tbs.TABLE_CN_STOCK_LHB, date_value, ['code', 'net_amount_buy', 'reason'])
    if lhb is not None and not lhb.empty:
        candidates = candidates.merge(lhb.drop_duplicates('code'), on='code', how='left')
        candidates['lhb_on_list'] = candidates['net_amount_buy'].notna()
    else:
        candidates['lhb_on_list'] = False

    limitup = _read_daily_table(tbs.TABLE_CN_STOCK_LIMITUP_REASON, date_value, ['code', 'title', 'reason'])
    if limitup is not None and not limitup.empty:
        candidates = candidates.merge(limitup.drop_duplicates('code'), on='code', how='left', suffixes=('', '_limitup'))
        candidates['limitup_reason'] = candidates.get('title', '')
    else:
        candidates['limitup_reason'] = ''

    candidates = candidates.drop_duplicates('code')
    return candidates, context


def _candidate_score(row, gate_ok=True):
    reasons = []
    risks = []
    strategy_count = _safe_int(row.get('strategy_count'))
    strategy_avg = _safe_float(row.get('strategy_avg_return_10d'))
    strategy_win = _safe_float(row.get('strategy_win_rate_10d'))
    fund_amount = _safe_float(row.get('fund_amount'))
    fund_rate = _safe_float(row.get('fund_rate'))
    change_rate = _safe_float(row.get('change_rate'))
    volume_ratio = _safe_float(row.get('volume_ratio_selection') if 'volume_ratio_selection' in row else row.get('volume_ratio'))
    positive_patterns = _safe_int(row.get('pattern_positive_count'))
    negative_patterns = _safe_int(row.get('pattern_negative_count'))

    score = min(22.0, strategy_count * 7.0)
    score += min(8.0, max(0.0, strategy_avg) * 0.8)
    score += min(5.0, max(0.0, strategy_win - 50.0) / 10.0)
    if strategy_count:
        reasons.append(f"命中{strategy_count}个策略：{row.get('strategy_names') or '-'}")
    if strategy_avg > 0:
        reasons.append(f"命中策略近7日10日平均收益约{strategy_avg:.2f}%")
    elif strategy_count:
        risks.append('命中策略近期平均收益未转正')

    if fund_amount > 0:
        money_score = min(12.0, fund_amount / 10000000.0) + min(8.0, max(0.0, fund_rate) * 0.8)
        score += money_score
        reasons.append(f"主力净流入{_format_amount(fund_amount)}，净占比{_format_number(fund_rate, 2, '%')}")
    elif fund_amount < 0:
        score -= 8.0
        risks.append(f"主力资金净流出{_format_amount(abs(fund_amount))}")

    if bool(row.get('indicator_buy')):
        score += 10.0
        reasons.append('出现在技术指标买入信号表')
    if positive_patterns > 0:
        score += min(5.0, positive_patterns * 2.0)
        names = row.get('pattern_positive_names') or '正向形态'
        reasons.append(f"识别到{names}")
    if negative_patterns > 0:
        score -= min(8.0, negative_patterns * 2.0)
        names = row.get('pattern_negative_names') or '负向形态'
        risks.append(f"存在{names}")

    if volume_ratio > 1.5:
        score += min(5.0, (volume_ratio - 1.0) * 2.0)
        reasons.append(f"量比{volume_ratio:.2f}，成交活跃")
    if bool(row.get('lhb_on_list')):
        net_buy = _safe_float(row.get('net_amount_buy'))
        if net_buy > 0:
            score += min(5.0, net_buy / 10000000.0)
            reasons.append(f"龙虎榜净买入{_format_amount(net_buy)}")
        else:
            risks.append('龙虎榜上榜但净买额不强')
    if row.get('limitup_reason'):
        score += 3.0
        reasons.append(f"涨停原因：{_short_text(row.get('limitup_reason'), 40)}")

    if change_rate >= 9:
        score -= 5.0
        risks.append('当日涨幅接近或达到涨停，追高风险较高')
    elif change_rate <= -5:
        score -= 4.0
        risks.append('当日跌幅较大，需确认趋势修复')
    if not gate_ok:
        score -= 15.0
        risks.append('关键数据资产门禁未通过，结论需降级为观察')

    score = max(0.0, min(100.0, score))
    if not reasons:
        reasons.append('仅有策略命中记录，辅助数据不足')
    if not risks:
        risks.append('未触发主要风险扣分，但仍需结合盘面和仓位控制')
    return round(score, 2), reasons[:5], risks[:5]


def score_candidates(candidates, context=None):
    if candidates is None or candidates.empty:
        return []
    context = context or {}
    gate_ok = bool(context.get('gate_ok', True))
    records = []
    for _, row in candidates.iterrows():
        score, reasons, risks = _candidate_score(row, gate_ok=gate_ok)
        records.append({
            'code': str(row.get('code') or ''),
            'name': str(row.get('name') or ''),
            'score': score,
            'strategy_count': _safe_int(row.get('strategy_count')),
            'strategy_names': row.get('strategy_names') or '',
            'strategy_avg_return_10d': _safe_float(row.get('strategy_avg_return_10d')),
            'strategy_win_rate_10d': _safe_float(row.get('strategy_win_rate_10d')),
            'change_rate': _safe_float(row.get('change_rate')),
            'new_price': _safe_float(row.get('new_price')),
            'fund_amount': _safe_float(row.get('fund_amount')),
            'fund_rate': _safe_float(row.get('fund_rate')),
            'indicator_buy': bool(row.get('indicator_buy')),
            'pattern_positive_names': row.get('pattern_positive_names') or '',
            'pattern_negative_names': row.get('pattern_negative_names') or '',
            'industry': row.get('industry') or '',
            'concept': row.get('concept') or '',
            'reasons': reasons,
            'risks': risks,
        })
    records.sort(key=lambda item: (item.get('score', 0), item.get('strategy_count', 0), item.get('fund_amount', 0)), reverse=True)
    return records


def _format_table(candidates):
    if not candidates:
        return '暂无候选\n'
    lines = [
        '| 排名 | 代码 | 名称 | 得分 | 涨跌幅 | 主力净流入 | 命中策略 | 入选理由 | 风险提示 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for idx, item in enumerate(candidates, start=1):
        lines.append(
            '| {rank} | {code} | {name} | {score:.2f} | {change} | {fund} | {strategies} | {reasons} | {risks} |'.format(
                rank=idx,
                code=item.get('code') or '-',
                name=item.get('name') or '-',
                score=_safe_float(item.get('score')),
                change=_format_number(item.get('change_rate'), 2, '%'),
                fund=_format_amount(item.get('fund_amount')),
                strategies=_short_text(item.get('strategy_names') or '-', 80).replace('|', '/'),
                reasons=_short_text('；'.join(item.get('reasons') or []), 120).replace('|', '/'),
                risks=_short_text('；'.join(item.get('risks') or []), 120).replace('|', '/'),
            )
        )
    return '\n'.join(lines) + '\n'


def _asset_gate_section(context):
    assets = (context or {}).get('assets') or {}
    critical = assets.get('critical_blocked') or []
    warning = assets.get('warning') or []
    if not critical and not warning:
        return ['- 关键数据资产门禁通过，报告按正常规则生成。']
    lines = []
    if critical:
        lines.append('- **关键资产门禁阻断，报告结论降级为观察清单。**')
        for item in critical[:6]:
            lines.append(f"  - {item.get('name') or item.get('key')}：{item.get('gate_message') or '门禁阻断'}")
    if warning:
        lines.append(f"- {len(warning)} 个数据资产存在 warning 门禁，需关注字段缺失或数据源延迟。")
    return lines


def build_report_content(date=None):
    date_value = _normalize_date(date)
    candidates, context = collect_selection_candidates(date_value)
    scored = score_candidates(candidates, context)
    top_n = config.get_selection_report_top_n()
    top_candidates = scored[:top_n]
    gate_ok = bool(context.get('gate_ok', True))

    title = f"{date_value} 每日选股报告"
    if not gate_ok:
        summary = f"关键数据资产门禁未通过，生成观察清单 {len(top_candidates)} 只，不建议作为正常选股结论。"
    elif not top_candidates:
        summary = '当日未从策略结果中筛选出候选股票。'
    else:
        summary = f"基于策略命中、资金流、技术信号和数据质量，筛选候选 {len(top_candidates)} 只。"

    llm_text = ''
    llm_result = None
    if top_candidates:
        try:
            from instock.lib import llm_client
            llm_result = llm_client.explain_selection_report(
                {
                    'date': date_value.strftime('%Y-%m-%d'),
                    'summary': summary,
                    'gate_ok': gate_ok,
                    'asset_gate': context.get('assets'),
                    'top_n': top_n,
                },
                top_candidates,
            )
            if llm_result.get('ok') and llm_result.get('text'):
                llm_text = llm_result.get('text')
        except Exception as exc:
            logging.error(f"selection_report.build_report_content LLM解释异常：{exc}")
            llm_result = {'enabled': False, 'model': config.get_agent_llm_model(), 'error': str(exc)}

    sections = [
        f"# {title}",
        '',
        '## 报告摘要',
        '',
        summary,
        '',
        '## 数据质量与门禁',
        '',
        '\n'.join(_asset_gate_section(context)),
        '',
        '## 候选股票 Top {}'.format(top_n),
        '',
        _format_table(top_candidates),
    ]
    if llm_text:
        sections.extend([
            '## Agent 解读',
            '',
            llm_text,
            '',
        ])
    sections.extend([
        '## 方法说明',
        '',
        '- 候选池来自当日各策略表命中结果，并合并行情、资金流、技术买入信号、K线形态、龙虎榜和涨停原因等辅助字段。',
        '- 得分由规则引擎生成，LLM（如启用）只负责解释已筛选结果，不新增股票。',
        '- 当关键数据资产门禁阻断时，报告自动降级为观察清单。',
        '- 本报告仅用于量化研究和系统复盘，不构成投资建议。',
        '',
    ])
    return title, summary, '\n'.join(sections), top_candidates, llm_result


def generate_selection_report(date=None):
    date_value = _normalize_date(date)
    title, summary, content, top_candidates, llm_result = build_report_content(date_value)
    report_dir = config.project_root() / 'reports' / 'selection'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f'{date_value}.md'
    report_path.write_text(content, encoding='utf-8')
    return {
        'date': date_value,
        'title': title,
        'summary': summary,
        'candidate_count': len(top_candidates),
        'top_codes': ','.join(item.get('code') or '' for item in top_candidates[:20]),
        'report_path': os.fspath(report_path),
        'llm_enabled': 1 if (llm_result or {}).get('enabled') else 0,
        'model': (llm_result or {}).get('model') or (config.get_agent_llm_model() if config.get_agent_llm_enabled(False) else ''),
        'created_at': datetime.datetime.now(),
    }


def _save_agent_run_log(date_value, llm_enabled, model, status='success', error_message=''):
    tbs = _modules()
    table = tbs.TABLE_AGENT_RUN_LOG
    table_name = table['name']
    row = {
        'run_id': datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),
        'date': date_value,
        'agent_key': 'selection_report',
        'llm_enabled': 1 if llm_enabled else 0,
        'model': model or '',
        'status': status,
        'duration_seconds': 0,
        'request_id': '',
        'input_tokens': 0,
        'output_tokens': 0,
        'error_message': _short_text(error_message),
        'created_at': datetime.datetime.now(),
    }
    data = pd.DataFrame([row], columns=list(table['columns']))
    cols_type = None if mdb.checkTableIsExist(table_name) else tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, '`run_id`')


def save_selection_report(date=None):
    tbs = _modules()
    date_value = _normalize_date(date)
    result = generate_selection_report(date_value)
    table = tbs.TABLE_DAILY_SELECTION_REPORT
    table_name = table['name']
    data = pd.DataFrame([result], columns=list(table['columns']))
    if mdb.checkTableIsExist(table_name):
        mdb.executeSql(f"DELETE FROM `{table_name}` where `date` = %s", (date_value,))
        cols_type = None
    else:
        cols_type = tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, '`date`')
    try:
        _save_agent_run_log(date_value, result.get('llm_enabled'), result.get('model'))
    except Exception as exc:
        logging.error(f"selection_report.save_selection_report记录Agent日志异常：{exc}")
    return 1

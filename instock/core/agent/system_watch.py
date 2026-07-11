#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
系统监看 Agent

读取控制台、任务、数据质量和数据资产的结构化状态，生成规则化洞察；
LLM 只作为可选摘要增强，不参与自动执行操作。
"""

import datetime
import json
import logging
import time
import uuid

import pandas as pd

from instock.lib import config
from instock.lib import console_service
from instock.lib import database as mdb
from instock.lib import task_runner


AGENT_KEY = 'system_watch'
INSIGHT_STATUS_OPEN = 'open'

_CRITICAL_ASSETS = {'stock_daily', 'selection_data', 'stock_moneyflow', 'indicators', 'indicators_buy', 'patterns', 'backtest_rank'}


__author__ = 'Kiro'
__date__ = '2026/06/10'


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


def _format_date(value):
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, datetime.date):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _safe_int(value, default=0):
    try:
        return int(value or 0)
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except Exception:
        return default


def _short_text(value, max_chars=1800):
    text = '' if value is None else str(value)
    return text[:max_chars]


def _to_json(value, max_chars=3900):
    try:
        text = json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text[:max_chars]


def _query(sql, params=()):
    try:
        return mdb.executeSqlFetch(sql, params) or []
    except Exception as exc:
        logging.error(f"system_watch._query处理异常：{sql}{exc}")
    return []


def _record_exists(table_name, date_value):
    if not mdb.checkTableIsExist(table_name):
        return False
    rows = _query(f"SELECT COUNT(*) FROM `{table_name}` WHERE `date`=%s", (date_value,))
    try:
        return bool(rows and int(rows[0][0] or 0) > 0)
    except Exception:
        return False


def collect_system_context(query_date=None):
    """采集系统监看上下文，所有异常都降级为空结果。"""
    date_value = _normalize_date(query_date)
    date_text = date_value.strftime('%Y-%m-%d')
    context = {'date': date_text}
    try:
        context['dashboard'] = console_service.get_console_dashboard(date_value)
    except Exception as exc:
        logging.error(f"system_watch.collect dashboard异常：{exc}")
        context['dashboard'] = {}
    try:
        context['health'] = console_service.get_system_health()
    except Exception as exc:
        logging.error(f"system_watch.collect health异常：{exc}")
        context['health'] = {}
    try:
        context['assets'] = console_service.get_data_assets(date_value)
    except Exception as exc:
        logging.error(f"system_watch.collect assets异常：{exc}")
        context['assets'] = {'summary': {}, 'assets': []}
    try:
        context['quality'] = console_service.get_data_quality_summary(date_value)
    except Exception as exc:
        logging.error(f"system_watch.collect quality异常：{exc}")
        context['quality'] = {}
    try:
        context['pipeline'] = console_service.get_pipeline_map(date_value)
    except Exception as exc:
        logging.error(f"system_watch.collect pipeline异常：{exc}")
        context['pipeline'] = {}
    try:
        context['recent_runs'] = task_runner.recent_runs(40)
    except Exception as exc:
        logging.error(f"system_watch.collect recent_runs异常：{exc}")
        context['recent_runs'] = []
    try:
        context['job_recent'] = task_runner.recent_job_runs(30)
    except Exception as exc:
        logging.error(f"system_watch.collect job_recent异常：{exc}")
        context['job_recent'] = []
    try:
        context['open_notices'] = task_runner.notices(30, status=task_runner.NOTICE_STATUS_OPEN)
    except Exception as exc:
        logging.error(f"system_watch.collect notices异常：{exc}")
        context['open_notices'] = []
    return context


def _finding(level, category, title, message, suggestion='', evidence=None, related_task_key='', related_run_id=''):
    return {
        'level': level,
        'category': category,
        'title': _short_text(title, 200),
        'message': _short_text(message),
        'suggestion': _short_text(suggestion),
        'evidence': evidence or {},
        'related_task_key': related_task_key or '',
        'related_run_id': related_run_id or '',
    }


def _is_query_date_today(date_text):
    return date_text == datetime.date.today().strftime('%Y-%m-%d')


def rule_based_findings(context):
    """基于结构化上下文生成规则化洞察。"""
    findings = []
    date_text = context.get('date') or datetime.date.today().strftime('%Y-%m-%d')
    health = context.get('health') or {}

    if health.get('scheduler_enabled') and not health.get('scheduler_alive'):
        findings.append(_finding(
            'critical', 'scheduler', '调度器心跳异常',
            f"调度器已启用，但最近心跳时间为 {health.get('scheduler_heartbeat_at') or '未知'}，超过健康阈值。",
            '检查 scheduler_service 进程、supervisord 状态和 system_task_state 心跳记录。',
            {
                'heartbeat_at': health.get('scheduler_heartbeat_at'),
                'age_seconds': health.get('scheduler_heartbeat_age_seconds'),
                'stale_seconds': health.get('scheduler_heartbeat_stale_seconds'),
            },
            related_task_key='__scheduler__',
        ))
    elif health.get('scheduler_enabled') is False:
        findings.append(_finding(
            'warning', 'scheduler', '任务调度已关闭',
            'TASK_SCHEDULER_ENABLED 当前为关闭状态，自动任务不会触发。',
            '如需自动运行盘中刷新和日终任务，请确认配置后重启调度器。',
            {'scheduler_enabled': False},
            related_task_key='__scheduler__',
        ))

    disk = health.get('disk') or {}
    disk_percent = _safe_float(disk.get('used_percent'))
    if disk_percent >= 90:
        findings.append(_finding(
            'critical', 'disk', '磁盘空间严重不足',
            f"项目所在磁盘使用率 {disk_percent:.1f}%，可能影响日志、缓存和报告写入。",
            '清理历史 K 线缓存、任务日志或扩容磁盘。',
            disk,
        ))
    elif disk_percent >= 80:
        findings.append(_finding(
            'warning', 'disk', '磁盘空间偏高',
            f"项目所在磁盘使用率 {disk_percent:.1f}%，建议提前清理缓存和旧日志。",
            '关注 instock/cache/hist 与 instock/log/tasks 目录增长。',
            disk,
        ))

    recent_runs = context.get('recent_runs') or []
    today_bad_runs = []
    for run in recent_runs:
        run_date = str(run.get('run_date') or '')[:10]
        if run_date != date_text:
            continue
        if run.get('status') in (task_runner.STATUS_FAILED, task_runner.STATUS_STOPPED):
            today_bad_runs.append(run)
    for run in today_bad_runs[:8]:
        status = run.get('status')
        findings.append(_finding(
            'critical' if status == task_runner.STATUS_FAILED else 'warning',
            'task',
            f"任务{run.get('task_name') or run.get('task_key')}状态异常",
            f"今日任务状态为 {status}，消息：{run.get('message') or '无'}。",
            '在控制台打开该任务日志，确认失败阶段后按依赖顺序重跑。',
            {
                'task_key': run.get('task_key'),
                'status': status,
                'start_time': run.get('start_time'),
                'end_time': run.get('end_time'),
                'message': run.get('message'),
            },
            related_task_key=run.get('task_key') or '',
            related_run_id=run.get('run_id') or '',
        ))

    pipeline = context.get('pipeline') or {}
    for stage in pipeline.get('stages') or []:
        for task in stage.get('tasks') or []:
            if task.get('timed_out'):
                findings.append(_finding(
                    'critical', 'task', f"任务{task.get('name') or task.get('key')}运行超时",
                    f"任务已运行 {task.get('running_seconds')} 秒，超过超时阈值 {task.get('timeout_seconds')} 秒。",
                    '检查任务日志和外部数据源限流情况，必要时在控制台手动停止后重跑。',
                    {
                        'task_key': task.get('key'),
                        'running_seconds': task.get('running_seconds'),
                        'timeout_seconds': task.get('timeout_seconds'),
                    },
                    related_task_key=task.get('key') or '',
                    related_run_id=task.get('running_run_id') or '',
                ))

    assets_payload = context.get('assets') or {}
    blocked_assets = []
    warning_assets = []
    for asset in assets_payload.get('assets') or []:
        gate_status = asset.get('gate_status') or 'pass'
        if gate_status == 'block':
            blocked_assets.append(asset)
        elif gate_status == 'warning':
            warning_assets.append(asset)
    for asset in blocked_assets[:10]:
        critical = asset.get('key') in _CRITICAL_ASSETS
        findings.append(_finding(
            'critical' if critical else 'warning', 'data_asset', f"数据资产门禁阻断：{asset.get('name')}",
            asset.get('gate_message') or f"{asset.get('name')} 完整度或质量未达标。",
            '先重跑对应上游任务，确认数据源和 data_quality_log 后再使用下游报告。',
            {
                'key': asset.get('key'),
                'table': asset.get('table'),
                'task_key': asset.get('task_key'),
                'actual': asset.get('actual'),
                'expected': asset.get('expected'),
                'completeness': asset.get('completeness'),
                'quality_score': asset.get('quality_score'),
                'gate_message': asset.get('gate_message'),
            },
            related_task_key=asset.get('task_key') or '',
        ))
    if warning_assets:
        sample = warning_assets[:5]
        findings.append(_finding(
            'warning', 'data_asset', '存在数据资产质量警告',
            f"{len(warning_assets)} 个数据资产处于 warning 门禁状态：" + '、'.join(item.get('name') or item.get('key') for item in sample),
            '关注门禁消息，若涉及日终报告输入资产，请重跑对应任务或等待数据源补齐。',
            {'assets': sample},
        ))

    quality = context.get('quality') or {}
    if _safe_int(quality.get('error_count')) > 0:
        findings.append(_finding(
            'critical', 'quality', '今日存在 error 级数据质量异常',
            f"今日数据质量检查 error={quality.get('error_count')}，failed={quality.get('failed_checks')}。",
            '查看 data_quality_log 中失败记录，优先处理 error 级表。',
            quality,
        ))
    elif _safe_int(quality.get('warning_count')) > 0 or _safe_int(quality.get('failed_checks')) > 0:
        findings.append(_finding(
            'warning', 'quality', '今日存在数据质量警告',
            f"今日数据质量检查 warning={quality.get('warning_count')}，failed={quality.get('failed_checks')}。",
            '检查是否为数据源延迟或字段缺失，报告中应标记数据质量降级。',
            quality,
        ))

    tbs = _modules()
    now = datetime.datetime.now()
    report_check_window = (not _is_query_date_today(date_text)) or (now.weekday() <= 4 and now.time() >= datetime.time(18, 0))
    if report_check_window:
        if not _record_exists(tbs.TABLE_DAILY_MARKET_REPORT['name'], date_text):
            findings.append(_finding(
                'warning', 'report', '每日复盘报告缺失',
                f"{date_text} 未找到 daily_market_report 记录。",
                '确认 daily_report_job 是否成功，必要时手动运行每日复盘报告任务。',
                {'table': tbs.TABLE_DAILY_MARKET_REPORT['name'], 'date': date_text},
                related_task_key='daily_report_rebuild',
            ))
        if not _record_exists(tbs.TABLE_DAILY_SELECTION_REPORT['name'], date_text):
            findings.append(_finding(
                'warning', 'report', '每日选股报告缺失',
                f"{date_text} 未找到 daily_selection_report 记录。",
                '确认 selection_report_job 是否成功，必要时手动运行每日选股报告任务。',
                {'table': tbs.TABLE_DAILY_SELECTION_REPORT['name'], 'date': date_text},
                related_task_key='selection_report_rebuild',
            ))

    open_notices = context.get('open_notices') or []
    if len(open_notices) >= 5:
        findings.append(_finding(
            'warning', 'notice', '未处理通知较多',
            f"当前 open 状态通知 {len(open_notices)} 条，可能存在连续任务或数据质量问题。",
            '在控制台通知抽屉中逐条确认，完成处理后标记 ack/resolved。',
            {'open_notice_count': len(open_notices), 'sample': open_notices[:5]},
        ))

    if not findings:
        findings.append(_finding(
            'info', 'system', '系统监看未发现关键异常',
            '调度器、任务、数据资产、数据质量和报告检查未触发 warning/critical 规则。',
            '继续保持日终任务后查看控制台资产门禁与报告输出。',
            {'date': date_text},
        ))
    return findings


def _save_agent_run_log(date_value, status, duration_seconds, llm_result=None, error_message=''):
    tbs = _modules()
    table = tbs.TABLE_AGENT_RUN_LOG
    table_name = table['name']
    llm_result = llm_result or {}
    row = {
        'run_id': uuid.uuid4().hex,
        'date': date_value,
        'agent_key': AGENT_KEY,
        'llm_enabled': 1 if llm_result.get('enabled') else 0,
        'model': llm_result.get('model') or config.get_agent_llm_model(),
        'status': status,
        'duration_seconds': duration_seconds,
        'request_id': llm_result.get('request_id') or '',
        'input_tokens': _safe_int(llm_result.get('input_tokens')),
        'output_tokens': _safe_int(llm_result.get('output_tokens')),
        'error_message': _short_text(error_message or llm_result.get('error') or ''),
        'created_at': datetime.datetime.now(),
    }
    data = pd.DataFrame([row], columns=list(table['columns']))
    cols_type = None if mdb.checkTableIsExist(table_name) else tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, '`run_id`')


def save_insights(findings, date_value=None):
    tbs = _modules()
    date_value = _normalize_date(date_value)
    table = tbs.TABLE_AGENT_INSIGHT
    table_name = table['name']
    created_at = datetime.datetime.now()
    rows = []
    for item in findings or []:
        rows.append({
            'insight_id': uuid.uuid4().hex,
            'date': date_value,
            'agent_key': AGENT_KEY,
            'level': item.get('level') or 'info',
            'category': item.get('category') or 'system',
            'title': _short_text(item.get('title'), 200),
            'message': _short_text(item.get('message')),
            'suggestion': _short_text(item.get('suggestion')),
            'evidence_json': _to_json(item.get('evidence')),
            'related_task_key': _short_text(item.get('related_task_key'), 100),
            'related_run_id': _short_text(item.get('related_run_id'), 64),
            'status': INSIGHT_STATUS_OPEN,
            'created_at': created_at,
        })
    if not rows:
        return 0
    if mdb.checkTableIsExist(table_name):
        mdb.executeSql(
            "UPDATE `agent_insight` SET `status`=%s WHERE `date`=%s AND `agent_key`=%s AND `status`=%s",
            ('resolved', date_value, AGENT_KEY, INSIGHT_STATUS_OPEN),
        )
    data = pd.DataFrame(rows, columns=list(table['columns']))
    cols_type = None if mdb.checkTableIsExist(table_name) else tbs.get_field_types(table['columns'])
    mdb.insert_db_from_df(data, table_name, cols_type, False, '`insight_id`')
    return len(rows)


def sync_notices(findings):
    count = 0
    for item in findings or []:
        if item.get('level') not in ('warning', 'critical'):
            continue
        try:
            notice_id = task_runner.create_notice(
                'agent_system_watch',
                item.get('level') or 'warning',
                item.get('title') or 'Agent系统监看提醒',
                item.get('message') or item.get('suggestion') or '',
            )
            if notice_id:
                count += 1
        except Exception as exc:
            logging.error(f"system_watch.sync_notices处理异常：{exc}")
    return count


def run_system_watch(date=None):
    """执行系统监看，返回写入洞察数量。"""
    start = time.time()
    date_value = _normalize_date(date)
    context = collect_system_context(date_value)
    findings = rule_based_findings(context)
    llm_result = None
    try:
        from instock.lib import llm_client
        llm_result = llm_client.summarize_system_watch(
            {
                'date': context.get('date'),
                'health': context.get('health'),
                'assets_summary': (context.get('assets') or {}).get('summary'),
                'quality': context.get('quality'),
                'open_notice_count': len(context.get('open_notices') or []),
            },
            findings,
        )
        if llm_result.get('ok') and llm_result.get('text'):
            findings.insert(0, _finding(
                'info', 'agent', 'Agent系统监看摘要',
                llm_result.get('text'),
                '该摘要由 LLM 基于结构化状态生成，具体操作仍以控制台日志和数据资产门禁为准。',
                {'model': llm_result.get('model'), 'request_id': llm_result.get('request_id')},
            ))
    except Exception as exc:
        logging.error(f"system_watch.run_system_watch LLM摘要异常：{exc}")
        llm_result = {'enabled': False, 'model': config.get_agent_llm_model(), 'error': str(exc)}
    saved = save_insights(findings, date_value)
    sync_notices(findings)
    try:
        _save_agent_run_log(date_value, 'success', round(time.time() - start, 3), llm_result)
    except Exception as exc:
        logging.error(f"system_watch.run_system_watch记录运行日志异常：{exc}")
    return saved

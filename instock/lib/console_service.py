#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
控制台领域聚合服务

将任务、数据资产、策略、报告和数据质量等控制台所需信息统一整理，
避免 Web Handler 和前端直接拼接业务表查询。
"""

import datetime
import logging
import shutil
import time
from typing import Optional

import pymysql

from instock.lib import config
from instock.lib import database as mdb
from instock.lib import task_registry as registry
from instock.lib import task_runner


__author__ = 'Kiro'
__date__ = '2026/06/08'


_TABLE_EXISTS_CACHE = {}
_TABLE_EXISTS_TTL_SECONDS = 300


def _query(sql, params=()):
    conn = mdb.get_connection()
    if conn is None:
        return []
    with conn:
        with conn.cursor(pymysql.cursors.DictCursor) as db:
            try:
                db.execute(sql, params)
                return db.fetchall()
            except Exception as exc:
                logging.error(f"console_service._query处理异常：{sql}{exc}")
    return []


def _table_exists(table_name: str) -> bool:
    cached = _TABLE_EXISTS_CACHE.get(table_name)
    now = time.time()
    if cached is not None:
        exists, timestamp = cached
        if now - timestamp <= _TABLE_EXISTS_TTL_SECONDS:
            return exists
    rows = _query(
        """
        SELECT COUNT(*) AS `count`
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
        """,
        (table_name,),
    )
    exists = bool(rows and int(rows[0].get('count') or 0) == 1)
    _TABLE_EXISTS_CACHE[table_name] = (exists, now)
    return exists


def _normalize_date(value=None) -> datetime.date:
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


def _asset_to_dict(status):
    return {
        'key': status.key,
        'name': status.name,
        'source': status.source,
        'expected': status.expected,
        'actual': status.actual,
        'completeness': round(status.completeness, 4),
        'quality_score': round(status.quality_score, 2),
        'status': status.status,
        'issues': status.issues,
        'last_update': status.last_update,
    }


def _strategy_to_dict(perf):
    return {
        'key': perf.key,
        'name': perf.name,
        'sample_count': perf.sample_count,
        'avg_return_10d': round(perf.avg_return_10d, 2),
        'win_rate_10d': round(perf.win_rate_10d, 2),
        'trend': perf.trend,
        'updated_at': perf.updated_at,
    }


def _summarize_assets(assets):
    summary = {
        'total': len(assets),
        'healthy': 0,
        'warning': 0,
        'critical': 0,
        'avg_completeness': 0.0,
        'avg_quality_score': 0.0,
        'last_update': '',
        'worst_asset': None,
    }
    if not assets:
        return summary

    total_completeness = 0.0
    total_quality = 0.0
    worst_asset = None
    last_update = ''
    for asset in assets:
        status = asset.get('status') or 'critical'
        if status in summary:
            summary[status] += 1
        total_completeness += _safe_float(asset.get('completeness'))
        total_quality += _safe_float(asset.get('quality_score'))
        if asset.get('last_update') and str(asset.get('last_update')) > last_update:
            last_update = str(asset.get('last_update'))
        if worst_asset is None or _safe_float(asset.get('completeness')) < _safe_float(worst_asset.get('completeness')):
            worst_asset = asset

    summary['avg_completeness'] = round(total_completeness / len(assets), 4)
    summary['avg_quality_score'] = round(total_quality / len(assets), 2)
    summary['last_update'] = last_update
    summary['worst_asset'] = worst_asset
    return summary


def _summarize_strategies(strategies):
    summary = {
        'total': len(strategies),
        'with_samples': 0,
        'avg_return_10d': 0.0,
        'avg_win_rate_10d': 0.0,
        'trend_up': 0,
        'trend_down': 0,
        'trend_flat': 0,
        'best_strategy': None,
        'worst_strategy': None,
    }
    sampled = [item for item in strategies if _safe_int(item.get('sample_count')) > 0]
    summary['with_samples'] = len(sampled)
    if not sampled:
        return summary

    total_return = 0.0
    total_win_rate = 0.0
    for item in sampled:
        total_return += _safe_float(item.get('avg_return_10d'))
        total_win_rate += _safe_float(item.get('win_rate_10d'))
        trend = item.get('trend') or 'flat'
        if trend == 'up':
            summary['trend_up'] += 1
        elif trend == 'down':
            summary['trend_down'] += 1
        else:
            summary['trend_flat'] += 1

    summary['avg_return_10d'] = round(total_return / len(sampled), 2)
    summary['avg_win_rate_10d'] = round(total_win_rate / len(sampled), 2)
    summary['best_strategy'] = max(sampled, key=lambda item: _safe_float(item.get('avg_return_10d')))
    summary['worst_strategy'] = min(sampled, key=lambda item: _safe_float(item.get('avg_return_10d')))
    return summary


def get_data_assets(query_date=None):
    """获取数据资产状态及摘要"""
    date_value = _normalize_date(query_date)
    try:
        from instock.lib import data_asset_manager
        statuses = data_asset_manager.get_all_assets_status(date_value)
        assets = [_asset_to_dict(status) for status in statuses]
    except Exception as exc:
        logging.error(f"console_service.get_data_assets处理异常：{exc}")
        assets = []
    return {
        'date': date_value.strftime('%Y-%m-%d'),
        'summary': _summarize_assets(assets),
        'assets': assets,
    }


def get_strategy_performance(days=7):
    """获取策略表现及摘要"""
    try:
        days = max(1, min(120, int(days or 7)))
    except Exception:
        days = 7
    try:
        from instock.lib import strategy_analytics
        strategies = [_strategy_to_dict(perf) for perf in strategy_analytics.get_all_strategies_performance(days)]
    except Exception as exc:
        logging.error(f"console_service.get_strategy_performance处理异常：{exc}")
        strategies = []
    return {
        'days': days,
        'summary': _summarize_strategies(strategies),
        'strategies': strategies,
    }


def get_data_quality_summary(query_date=None):
    """获取数据质量日志摘要"""
    date_value = _normalize_date(query_date)
    result = {
        'date': date_value.strftime('%Y-%m-%d'),
        'status': 'no_data',
        'total_checks': 0,
        'passed_checks': 0,
        'failed_checks': 0,
        'error_count': 0,
        'warning_count': 0,
        'issue_count': 0,
        'latest_date': '',
    }
    if not _table_exists('data_quality_log'):
        result['status'] = 'no_table'
        return result

    latest_rows = _query("SELECT MAX(`run_date`) AS `latest_date` FROM `data_quality_log`")
    if latest_rows and latest_rows[0].get('latest_date'):
        result['latest_date'] = _format_date(latest_rows[0].get('latest_date'))

    rows = _query(
        """
        SELECT COUNT(*) AS `total_checks`,
               SUM(CASE WHEN `passed` = 1 THEN 1 ELSE 0 END) AS `passed_checks`,
               SUM(CASE WHEN `passed` = 0 THEN 1 ELSE 0 END) AS `failed_checks`,
               SUM(CASE WHEN `passed` = 0 AND `level` = 'error' THEN 1 ELSE 0 END) AS `error_count`,
               SUM(CASE WHEN `passed` = 0 AND `level` = 'warning' THEN 1 ELSE 0 END) AS `warning_count`,
               SUM(CASE WHEN `passed` = 0 THEN IFNULL(`issue_count`, 0) ELSE 0 END) AS `issue_count`
        FROM `data_quality_log`
        WHERE `run_date` = %s
        """,
        (date_value,),
    )
    if not rows:
        return result

    row = rows[0]
    result['total_checks'] = _safe_int(row.get('total_checks'))
    result['passed_checks'] = _safe_int(row.get('passed_checks'))
    result['failed_checks'] = _safe_int(row.get('failed_checks'))
    result['error_count'] = _safe_int(row.get('error_count'))
    result['warning_count'] = _safe_int(row.get('warning_count'))
    result['issue_count'] = _safe_int(row.get('issue_count'))
    if result['total_checks'] <= 0:
        result['status'] = 'no_data'
    elif result['error_count'] > 0:
        result['status'] = 'critical'
    elif result['warning_count'] > 0 or result['failed_checks'] > 0:
        result['status'] = 'warning'
    else:
        result['status'] = 'healthy'
    return result


def get_recent_reports(limit=20):
    """获取最近每日复盘报告列表"""
    try:
        limit = max(1, min(100, int(limit or 20)))
    except Exception:
        limit = 20
    if not _table_exists('daily_market_report'):
        return {'total': 0, 'reports': [], 'latest': None}

    rows = _query(
        """
        SELECT `date`, `title`, `summary`, `report_path`, `created_at`
        FROM `daily_market_report`
        ORDER BY `date` DESC
        LIMIT %s
        """,
        (limit,),
    )
    reports = []
    for row in rows:
        report_date = _format_date(row.get('date'))[:10]
        reports.append({
            'date': report_date,
            'title': row.get('title') or '每日复盘报告',
            'summary': row.get('summary') or '',
            'report_path': row.get('report_path') or '',
            'created_at': _format_date(row.get('created_at')),
            'url': f'/instock/report/daily?date={report_date}' if report_date else '/instock/report/daily',
        })
    return {
        'total': len(reports),
        'latest': reports[0] if reports else None,
        'reports': reports,
    }


def get_task_duration_stats(task_key: Optional[str] = None):
    """获取任务最近成功运行耗时统计"""
    if not _table_exists('system_task_run'):
        return {} if task_key is None else {'task_key': task_key, 'sample_count': 0}

    params = []
    where = "WHERE `status` = %s AND IFNULL(`duration_seconds`, 0) > 0"
    params.append(task_runner.STATUS_SUCCESS)
    if task_key:
        where += " AND `task_key` = %s"
        params.append(task_key)

    rows = _query(
        f"""
        SELECT `task_key`, COUNT(*) AS `sample_count`,
               AVG(`duration_seconds`) AS `avg_seconds`,
               MIN(`duration_seconds`) AS `min_seconds`,
               MAX(`duration_seconds`) AS `max_seconds`
        FROM `system_task_run`
        {where}
        GROUP BY `task_key`
        """,
        tuple(params),
    )
    stats = {}
    for row in rows:
        key = row.get('task_key')
        stats[key] = {
            'task_key': key,
            'sample_count': _safe_int(row.get('sample_count')),
            'avg_seconds': round(_safe_float(row.get('avg_seconds')), 2),
            'min_seconds': round(_safe_float(row.get('min_seconds')), 2),
            'max_seconds': round(_safe_float(row.get('max_seconds')), 2),
        }
    if task_key:
        return stats.get(task_key, {'task_key': task_key, 'sample_count': 0})
    return stats


def get_pipeline_map():
    """获取任务管线阶段和任务定义"""
    duration_stats = get_task_duration_stats()
    try:
        runtime_tasks = {task.get('key'): task for task in task_runner.task_payloads()}
    except Exception as exc:
        logging.error(f"console_service.get_pipeline_map获取任务运行态异常：{exc}")
        runtime_tasks = {}
    stages = []
    for stage_key in registry.STAGE_ORDER:
        stage_tasks = []
        for task in registry.visible_tasks():
            if task.category != stage_key:
                continue
            item = task.to_dict()
            item.update(runtime_tasks.get(task.key, {}))
            item['duration_stats'] = duration_stats.get(task.key, {'task_key': task.key, 'sample_count': 0})
            stage_tasks.append(item)
        stages.append({
            'key': stage_key,
            'label': registry.STAGE_LABELS.get(stage_key, stage_key),
            'description': registry.STAGE_DESCRIPTIONS.get(stage_key, ''),
            'task_count': len(stage_tasks),
            'tasks': stage_tasks,
        })

    edges = []
    for index in range(len(registry.STAGE_ORDER) - 1):
        edges.append({'from': registry.STAGE_ORDER[index], 'to': registry.STAGE_ORDER[index + 1]})

    return {
        'stages': stages,
        'edges': edges,
        'summary': {
            'stage_count': len(stages),
            'task_count': sum(stage['task_count'] for stage in stages),
            'manual_count': sum(1 for task in registry.visible_tasks() if task.allow_manual_start),
            'stoppable_count': sum(1 for task in registry.visible_tasks() if task.allow_stop),
        },
    }


def get_system_health(snapshot=None):
    """获取系统健康摘要"""
    db_ok = bool(_query('SELECT 1 AS `ok`'))
    if snapshot is None:
        try:
            snapshot = task_runner.overview()
        except Exception as exc:
            logging.error(f"console_service.get_system_health获取任务摘要异常：{exc}")
            snapshot = {}

    disk = {'total_gb': 0.0, 'used_gb': 0.0, 'free_gb': 0.0, 'used_percent': 0.0}
    try:
        usage = shutil.disk_usage(config.project_root())
        disk = {
            'total_gb': round(usage.total / 1024 / 1024 / 1024, 2),
            'used_gb': round(usage.used / 1024 / 1024 / 1024, 2),
            'free_gb': round(usage.free / 1024 / 1024 / 1024, 2),
            'used_percent': round((usage.used / usage.total) * 100, 2) if usage.total else 0.0,
        }
    except Exception as exc:
        logging.error(f"console_service.get_system_health磁盘统计异常：{exc}")

    summary = snapshot.get('summary') or {}
    scheduler_enabled = bool(snapshot.get('scheduler_enabled'))
    scheduler_alive = bool(snapshot.get('scheduler_alive'))
    health_status = 'healthy'
    if not db_ok or not scheduler_enabled or not scheduler_alive:
        health_status = 'warning'
    if _safe_int(summary.get('failed')) > 0:
        health_status = 'critical'

    return {
        'status': health_status,
        'db_ok': db_ok,
        'disk': disk,
        'today': snapshot.get('today') or datetime.date.today().strftime('%Y-%m-%d'),
        'summary': summary,
        'open_notices': _safe_int(snapshot.get('open_notices')),
        'scheduler_enabled': scheduler_enabled,
        'scheduler_alive': scheduler_alive,
        'scheduler_heartbeat_at': snapshot.get('scheduler_heartbeat_at') or '',
        'scheduler_heartbeat_age_seconds': snapshot.get('scheduler_heartbeat_age_seconds'),
        'scheduler_heartbeat_stale_seconds': snapshot.get('scheduler_heartbeat_stale_seconds'),
        'scheduler_updated_at': snapshot.get('scheduler_updated_at') or '',
        'running_tasks': _safe_int(summary.get('running')),
        'failed_tasks_today': _safe_int(summary.get('failed')),
    }


def get_console_dashboard(query_date=None):
    """获取控制台首页聚合数据"""
    date_value = _normalize_date(query_date)
    try:
        task_runner.ensure_task_states()
        snapshot = task_runner.console_snapshot(run_limit=12, job_limit=12, notice_limit=8)
    except Exception as exc:
        logging.error(f"console_service.get_console_dashboard任务快照异常：{exc}")
        snapshot = {
            'today': date_value.strftime('%Y-%m-%d'),
            'summary': {'running': 0, 'success': 0, 'failed': 0, 'stopped': 0, 'skipped': 0, 'total': 0},
            'tasks': [],
            'recent': [],
            'job_recent': [],
            'notices': [],
            'open_notices': 0,
        }

    return {
        'date': date_value.strftime('%Y-%m-%d'),
        'health': get_system_health(snapshot),
        'tasks': {
            'today': snapshot.get('today'),
            'summary': snapshot.get('summary') or {},
            'open_notices': snapshot.get('open_notices') or 0,
            'recent': snapshot.get('recent') or [],
            'job_recent': snapshot.get('job_recent') or [],
            'notices': snapshot.get('notices') or [],
        },
        'data_assets': get_data_assets(date_value),
        'strategies': get_strategy_performance(7),
        'quality': get_data_quality_summary(date_value),
        'reports': get_recent_reports(5),
    }

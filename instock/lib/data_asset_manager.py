#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Optional
import logging
import time

from instock.lib import database as mdb


_CACHE_TTL_SECONDS = 60
_STATUS_CACHE = {}
_MAX_STATUS_WORKERS = 4


@dataclass
class DataAsset:
    """数据资产定义"""
    key: str
    name: str
    source: str
    table: str
    update_frequency: str
    expected_count: int
    quality_checks: list
    description: str = ''
    depends_on: list = None
    task_key: str = ''
    page_table: str = ''
    expected_ready_time: str = ''

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
        if not self.page_table:
            self.page_table = self.table


@dataclass
class DataAssetStatus:
    """数据资产状态"""
    key: str
    name: str
    source: str
    expected: int
    actual: int
    completeness: float
    quality_score: float
    status: str
    issues: list
    last_update: Optional[str] = None
    table: str = ''
    task_key: str = ''
    depends_on: list = None
    page_url: str = ''
    expected_ready_time: str = ''
    gate_status: str = 'pass'
    gate_message: str = ''

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


def _cache_get(key):
    cached = _STATUS_CACHE.get(key)
    if cached is None:
        return None
    value, timestamp = cached
    if time.time() - timestamp <= _CACHE_TTL_SECONDS:
        return value
    _STATUS_CACHE.pop(key, None)
    return None


def _cache_set(key, value):
    if len(_STATUS_CACHE) > 256:
        _STATUS_CACHE.clear()
    _STATUS_CACHE[key] = (value, time.time())


def _row_value(row, index, key=None, default=None):
    if row is None:
        return default
    try:
        if key is not None and hasattr(row, 'get'):
            return row.get(key, default)
    except Exception:
        pass
    try:
        return row[index]
    except Exception:
        return default


def _fetch_one(sql, params=()):
    rows = mdb.executeSqlFetch(sql, params)
    if rows:
        return rows[0]
    return None


def _normalize_query_date(query_date):
    if query_date is None:
        return date.today()
    return query_date


def _get_asset_counts(asset: DataAsset, query_date: date) -> tuple[int, Optional[str]]:
    if not asset.table:
        return 0, None

    try:
        sql = f"""
        SELECT COUNT(*) AS cnt,
               (SELECT MAX(`date`) FROM `{asset.table}`) AS last_date
        FROM `{asset.table}` WHERE `date` = %s
        """
        row = _fetch_one(sql, (query_date,))
        actual = int(_row_value(row, 0, 'cnt', 0) or 0)
        last_date = _row_value(row, 1, 'last_date')
        return actual, str(last_date) if last_date else None
    except Exception as e:
        logging.error(f"data_asset_manager._get_asset_counts处理异常：{asset.key} {e}")
    return 0, None


def get_asset_record_count(asset: DataAsset, query_date: date) -> int:
    """查询数据资产的记录数"""
    actual, _ = _get_asset_counts(asset, query_date)
    return actual


def run_quality_checks(asset: DataAsset, query_date: date) -> tuple[float, list]:
    """运行质量检查规则，返回(质量分, 问题列表)"""
    if not asset.table or not asset.quality_checks:
        return 100.0, []

    issues = []
    total_checks = len(asset.quality_checks)
    passed_count = 0

    try:
        fields = []
        for i, check in enumerate(asset.quality_checks):
            fields.append(f"SUM(CASE WHEN NOT ({check}) THEN 1 ELSE 0 END) AS fail_{i}")
        sql = f"SELECT {', '.join(fields)} FROM `{asset.table}` WHERE `date` = %s"
        row = _fetch_one(sql, (query_date,))
        for i, check in enumerate(asset.quality_checks):
            failed_count = int(_row_value(row, i, f'fail_{i}', 0) or 0)
            if failed_count > 0:
                issues.append(f"{check}: {failed_count}条记录不符合")
            else:
                passed_count += 1
    except Exception as e:
        logging.error(f"data_asset_manager.run_quality_checks处理异常：{asset.key} {e}")
        issues.append(f"质量检查失败: {str(e)[:100]}")

    quality_score = (passed_count / total_checks) * 100
    return quality_score, issues


def calculate_completeness(asset: DataAsset, actual_count: int) -> float:
    """计算数据完整度 0-1"""
    if asset.expected_count == 0:
        return 1.0
    return min(1.0, actual_count / asset.expected_count)


def _asset_page_url(asset: DataAsset) -> str:
    if not asset.page_table:
        return ''
    return f'/instock/data?table_name={asset.page_table}'


def _quality_log_summary(asset: DataAsset, query_date: date):
    try:
        from instock.core import data_quality
        return data_quality.summarize_quality_log(asset.table, query_date)
    except Exception as exc:
        logging.error(f"data_asset_manager._quality_log_summary处理异常：{asset.key} {exc}")
    return {
        'total_checks': 0,
        'failed_checks': 0,
        'error_count': 0,
        'warning_count': 0,
        'issue_count': 0,
        'latest_message': '',
    }


def _gate_status(asset: DataAsset, completeness: float, quality_score: float, quality_summary: dict, issues: list) -> tuple[str, str]:
    error_count = int(quality_summary.get('error_count') or 0)
    warning_count = int(quality_summary.get('warning_count') or 0)
    issue_count = int(quality_summary.get('issue_count') or 0)
    latest_message = quality_summary.get('latest_message') or ''
    completeness_block = asset.expected_count > 0 and completeness < 0.80
    completeness_warning = asset.expected_count > 0 and completeness < 0.95
    if completeness_block or error_count > 0 or quality_score < 70:
        message = latest_message or f'完整度 {round(completeness * 100, 1)}%，错误 {error_count}，质量分 {round(quality_score, 1)}'
        return 'block', message
    if completeness_warning or warning_count > 0 or issues:
        message = latest_message or f'完整度 {round(completeness * 100, 1)}%，警告 {warning_count}，问题 {issue_count}'
        return 'warning', message
    return 'pass', '资产质量门禁通过'


def get_asset_status(asset: DataAsset, query_date: date) -> DataAssetStatus:
    """获取单个数据资产状态"""
    query_date = _normalize_query_date(query_date)
    cache_key = ('asset', asset.key, str(query_date))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    actual_count, last_update = _get_asset_counts(asset, query_date)
    completeness = calculate_completeness(asset, actual_count)
    quality_score, issues = run_quality_checks(asset, query_date)
    quality_summary = _quality_log_summary(asset, query_date)
    gate_status, gate_message = _gate_status(asset, completeness, quality_score, quality_summary, issues)

    # 判断状态
    if gate_status == 'block':
        status = 'critical'
    elif gate_status == 'warning':
        status = 'warning'
    elif completeness >= 0.95 and quality_score >= 90:
        status = 'healthy'
    else:
        status = 'warning'

    result = DataAssetStatus(
        key=asset.key,
        name=asset.name,
        source=asset.source,
        expected=asset.expected_count,
        actual=actual_count,
        completeness=completeness,
        quality_score=quality_score,
        status=status,
        issues=issues,
        last_update=last_update,
        table=asset.table,
        task_key=asset.task_key,
        depends_on=list(asset.depends_on or []),
        page_url=_asset_page_url(asset),
        expected_ready_time=asset.expected_ready_time,
        gate_status=gate_status,
        gate_message=gate_message,
    )
    _cache_set(cache_key, result)
    return result


def get_all_assets_status(query_date: date = None) -> list[DataAssetStatus]:
    """获取所有数据资产状态"""
    from instock.lib import data_asset_registry as registry

    query_date = _normalize_query_date(query_date)
    cache_key = ('all', str(query_date))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    assets = registry.get_all_assets()
    status_map = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_STATUS_WORKERS, max(1, len(assets)))) as executor:
        futures = {executor.submit(get_asset_status, asset, query_date): asset for asset in assets}
        for future in as_completed(futures):
            asset = futures[future]
            try:
                status_map[asset.key] = future.result()
            except Exception as e:
                logging.error(f"data_asset_manager.get_all_assets_status处理异常：{asset.key} {e}")

    statuses = [status_map[asset.key] for asset in assets if asset.key in status_map]
    _cache_set(cache_key, statuses)
    return statuses

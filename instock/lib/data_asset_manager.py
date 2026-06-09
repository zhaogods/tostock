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

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


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

    # 判断状态
    if completeness >= 0.95 and quality_score >= 90:
        status = 'healthy'
    elif completeness >= 0.80 or quality_score >= 70:
        status = 'warning'
    else:
        status = 'critical'

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

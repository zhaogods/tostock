#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import logging

from instock.lib import database as mdb


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


def get_asset_record_count(asset: DataAsset, query_date: date) -> int:
    """查询数据资产的记录数"""
    if not asset.table:
        return 0

    try:
        sql = f"SELECT COUNT(*) AS cnt FROM `{asset.table}` WHERE `date` = %s"
        rows = mdb.executeSql(sql, (query_date,))
        if rows:
            return int(rows[0].get('cnt', 0))
    except Exception as e:
        logging.error(f"data_asset_manager.get_asset_record_count处理异常：{asset.key} {e}")

    return 0


def run_quality_checks(asset: DataAsset, query_date: date) -> tuple[float, list]:
    """运行质量检查规则，返回(质量分, 问题列表)"""
    if not asset.table or not asset.quality_checks:
        return 100.0, []

    issues = []
    passed_count = 0

    try:
        for check in asset.quality_checks:
            sql = f"SELECT COUNT(*) AS cnt FROM `{asset.table}` WHERE `date` = %s AND NOT ({check})"
            rows = mdb.executeSql(sql, (query_date,))
            if rows:
                failed_count = int(rows[0].get('cnt', 0))
                if failed_count > 0:
                    issues.append(f"{check}: {failed_count}条记录不符合")
                else:
                    passed_count += 1
    except Exception as e:
        logging.error(f"data_asset_manager.run_quality_checks处理异常：{asset.key} {e}")
        issues.append(f"质量检查失败: {str(e)[:100]}")

    total_checks = len(asset.quality_checks)
    if total_checks == 0:
        return 100.0, issues

    quality_score = (passed_count / total_checks) * 100
    return quality_score, issues


def calculate_completeness(asset: DataAsset, actual_count: int) -> float:
    """计算数据完整度 0-1"""
    if asset.expected_count == 0:
        return 1.0
    return min(1.0, actual_count / asset.expected_count)


def get_asset_status(asset: DataAsset, query_date: date) -> DataAssetStatus:
    """获取单个数据资产状态"""
    actual_count = get_asset_record_count(asset, query_date)
    completeness = calculate_completeness(asset, actual_count)
    quality_score, issues = run_quality_checks(asset, query_date)

    # 判断状态
    if completeness >= 0.95 and quality_score >= 90:
        status = 'healthy'
    elif completeness >= 0.80 or quality_score >= 70:
        status = 'warning'
    else:
        status = 'critical'

    # 查询最后更新时间
    last_update = None
    try:
        if asset.table:
            sql = f"SELECT MAX(`date`) AS last_date FROM `{asset.table}`"
            rows = mdb.executeSql(sql)
            if rows and rows[0].get('last_date'):
                last_update = str(rows[0]['last_date'])
    except Exception as e:
        logging.error(f"data_asset_manager.get_asset_status查询更新时间异常：{e}")

    return DataAssetStatus(
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


def get_all_assets_status(query_date: date = None) -> list[DataAssetStatus]:
    """获取所有数据资产状态"""
    from instock.lib import data_asset_registry as registry

    if query_date is None:
        query_date = date.today()

    statuses = []
    for asset in registry.get_all_assets():
        try:
            status = get_asset_status(asset, query_date)
            statuses.append(status)
        except Exception as e:
            logging.error(f"data_asset_manager.get_all_assets_status处理异常：{asset.key} {e}")

    return statuses

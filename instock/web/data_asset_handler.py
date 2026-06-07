#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from abc import ABC
from datetime import date, datetime

from tornado import gen

import instock.web.base as webBase
from instock.lib import data_asset_manager


def _json_default(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)


class _JsonMixin:
    def write_json(self, data, status=200):
        self.set_status(status)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        self.write(json.dumps(data, ensure_ascii=False, default=_json_default))

    def write_error_json(self, message, status=400, **extra):
        payload = {'ok': False, 'message': message}
        payload.update(extra)
        self.write_json(payload, status)


class DataAssetsStatusApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    """获取所有数据资产状态"""

    def get(self):
        try:
            date_str = self.get_argument('date', default='', strip=True)
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

            statuses = data_asset_manager.get_all_assets_status(query_date)

            # 转换为字典
            assets_data = []
            for status in statuses:
                assets_data.append({
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
                })

            self.write_json({
                'ok': True,
                'date': query_date.strftime('%Y-%m-%d'),
                'assets': assets_data,
            })

        except ValueError as e:
            self.write_error_json('日期格式错误，请使用 YYYY-MM-DD', 400)
        except Exception as e:
            logging.error(f"DataAssetsStatusApiHandler处理异常：{e}")
            self.write_error_json('获取数据资产状态失败', 500)


class DataAssetDetailApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    """获取单个数据资产详情"""

    def get(self, asset_key):
        try:
            from instock.lib import data_asset_registry as registry

            date_str = self.get_argument('date', default='', strip=True)
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

            asset = registry.get_asset(asset_key)
            if not asset:
                self.write_error_json('数据资产不存在', 404)
                return

            status = data_asset_manager.get_asset_status(asset, query_date)

            self.write_json({
                'ok': True,
                'date': query_date.strftime('%Y-%m-%d'),
                'asset': {
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
                    'description': asset.description,
                    'update_frequency': asset.update_frequency,
                    'depends_on': asset.depends_on,
                },
            })

        except ValueError as e:
            self.write_error_json('日期格式错误，请使用 YYYY-MM-DD', 400)
        except Exception as e:
            logging.error(f"DataAssetDetailApiHandler处理异常：{e}")
            self.write_error_json('获取数据资产详情失败', 500)

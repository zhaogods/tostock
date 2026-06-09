#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略表现API处理器
"""

import logging
from abc import ABC

import instock.web.base as webBase
import instock.lib.strategy_analytics as strategy_analytics

__author__ = 'Kiro'
__date__ = '2026/06/07'


class _JsonMixin:
    """JSON响应混入类"""
    def write_json(self, data):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(data)


class StrategiesPerformanceApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    """策略表现API"""

    def get(self):
        """获取所有策略表现"""
        days_str = self.get_argument('days', default='7', strip=True)
        try:
            days = int(days_str)
        except ValueError:
            days = 7

        try:
            performances = strategy_analytics.get_all_strategies_performance(days)

            strategies_data = []
            for perf in performances:
                strategies_data.append({
                    'key': perf.key,
                    'name': perf.name,
                    'sample_count': perf.sample_count,
                    'avg_return_10d': round(perf.avg_return_10d, 2),
                    'win_rate_10d': round(perf.win_rate_10d, 2),
                    'trend': perf.trend,
                    'updated_at': perf.updated_at,
                })

            self.write_json({
                'ok': True,
                'days': days,
                'strategies': strategies_data
            })
        except Exception as e:
            logging.error(f"StrategiesPerformanceApiHandler.get处理异常：{e}")
            self.write_json({'ok': False, 'error': str(e)})

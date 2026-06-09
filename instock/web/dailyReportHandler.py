#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
from abc import ABC
from pathlib import Path

from tornado import gen

import instock.core.singleton_stock_web_module_data as sswmd
import instock.core.tablestructure as tbs
import instock.web.base as webBase
from instock.lib import config
from instock.core.report import daily_recap


def _get_report_by_date(handler, report_date):
    return handler.db.get(
        "SELECT `date`,`title`,`summary`,`report_path`,`created_at` FROM `daily_market_report` WHERE `date` = %s",
        report_date,
    )


def _get_latest_report(handler):
    return handler.db.get(
        "SELECT `date`,`title`,`summary`,`report_path`,`created_at` FROM `daily_market_report` ORDER BY `date` DESC LIMIT 1"
    )


def _format_report_date(value):
    if hasattr(value, 'strftime'):
        return value.strftime("%Y-%m-%d")
    return str(value)


class DailyReportHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        date_arg = self.get_argument("date", default=None, strip=False)
        report = None
        requested_date = date_arg or datetime.date.today().strftime("%Y-%m-%d")
        fallback_used = False
        error_message = ""
        try:
            report = _get_report_by_date(self, requested_date)
            if report is None:
                report = _get_latest_report(self)
                fallback_used = report is not None
        except Exception as e:
            logging.error(f"dailyReportHandler.DailyReportHandler查询异常：{e}")

        report_content = "暂无复盘报告"
        selected_date = requested_date
        title = "每日复盘报告"
        summary = ""
        created_at = None

        if report is not None:
            actual_date = _format_report_date(report.date)
            selected_date = actual_date
            title = report.title
            summary = report.summary
            created_at = report.created_at
            if fallback_used:
                if date_arg:
                    error_message = f"指定日期 {requested_date} 无报告，已展示最新可用报告（{actual_date}）。"
                else:
                    error_message = f"今日报告未生成，已展示最新可用报告（{actual_date}）。"
            try:
                daily_dir = (config.project_root() / 'reports' / 'daily').resolve()
                report_path = Path(report.report_path).resolve()
                if daily_dir == report_path.parent and report_path.is_file():
                    report_content = report_path.read_text(encoding='utf-8')
                else:
                    _, generated_summary, report_content = daily_recap.build_report_content(actual_date)
                    if not summary:
                        summary = generated_summary
                    error_message = "报告文件不存在或路径不在 reports/daily 目录下，已根据当前数据库数据重新生成页面内容。"
            except Exception as e:
                logging.error(f"dailyReportHandler.DailyReportHandler读取报告异常：{e}")
                error_message = "读取报告文件失败。"

        self.render(
            "daily_report.html",
            web_module_data=sswmd.stock_web_module_data().get_data(tbs.TABLE_DAILY_MARKET_REPORT['name']),
            selected_date=selected_date,
            title=title,
            summary=summary,
            created_at=created_at,
            report_content=report_content,
            error_message=error_message,
            leftMenu=webBase.GetLeftMenu(self.request.uri),
        )

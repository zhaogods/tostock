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


class DailyReportHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        date_arg = self.get_argument("date", default=None, strip=False)
        report = None
        try:
            if date_arg:
                report = self.db.get(
                    "SELECT `date`,`title`,`summary`,`report_path`,`created_at` FROM `daily_market_report` WHERE `date` = %s",
                    date_arg,
                )
            else:
                today = datetime.date.today().strftime("%Y-%m-%d")
                report = self.db.get(
                    "SELECT `date`,`title`,`summary`,`report_path`,`created_at` FROM `daily_market_report` WHERE `date` = %s",
                    today,
                )
                if report is None:
                    report = self.db.get(
                        "SELECT `date`,`title`,`summary`,`report_path`,`created_at` FROM `daily_market_report` ORDER BY `date` DESC LIMIT 1"
                    )
        except Exception as e:
            logging.error(f"dailyReportHandler.DailyReportHandler查询异常：{e}")

        report_content = "暂无复盘报告"
        selected_date = date_arg or datetime.date.today().strftime("%Y-%m-%d")
        title = "每日复盘报告"
        summary = ""
        created_at = None
        error_message = ""

        if report is not None:
            selected_date = report.date.strftime("%Y-%m-%d") if hasattr(report.date, 'strftime') else str(report.date)
            title = report.title
            summary = report.summary
            created_at = report.created_at
            try:
                daily_dir = (config.project_root() / 'reports' / 'daily').resolve()
                report_path = Path(report.report_path).resolve()
                if daily_dir == report_path.parent and report_path.is_file():
                    report_content = report_path.read_text(encoding='utf-8')
                else:
                    error_message = "报告文件不存在或路径不在 reports/daily 目录下。"
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

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
from instock.core.report import selection_report


__author__ = 'Kiro'
__date__ = '2026/06/10'


def _get_report_by_date(handler, report_date):
    return handler.db.get(
        "SELECT `date`,`title`,`summary`,`candidate_count`,`top_codes`,`report_path`,`llm_enabled`,`model`,`created_at` "
        "FROM `daily_selection_report` WHERE `date` = %s",
        report_date,
    )


def _get_latest_report(handler):
    return handler.db.get(
        "SELECT `date`,`title`,`summary`,`candidate_count`,`top_codes`,`report_path`,`llm_enabled`,`model`,`created_at` "
        "FROM `daily_selection_report` ORDER BY `date` DESC LIMIT 1"
    )


def _format_report_date(value):
    if hasattr(value, 'strftime'):
        return value.strftime("%Y-%m-%d")
    return str(value)


class SelectionReportHandler(webBase.BaseHandler, ABC):
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
            logging.error(f"selectionReportHandler.SelectionReportHandler查询异常：{e}")

        report_content = "暂无选股报告"
        selected_date = requested_date
        title = "每日选股报告"
        summary = ""
        created_at = None
        candidate_count = 0
        top_codes = ""
        llm_enabled = False
        model = ""

        if report is not None:
            actual_date = _format_report_date(report.date)
            selected_date = actual_date
            title = report.title
            summary = report.summary
            created_at = report.created_at
            candidate_count = report.candidate_count
            top_codes = report.top_codes
            llm_enabled = bool(report.llm_enabled)
            model = report.model
            if fallback_used:
                if date_arg:
                    error_message = f"指定日期 {requested_date} 无选股报告，已展示最新可用报告（{actual_date}）。"
                else:
                    error_message = f"今日选股报告未生成，已展示最新可用报告（{actual_date}）。"
            try:
                selection_dir = (config.project_root() / 'reports' / 'selection').resolve()
                report_path = Path(report.report_path).resolve()
                if selection_dir == report_path.parent and report_path.is_file():
                    report_content = report_path.read_text(encoding='utf-8')
                else:
                    generated_title, generated_summary, report_content, _, _ = selection_report.build_report_content(actual_date)
                    if not title:
                        title = generated_title
                    if not summary:
                        summary = generated_summary
                    error_message = "报告文件不存在或路径不在 reports/selection 目录下，已根据当前数据库数据重新生成页面内容。"
            except Exception as e:
                logging.error(f"selectionReportHandler.SelectionReportHandler读取报告异常：{e}")
                error_message = "读取选股报告文件失败。"

        self.render(
            "selection_report.html",
            web_module_data=sswmd.stock_web_module_data().get_data(tbs.TABLE_DAILY_SELECTION_REPORT['name']),
            selected_date=selected_date,
            title=title,
            summary=summary,
            created_at=created_at,
            candidate_count=candidate_count,
            top_codes=top_codes,
            llm_enabled=llm_enabled,
            model=model,
            report_content=report_content,
            error_message=error_message,
            leftMenu=webBase.GetLeftMenu(self.request.uri),
        )

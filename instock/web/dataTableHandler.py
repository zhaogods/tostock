#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import json
from abc import ABC
from tornado import gen
import logging
import datetime
import instock.lib.trade_time as trd
import instock.core.singleton_stock_web_module_data as sswmd
import instock.web.base as webBase

__author__ = 'myh '
__date__ = '2023/3/10 '


class MyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, bytes):
            return "是" if ord(obj) == 1 else "否"
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)


def _get_table_name_arg(handler):
    table_name = handler.get_argument("table_name", default=None, strip=False)
    if table_name is None:
        table_name = handler.get_argument("name", default=None, strip=False)
    return table_name


def _get_date_column(web_module_data):
    if 'date' in web_module_data.columns:
        return 'date'
    if 'run_date' in web_module_data.columns:
        return 'run_date'
    return None


def _format_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def _get_fallback_date(web_module_data):
    run_date, run_date_nph = trd.get_trade_date_last()
    if web_module_data.type == "运行监控":
        return datetime.date.today().strftime("%Y-%m-%d")
    if web_module_data.is_realtime:
        return run_date_nph.strftime("%Y-%m-%d")
    return run_date.strftime("%Y-%m-%d")


def _get_latest_data_date(handler, web_module_data):
    date_column = _get_date_column(web_module_data)
    if date_column is None:
        return None
    try:
        sql = f"SELECT MAX(`{date_column}`) AS `max_date` FROM `{web_module_data.table_name}`"
        row = handler.db.get(sql)
        if row is not None:
            return _format_date(row.get('max_date'))
    except Exception as e:
        logging.error(f"dataTableHandler获取{web_module_data.table_name}最新日期异常：{e}")
    return None


# 获得页面数据。
class GetStockHtmlHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        table_name = _get_table_name_arg(self)
        web_module_data = sswmd.stock_web_module_data().get_data(table_name)
        if getattr(web_module_data, 'is_virtual', False):
            self.redirect(web_module_data.url)
            return
        date_now_str = _get_latest_data_date(self, web_module_data)
        if date_now_str is None:
            date_now_str = _get_fallback_date(web_module_data)
        column_names_json = json.dumps(web_module_data.column_names, ensure_ascii=False)
        self.render("stock_web.html", web_module_data=web_module_data, date_now=date_now_str,
                    column_names_json=column_names_json,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 获得股票数据内容。
class GetStockDataHandler(webBase.BaseHandler, ABC):
    def get(self):
        table_name = _get_table_name_arg(self)
        date = self.get_argument("date", default=None, strip=False)
        web_module_data = sswmd.stock_web_module_data().get_data(table_name)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        if getattr(web_module_data, 'is_virtual', False):
            self.set_status(400)
            self.write(json.dumps({'error': f'{web_module_data.name} 是导航入口，不是数据表。'}, ensure_ascii=False))
            return

        if date is None:
            where = ""
            params = ()
        else:
            if 'date' in web_module_data.columns:
                where = " WHERE `date` = %s"
                params = (date,)
            elif 'run_date' in web_module_data.columns:
                where = " WHERE `run_date` = %s"
                params = (date,)
            else:
                where = ""
                params = ()

        order_by = ""
        if web_module_data.order_by is not None:
            order_by = f" ORDER BY {web_module_data.order_by}"

        order_columns = ""
        if web_module_data.order_columns is not None:
            order_columns = f",{web_module_data.order_columns}"

        sql = f" SELECT *{order_columns} FROM `{web_module_data.table_name}`{where}{order_by}"
        data = self.db.query(sql, *params)
        if web_module_data.type == "运行监控":
            data = [dict(row) for row in data]
            for row in data:
                for field, value in list(row.items()):
                    if isinstance(value, datetime.datetime):
                        row[field] = value.strftime('%Y-%m-%d %H:%M:%S')

        self.write(json.dumps(data, cls=MyEncoder))

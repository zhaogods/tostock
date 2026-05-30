#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import logging
import pandas as pd
import pymysql
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.core.tablestructure as tbs
import instock.lib.database as mdb

__author__ = 'myh '
__date__ = '2023/3/10 '


# 创建新数据库。
def create_new_database():
    _MYSQL_CONN_DBAPI = mdb.MYSQL_CONN_DBAPI.copy()
    _MYSQL_CONN_DBAPI['database'] = "mysql"
    _MYSQL_CONN_DBAPI.pop('charset', None)
    with pymysql.connect(**_MYSQL_CONN_DBAPI) as conn:
        with conn.cursor() as db:
            create_sql = f"CREATE DATABASE IF NOT EXISTS `{mdb.db_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            db.execute(create_sql)
        conn.commit()


def _iter_project_tables():
    tables = [
        (tbs.TABLE_CN_STOCK_ATTENTION, "`code`"),
        (tbs.TABLE_CN_STOCK_SELECTION, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_SPOT, "`date`,`code`"),
        (tbs.TABLE_CN_ETF_SPOT, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY, "`date`,`name`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT, "`date`,`name`"),
        (tbs.TABLE_CN_STOCK_BONUS, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_TOP, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_lHB, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_BLOCKTRADE, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_CHIP_RACE_OPEN, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_CHIP_RACE_END, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_LIMITUP_REASON, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_SPOT_BUY, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_INDICATORS, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_INDICATORS_BUY, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_INDICATORS_SELL, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_KLINE_PATTERN, "`date`,`code`"),
    ]
    tables.extend((table, "`date`,`code`") for table in tbs.TABLE_CN_STOCK_STRATEGIES)
    return tables


# 创建基础表。
def create_new_base_table():
    ensure_project_tables()


def ensure_project_tables():
    for table, primary_keys in _iter_project_tables():
        table_name = table['name']
        if mdb.checkTableIsExist(table_name):
            continue
        try:
            data = pd.DataFrame(columns=list(table['columns']))
            cols_type = tbs.get_field_types(table['columns'])
            mdb.insert_db_from_df(data, table_name, cols_type, False, primary_keys)
        except Exception as e:
            logging.error(f"init_job.ensure_project_tables处理异常：{table_name}表{e}")


def check_database():
    with pymysql.connect(**mdb.MYSQL_CONN_DBAPI) as conn:
        with conn.cursor() as db:
            db.execute(" select 1 ")


def main():
    # 检查，如果执行 select 1 失败，说明数据库不存在，然后创建一个新的数据库。
    try:
        check_database()
    except Exception as e:
        logging.error(f"执行信息：数据库不存在（{e}），将创建。")
        create_new_database()
        try:
            check_database()
            logging.info("数据库创建成功。")
        except Exception as e2:
            logging.error(f"数据库创建失败：{e2}")
            return
    ensure_project_tables()


# main函数入口
if __name__ == '__main__':
    main()

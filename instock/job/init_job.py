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
        (tbs.TABLE_JOB_RUN_LOG, "`run_date`,`job_name`,`start_time`"),
        (tbs.TABLE_DATA_QUALITY_LOG, "`run_date`,`table_name`,`check_name`,`created_at`"),
        (tbs.TABLE_SYSTEM_TASK_RUN, "`run_id`"),
        (tbs.TABLE_SYSTEM_TASK_STATE, "`task_key`"),
        (tbs.TABLE_SYSTEM_TASK_NOTICE, "`notice_id`"),
        (tbs.TABLE_CN_STOCK_STRATEGY_BACKTEST_RANK, "`date`,`strategy_table`"),
        (tbs.TABLE_DAILY_MARKET_REPORT, "`date`"),
        (tbs.TABLE_CN_STOCK_ATTENTION, "`code`"),
        (tbs.TABLE_CN_STOCK_SELECTION, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_SPOT, "`date`,`code`"),
        (tbs.TABLE_CN_ETF_SPOT, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW_INDUSTRY, "`date`,`name`"),
        (tbs.TABLE_CN_STOCK_FUND_FLOW_CONCEPT, "`date`,`name`"),
        (tbs.TABLE_CN_STOCK_BONUS, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_TOP, "`date`,`code`"),
        (tbs.TABLE_CN_STOCK_LHB, "`date`,`code`"),
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


def _column_exists(table_name, column_name):
    conn = mdb.get_connection()
    if conn is None:
        return False
    with conn:
        with conn.cursor() as db:
            db.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
                """,
                (table_name, column_name),
            )
            return int(db.fetchone()[0] or 0) == 1


def _safe_execute(sql, params=()):
    conn = mdb.get_connection()
    if conn is None:
        return False
    with conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                return True
            except Exception as e:
                logging.error(f"init_job._safe_execute处理异常：{sql}{e}")
    return False


def _ensure_column(table_name, column_name, column_sql):
    if not mdb.checkTableIsExist(table_name):
        return
    if _column_exists(table_name, column_name):
        return
    _safe_execute(f"ALTER TABLE `{table_name}` ADD COLUMN {column_sql}")


def _backfill_attention_names():
    table_name = tbs.TABLE_CN_STOCK_ATTENTION['name']
    if not (mdb.checkTableIsExist(table_name) and _column_exists(table_name, 'name')):
        return
    if mdb.checkTableIsExist(tbs.TABLE_CN_STOCK_SPOT['name']):
        _safe_execute(
            f"""
            UPDATE `{table_name}` a
            JOIN `{tbs.TABLE_CN_STOCK_SPOT['name']}` s ON s.`code` = a.`code`
            LEFT JOIN `{tbs.TABLE_CN_STOCK_SPOT['name']}` newer
                ON newer.`code` = s.`code` AND newer.`date` > s.`date`
            SET a.`name` = s.`name`
            WHERE (a.`name` IS NULL OR a.`name` = '')
              AND IFNULL(s.`name`, '') <> ''
              AND newer.`code` IS NULL
            """
        )
    if mdb.checkTableIsExist(tbs.TABLE_CN_ETF_SPOT['name']):
        _safe_execute(
            f"""
            UPDATE `{table_name}` a
            JOIN `{tbs.TABLE_CN_ETF_SPOT['name']}` s ON s.`code` = a.`code`
            LEFT JOIN `{tbs.TABLE_CN_ETF_SPOT['name']}` newer
                ON newer.`code` = s.`code` AND newer.`date` > s.`date`
            SET a.`name` = s.`name`
            WHERE (a.`name` IS NULL OR a.`name` = '')
              AND IFNULL(s.`name`, '') <> ''
              AND newer.`code` IS NULL
            """
        )


def _migrate_lhb_ranking_date():
    """将龙虎榜“上榜日”历史列从 ranking_times 迁移为 ranking_date。"""
    table_name = tbs.TABLE_CN_STOCK_LHB['name']
    if not mdb.checkTableIsExist(table_name):
        return
    has_old = _column_exists(table_name, 'ranking_times')
    has_new = _column_exists(table_name, 'ranking_date')
    if has_old and not has_new:
        _safe_execute(f"ALTER TABLE `{table_name}` CHANGE COLUMN `ranking_times` `ranking_date` DATE NULL")
    elif has_old and has_new:
        logging.warning(f"{table_name} 同时存在 ranking_times 与 ranking_date，跳过自动迁移以避免覆盖数据。")


def ensure_schema_extensions():
    """为已存在部署补充新增字段，保持 init_job 幂等。"""
    _ensure_column(
        tbs.TABLE_CN_STOCK_ATTENTION['name'],
        'name',
        "`name` VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `code`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_STATE['name'],
        'schedule_mode',
        "`schedule_mode` VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `next_fire_time`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_STATE['name'],
        'cron_expression',
        "`cron_expression` VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `schedule_mode`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_RUN['name'],
        'trade_date',
        "`trade_date` DATE NULL AFTER `run_date`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_RUN['name'],
        'pipeline_run_id',
        "`pipeline_run_id` VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `trade_date`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_RUN['name'],
        'parent_run_id',
        "`parent_run_id` VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `pipeline_run_id`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_RUN['name'],
        'attempt',
        "`attempt` SMALLINT NULL AFTER `parent_run_id`",
    )
    _ensure_column(
        tbs.TABLE_SYSTEM_TASK_RUN['name'],
        'skip_reason',
        "`skip_reason` VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `attempt`",
    )
    _migrate_lhb_ranking_date()
    _backfill_attention_names()


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
    ensure_schema_extensions()


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
    try:
        from instock.lib import task_runner
        task_runner.ensure_task_states()
    except Exception as e:
        logging.error(f"init_job.main同步任务状态异常：{e}")


# main函数入口
if __name__ == '__main__':
    main()

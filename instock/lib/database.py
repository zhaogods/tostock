#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect

from instock.lib import config

__author__ = 'myh '
__date__ = '2023/3/10 '

_db_config = config.get_db_config()
db_host = _db_config.get('host', 'localhost')
db_user = _db_config.get('user', 'root')
db_password = _db_config.get('password', '')
db_database = _db_config.get('database', 'test')
db_port = int(_db_config.get('port', 3306))
db_charset = _db_config.get('charset', 'utf8mb4')

MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    db_user, db_password, db_host, db_port, db_database, db_charset)
MYSQL_CONN_LOG_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    db_user, '***' if db_password else '', db_host, db_port, db_database, db_charset)
logging.info(f"数据库链接信息：{MYSQL_CONN_LOG_URL}")

MYSQL_CONN_DBAPI = {'host': db_host, 'user': db_user, 'password': db_password, 'database': db_database,
                    'charset': db_charset, 'port': db_port, 'connect_timeout': 10, 'autocommit': True}
MYSQL_CONN_DBAPI_LOG = MYSQL_CONN_DBAPI.copy()
MYSQL_CONN_DBAPI_LOG['password'] = '***' if db_password else ''

MYSQL_CONN_TORNDB = {'host': f'{db_host}:{str(db_port)}', 'user': db_user, 'password': db_password,
                     'database': db_database, 'charset': db_charset, 'max_idle_time': 3600, 'connect_timeout': 1000}


_engines = {}

# 通过数据库链接 engine
def engine():
    if None not in _engines:
        _engines[None] = create_engine(
            MYSQL_CONN_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20
        )
    return _engines[None]


def engine_to_db(to_db):
    if to_db not in _engines:
        _engines[to_db] = create_engine(
            MYSQL_CONN_URL.replace(f'/{db_database}?', f'/{to_db}?'),
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20
        )
    return _engines[to_db]


def _run_date_from_data(data):
    try:
        if 'date' in data.columns and len(data.index) > 0:
            value = data.iloc[0]['date']
            if hasattr(value, 'date'):
                return value.date()
            return value
    except Exception:
        pass
    return None


def _record_data_quality(table_name, data):
    try:
        if data is None or len(data.index) == 0:
            return
        from instock.core import data_quality
        results = data_quality.validate_dataframe(table_name, data)
        data_quality.record_quality_results(table_name, results, _run_date_from_data(data))
    except Exception as exc:
        logging.error(f"database._record_data_quality处理异常：{table_name}{exc}")


def _sanitize_db_value(value):
    if value is None:
        return None
    try:
        if math.isnan(value) or math.isinf(value):
            return None
    except Exception:
        pass
    try:
        if value != value:
            return None
    except Exception:
        pass
    return value


def _sanitize_dataframe_for_db(data):
    try:
        return data.replace([float('inf'), float('-inf')], None)
    except Exception:
        return data


# DB Api -数据库连接对象connection
def get_connection():
    try:
        return pymysql.connect(**MYSQL_CONN_DBAPI)
    except Exception as e:
        logging.error(f"database.conn_not_cursor处理异常：{MYSQL_CONN_DBAPI_LOG}{e}")
    return None


# 定义通用方法函数，插入数据库表，并创建数据库主键，保证重跑数据的时候索引唯一。
def insert_db_from_df(data, table_name, cols_type, write_index, primary_keys, indexs=None):
    # 插入默认的数据库。
    insert_other_db_from_df(None, data, table_name, cols_type, write_index, primary_keys, indexs)


# 增加一个插入到其他数据库的方法。
def insert_other_db_from_df(to_db, data, table_name, cols_type, write_index, primary_keys, indexs=None):
    if data is None or len(data.index) == 0:
        logging.warning(f"database.insert: 拒绝写入空DataFrame到 {table_name}")
        return

    # 移除质量标记列（仅用于内部传递，不写入数据库）
    if '_quality' in data.columns:
        data = data.drop(columns=['_quality'])

    # 定义engine
    if to_db is None:
        engine_mysql = engine()
    else:
        engine_mysql = engine_to_db(to_db)
    # 使用 http://docs.sqlalchemy.org/en/latest/core/reflection.html
    # 使用检查检查数据库表是否有主键。
    ipt = inspect(engine_mysql)
    col_name_list = data.columns.tolist()
    # 如果有索引，把索引增加到varchar上面。
    if write_index:
        # 插入到第一个位置：
        col_name_list.insert(0, data.index.name)
    data = _sanitize_dataframe_for_db(data)
    if to_db is None:
        _record_data_quality(table_name, data)
    try:
        if cols_type is None:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        index=write_index, )
        elif not cols_type:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype={col_name: NVARCHAR(255) for col_name in col_name_list}, index=write_index, )
        else:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype=cols_type, index=write_index, )
    except Exception as e:
        logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表{e}")

    # 判断是否存在主键
    if not ipt.get_pk_constraint(table_name)['constrained_columns']:
        try:
            # 执行数据库插入数据。
            conn = get_connection()
            if conn is None:
                logging.error(f"database.insert_other_db_from_df：无法获取数据库连接，跳过 {table_name} 表主键设置")
                return
            with conn as conn_ctx:
                with conn_ctx.cursor() as db:
                    db.execute(f'ALTER TABLE `{table_name}` ADD PRIMARY KEY ({primary_keys});')
                    if indexs is not None:
                        for k in indexs:
                            db.execute(f'ALTER TABLE `{table_name}` ADD INDEX IN{k}({indexs[k]});')
        except Exception as e:
            logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表{e}")


# 更新数据
def update_db_from_df(data, table_name, where):
    data = _sanitize_dataframe_for_db(data)
    data = data.astype(object).where(data.notnull(), None)
    cols = tuple(data.columns)
    where = tuple(where)
    set_cols = tuple(col for col in cols if col not in where)
    if not set_cols or not where:
        return

    set_sql = ', '.join(f'`{col}` = %s' for col in set_cols)
    where_sql = ' and '.join(f'`{col}` = %s' for col in where)
    sql = f'UPDATE `{table_name}` set {set_sql} where {where_sql}'

    conn = get_connection()
    if conn is None:
        return
    with conn:
        with conn.cursor() as db:
            try:
                for row in data.itertuples(index=False, name=None):
                    row_map = dict(zip(cols, row))
                    params = [_sanitize_db_value(row_map[col]) for col in set_cols]
                    params.extend(_sanitize_db_value(row_map[col]) for col in where)
                    db.execute(sql, params)
            except Exception as e:
                logging.error(f"database.update_db_from_df处理异常：{sql}{e}")


# 检查表是否存在
def checkTableIsExist(tableName):
    conn = get_connection()
    if conn is None:
        return False
    with conn:
        with conn.cursor() as db:
            db.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = %s
                """, (tableName,))
            if db.fetchone()[0] == 1:
                return True
    return False


# 增删改数据
def executeSql(sql, params=()):
    conn = get_connection()
    if conn is None:
        return
    with conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
            except Exception as e:
                logging.error(f"database.executeSql处理异常：{sql}{e}")


# 查询数据
def executeSqlFetch(sql, params=()):
    conn = get_connection()
    if conn is None:
        return None
    with conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                return db.fetchall()
            except Exception as e:
                logging.error(f"database.executeSqlFetch处理异常：{sql}{e}")
    return None


# 计算数量
def executeSqlCount(sql, params=()):
    conn = get_connection()
    if conn is None:
        return 0
    with conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                result = db.fetchall()
                if len(result) == 1:
                    return int(result[0][0])
                else:
                    return 0
            except Exception as e:
                logging.error(f"database.select_count计算数量处理异常：{e}")
    return 0

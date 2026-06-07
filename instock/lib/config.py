#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path


def project_root():
    return Path(__file__).resolve().parents[2]


def _parse_env_value(value):
    value = value.strip()
    if not value:
        return value
    if value[0] in ('"', "'") and value[-1:] == value[0]:
        return value[1:-1]
    if ' #' in value:
        value = value.split(' #', 1)[0].rstrip()
    return value


def load_dotenv(override=False):
    env_path = project_root() / '.env'
    if not env_path.exists():
        return
    with env_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = _parse_env_value(value)
            if key and (override or key not in os.environ):
                os.environ[key] = value


load_dotenv()


def _read_json(path):
    try:
        if path.exists():
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        return {}
    return {}


def _env(name, default=None):
    value = os.environ.get(name)
    if value is None or value == '':
        return default
    return value


def get_bool(name, default=False):
    value = _env(name)
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def get_int(name, default):
    value = _env(name)
    if value is None:
        return default
    return int(value)


def get_db_config(mask_password=False):
    cfg = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'test',
        'port': 3306,
        'charset': 'utf8mb4',
    }
    file_cfg = _read_json(project_root() / 'instock' / 'config' / 'database.json')
    cfg.update({k: v for k, v in file_cfg.items() if v is not None and v != ''})

    env_map = {
        'db_host': 'host',
        'db_user': 'user',
        'db_password': 'password',
        'db_database': 'database',
        'db_port': 'port',
        'db_charset': 'charset',
    }
    for env_name, key in env_map.items():
        value = _env(env_name)
        if value is not None:
            cfg[key] = int(value) if key == 'port' else value

    if mask_password:
        cfg = cfg.copy()
        cfg['password'] = '***' if cfg.get('password') else ''
    return cfg


def get_tushare_token():
    token = _env('TUSHARE_TOKEN', '')
    if token:
        return token
    cfg = _read_json(project_root() / 'instock' / 'config' / 'tushare.json')
    return cfg.get('token', '') or ''


def get_tushare_rate_limits():
    env_names = {
        'daily': ('TUSHARE_DAILY_RATE', 400),
        'daily_basic': ('TUSHARE_DAILY_BASIC_RATE', 150),
        'moneyflow': ('TUSHARE_MONEYFLOW_RATE', 150),
        'stock_basic': ('TUSHARE_STOCK_BASIC_RATE', 40),
        'fina_indicator': ('TUSHARE_FINA_INDICATOR_RATE', 160),
    }
    rates = {}
    for api_name, (env_name, default) in env_names.items():
        value = _env(env_name, default)
        try:
            rate = int(value)
        except ValueError as exc:
            raise RuntimeError(f'Tushare 频率配置 {env_name} 必须是整数') from exc
        if rate <= 0:
            raise RuntimeError(f'Tushare 频率配置 {env_name} 必须大于 0')
        rates[api_name] = rate
    return rates


def get_tushare_batch_rate_limit():
    return get_int('TUSHARE_RATE_LIMIT', 180)


def get_tushare_retry_config():
    return {
        'total': get_int('TUSHARE_RETRY_TOTAL', 5),
        'sleep_seconds': get_int('TUSHARE_RETRY_SLEEP_SECONDS', 60),
    }


def get_job_date_workers():
    return max(1, get_int('JOB_DATE_WORKERS', 1))


def get_stock_workers(default=4):
    return max(1, get_int('STOCK_WORKERS', default))


def get_backtest_stock_workers(default=4):
    return max(1, get_int('BACKTEST_STOCK_WORKERS', get_stock_workers(default)))


def get_backtest_check_workers(default=40):
    return max(1, get_int('BACKTEST_CHECK_WORKERS', default))


def get_backtest_table_workers(default=4):
    return max(1, get_int('BACKTEST_TABLE_WORKERS', default))


def get_web_config():
    return {
        'port': get_int('WEB_PORT', 9988),
        'debug': get_bool('Tornado_DEBUG', False),
        'cookie_secret': _env('Tornado_COOKIE_SECRET', '027bb1b670eddf0392cdda8709268a17b58b7'),
    }

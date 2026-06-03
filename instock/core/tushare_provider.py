#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import time

import numpy as np
import pandas as pd
import tushare as ts

from instock.lib import config
from instock.lib.rate_limiter import get_global_rate_limiter


class TushareProvider:
    _API_RATE_ENV = {
        'daily': 'TUSHARE_DAILY_RATE',
        'daily_basic': 'TUSHARE_DAILY_BASIC_RATE',
        'moneyflow': 'TUSHARE_MONEYFLOW_RATE',
        'stock_basic': 'TUSHARE_STOCK_BASIC_RATE',
    }

    STOCK_SPOT_COLUMNS = (
        'date', 'code', 'name', 'new_price', 'change_rate', 'ups_downs',
        'volume', 'deal_amount', 'amplitude', 'turnoverrate', 'volume_ratio',
        'open_price', 'high_price', 'low_price', 'pre_close_price',
        'speed_increase', 'speed_increase_5', 'speed_increase_60', 'speed_increase_all',
        'dtsyl', 'pe9', 'pe', 'pbnewmrq',
        'basic_eps', 'bvps', 'per_capital_reserve', 'per_unassign_profit',
        'roe_weight', 'sale_gpr', 'debt_asset_ratio',
        'total_operate_income', 'toi_yoy_ratio', 'parent_netprofit', 'netprofit_yoy_ratio',
        'report_date', 'total_shares', 'free_shares', 'total_market_cap', 'free_cap',
        'industry', 'listing_date',
    )

    def __init__(self, token=None):
        token = token or self._read_token()
        if not token or token.startswith('YOUR_'):
            raise RuntimeError(
                "Tushare token 未配置。请在 .env 中设置 TUSHARE_TOKEN，"
                "或在 instock/config/tushare.json 中填入 token"
            )
        ts.set_token(token)
        self.pro = ts.pro_api()
        self._rate_limits = self._read_rate_limits()
        self._retry_config = config.get_tushare_retry_config()
        self._rate_limiter = get_global_rate_limiter()

    @classmethod
    def _read_rate_limits(cls):
        return config.get_tushare_rate_limits()

    def _throttle(self, api_name):
        rate = self._rate_limits[api_name]
        self._rate_limiter.wait(f'tushare:{api_name}', rate)

    @staticmethod
    def _is_rate_limit_error(exc):
        message = str(exc).lower()
        return any(keyword in message for keyword in (
            '频率超限', '频次', 'rate limit', 'too many requests', '每分钟', 'minute'
        ))

    def _call_with_retry(self, api_name, description, callback):
        retry_total = max(0, int(self._retry_config.get('total', 0)))
        sleep_seconds = max(1, int(self._retry_config.get('sleep_seconds', 60)))
        for attempt in range(retry_total + 1):
            self._throttle(api_name)
            try:
                return callback()
            except Exception as exc:
                if not self._is_rate_limit_error(exc):
                    logging.warning(f"Tushare {description} 失败：{exc}")
                    return None
                if attempt >= retry_total:
                    logging.warning(f"Tushare {description} 频率超限，重试耗尽：{exc}")
                    return None
                logging.warning(
                    f"Tushare {description} 频率超限，等待 {sleep_seconds}s 后重试 "
                    f"({attempt + 1}/{retry_total})：{exc}"
                )
                time.sleep(sleep_seconds)
        return None

    @staticmethod
    def _read_token():
        return config.get_tushare_token()

    # ---- 代码格式转换 ----
    @staticmethod
    def to_ts_code(code):
        code = str(code).zfill(6)
        if code.startswith(('6', '9')):
            return f"{code}.SH"
        return f"{code}.SZ"

    @staticmethod
    def from_ts_code(ts_code):
        return ts_code.split('.')[0]

    def _get_stock_names(self):
        if hasattr(self, '_stock_names_cache'):
            return self._stock_names_cache
        basic = self._call_with_retry(
            'stock_basic',
            'stock_basic(name)',
            lambda: self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        )
        try:
            if basic is not None and not basic.empty:
                basic['code'] = basic['ts_code'].apply(self.from_ts_code)
                self._stock_names_cache = dict(zip(basic['code'], basic['name']))
            else:
                self._stock_names_cache = {}
        except Exception:
            self._stock_names_cache = {}
        return self._stock_names_cache

    # ---- 股票实时行情 ----
    def fetch_stock_spot(self, date):
        date_str = date.strftime('%Y%m%d')
        daily = self._call_with_retry(
            'daily',
            f'daily({date_str})',
            lambda: self.pro.daily(trade_date=date_str)
        )
        if daily is None or daily.empty:
            return None

        basic = self._call_with_retry(
            'daily_basic',
            f'daily_basic({date_str})',
            lambda: self.pro.daily_basic(ts_code='', trade_date=date_str)
        )

        if basic is not None and not basic.empty:
            df = daily.merge(basic, on=['ts_code', 'trade_date'], how='left', suffixes=('', '_basic'))
        else:
            df = daily.copy()

        names = self._get_stock_names()

        result = pd.DataFrame()
        result['date'] = pd.to_datetime(df['trade_date']).dt.date
        result['code'] = df['ts_code'].apply(self.from_ts_code)
        result['name'] = result['code'].map(names).fillna('')
        result['new_price'] = pd.to_numeric(df['close'], errors='coerce')
        result['change_rate'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        result['ups_downs'] = pd.to_numeric(df['change'], errors='coerce')
        result['volume'] = pd.to_numeric(df['vol'], errors='coerce')
        result['deal_amount'] = pd.to_numeric(df['amount'], errors='coerce')

        high = pd.to_numeric(df['high'], errors='coerce')
        low = pd.to_numeric(df['low'], errors='coerce')
        pre_close = pd.to_numeric(df['pre_close'], errors='coerce')
        result['amplitude'] = np.where(
            (pre_close > 0) & high.notna() & low.notna(),
            (high - low) / pre_close * 100, 0.0,
        )

        t_rate = df.get('turnover_rate')
        if t_rate is not None:
            result['turnoverrate'] = pd.to_numeric(t_rate, errors='coerce')
        else:
            result['turnoverrate'] = 0.0

        v_ratio = df.get('volume_ratio')
        if v_ratio is not None:
            result['volume_ratio'] = pd.to_numeric(v_ratio, errors='coerce')
        else:
            result['volume_ratio'] = 0.0

        result['open_price'] = pd.to_numeric(df['open'], errors='coerce')
        result['high_price'] = high
        result['low_price'] = low
        result['pre_close_price'] = pre_close

        result['speed_increase'] = 0.0
        result['speed_increase_5'] = 0.0
        result['speed_increase_60'] = 0.0
        result['speed_increase_all'] = 0.0
        result['dtsyl'] = 0.0
        result['pe9'] = self._safe_numeric(df, 'pe_ttm')
        result['pe'] = self._safe_numeric(df, 'pe')
        result['pbnewmrq'] = self._safe_numeric(df, 'pb')

        result['basic_eps'] = 0.0
        result['bvps'] = 0.0
        result['per_capital_reserve'] = 0.0
        result['per_unassign_profit'] = 0.0
        result['roe_weight'] = 0.0
        result['sale_gpr'] = 0.0
        result['debt_asset_ratio'] = 0.0
        result['total_operate_income'] = 0
        result['toi_yoy_ratio'] = 0.0
        result['parent_netprofit'] = 0
        result['netprofit_yoy_ratio'] = 0.0
        result['report_date'] = None

        result['total_shares'] = self._safe_numeric(df, 'total_share', 0) * 10000
        result['free_shares'] = self._safe_numeric(df, 'float_share', 0) * 10000
        result['total_market_cap'] = self._safe_numeric(df, 'total_mv', 0) * 10000
        result['free_cap'] = self._safe_numeric(df, 'circ_mv', 0) * 10000

        result['industry'] = ''
        result['listing_date'] = None

        result = result.reindex(columns=self.STOCK_SPOT_COLUMNS)
        return result

    # ---- 个股资金流向 ----
    def fetch_stock_fund_flow(self, indicator='今日', date=None):
        if indicator != '今日':
            return None
        if date is None:
            date = datetime.date.today()
        trade_date = date.strftime('%Y%m%d')
        mf = self._call_with_retry(
            'moneyflow',
            f'moneyflow({trade_date})',
            lambda: self.pro.moneyflow(trade_date=trade_date)
        )
        if mf is None or mf.empty:
            return None

        mf['buy_elg_amount'] = pd.to_numeric(mf.get('buy_elg_amount', 0), errors='coerce').fillna(0)
        mf['sell_elg_amount'] = pd.to_numeric(mf.get('sell_elg_amount', 0), errors='coerce').fillna(0)
        mf['buy_lg_amount'] = pd.to_numeric(mf.get('buy_lg_amount', 0), errors='coerce').fillna(0)
        mf['sell_lg_amount'] = pd.to_numeric(mf.get('sell_lg_amount', 0), errors='coerce').fillna(0)
        mf['buy_md_amount'] = pd.to_numeric(mf.get('buy_md_amount', 0), errors='coerce').fillna(0)
        mf['sell_md_amount'] = pd.to_numeric(mf.get('sell_md_amount', 0), errors='coerce').fillna(0)
        mf['buy_sm_amount'] = pd.to_numeric(mf.get('buy_sm_amount', 0), errors='coerce').fillna(0)
        mf['sell_sm_amount'] = pd.to_numeric(mf.get('sell_sm_amount', 0), errors='coerce').fillna(0)
        net_mf = pd.to_numeric(mf.get('net_mf_amount', 0), errors='coerce').fillna(0)

        total_amount = (
            mf['buy_elg_amount'] + mf['sell_elg_amount'] +
            mf['buy_lg_amount'] + mf['sell_lg_amount'] +
            mf['buy_md_amount'] + mf['sell_md_amount'] +
            mf['buy_sm_amount'] + mf['sell_sm_amount']
        )

        result = pd.DataFrame()
        result['code'] = mf['ts_code'].apply(self.from_ts_code)
        names = self._get_stock_names()
        result['name'] = result['code'].map(names).fillna('')
        result['new_price'] = 0.0
        result['今日涨跌幅'] = 0.0
        result['今日主力净流入-净额'] = (net_mf * 10000).astype('int64')
        result['今日主力净流入-净占比'] = np.where(total_amount > 0, net_mf / total_amount * 100, 0.0)
        result['今日超大单净流入-净额'] = ((mf['buy_elg_amount'] - mf['sell_elg_amount']) * 10000).astype('int64')
        result['今日超大单净流入-净占比'] = 0.0
        result['今日大单净流入-净额'] = ((mf['buy_lg_amount'] - mf['sell_lg_amount']) * 10000).astype('int64')
        result['今日大单净流入-净占比'] = 0.0
        result['今日中单净流入-净额'] = ((mf['buy_md_amount'] - mf['sell_md_amount']) * 10000).astype('int64')
        result['今日中单净流入-净占比'] = 0.0
        result['今日小单净流入-净额'] = ((mf['buy_sm_amount'] - mf['sell_sm_amount']) * 10000).astype('int64')
        result['今日小单净流入-净占比'] = 0.0
        return result

    # ---- 股票历史行情（单股）----
    def fetch_stock_hist(self, code, start_date, end_date,
                         period='daily', adjust='qfq'):
        ts_code = self.to_ts_code(code)
        df = self._call_with_retry(
            'daily',
            f'daily({code})',
            lambda: self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        )
        if df is None or df.empty:
            return None

        df['trade_date'] = pd.to_datetime(df['trade_date'])

        result = pd.DataFrame()
        result['日期'] = df['trade_date'].dt.strftime('%Y-%m-%d')
        result['开盘'] = pd.to_numeric(df['open'], errors='coerce')
        result['收盘'] = pd.to_numeric(df['close'], errors='coerce')
        result['最高'] = pd.to_numeric(df['high'], errors='coerce')
        result['最低'] = pd.to_numeric(df['low'], errors='coerce')
        result['成交量'] = pd.to_numeric(df['vol'], errors='coerce')
        result['成交额'] = pd.to_numeric(df['amount'], errors='coerce')
        pre_close = pd.to_numeric(df['pre_close'], errors='coerce')
        high = pd.to_numeric(df['high'], errors='coerce')
        low = pd.to_numeric(df['low'], errors='coerce')
        result['振幅'] = np.where(
            (pre_close > 0) & high.notna() & low.notna(),
            (high - low) / pre_close * 100, 0.0)
        result['涨跌幅'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        result['涨跌额'] = pd.to_numeric(df['change'], errors='coerce')
        result['换手率'] = 0.0
        result = result.sort_values('日期').reset_index(drop=True)
        return result

    # ---- 批量填充历史缓存 ----
    def fill_hist_cache(self, start_date, end_date, adjust='qfq'):
        import os as _os
        import time as _time

        codes = self._get_all_codes()
        if not codes:
            logging.warning("无法获取股票列表，批量填充取消")
            return 0

        cache_root = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)), 'cache', 'hist')
        _os.makedirs(cache_root, exist_ok=True)

        cache_dir = _os.path.join(cache_root, start_date[:6], start_date)
        _os.makedirs(cache_dir, exist_ok=True)

        count = 0
        total = len(codes)
        rate_limit = max(1, config.get_tushare_batch_rate_limit())

        for i, code in enumerate(codes):
            cache_file = _os.path.join(
                cache_dir, f"{code}{adjust}.gzip.pickle")
            if _os.path.isfile(cache_file):
                count += 1
                continue

            df = self.fetch_stock_hist(code, start_date, end_date, adjust=adjust)
            if df is not None and not df.empty:
                df.to_pickle(cache_file, compression='gzip')
                count += 1

            if (i + 1) % rate_limit == 0:
                _time.sleep(60)

        logging.info(f"历史缓存填充完成: {count}/{total} 只股票已缓存")
        return count

    def _get_all_codes(self):
        basic = self._call_with_retry(
            'stock_basic',
            'stock_basic(codes)',
            lambda: self.pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        )
        try:
            if basic is not None and not basic.empty:
                return sorted(basic['ts_code'].apply(self.from_ts_code).tolist())
        except Exception:
            pass
        return []

    @staticmethod
    def _safe_numeric(df, column, default=0.0):
        if column in df.columns:
            return pd.to_numeric(df[column], errors='coerce').fillna(default)
        return default

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
import logging
import os

import numpy as np
import pandas as pd
import tushare as ts


class TushareProvider:
    CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')

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
            raise RuntimeError("Tushare token 未配置，请在 instock/config/tushare.json 中填入 token")
        ts.set_token(token)
        self.pro = ts.pro_api()

    def _read_token(self):
        config_path = os.path.join(self.CONFIG_DIR, 'tushare.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('token', '')
        except Exception:
            return ''

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

    # ---- 股票实时行情 ----
    def fetch_stock_spot(self, date):
        date_str = date.strftime('%Y%m%d')
        try:
            daily = self.pro.daily(trade_date=date_str)
        except Exception as e:
            logging.warning(f"Tushare daily 接口失败：{e}")
            return None
        if daily is None or daily.empty:
            return None

        try:
            basic = self.pro.daily_basic(ts_code='', trade_date=date_str)
        except Exception:
            basic = None

        if basic is not None and not basic.empty:
            df = daily.merge(basic, on=['ts_code', 'trade_date'], how='left', suffixes=('', '_basic'))
        else:
            df = daily.copy()

        result = pd.DataFrame()
        result['date'] = pd.to_datetime(df['trade_date']).dt.date
        result['code'] = df['ts_code'].apply(self.from_ts_code)
        result['name'] = ''
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
        try:
            mf = self.pro.moneyflow(trade_date=trade_date)
        except Exception as e:
            logging.warning(f"Tushare moneyflow 接口失败：{e}")
            return None
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
        result['name'] = ''
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

    @staticmethod
    def _safe_numeric(df, column, default=0.0):
        if column in df.columns:
            return pd.to_numeric(df[column], errors='coerce').fillna(default)
        return default

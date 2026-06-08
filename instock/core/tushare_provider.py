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
from instock.lib.fetch_result import FetchResult, FetchStatus


class TushareProvider:
    _API_RATE_ENV = {
        'daily': 'TUSHARE_DAILY_RATE',
        'hist_bar': 'TUSHARE_HIST_BAR_RATE',
        'daily_basic': 'TUSHARE_DAILY_BASIC_RATE',
        'moneyflow': 'TUSHARE_MONEYFLOW_RATE',
        'stock_basic': 'TUSHARE_STOCK_BASIC_RATE',
        'fina_indicator': 'TUSHARE_FINA_INDICATOR_RATE',
        'dividend': 'TUSHARE_DIVIDEND_RATE',
        'block_trade': 'TUSHARE_BLOCK_TRADE_RATE',
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

    @staticmethod
    def _is_network_error(exc):
        exc_type = type(exc).__name__
        message = str(exc).lower()
        return any(k in exc_type.lower() or k in message for k in (
            'timeout', 'connection', 'network', 'unreachable'
        ))

    def _call_with_retry(self, api_name, description, callback):
        retry_total = max(0, int(self._retry_config.get('total', 0)))
        sleep_seconds = max(1, int(self._retry_config.get('sleep_seconds', 60)))
        for attempt in range(retry_total + 1):
            self._throttle(api_name)
            try:
                data = callback()
                return FetchResult(FetchStatus.SUCCESS, data)
            except Exception as exc:
                if self._is_network_error(exc):
                    logging.warning(f"Tushare {description} 网络错误：{exc}")
                    return FetchResult(FetchStatus.NETWORK_ERROR, message=str(exc))
                if not self._is_rate_limit_error(exc):
                    logging.warning(f"Tushare {description} API错误：{exc}")
                    return FetchResult(FetchStatus.API_ERROR, message=str(exc))
                if attempt >= retry_total:
                    logging.warning(f"Tushare {description} 频率超限，重试耗尽：{exc}")
                    return FetchResult(FetchStatus.RATE_LIMIT, message=str(exc))
                logging.warning(
                    f"Tushare {description} 频率超限，等待 {sleep_seconds}s 后重试 "
                    f"({attempt + 1}/{retry_total})：{exc}"
                )
                time.sleep(sleep_seconds)
        return FetchResult(FetchStatus.RATE_LIMIT, message="重试耗尽")

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
        result = self._call_with_retry(
            'stock_basic',
            'stock_basic(name)',
            lambda: self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        )
        try:
            if result.is_success and result.data is not None and not result.data.empty:
                basic = result.data
                basic['code'] = basic['ts_code'].apply(self.from_ts_code)
                self._stock_names_cache = dict(zip(basic['code'], basic['name']))
            else:
                self._stock_names_cache = {}
        except Exception:
            self._stock_names_cache = {}
        return self._stock_names_cache

    def _get_stock_info(self):
        """获取股票基本信息（扩展版）"""
        if hasattr(self, '_stock_info_cache'):
            return self._stock_info_cache
        result = self._call_with_retry(
            'stock_basic',
            'stock_basic(extended)',
            lambda: self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry,list_date')
        )
        try:
            if result.is_success and result.data is not None and not result.data.empty:
                df = result.data
                df['code'] = df['ts_code'].apply(self.from_ts_code)
                self._stock_info_cache = df.set_index('code')[['name', 'industry', 'list_date']].to_dict('index')
            else:
                self._stock_info_cache = {}
        except Exception:
            self._stock_info_cache = {}
        return self._stock_info_cache

    @staticmethod
    def _get_latest_report_period(date):
        """获取指定日期对应的最近报告期"""
        year = date.year
        month = date.month
        if month <= 3:
            return f"{year-1}1231"
        elif month <= 6:
            return f"{year}0331"
        elif month <= 9:
            return f"{year}0630"
        else:
            return f"{year}0930"

    def _fetch_fina_indicator_batch(self, period):
        """批量获取财务指标（按报告期）"""
        result = self._call_with_retry(
            'fina_indicator',
            f'fina_indicator({period})',
            lambda: self.pro.fina_indicator(period=period)
        )
        if not result.is_success or result.data is None or result.data.empty:
            return None

        df = result.data
        df['code'] = df['ts_code'].apply(self.from_ts_code)

        field_mapping = {
            'eps': 'basic_eps',
            'bps': 'bvps',
            'capital_rese_ps': 'per_capital_reserve',
            'undist_profit_ps': 'per_unassign_profit',
            'roe_waa': 'roe_weight',
            'grossprofit_margin': 'sale_gpr',
            'debt_to_assets': 'debt_asset_ratio',
            'or_yoy': 'toi_yoy_ratio',
        }

        result_df = pd.DataFrame()
        result_df['code'] = df['code']
        for ts_field, proj_field in field_mapping.items():
            result_df[proj_field] = pd.to_numeric(df.get(ts_field, 0), errors='coerce').fillna(0.0)

        return result_df

    def get_fina_indicator_cached(self, date):
        """获取财务指标（从缓存读取）

        缓存由 instock/job/fina_indicator_job.py 生成
        """
        import os

        period = self._get_latest_report_period(date)
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'fina', period[:4])
        cache_file = os.path.join(cache_dir, f"fina_{period}_all.pkl")

        if os.path.exists(cache_file):
            try:
                return pd.read_pickle(cache_file)
            except Exception as e:
                logging.warning(f"财务缓存读取失败: {e}")
        else:
            logging.info(f"财务缓存不存在，请先运行: python instock/job/fina_indicator_job.py")

        return None

    # ---- 股票实时行情 ----
    def fetch_stock_spot(self, date):
        date_str = date.strftime('%Y%m%d')
        daily_result = self._call_with_retry(
            'daily',
            f'daily({date_str})',
            lambda: self.pro.daily(trade_date=date_str)
        )
        if not daily_result.is_success:
            return daily_result

        daily = daily_result.data
        if daily is None or daily.empty:
            return FetchResult(FetchStatus.EMPTY, message=f"无交易数据：{date}")

        basic_result = self._call_with_retry(
            'daily_basic',
            f'daily_basic({date_str})',
            lambda: self.pro.daily_basic(ts_code='', trade_date=date_str)
        )

        quality_flag = 'complete'
        if basic_result.is_success and basic_result.data is not None and not basic_result.data.empty:
            df = daily.merge(basic_result.data, on=['ts_code', 'trade_date'], how='left', suffixes=('', '_basic'))
        else:
            logging.warning(f"daily_basic失败，使用默认值：{date}")
            df = daily.copy()
            quality_flag = 'partial_basic_missing'

        names = self._get_stock_names()

        result = pd.DataFrame()
        result['date'] = pd.to_datetime(df['trade_date']).dt.date
        result['code'] = df['ts_code'].apply(self.from_ts_code)
        result['name'] = result['code'].map(names).fillna('')
        result['new_price'] = pd.to_numeric(df['close'], errors='coerce')
        result['change_rate'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        result['ups_downs'] = pd.to_numeric(df['change'], errors='coerce')
        result['volume'] = pd.to_numeric(df['vol'], errors='coerce')
        result['deal_amount'] = pd.to_numeric(df['amount'], errors='coerce') * 1000

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

        # 补充财务指标
        try:
            fina_df = self.get_fina_indicator_cached(date)
            if fina_df is not None and not fina_df.empty:
                result = result.merge(fina_df, on='code', how='left')
                for field in ['basic_eps', 'bvps', 'per_capital_reserve',
                              'per_unassign_profit', 'roe_weight', 'sale_gpr',
                              'debt_asset_ratio', 'toi_yoy_ratio']:
                    if field in result.columns:
                        result[field] = result[field].fillna(0.0)
        except Exception as e:
            logging.warning(f"财务指标获取失败，使用默认值: {e}")

        # 确保财务字段存在
        for field in ['basic_eps', 'bvps', 'per_capital_reserve',
                      'per_unassign_profit', 'roe_weight', 'sale_gpr',
                      'debt_asset_ratio', 'toi_yoy_ratio']:
            if field not in result.columns:
                result[field] = 0.0

        result['total_operate_income'] = 0
        result['parent_netprofit'] = 0
        result['netprofit_yoy_ratio'] = 0.0
        result['report_date'] = None

        result['total_shares'] = self._safe_numeric(df, 'total_share', 0) * 10000
        result['free_shares'] = self._safe_numeric(df, 'float_share', 0) * 10000
        result['total_market_cap'] = self._safe_numeric(df, 'total_mv', 0) * 10000
        result['free_cap'] = self._safe_numeric(df, 'circ_mv', 0) * 10000

        # 补充基础信息
        stock_info = self._get_stock_info()
        result['industry'] = result['code'].map(lambda c: stock_info.get(c, {}).get('industry', ''))
        result['listing_date'] = result['code'].map(lambda c: stock_info.get(c, {}).get('list_date', None))

        result = result.reindex(columns=self.STOCK_SPOT_COLUMNS)
        result['_quality'] = quality_flag

        status = FetchStatus.SUCCESS if quality_flag == 'complete' else FetchStatus.PARTIAL
        return FetchResult(status, result)

    # ---- 个股资金流向 ----
    def fetch_stock_fund_flow(self, indicator='今日', date=None):
        if indicator != '今日':
            return FetchResult(FetchStatus.EMPTY, message=f"不支持的indicator: {indicator}")
        if date is None:
            date = datetime.date.today()
        trade_date = date.strftime('%Y%m%d')
        mf_result = self._call_with_retry(
            'moneyflow',
            f'moneyflow({trade_date})',
            lambda: self.pro.moneyflow(trade_date=trade_date)
        )
        if not mf_result.is_success:
            return mf_result

        mf = mf_result.data
        if mf is None or mf.empty:
            return FetchResult(FetchStatus.EMPTY, message=f"无资金流向数据：{date}")

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
        return FetchResult(FetchStatus.SUCCESS, result)

    # ---- 股票历史行情（单股）----
    def fetch_stock_hist(self, code, start_date, end_date,
                         period='daily', adjust='qfq'):
        ts_code = self.to_ts_code(code)
        adjust = adjust if adjust in ('qfq', 'hfq', '') else 'qfq'
        adj_param = adjust or None
        freq = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}.get(period, period)
        result = self._call_with_retry(
            'hist_bar',
            f'pro_bar({code}, adj={adjust or "不复权"})',
            lambda: ts.pro_bar(ts_code=ts_code, start_date=start_date, end_date=end_date,
                               freq=freq, adj=adj_param, asset='E')
        )
        if not result.is_success:
            return result

        df = result.data
        if df is None or df.empty:
            return FetchResult(FetchStatus.EMPTY, message=f"无历史数据：{code}")

        df = df.copy()
        if 'trade_date' not in df.columns:
            return FetchResult(FetchStatus.API_ERROR, message=f"历史数据缺少trade_date字段：{code}")
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)

        turnover_result = self._call_with_retry(
            'daily_basic',
            f'daily_basic_hist({code})',
            lambda: self.pro.daily_basic(
                ts_code=ts_code, start_date=start_date, end_date=end_date,
                fields='ts_code,trade_date,turnover_rate')
        )
        if turnover_result.is_success and turnover_result.data is not None and not turnover_result.data.empty:
            turnover_df = turnover_result.data.copy()
            if 'trade_date' in turnover_df.columns and 'turnover_rate' in turnover_df.columns:
                turnover_df['trade_date'] = pd.to_datetime(turnover_df['trade_date'])
                turnover_df = turnover_df[['trade_date', 'turnover_rate']].drop_duplicates('trade_date', keep='last')
                df = df.merge(turnover_df, on='trade_date', how='left')
            else:
                logging.warning(f"daily_basic历史换手率字段缺失，使用默认值：{code}")
        else:
            logging.warning(f"daily_basic历史换手率获取失败，使用默认值：{code}{turnover_result.message}")

        def _numeric(column, default=0.0):
            if column in df.columns:
                return pd.to_numeric(df[column], errors='coerce').fillna(default)
            return pd.Series(default, index=df.index, dtype='float64')

        open_price = _numeric('open')
        close = _numeric('close')
        high = _numeric('high')
        low = _numeric('low')
        pre_close = _numeric('pre_close', np.nan)
        pre_close = pre_close.where(pre_close > 0, close.shift(1)).fillna(0.0)
        change = _numeric('change', np.nan)
        change = change.where(change.notna(), close - pre_close).fillna(0.0)
        pct_chg = _numeric('pct_chg', np.nan)
        pct_chg = pct_chg.where(
            pct_chg.notna(),
            np.where(pre_close > 0, change / pre_close * 100, 0.0),
        ).fillna(0.0)

        data = pd.DataFrame()
        data['日期'] = df['trade_date'].dt.strftime('%Y-%m-%d')
        data['开盘'] = open_price
        data['收盘'] = close
        data['最高'] = high
        data['最低'] = low
        data['成交量'] = _numeric('vol')
        data['成交额'] = _numeric('amount') * 1000
        data['振幅'] = np.where(
            (pre_close > 0) & high.notna() & low.notna(),
            (high - low) / pre_close * 100, 0.0)
        data['涨跌幅'] = pct_chg
        data['涨跌额'] = change
        data['换手率'] = _numeric('turnover_rate')
        return FetchResult(FetchStatus.SUCCESS, data)

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

            hist_result = self.fetch_stock_hist(code, start_date, end_date, adjust=adjust)
            if isinstance(hist_result, FetchResult):
                if not hist_result.is_success:
                    continue
                df = hist_result.data
            else:
                df = hist_result
            if df is not None and not df.empty:
                df.to_pickle(cache_file, compression='gzip')
                count += 1

            if (i + 1) % rate_limit == 0:
                _time.sleep(60)

        logging.info(f"历史缓存填充完成: {count}/{total} 只股票已缓存")
        return count

    def _get_all_codes(self):
        result = self._call_with_retry(
            'stock_basic',
            'stock_basic(codes)',
            lambda: self.pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        )
        try:
            if result.is_success and result.data is not None and not result.data.empty:
                return sorted(result.data['ts_code'].apply(self.from_ts_code).tolist())
        except Exception:
            pass
        return []

    @staticmethod
    def _safe_numeric(df, column, default=0.0):
        if column in df.columns:
            return pd.to_numeric(df[column], errors='coerce').fillna(default)
        return default

    def fetch_dividend(self, date):
        """获取分红配送数据（Tushare版本）

        Args:
            date: 查询日期

        Returns:
            DataFrame with columns: date, code, name, convertible_total_rate,
            convertible_rate, convertible_transfer_rate, bonusaward_rate,
            bonusaward_yield, basic_eps, bvps, per_capital_reserve,
            per_unassign_profit, netprofit_yoy_ratio, total_shares,
            plan_date, record_date, ex_dividend_date, progress, report_date
        """
        # 查询当年及前一年的分红数据（覆盖跨年公告）
        year = date.year
        start_date = f'{year-1}0101'
        end_date = f'{year}1231'

        result = self._call_with_retry(
            'dividend',
            f'dividend({year})',
            lambda: self.pro.dividend(ann_date=start_date, end_date=end_date, fields='')
        )

        if not result.is_success or result.data is None or result.data.empty:
            return None

        df = result.data.copy()
        df['code'] = df['ts_code'].apply(self.from_ts_code)

        # 基础字段映射
        output = pd.DataFrame()
        output['date'] = date
        output['code'] = df['code']
        output['convertible_rate'] = self._safe_numeric(df, 'stk_div', 0.0)
        output['convertible_transfer_rate'] = self._safe_numeric(df, 'stk_bo_rate', 0.0)
        output['convertible_total_rate'] = self._safe_numeric(df, 'stk_co_rate', 0.0)
        output['bonusaward_rate'] = self._safe_numeric(df, 'cash_div', 0.0)
        output['plan_date'] = pd.to_datetime(df['ann_date'], errors='coerce')
        output['record_date'] = pd.to_datetime(df['record_date'], errors='coerce')
        output['ex_dividend_date'] = pd.to_datetime(df['ex_date'], errors='coerce')
        output['progress'] = df['div_proc'].fillna('')
        output['report_date'] = pd.to_datetime(df['end_date'], errors='coerce')

        # 补充财务字段（从fina_indicator缓存）
        try:
            fina_df = self.get_fina_indicator_cached(date)
            if fina_df is not None and not fina_df.empty:
                output = output.merge(fina_df[['code', 'basic_eps', 'bvps', 'per_capital_reserve',
                                                'per_unassign_profit', 'roe_weight', 'sale_gpr',
                                                'debt_asset_ratio', 'toi_yoy_ratio']],
                                      on='code', how='left')
                output['netprofit_yoy_ratio'] = output['toi_yoy_ratio']
        except Exception as e:
            logging.warning(f"分红配送补充财务数据失败: {e}")

        # 补充股票名称和总股本（从stock_basic）
        stock_info = self._get_stock_info()
        output['name'] = output['code'].map(lambda c: stock_info.get(c, {}).get('name', ''))
        output['total_shares'] = output['code'].map(lambda c: stock_info.get(c, {}).get('total_share', 0))

        # 计算股息率（如果有收盘价）
        output['bonusaward_yield'] = 0.0

        # 确保所有字段存在
        for field in ['basic_eps', 'bvps', 'per_capital_reserve', 'per_unassign_profit',
                      'roe_weight', 'sale_gpr', 'debt_asset_ratio', 'netprofit_yoy_ratio']:
            if field not in output.columns:
                output[field] = 0.0

        return output

    def fetch_block_trade(self, date):
        """获取大宗交易数据（Tushare版本）

        Args:
            date: 查询日期

        Returns:
            DataFrame with columns: date, code, name, new_price, change_rate,
            average_price, overflow_rate, trade_number, sum_volume,
            sum_turnover, turnover_market_rate
        """
        trade_date = date.strftime('%Y%m%d')

        result = self._call_with_retry(
            'block_trade',
            f'block_trade({trade_date})',
            lambda: self.pro.block_trade(trade_date=trade_date)
        )

        if not result.is_success or result.data is None or result.data.empty:
            return None

        df = result.data.copy()
        df['code'] = df['ts_code'].apply(self.from_ts_code)

        # 基础字段映射
        output = pd.DataFrame()
        output['date'] = date
        output['code'] = df['code']
        output['average_price'] = self._safe_numeric(df, 'price', 0.0)
        output['sum_volume'] = self._safe_numeric(df, 'vol', 0.0)
        output['sum_turnover'] = self._safe_numeric(df, 'amount', 0.0)
        output['trade_number'] = 0

        # 补充股票名称
        stock_info = self._get_stock_info()
        output['name'] = output['code'].map(lambda c: stock_info.get(c, {}).get('name', ''))

        # 补充收盘价和涨跌幅（直接调用daily接口）
        try:
            ts_codes = ','.join(output['code'].apply(self.to_ts_code).tolist())
            daily_result = self._call_with_retry(
                'daily',
                f'daily({trade_date})',
                lambda: self.pro.daily(trade_date=trade_date, ts_code=ts_codes)
            )
            if daily_result.is_success and daily_result.data is not None and not daily_result.data.empty:
                daily_df = daily_result.data.copy()
                daily_df['code'] = daily_df['ts_code'].apply(self.from_ts_code)
                daily_df = daily_df[['code', 'close', 'pct_chg']].copy()
                daily_df.columns = ['code', 'new_price', 'change_rate']
                output = output.merge(daily_df, on='code', how='left')
            else:
                output['new_price'] = 0.0
                output['change_rate'] = 0.0
        except Exception as e:
            logging.warning(f"大宗交易补充收盘价失败: {e}")
            output['new_price'] = 0.0
            output['change_rate'] = 0.0

        # 计算折溢率
        output['overflow_rate'] = ((output['average_price'] / output['new_price']) - 1) * 100
        output['overflow_rate'] = output['overflow_rate'].replace([np.inf, -np.inf], 0.0).fillna(0.0)

        output['turnover_market_rate'] = 0.0

        return output

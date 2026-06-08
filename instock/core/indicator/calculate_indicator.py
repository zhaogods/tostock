#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import pandas as pd
import numpy as np
import talib as tl

__author__ = 'myh '
__date__ = '2023/3/10 '


def _na_fill(series):
    """NaN/Inf 替换为 0，兼容 pandas 3.0 CoW（不可禁用 .values 写保护）"""
    return series.fillna(0.0).replace([np.inf, -np.inf], 0.0)


def get_indicators(data, end_date=None, threshold=120, calc_threshold=None):
    try:
        isCopy = False
        if end_date is not None:
            mask = (data['date'] <= end_date)
            data = data.loc[mask]
            isCopy = True
        if calc_threshold is not None:
            data = data.tail(n=calc_threshold)
            isCopy = True

        if isCopy:
            data = data.copy()

        # import stockstats
        # test = data.copy()
        # test = stockstats.StockDataFrame.retype(test)  # 验证计算结果

        with np.errstate(divide='ignore', invalid='ignore'):

            # macd
            data.loc[:, 'macd'], data.loc[:, 'macds'], data.loc[:, 'macdh'] = tl.MACD(
                data['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
            data.loc[:, 'macd'] = _na_fill(data['macd'])
            data.loc[:, 'macds'] = _na_fill(data['macds'])
            data.loc[:, 'macdh'] = _na_fill(data['macdh'])

            # kdjk
            data.loc[:, 'kdjk'], data.loc[:, 'kdjd'] = tl.STOCH(
                data['high'].values, data['low'].values, data['close'].values, fastk_period=9,
                slowk_period=5, slowk_matype=1, slowd_period=5, slowd_matype=1)
            data.loc[:, 'kdjk'] = _na_fill(data['kdjk'])
            data.loc[:, 'kdjd'] = _na_fill(data['kdjd'])
            data.loc[:, 'kdjj'] = 3 * data['kdjk'].values - 2 * data['kdjd'].values

            # boll 计算结果和stockstats不同boll_ub,boll_lb
            data.loc[:, 'boll_ub'], data.loc[:, 'boll'], data.loc[:, 'boll_lb'] = tl.BBANDS \
                (data['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            data.loc[:, 'boll_ub'] = _na_fill(data['boll_ub'])
            data.loc[:, 'boll'] = _na_fill(data['boll'])
            data.loc[:, 'boll_lb'] = _na_fill(data['boll_lb'])

            # trix
            data.loc[:, 'trix'] = tl.TRIX(data['close'].values, timeperiod=12)
            data.loc[:, 'trix'] = _na_fill(data['trix'])
            data.loc[:, 'trix_20_sma'] = tl.MA(data['trix'].values, timeperiod=20)
            data.loc[:, 'trix_20_sma'] = _na_fill(data['trix_20_sma'])

            # cr
            data.loc[:, 'm_price'] = data['amount'].values / data['volume'].values
            data.loc[:, 'm_price_sf1'] = data['m_price'].shift(1, fill_value=0.0).values
            data.loc[:, 'h_m'] = data['high'].values - data[['m_price_sf1', 'high']].values.min(axis=1)
            data.loc[:, 'm_l'] = data['m_price_sf1'].values - data[['m_price_sf1', 'low']].values.min(axis=1)
            data.loc[:, 'h_m_sum'] = tl.SUM(data['h_m'].values, timeperiod=26)
            data.loc[:, 'm_l_sum'] = tl.SUM(data['m_l'].values, timeperiod=26)
            data.loc[:, 'cr'] = data['h_m_sum'].values / data['m_l_sum'].values
            data.loc[:, 'cr'] = _na_fill(data['cr']) * 100
            data.loc[:, 'cr-ma1'] = tl.MA(data['cr'].values, timeperiod=5)
            data.loc[:, 'cr-ma1'] = _na_fill(data['cr-ma1'])
            data.loc[:, 'cr-ma2'] = tl.MA(data['cr'].values, timeperiod=10)
            data.loc[:, 'cr-ma2'] = _na_fill(data['cr-ma2'])
            data.loc[:, 'cr-ma3'] = tl.MA(data['cr'].values, timeperiod=20)
            data.loc[:, 'cr-ma3'] = _na_fill(data['cr-ma3'])

            # rsi
            data.loc[:, 'rsi'] = tl.RSI(data['close'].values, timeperiod=14)
            data.loc[:, 'rsi'] = _na_fill(data['rsi'])
            data.loc[:, 'rsi_6'] = tl.RSI(data['close'].values, timeperiod=6)
            data.loc[:, 'rsi_6'] = _na_fill(data['rsi_6'])
            data.loc[:, 'rsi_12'] = tl.RSI(data['close'].values, timeperiod=12)
            data.loc[:, 'rsi_12'] = _na_fill(data['rsi_12'])
            data.loc[:, 'rsi_24'] = tl.RSI(data['close'].values, timeperiod=24)
            data.loc[:, 'rsi_24'] = _na_fill(data['rsi_24'])

            # vr
            data.loc[:, 'av'] = np.where(data['p_change'].values > 0, data['volume'].values, 0)
            data.loc[:, 'avs'] = tl.SUM(data['av'].values, timeperiod=26)
            data.loc[:, 'bv'] = np.where(data['p_change'].values < 0, data['volume'].values, 0)
            data.loc[:, 'bvs'] = tl.SUM(data['bv'].values, timeperiod=26)
            data.loc[:, 'cv'] = np.where(data['p_change'].values == 0, data['volume'].values, 0)
            data.loc[:, 'cvs'] = tl.SUM(data['cv'].values, timeperiod=26)
            data.loc[:, 'vr'] = (data['avs'].values + data['cvs'].values / 2) / (data['bvs'].values + data['cvs'].values / 2)
            data.loc[:, 'vr'] = _na_fill(data['vr']) * 100
            data.loc[:, 'vr_6_sma'] = tl.MA(data['vr'].values, timeperiod=6)
            data.loc[:, 'vr_6_sma'] = _na_fill(data['vr_6_sma'])

            # atr
            data.loc[:, 'prev_close'] = data['close'].shift(1, fill_value=0.0).values
            data.loc[:, 'h_l'] = data['high'].values - data['low'].values
            data.loc[:, 'h_cy'] = data['high'].values - data['prev_close'].values
            data.loc[:, 'cy_l'] = data['prev_close'].values - data['low'].values
            data.loc[:, 'h_cy_a'] = abs(data['h_cy'].values)
            data.loc[:, 'cy_l_a'] = abs(data['cy_l'].values)
            data.loc[:, 'tr'] = data.loc[:, ['h_l', 'h_cy_a', 'cy_l_a']].T.max().values
            data.loc[:, 'tr'] = _na_fill(data['tr'])
            data.loc[:, 'atr'] = tl.ATR(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            data.loc[:, 'atr'] = _na_fill(data['atr'])

            # DMI
            # talib计算公式和stockstats不同
            # talib计算公式
            # data.loc[:, 'pdi'] = tl.PLUS_DI(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            # data.loc[:, 'pdi'] = _na_fill(data['pdi'])
            # data.loc[:, 'mdi'] = tl.MINUS_DI(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            # data.loc[:, 'mdi'] = _na_fill(data['mdi'])
            # data.loc[:, 'dx'] = tl.DX(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            # data.loc[:, 'dx'] = _na_fill(data['dx'])
            # data.loc[:, 'adx'] = tl.ADX(data['high'].values, data['low'].values, data['close'].values, timeperiod=6)
            # data.loc[:, 'adx'] = _na_fill(data['adx'])
            # data.loc[:, 'adxr'] = tl.ADXR(data['high'].values, data['low'].values, data['close'].values, timeperiod=6)
            # data.loc[:, 'adxr'] = _na_fill(data['adxr'])
            # stockstats计算公式
            data.loc[:, 'high_delta'] = np.insert(np.diff(data['high'].values), 0, 0.0)
            data.loc[:, 'high_m'] = (data['high_delta'].values + abs(data['high_delta'].values)) / 2
            data.loc[:, 'low_delta'] = np.insert(-np.diff(data['low'].values), 0, 0.0)
            data.loc[:, 'low_m'] = (data['low_delta'].values + abs(data['low_delta'].values)) / 2
            data.loc[:, 'pdm'] = tl.EMA(np.where(data['high_m'].values > data['low_m'].values, data['high_m'].values, 0), timeperiod=14)
            data.loc[:, 'pdm'] = _na_fill(data['pdm'])
            data.loc[:, 'pdi'] = data['pdm'].values / data['atr'].values
            data.loc[:, 'pdi'] = _na_fill(data['pdi']) * 100
            data.loc[:, 'mdm'] = tl.EMA(np.where(data['low_m'].values > data['high_m'].values, data['low_m'].values, 0), timeperiod=14)
            data.loc[:, 'mdm'] = _na_fill(data['mdm'])
            data.loc[:, 'mdi'] = data['mdm'].values / data['atr'].values
            data.loc[:, 'mdi'] = _na_fill(data['mdi']) * 100
            data.loc[:, 'dx'] = abs(data['pdi'].values - data['mdi'].values) / (data['pdi'].values + data['mdi'].values)
            data.loc[:, 'dx'] = _na_fill(data['dx']) * 100
            data.loc[:, 'adx'] = tl.EMA(data['dx'].values, timeperiod=6)
            data.loc[:, 'adx'] = _na_fill(data['adx'])
            data.loc[:, 'adxr'] = tl.EMA(data['adx'].values, timeperiod=6)
            data.loc[:, 'adxr'] = _na_fill(data['adxr'])

            # wr
            data.loc[:, 'wr_6'] = tl.WILLR(data['high'].values, data['low'].values, data['close'].values, timeperiod=6)
            data.loc[:, 'wr_6'] = _na_fill(data['wr_6'])
            data.loc[:, 'wr_10'] = tl.WILLR(data['high'].values, data['low'].values, data['close'].values, timeperiod=10)
            data.loc[:, 'wr_10'] = _na_fill(data['wr_10'])
            data.loc[:, 'wr_14'] = tl.WILLR(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            data.loc[:, 'wr_14'] = _na_fill(data['wr_14'])

            # cci 计算方法和结果和stockstats不同，stockstats典型价采用均价(总额/成交量)计算
            data.loc[:, 'cci'] = tl.CCI(data['high'].values, data['low'].values, data['close'].values, timeperiod=14)
            data.loc[:, 'cci'] = _na_fill(data['cci'])
            data.loc[:, 'cci_84'] = tl.CCI(data['high'].values, data['low'].values, data['close'].values, timeperiod=84)
            data.loc[:, 'cci_84'] = _na_fill(data['cci_84'])

            # dma
            data.loc[:, 'ma10'] = tl.MA(data['close'].values, timeperiod=10)
            data.loc[:, 'ma10'] = _na_fill(data['ma10'])
            data.loc[:, 'ma50'] = tl.MA(data['close'].values, timeperiod=50)
            data.loc[:, 'ma50'] = _na_fill(data['ma50'])
            data.loc[:, 'dma'] = data['ma10'].values - data['ma50'].values
            data.loc[:, 'dma_10_sma'] = tl.MA(data['dma'].values, timeperiod=10)
            data.loc[:, 'dma_10_sma'] = _na_fill(data['dma_10_sma'])

            # tema
            data.loc[:, 'tema'] = tl.TEMA(data['close'].values, timeperiod=14)
            data.loc[:, 'tema'] = _na_fill(data['tema'])

            # mfi 计算方法和结果和stockstats不同，stockstats典型价采用均价(总额/成交量)计算
            data.loc[:, 'mfi'] = tl.MFI(data['high'].values, data['low'].values, data['close'].values, data['volume'].values, timeperiod=14)
            data.loc[:, 'mfi'] = _na_fill(data['mfi'])
            data.loc[:, 'mfisma'] = tl.MA(data['mfi'].values, timeperiod=6)

            # vwma
            data.loc[:, 'tpv_14'] = tl.SUM(data['amount'].values, timeperiod=14)
            data.loc[:, 'vol_14'] = tl.SUM(data['volume'].values, timeperiod=14)
            data.loc[:, 'vwma'] = data['tpv_14'].values / data['vol_14'].values
            data.loc[:, 'vwma'] = _na_fill(data['vwma'])
            data.loc[:, 'mvwma'] = tl.MA(data['vwma'].values, timeperiod=6)

            # ppo
            data.loc[:, 'ppo'] = tl.PPO(data['close'].values, fastperiod=12, slowperiod=26, matype=1)
            data.loc[:, 'ppo'] = _na_fill(data['ppo'])
            data.loc[:, 'ppos'] = tl.EMA(data['ppo'].values, timeperiod=9)
            data.loc[:, 'ppos'] = _na_fill(data['ppos'])
            data.loc[:, 'ppoh'] = data['ppo'].values - data['ppos'].values

            # stochrsi
            # talib计算公式和stockstats不同
            # talib计算公式
            # data.loc[:, 'stochrsi_k'], data.loc[:, 'stochrsi_d'] = tl.STOCHRSI(data['close'].values, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)
            data.loc[:, 'rsi_min'] = tl.MIN(data['rsi'].values, timeperiod=14)
            data.loc[:, 'rsi_max'] = tl.MAX(data['rsi'].values, timeperiod=14)
            data.loc[:, 'stochrsi_k'] = (data['rsi'].values - data['rsi_min'].values) / (data['rsi_max'].values - data['rsi_min'].values)
            data.loc[:, 'stochrsi_k'] = _na_fill(data['stochrsi_k']) * 100
            data.loc[:, 'stochrsi_d'] = tl.MA(data['stochrsi_k'].values, timeperiod=3)

            # wt
            data.loc[:, 'esa'] = tl.EMA(data['m_price'].values, timeperiod=10)
            data.loc[:, 'esa'] = _na_fill(data['esa'])
            data.loc[:, 'esa_d'] = tl.EMA(abs(data['m_price'].values - data['esa'].values), timeperiod=10)
            data.loc[:, 'esa_ci'] = (data['m_price'].values - data['esa'].values) / (0.015 * data['esa_d'].values)
            data.loc[:, 'esa_ci'] = _na_fill(data['esa_ci'])
            data.loc[:, 'wt1'] = tl.EMA(data['esa_ci'].values, timeperiod=21)
            data.loc[:, 'wt1'] = _na_fill(data['wt1'])
            data.loc[:, 'wt2'] = tl.MA(data['wt1'].values, timeperiod=4)
            data.loc[:, 'wt2'] = _na_fill(data['wt2'])

            # Supertrend
            data.loc[:, 'm_atr'] = data['atr'].values * 3
            data.loc[:, 'hl_avg'] = (data['high'].values + data['low'].values) / 2.0
            data.loc[:, 'b_ub'] = data['hl_avg'].values + data['m_atr'].values
            data.loc[:, 'b_lb'] = data['hl_avg'].values - data['m_atr'].values
            size = len(data.index)
            ub = np.empty(size, dtype=np.float64)
            lb = np.empty(size, dtype=np.float64)
            st = np.empty(size, dtype=np.float64)
            for i in range(size):
                if i == 0:
                    ub[i] = data['b_ub'].iloc[i]
                    lb[i] = data['b_lb'].iloc[i]
                    if data['close'].iloc[i] <= ub[i]:
                        st[i] = ub[i]
                    else:
                        st[i] = lb[i]
                    continue

                last_close = data['close'].iloc[i - 1]
                curr_close = data['close'].iloc[i]
                last_ub = ub[i - 1]
                last_lb = lb[i - 1]
                last_st = st[i - 1]
                curr_b_ub = data['b_ub'].iloc[i]
                curr_b_lb = data['b_lb'].iloc[i]

                # calculate current upper band
                if curr_b_ub < last_ub or last_close > last_ub:
                    ub[i] = curr_b_ub
                else:
                    ub[i] = last_ub

                # calculate current lower band
                if curr_b_lb > last_lb or last_close < last_lb:
                    lb[i] = curr_b_lb
                else:
                    lb[i] = last_lb

                # calculate supertrend
                if last_st == last_ub:
                    if curr_close <= ub[i]:
                        st[i] = ub[i]
                    else:
                        st[i] = lb[i]
                elif last_st == last_lb:
                    if curr_close > lb[i]:
                        st[i] = lb[i]
                    else:
                        st[i] = ub[i]

            data.loc[:, 'supertrend_ub'] = ub
            data.loc[:, 'supertrend_lb'] = lb
            data.loc[:, 'supertrend'] = st
            data = data.copy()
            # ----------stockstats没有以下指标-----------------
            # roc
            data.loc[:, 'roc'] = tl.ROC(data['close'].values, timeperiod=12)
            data.loc[:, 'roc'] = _na_fill(data['roc'])
            data.loc[:, 'rocma'] = tl.MA(data['roc'].values, timeperiod=6)
            data.loc[:, 'rocma'] = _na_fill(data['rocma'])
            data.loc[:, 'rocema'] = tl.EMA(data['roc'].values, timeperiod=9)
            data.loc[:, 'rocema'] = _na_fill(data['rocema'])

            # obv
            data.loc[:, 'obv'] = tl.OBV(data['close'].values, data['volume'].values)
            data.loc[:, 'obv'] = _na_fill(data['obv'])

            # sar
            data.loc[:, 'sar'] = tl.SAR(data['high'].values, data['low'].values)
            data.loc[:, 'sar'] = _na_fill(data['sar'])

            # psy
            data.loc[:, 'price_up'] = 0.0
            data.loc[data['close'].values > data['prev_close'].values, 'price_up'] = 1.0
            data.loc[:, 'price_up_sum'] = tl.SUM(data['price_up'].values, timeperiod=12)
            data.loc[:, 'psy'] = data['price_up_sum'].values / 12.0
            data.loc[:, 'psy'] = _na_fill(data['psy']) * 100
            data.loc[:, 'psyma'] = tl.MA(data['psy'].values, timeperiod=6)

            # BRAR
            data.loc[:, 'h_o'] = data['high'].values - data['open'].values
            data.loc[:, 'o_l'] = data['open'].values - data['low'].values
            data.loc[:, 'h_o_sum'] = tl.SUM(data['h_o'].values, timeperiod=26)
            data.loc[:, 'o_l_sum'] = tl.SUM(data['o_l'].values, timeperiod=26)
            data.loc[:, 'ar'] = data['h_o_sum'].values / data['o_l_sum'].values
            data.loc[:, 'ar'] = _na_fill(data['ar']) * 100
            data.loc[:, 'h_cy_sum'] = tl.SUM(data['h_cy'].values, timeperiod=26)
            data.loc[:, 'cy_l_sum'] = tl.SUM(data['cy_l'].values, timeperiod=26)
            data.loc[:, 'br'] = data['h_cy_sum'].values / data['cy_l_sum'].values
            data.loc[:, 'br'] = _na_fill(data['br']) * 100

            # EMV
            data.loc[:, 'prev_high'] = data['high'].shift(1, fill_value=0.0).values
            data.loc[:, 'prev_low'] = data['low'].shift(1, fill_value=0.0).values
            data.loc[:, 'phl_avg'] = (data['prev_high'].values + data['prev_low'].values) / 2.0
            data.loc[:, 'emva_em'] = (data['hl_avg'].values - data['phl_avg'].values) * data['h_l'].values / data['amount'].values
            data.loc[:, 'emv'] = tl.SUM(data['emva_em'].values, timeperiod=14)
            data.loc[:, 'emv'] = _na_fill(data['emv'])
            data.loc[:, 'emva'] = tl.MA(data['emv'].values, timeperiod=9)
            data.loc[:, 'emva'] = _na_fill(data['emva'])

            # BIAS
            data.loc[:, 'ma6'] = tl.MA(data['close'].values, timeperiod=6)
            data.loc[:, 'ma6'] = _na_fill(data['ma6'])
            data.loc[:, 'ma12'] = tl.MA(data['close'].values, timeperiod=12)
            data.loc[:, 'ma12'] = _na_fill(data['ma12'])
            data.loc[:, 'ma24'] = tl.MA(data['close'].values, timeperiod=24)
            data.loc[:, 'ma24'] = _na_fill(data['ma24'])
            data.loc[:, 'bias'] = ((data['close'].values - data['ma6'].values) / data['ma6'].values)
            data.loc[:, 'bias'] = _na_fill(data['bias']) * 100
            data.loc[:, 'bias_12'] = (data['close'].values - data['ma12'].values) / data['ma12'].values
            data.loc[:, 'bias_12'] = _na_fill(data['bias_12']) * 100
            data.loc[:, 'bias_24'] = (data['close'].values - data['ma24'].values) / data['ma24'].values
            data.loc[:, 'bias_24'] = _na_fill(data['bias_24']) * 100

            # DPO
            data.loc[:, 'c_m_11'] = tl.MA(data['close'].values, timeperiod=11)
            data.loc[:, 'dpo'] = data['close'].values - data['c_m_11'].shift(1, fill_value=0.0).values
            data.loc[:, 'dpo'] = _na_fill(data['dpo'])
            data.loc[:, 'madpo'] = tl.MA(data['dpo'].values, timeperiod=6)
            data.loc[:, 'madpo'] = _na_fill(data['madpo'])

            # VHF
            data.loc[:, 'hcp_lcp'] = tl.MAX(data['close'].values, timeperiod=28) - tl.MIN(data['close'].values, timeperiod=28)
            data.loc[:, 'hcp_lcp'] = _na_fill(data['hcp_lcp'])
            data.loc[:, 'vhf'] = np.divide(data['hcp_lcp'].values, tl.SUM(abs(data['close'].values - data['prev_close'].values), timeperiod=28))
            data.loc[:, 'vhf'] = _na_fill(data['vhf'])

            # RVI
            data.loc[:, 'rvi_x'] = ((data['close'].values - data['open'].values) +
                                    2 * (data['prev_close'].values - data['open'].shift(1, fill_value=0.0).values) +
                                    2 * (data['close'].shift(2, fill_value=0.0).values - data['open'].shift(2, fill_value=0.0).values) +
                                    (data['close'].shift(3, fill_value=0.0).values - data['open'].shift(3, fill_value=0.0).values)) / 6
            data.loc[:, 'rvi_y'] = ((data['high'].values - data['low'].values) +
                                    2 * (data['prev_high'].values - data['prev_low'].values) +
                                    2 * (data['high'].shift(2, fill_value=0.0).values - data['low'].shift(2, fill_value=0.0).values) +
                                    (data['high'].shift(3, fill_value=0.0).values - data['low'].shift(3, fill_value=0.0).values)) / 6
            data.loc[:, 'rvi'] = tl.MA(data['rvi_x'].values, timeperiod=10) / tl.MA(data['rvi_y'].values, timeperiod=10)
            data.loc[:, 'rvi'] = _na_fill(data['rvi'])
            data.loc[:, 'rvis'] = (data['rvi'].values +
                                   2 * data['rvi'].shift(1, fill_value=0.0).values +
                                   2 * data['rvi'].shift(2, fill_value=0.0).values +
                                   data['rvi'].shift(3, fill_value=0.0).values) / 6

            # FI
            data.loc[:, 'fi'] = np.insert(np.diff(data['close'].values), 0, 0.0) * data['volume'].values
            data.loc[:, 'force_2'] = tl.EMA(data['fi'].values, timeperiod=2)
            data.loc[:, 'force_2'] = _na_fill(data['force_2'])
            data.loc[:, 'force_13'] = tl.EMA(data['fi'].values, timeperiod=13)
            data.loc[:, 'force_13'] = _na_fill(data['force_13'])

            # ENE
            data.loc[:, 'ene_ue'] = (1 + 11 / 100) * data['ma10'].values
            data.loc[:, 'ene_le'] = (1 - 9 / 100) * data['ma10'].values
            data.loc[:, 'ene'] = (data['ene_ue'].values + data['ene_le'].values) / 2

            # VOL
            data.loc[:, 'vol_5'] = tl.MA(data['volume'].values, timeperiod=5)
            data.loc[:, 'vol_5'] = _na_fill(data['vol_5'])
            data.loc[:, 'vol_10'] = tl.MA(data['volume'].values, timeperiod=10)
            data.loc[:, 'vol_10'] = _na_fill(data['vol_10'])

            # MA
            data.loc[:, 'ma20'] = tl.MA(data['close'].values, timeperiod=20)
            data.loc[:, 'ma20'] = _na_fill(data['ma20'])
            data.loc[:, 'ma200'] = tl.MA(data['close'].values, timeperiod=200)
            data.loc[:, 'ma200'] = _na_fill(data['ma200'])

        if threshold is not None:
            data = data.tail(n=threshold).copy()
        return data
    except Exception as e:
        logging.error(f"calculate_indicator.get_indicators处理异常：{e}")
    return None


def get_indicator(code_name, data, stock_column, date=None, calc_threshold=250):
    try:
        if date is None:
            end_date = code_name[0]
        else:
            end_date = date.strftime("%Y-%m-%d")

        code = code_name[1]
        # 设置返回数组。
        stock_data_list = [end_date, code]
        columns_num = len(stock_column) - 2
        # 增加空判断，如果是空返回 0 数据。
        if len(data.index) <= 1:
            for i in range(columns_num):
                stock_data_list.append(0)
            return pd.Series(stock_data_list, index=stock_column)

        idr_data = get_indicators(data, end_date=end_date, threshold=1, calc_threshold=calc_threshold)

        # 增加空判断，如果是空返回 0 数据。
        if idr_data is None:
            for i in range(columns_num):
                stock_data_list.append(0)
            return pd.Series(stock_data_list, index=stock_column)

        # 初始化统计类
        for i in range(columns_num):
            # 将数据的最后一个返回。
            tmp_val = idr_data[stock_column[i + 2]].tail(1).values[0]
            # 解决值中存在INF NaN问题。
            if np.isinf(tmp_val) or np.isnan(tmp_val):
                stock_data_list.append(0)
            else:
                stock_data_list.append(tmp_val)

        return pd.Series(stock_data_list, index=stock_column)
    except Exception as e:
        logging.error(f"calculate_indicator.get_indicator处理异常：{code}代码{e}")
    return None

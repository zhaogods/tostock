#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/4/7 15:22
Desc: 东方财富网-数据中心-年报季报-分红送配
https://data.eastmoney.com/yjfp/
"""
import pandas as pd
import akshare as ak

__author__ = 'myh '
__date__ = '2025/12/31 '


def stock_fhps_em(date: str = "20231231") -> pd.DataFrame:
    return ak.stock_fhps_em(date=date)


if __name__ == "__main__":
    stock_fhps_em_df = stock_fhps_em(date="20221231")
    print(stock_fhps_em_df)

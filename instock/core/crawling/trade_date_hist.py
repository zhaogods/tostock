#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/10/1 19:27
Desc: 新浪财经-交易日历
https://finance.sina.com.cn/realstock/company/klc_td_sh.txt
"""
import pandas as pd


def tool_trade_date_hist_sina() -> pd.DataFrame:
    import akshare as ak
    return ak.tool_trade_date_hist_sina()


if __name__ == "__main__":
    tool_trade_date_hist_df = tool_trade_date_hist_sina()
    print(tool_trade_date_hist_df)

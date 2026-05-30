#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
import time
import random
from instock.core.singleton_proxy import proxys

__author__ = 'myh '
__date__ = '2025/12/31 '

_RETRY_TOTAL = int(os.environ.get('HTTP_RETRY_TOTAL', '3'))
_RETRY_BACKOFF = float(os.environ.get('HTTP_RETRY_BACKOFF', '0.1'))
_RETRY_TIMEOUT_GET = int(os.environ.get('HTTP_TIMEOUT_GET', '10'))
_RETRY_TIMEOUT_POST = int(os.environ.get('HTTP_TIMEOUT_POST', '60'))
_POOL_CONNECTIONS = int(os.environ.get('HTTP_POOL_CONNS', '50'))
_POOL_MAXSIZE = int(os.environ.get('HTTP_POOL_MAXSIZE', '50'))
_RETRY_SLEEP_MIN = float(os.environ.get('HTTP_RETRY_SLEEP_MIN', '1'))
_RETRY_SLEEP_MAX = float(os.environ.get('HTTP_RETRY_SLEEP_MAX', '3'))

class eastmoney_fetcher:
    """
    东方财富网数据获取器
    封装了Cookie管理、会话管理和请求发送功能
    """

    def __init__(self):
        """初始化获取器"""
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.session = self._create_session()

    def _get_cookie(self):
        """
        获取东方财富网的Cookie
        优先级：环境变量 > 文件
        """
        cookie = os.environ.get('EAST_MONEY_COOKIE')
        if cookie:
            return cookie

        cookie_file = Path(os.path.join(self.base_dir, 'config', 'eastmoney_cookie.txt'))
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookie = f.read().strip()
            if cookie:
                return cookie

        return None

    def _create_session(self):
        """创建并配置会话"""
        session = requests.Session()

        # 配置连接池
        retry_strategy = Retry(
            total=_RETRY_TOTAL,
            backoff_factor=_RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=_POOL_CONNECTIONS,
            pool_maxsize=_POOL_MAXSIZE,
        )

        # 为http和https请求添加适配器
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
        }
        session.headers.update(headers)
        cookie = self._get_cookie()
        if cookie:
            session.headers['Cookie'] = cookie
        return session

    def make_request(self, url, params=None, retry=_RETRY_TOTAL, timeout=_RETRY_TIMEOUT_GET):
        """
        发送请求
        :param url: 请求URL
        :param params: 请求参数
        :param retry: 重试次数
        :param timeout: 超时时间
        :return: 响应对象
        """
        for i in range(retry):
            try:
                response = self.session.get(
                    url,
                    proxies=proxys().get_proxies(),
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()  # 检查HTTP错误
                return response
            except requests.exceptions.RequestException as e:
                print(f"请求错误: {e}, 第 {i + 1}/{retry} 次重试")
                if i < retry - 1:
                    # 随机延迟后重试
                    time.sleep(random.uniform(_RETRY_SLEEP_MIN, _RETRY_SLEEP_MAX))
                else:
                    raise

    def make_post_request(self, url, data=None, json=None, params=None, retry=_RETRY_TOTAL, timeout=_RETRY_TIMEOUT_POST):
        """
        发送POST请求
        :param url: 请求URL
        :param data: 请求数据（表单形式）
        :param json: 请求数据（JSON形式）
        :param params: URL参数
        :param retry: 重试次数
        :param timeout: 超时时间
        :return: 响应对象
        """
        for i in range(retry):
            try:
                response = self.session.post(
                    url,
                    proxies=proxys().get_proxies(),
                    params=params,
                    data=data,
                    json=json,
                    timeout=timeout
                )
                response.raise_for_status()  # 检查HTTP错误
                return response
            except requests.exceptions.RequestException as e:
                print(f"请求错误: {e}, 第 {i + 1}/{retry} 次重试")
                if i < retry - 1:
                    # 随机延迟后重试
                    time.sleep(random.uniform(_RETRY_SLEEP_MIN, _RETRY_SLEEP_MAX))
                else:
                    raise

    def update_cookie(self, new_cookie):
        """
        更新Cookie
        :param new_cookie: 新的Cookie值
        """
        self.session.cookies.update({'Cookie': new_cookie})

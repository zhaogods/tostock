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
_MIN_REQUEST_INTERVAL = float(os.environ.get('HTTP_MIN_INTERVAL', '1.0'))

class eastmoney_fetcher:
    """
    东方财富网数据获取器
    封装了Cookie管理、会话管理和请求发送功能
    """

    def __init__(self):
        """初始化获取器"""
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.session = self._create_session()
        self.has_cookie = self._get_cookie() is not None
        self._last_request_time = 0

    def _rate_limit(self):
        """确保请求间隔不小于 _MIN_REQUEST_INTERVAL 秒"""
        elapsed = time.time() - self._last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

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
            'Accept-Encoding': 'gzip, deflate',
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
        self._rate_limit()
        for i in range(retry):
            if self.has_cookie:
                proxies = {"http": None, "https": None}
            else:
                proxies = proxys().get_proxies()
            try:
                response = self.session.get(
                    url,
                    proxies=proxies,
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()
                if not self.has_cookie:
                    proxys().mark_ok()
                return response
            except requests.exceptions.RequestException as e:
                # 502 是网站问题，不是代理问题
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 502:
                    print(f"东方财富返回 502 (网站问题): {url}, 第 {i + 1}/{retry} 次重试")
                else:
                    if not self.has_cookie:
                        proxys().mark_failed(proxies)
                    print(f"请求错误: {e}, 第 {i + 1}/{retry} 次重试")

                if i < retry - 1:
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
        self._rate_limit()
        for i in range(retry):
            if self.has_cookie:
                proxies = {"http": None, "https": None}
            else:
                proxies = proxys().get_proxies()
            try:
                response = self.session.post(
                    url,
                    proxies=proxies,
                    params=params,
                    data=data,
                    json=json,
                    timeout=timeout
                )
                response.raise_for_status()
                if not self.has_cookie:
                    proxys().mark_ok()
                return response
            except requests.exceptions.RequestException as e:
                # 502 是网站问题，不是代理问题
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 502:
                    print(f"东方财富返回 502 (网站问题): {url}, 第 {i + 1}/{retry} 次重试")
                else:
                    if not self.has_cookie:
                        proxys().mark_failed(proxies)
                    print(f"请求错误: {e}, 第 {i + 1}/{retry} 次重试")

                if i < retry - 1:
                    time.sleep(random.uniform(_RETRY_SLEEP_MIN, _RETRY_SLEEP_MAX))
                else:
                    raise

    def update_cookie(self, new_cookie):
        """
        更新Cookie
        :param new_cookie: 新的Cookie值
        """
        self.session.cookies.update({'Cookie': new_cookie})

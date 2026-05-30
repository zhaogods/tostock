#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import random
import time
from pathlib import Path

import requests

__author__ = "myh "
__date__ = "2026/5/29 "

_PROXY_FILE = Path(os.path.join(
    os.path.dirname(__file__), "config", "proxy.txt"))

_API_DEFAULTS = {
    "uid": os.environ.get("XIEQU_UID", ""),
    "vkey": os.environ.get("XIEQU_VKEY", ""),
    "num": os.environ.get("XIEQU_NUM", "5"),
    "time": os.environ.get("XIEQU_TIME", "30"),
}

_API_BASE = "http://api.xiequ.cn/VAD/GetIp.aspx"


def fetch_proxies(uid=None, vkey=None, num=None, time_sec=None):
    api_uid = uid or _API_DEFAULTS["uid"]
    api_vkey = vkey or _API_DEFAULTS["vkey"]
    api_num = num or _API_DEFAULTS["num"]
    api_time = time_sec or _API_DEFAULTS["time"]

    if not api_uid or not api_vkey:
        logging.warning("proxy_fetcher: XIEQU_UID/XIEQU_VKEY 未配置，跳过代理提取")
        return []

    params = {
        "act": "get",
        "uid": api_uid,
        "vkey": api_vkey,
        "num": api_num,
        "time": api_time,
        "plat": "1",
        "re": "1",
        "type": "2",
        "so": "1",
        "ow": "1",
        "spl": "1",
        "addr": "",
        "db": "1",
    }

    try:
        r = requests.get(_API_BASE, params=params, timeout=15)
        r.raise_for_status()
        text = r.text.strip()
    except Exception as e:
        logging.error(f"proxy_fetcher: API 请求失败 {e}")
        return []

    if not text or text.startswith("-"):
        logging.warning(f"proxy_fetcher: API 返回异常: {text}")
        return []

    proxies = [line.strip() for line in text.splitlines() if line.strip()]
    logging.info(f"proxy_fetcher: 获取到 {len(proxies)} 个代理")

    valid = validate_proxies(proxies)
    if valid:
        write_proxy_file(valid)
    return valid


def validate_proxies(proxies, test_url="https://push2.eastmoney.com", timeout=5):
    valid = []
    for proxy in proxies:
        if test_proxy(proxy, test_url, timeout):
            valid.append(proxy)
        time.sleep(random.uniform(0.3, 1))
    logging.info(f"proxy_fetcher: 验证通过 {len(valid)}/{len(proxies)}")
    return valid


def test_proxy(proxy, test_url="https://push2.eastmoney.com", timeout=5):
    try:
        r = requests.get(
            test_url,
            proxies={"http": proxy, "https": proxy},
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return r.status_code == 200
    except Exception:
        return False


def write_proxy_file(proxies):
    _PROXY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROXY_FILE.write_text("\n".join(proxies), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = fetch_proxies()
    print(f"可用代理数: {len(count)}")

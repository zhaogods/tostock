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
    os.path.dirname(__file__), "..", "config", "proxy.txt")).resolve()

def _get_api_url():
    return os.environ.get("XIEQU_API_URL", "")


def refresh_proxy_pool():
    """从携趣 API 获取代理并验证，写入 proxy.txt。返回可用代理列表。"""
    api_url = _get_api_url()
    if not api_url:
        return []

    try:
        r = requests.get(api_url, timeout=15)
        r.raise_for_status()
        text = r.text.strip()
    except Exception as e:
        logging.warning(f"proxy_fetcher: API 请求失败 {e}")
        return []

    if not text or text.startswith("-"):
        logging.warning(f"proxy_fetcher: API 返回异常: {text[:200]}")
        return []

    proxies = [line.strip() for line in text.splitlines() if line.strip()]
    logging.info(f"proxy_fetcher: 获取到 {len(proxies)} 个代理")

    valid = _validate_proxies(proxies)
    if valid:
        _write_proxy_file(valid)
    return valid


def _validate_proxies(proxies, timeout=4):
    valid = []
    max_check = min(len(proxies), 5)
    for i, proxy in enumerate(proxies[:max_check]):
        ok = _test_proxy(proxy, timeout)
        if ok:
            valid.append(proxy)
            if len(valid) >= 2:
                break
        if i < max_check - 1 and len(valid) < 2:
            time.sleep(random.uniform(0.1, 0.2))
    logging.info(f"proxy_fetcher: 验证通过 {len(valid)}/{len(proxies)}")
    return valid


def _test_proxy(proxy, timeout=4):
    test_targets = [
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "http://push2.eastmoney.com/api/qt/clist/get",
    ]
    for url in test_targets:
        try:
            r = requests.get(
                url,
                proxies={"http": proxy, "https": proxy},
                timeout=(3, timeout),
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code not in (200, 502):
                return False
        except Exception:
            return False
    return True


def _write_proxy_file(proxies):
    _PROXY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROXY_FILE.write_text("\n".join(proxies), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 自动加载项目根目录 .env
    _env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env.exists():
        with open(_env, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k and v:
                        os.environ.setdefault(k, v)
    count = refresh_proxy_pool()
    print(f"可用代理数: {len(count)}")

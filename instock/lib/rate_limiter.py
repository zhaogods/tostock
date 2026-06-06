#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import threading
import time
from pathlib import Path

from instock.lib import config

try:
    import portalocker
    HAS_FILE_LOCK = True
except ImportError:
    portalocker = None
    HAS_FILE_LOCK = False
    import logging
    logging.warning("portalocker未安装，跨进程速率限制可能不可靠")

try:
    import fcntl
except ImportError:
    fcntl = None

_process_lock = threading.Lock()


class FileRateLimiter:
    """跨进程文件锁限流器。

    每次调用会在共享状态文件中为指定 key 预占下一个可用时间点，
    因此多个 Python 进程/线程会共享同一个速率预算。
    """

    def __init__(self, state_dir=None, name='tushare_rate_limit'):
        if state_dir is None:
            state_dir = config.project_root() / 'instock' / 'cache'
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.state_dir / f'{name}.lock'
        self.state_path = self.state_dir / f'{name}.json'
        self.log_wait_seconds = config.get_int('TUSHARE_RATE_LOG_WAIT_SECONDS', 5)
        self._thread_lock = threading.Lock()

    def wait(self, key, rate_per_minute):
        rate = int(rate_per_minute)
        if rate <= 0:
            raise RuntimeError(f'限流配置 {key} 必须大于 0，当前值：{rate_per_minute}')

        interval = 60.0 / rate
        now = time.time()
        scheduled_at = self._reserve_slot(str(key), interval, now)
        wait_seconds = max(0.0, scheduled_at - now)
        if wait_seconds >= self.log_wait_seconds:
            logging.info(f"Tushare 全局限流等待：{key} {wait_seconds:.2f}s，rate={rate}/min")
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return wait_seconds

    def _reserve_slot(self, key, interval, now):
        with self._thread_lock:
            with self.lock_path.open('a+', encoding='utf-8') as lock_file:
                if HAS_FILE_LOCK:
                    portalocker.lock(lock_file, portalocker.LOCK_EX)
                elif fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    state = self._load_state()
                    last = float(state.get(key, 0) or 0)
                    scheduled_at = max(now, last + interval)
                    state[key] = scheduled_at
                    self._save_state(state)
                    return scheduled_at
                finally:
                    if HAS_FILE_LOCK:
                        portalocker.unlock(lock_file)
                    elif fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load_state(self):
        try:
            if self.state_path.exists():
                with self.state_path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logging.warning(f"读取限流状态失败，重置状态：{self.state_path} {exc}")
        return {}

    def _save_state(self, state):
        tmp_path = self.state_path.with_suffix('.json.tmp')
        with tmp_path.open('w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_path, self.state_path)


_global_limiters = {}


def get_global_rate_limiter(name='tushare_rate_limit'):
    with _process_lock:
        limiter = _global_limiters.get(name)
        if limiter is None:
            limiter = FileRateLimiter(name=name)
            _global_limiters[name] = limiter
        return limiter

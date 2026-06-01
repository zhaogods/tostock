#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os
import time

from instock.lib import task_registry as registry
from instock.lib import task_runner


DEFAULT_TICK_SECONDS = int(os.environ.get('TASK_SCHEDULER_TICK_SECONDS', '60'))


def scheduler_enabled():
    value = os.environ.get('TASK_SCHEDULER_ENABLED', 'true')
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _minute_floor(value):
    return value.replace(second=0, microsecond=0)


def _parse_time(value):
    hour, minute = str(value).split(':', 1)
    return datetime.time(int(hour), int(minute))


def _weekday_allowed(now, schedule):
    weekdays = schedule.get('weekdays')
    return weekdays is None or now.weekday() in weekdays


def _interval_due(now, schedule):
    if not _weekday_allowed(now, schedule):
        return False
    now_time = now.time().replace(second=0, microsecond=0)
    for start_text, end_text in schedule.get('windows', ()):
        start = _parse_time(start_text)
        end = _parse_time(end_text)
        if not (start <= now_time <= end):
            continue
        start_dt = datetime.datetime.combine(now.date(), start)
        delta_minutes = int((_minute_floor(now) - start_dt).total_seconds() // 60)
        return delta_minutes >= 0 and delta_minutes % int(schedule.get('interval_minutes', 30)) == 0
    return False


def _daily_due(now, schedule):
    if not _weekday_allowed(now, schedule):
        return False
    return now.time().replace(second=0, microsecond=0) == _parse_time(schedule.get('time'))


def _monitor_due(now, schedule, last_fire_time):
    if last_fire_time is None:
        return True
    return (_minute_floor(now) - _minute_floor(last_fire_time)).total_seconds() >= int(schedule.get('minutes', 30)) * 60


def _due_now(task, now, last_fire_time):
    schedule = task.schedule
    if not schedule:
        return False
    schedule_type = schedule.get('type')
    if schedule_type == 'interval_in_windows':
        return _interval_due(now, schedule)
    if schedule_type in ('daily_at', 'weekly_at'):
        return _daily_due(now, schedule)
    if schedule_type == 'monitor_interval':
        return _monitor_due(now, schedule, last_fire_time)
    return False


def _recently_fired(now, last_fire_time):
    if last_fire_time is None:
        return False
    return _minute_floor(now) == _minute_floor(last_fire_time)


def _next_fire_after(task, after):
    if not task.schedule:
        return None
    if task.schedule.get('type') == 'monitor_interval':
        return _minute_floor(after) + datetime.timedelta(minutes=int(task.schedule.get('minutes', 30)))
    cursor = _minute_floor(after) + datetime.timedelta(minutes=1)
    for _ in range(8 * 24 * 60):
        if _due_now(task, cursor, None):
            return cursor
        cursor += datetime.timedelta(minutes=1)
    return None


def scheduled_tasks():
    return [task for task in registry.all_tasks(include_internal=False) if task.schedule]


def run_once(now=None):
    now = now or datetime.datetime.now()
    now = _minute_floor(now)
    task_runner.ensure_task_states()
    task_runner.write_scheduler_heartbeat(now)
    enabled = scheduler_enabled()
    fired = []
    for task in scheduled_tasks():
        state = task_runner.get_task_state(task.key)
        last_fire_time = state.get('last_fire_time')
        if isinstance(last_fire_time, str) and last_fire_time:
            last_fire_time = datetime.datetime.strptime(last_fire_time, '%Y-%m-%d %H:%M:%S')
        next_fire_time = _next_fire_after(task, now)
        task_runner.update_task_state(task.key, next_fire_time=next_fire_time)
        if not enabled or not task_runner.task_enabled(task.key):
            continue
        if not _due_now(task, now, last_fire_time):
            continue
        if _recently_fired(now, last_fire_time):
            continue
        ok, result = task_runner.start_task(task.key, trigger_type='schedule')
        if ok:
            fired.append({'task_key': task.key, 'run_id': result.get('run_id', '')})
        else:
            task_runner.create_notice(task.key, 'warning', f'{task.name} 调度触发失败', result.get('message', '任务启动失败'))
    return fired


def run_forever(tick_seconds=DEFAULT_TICK_SECONDS):
    logging.info('task_scheduler started')
    while True:
        try:
            run_once()
        except Exception as exc:
            logging.exception(f'task_scheduler.run_forever处理异常：{exc}')
        time.sleep(tick_seconds)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pymysql

from instock.lib import config
from instock.lib import cron_utils
from instock.lib import task_registry as registry

STATUS_RUNNING = 'running'
STATUS_SUCCESS = 'success'
STATUS_FAILED = 'failed'
STATUS_STOPPED = 'stopped'
STATUS_SKIPPED = 'skipped'

NOTICE_STATUS_OPEN = 'open'
NOTICE_STATUS_ACK = 'ack'
NOTICE_STATUS_RESOLVED = 'resolved'

SCHEDULER_HEARTBEAT_KEY = '__scheduler__'
SCHEDULER_HEARTBEAT_STALE_SECONDS = 180
SCHEDULE_MODE_DEFAULT = 'default'
SCHEDULE_MODE_CRON = 'cron'
MAX_LOG_READ_CHARS = 200000

_RUNNING_PROCESSES = {}
_SCHEMA_READY = False


def _now():
    return datetime.datetime.now().replace(microsecond=0)


def _today():
    return datetime.date.today()


def scheduler_enabled():
    return config.get_task_scheduler_enabled()


def _parse_datetime(value):
    if isinstance(value, datetime.datetime):
        return value.replace(microsecond=0)
    if isinstance(value, str) and value:
        try:
            return datetime.datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    return None


def _elapsed_seconds(start_time, now=None):
    start = _parse_datetime(start_time)
    if start is None:
        return 0
    return max(0, int(((now or _now()) - start).total_seconds()))


def _pid_exists(pid):
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and f'"{pid}"' in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _terminate_process(proc, wait_seconds=5):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def _terminate_pid(pid):
    if not pid:
        return False, '任务缺少进程ID'
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False, '进程ID不合法'
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, '运行进程已不存在'
    except Exception as exc:
        return False, f'停止任务失败：{exc}'
    time.sleep(2)
    if _pid_exists(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as exc:
            return False, f'强制停止任务失败：{exc}'
    return True, '已发送停止信号'


def _task_timeout_seconds(task_key):
    task = registry.get_task(task_key)
    return int(task.timeout_seconds or 0) if task else 0


def _timeout_message(task_key, elapsed):
    task = registry.get_task(task_key)
    task_name = task.name if task else task_key
    return f'{task_name} 运行超时（{elapsed}秒），已自动停止'


def _project_root():
    return config.project_root()


def _job_dir():
    return _project_root() / 'instock' / 'job'


def _python_executable():
    if sys.platform == 'win32':
        venv_python = _project_root() / '.venv' / 'Scripts' / 'python.exe'
    else:
        venv_python = _project_root() / '.venv' / 'bin' / 'python3'
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _log_dir():
    path = _project_root() / 'instock' / 'log' / 'tasks'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _short_message(message):
    if message is None:
        return ''
    return str(message)[:1800]


def _json_args(args):
    if not args:
        return ''
    return json.dumps(args, ensure_ascii=False)


def _trade_date_from_args(args):
    if not args:
        return _today()
    try:
        first = str(args[0]).split(',', 1)[0]
        return datetime.datetime.strptime(first, '%Y-%m-%d').date()
    except Exception:
        return _today()


def _rows_to_dicts(rows):
    data = []
    for row in rows or []:
        item = dict(row)
        for key, value in list(item.items()):
            if isinstance(value, datetime.datetime):
                item[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, datetime.date):
                item[key] = value.strftime('%Y-%m-%d')
        data.append(item)
    return data


def _execute(sql, params=()):
    from instock.lib import database as mdb
    return mdb.executeSql(sql, params)


def _query(sql, params=()):
    from instock.lib import database as mdb
    conn = mdb.get_connection()
    if conn is None:
        return []
    with conn:
        with conn.cursor(pymysql.cursors.DictCursor) as db:
            try:
                db.execute(sql, params)
                return db.fetchall()
            except Exception as exc:
                logging.error(f'task_runner._query处理异常：{sql}{exc}')
    return []


def _column_exists(table_name, column_name):
    rows = _query(
        """
        SELECT COUNT(*) AS `count`
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(rows and int(rows[0].get('count') or 0) == 1)


def ensure_task_schema():
    """补齐已有部署中的任务调度扩展字段。"""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    from instock.lib import database as mdb
    state_table_name = 'system_task_state'
    run_table_name = 'system_task_run'
    if mdb.checkTableIsExist(state_table_name):
        if not _column_exists(state_table_name, 'schedule_mode'):
            _execute(
                "ALTER TABLE `system_task_state` ADD COLUMN `schedule_mode` "
                "VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `next_fire_time`"
            )
        if not _column_exists(state_table_name, 'cron_expression'):
            _execute(
                "ALTER TABLE `system_task_state` ADD COLUMN `cron_expression` "
                "VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `schedule_mode`"
            )
    if mdb.checkTableIsExist(run_table_name):
        run_columns = (
            ('trade_date', "DATE NULL AFTER `run_date`"),
            ('pipeline_run_id', "VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `trade_date`"),
            ('parent_run_id', "VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `pipeline_run_id`"),
            ('attempt', "SMALLINT NULL AFTER `parent_run_id`"),
            ('skip_reason', "VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER `attempt`"),
        )
        for column_name, column_sql in run_columns:
            if not _column_exists(run_table_name, column_name):
                _execute(f"ALTER TABLE `system_task_run` ADD COLUMN `{column_name}` {column_sql}")
    _SCHEMA_READY = True


def write_scheduler_heartbeat(now=None):
    ensure_task_schema()
    heartbeat_time = now or _now()
    _update_state(SCHEDULER_HEARTBEAT_KEY, last_fire_time=heartbeat_time, enabled=scheduler_enabled())


def scheduler_heartbeat():
    state = get_task_state(SCHEDULER_HEARTBEAT_KEY)
    heartbeat_at = state.get('last_fire_time') or state.get('updated_at') or ''
    heartbeat_time = _parse_datetime(heartbeat_at)
    age_seconds = None
    alive = False
    if heartbeat_time is not None:
        age_seconds = _elapsed_seconds(heartbeat_time)
        alive = age_seconds <= SCHEDULER_HEARTBEAT_STALE_SECONDS
    return {
        'scheduler_enabled': scheduler_enabled(),
        'scheduler_alive': alive,
        'scheduler_heartbeat_at': heartbeat_at,
        'scheduler_heartbeat_age_seconds': age_seconds,
        'scheduler_heartbeat_stale_seconds': SCHEDULER_HEARTBEAT_STALE_SECONDS,
    }


def _create_run(task, trigger_type, args, status=STATUS_RUNNING, pid=None, log_path='', message='', run_id=None,
                pipeline_run_id='', parent_run_id='', trade_date=None, attempt=1, skip_reason=''):
    ensure_task_schema()
    run_id = run_id or uuid.uuid4().hex
    start_time = _now()
    trade_date = trade_date or _today()
    _execute(
        "INSERT INTO `system_task_run` "
        "(`run_id`,`task_key`,`task_name`,`category`,`trigger_type`,`schedule_key`,`run_date`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`args`,`status`,`pid`,`lock_group`,`start_time`,`end_time`,`duration_seconds`,`log_path`,`message`,`created_at`) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            run_id,
            task.key,
            task.name,
            task.category,
            trigger_type,
            task.key if trigger_type == 'schedule' else '',
            _today(),
            trade_date,
            pipeline_run_id,
            parent_run_id,
            int(attempt or 1),
            _short_message(skip_reason),
            _json_args(args),
            status,
            pid,
            task.lock_group,
            start_time,
            None,
            0,
            log_path,
            _short_message(message),
            start_time,
        ),
    )
    return run_id, start_time


def _finish_run(run_id, status, start_time=None, message=''):
    end_time = _now()
    duration = 0
    start = _parse_datetime(start_time)
    if start is not None:
        duration = (end_time - start).total_seconds()
    _execute(
        "UPDATE `system_task_run` SET `end_time`=%s,`duration_seconds`=%s,`status`=%s,`message`=%s WHERE `run_id`=%s",
        (end_time, duration, status, _short_message(message), run_id),
    )


def _update_pid(run_id, pid):
    _execute("UPDATE `system_task_run` SET `pid`=%s WHERE `run_id`=%s", (pid, run_id))


def _update_state(task_key, last_run_id='', last_fire_time=None, next_fire_time=None, enabled=None, schedule_mode=None, cron_expression=None, clear_next_fire_time=False):
    ensure_task_schema()
    existing = _query("SELECT `task_key` FROM `system_task_state` WHERE `task_key`=%s", (task_key,))
    updated_at = _now()
    if existing:
        assignments = ["`updated_at`=%s"]
        params = [updated_at]
        if last_run_id:
            assignments.append("`last_run_id`=%s")
            params.append(last_run_id)
        if last_fire_time is not None:
            assignments.append("`last_fire_time`=%s")
            params.append(last_fire_time)
        if next_fire_time is not None or clear_next_fire_time:
            assignments.append("`next_fire_time`=%s")
            params.append(next_fire_time)
        if enabled is not None:
            assignments.append("`enabled`=%s")
            params.append(1 if enabled else 0)
        if schedule_mode is not None:
            assignments.append("`schedule_mode`=%s")
            params.append(schedule_mode)
        if cron_expression is not None:
            assignments.append("`cron_expression`=%s")
            params.append(cron_expression)
        params.append(task_key)
        _execute(f"UPDATE `system_task_state` SET {', '.join(assignments)} WHERE `task_key`=%s", tuple(params))
    else:
        _execute(
            "INSERT IGNORE INTO `system_task_state` "
            "(`task_key`,`enabled`,`last_fire_time`,`next_fire_time`,`schedule_mode`,`cron_expression`,`last_run_id`,`updated_at`) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                task_key,
                1 if enabled is not False else 0,
                last_fire_time,
                next_fire_time,
                schedule_mode or SCHEDULE_MODE_DEFAULT,
                cron_expression or '',
                last_run_id,
                updated_at,
            ),
        )


def ensure_task_states():
    ensure_task_schema()
    rows = _query("SELECT `task_key` FROM `system_task_state`")
    existing = {row.get('task_key') for row in rows}
    updated_at = _now()
    for task in registry.all_tasks(include_internal=False):
        if task.key in existing:
            continue
        _execute(
            "INSERT IGNORE INTO `system_task_state` "
            "(`task_key`,`enabled`,`last_fire_time`,`next_fire_time`,`schedule_mode`,`cron_expression`,`last_run_id`,`updated_at`) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (task.key, 1 if task.enabled_by_default else 0, None, None, SCHEDULE_MODE_DEFAULT, '', '', updated_at),
        )


def get_task_state(task_key):
    ensure_task_schema()
    rows = _query(
        "SELECT `task_key`,`enabled`,`last_fire_time`,`next_fire_time`,`schedule_mode`,`cron_expression`,`last_run_id`,`updated_at` "
        "FROM `system_task_state` WHERE `task_key`=%s",
        (task_key,),
    )
    return rows[0] if rows else {}


def update_task_state(task_key, last_run_id='', last_fire_time=None, next_fire_time=None, enabled=None):
    _update_state(task_key, last_run_id=last_run_id, last_fire_time=last_fire_time, next_fire_time=next_fire_time, enabled=enabled)


def task_enabled(task_key):
    ensure_task_schema()
    task = registry.get_task(task_key)
    if task is None:
        return False
    rows = _query("SELECT `enabled` FROM `system_task_state` WHERE `task_key`=%s", (task_key,))
    if not rows:
        return task.enabled_by_default
    return int(rows[0]['enabled'] or 0) == 1


def validate_task_schedule(task_key, cron_expression):
    task = registry.get_task(task_key)
    if task is None:
        return False, '未知任务'
    if not task.visible:
        return False, '该任务不允许配置计划'
    return cron_utils.validate_cron_expression(cron_expression)


def effective_schedule_for_task(task, state=None):
    state = state or {}
    mode = state.get('schedule_mode') or SCHEDULE_MODE_DEFAULT
    cron_expression = (state.get('cron_expression') or '').strip()
    if mode == SCHEDULE_MODE_CRON and cron_expression:
        ok, message = cron_utils.validate_cron_expression(cron_expression)
        if ok:
            return {
                'mode': SCHEDULE_MODE_CRON,
                'cron_expression': cron_expression,
                'text': cron_utils.describe_cron_expression(cron_expression),
                'valid': True,
                'message': message,
            }
        return {
            'mode': SCHEDULE_MODE_DEFAULT,
            'cron_expression': '',
            'text': registry.schedule_text(task.schedule),
            'valid': False,
            'message': message,
        }
    return {
        'mode': SCHEDULE_MODE_DEFAULT,
        'cron_expression': '',
        'text': registry.schedule_text(task.schedule),
        'valid': True,
        'message': '使用默认计划',
    }


def set_task_schedule(task_key, schedule_mode=SCHEDULE_MODE_DEFAULT, cron_expression=''):
    ensure_task_schema()
    task = registry.get_task(task_key)
    if task is None:
        return False, {'message': '未知任务'}
    if not task.visible:
        return False, {'message': '该任务不允许配置计划'}
    schedule_mode = (schedule_mode or SCHEDULE_MODE_DEFAULT).strip().lower()
    cron_expression = (cron_expression or '').strip()
    if schedule_mode in ('reset', SCHEDULE_MODE_DEFAULT):
        _update_state(task_key, schedule_mode=SCHEDULE_MODE_DEFAULT, cron_expression='', clear_next_fire_time=True)
        return True, {'message': '已恢复默认计划', 'schedule_mode': SCHEDULE_MODE_DEFAULT, 'cron_expression': ''}
    if schedule_mode != SCHEDULE_MODE_CRON:
        return False, {'message': '计划模式不支持'}
    ok, message = validate_task_schedule(task_key, cron_expression)
    if not ok:
        return False, {'message': message}
    next_fire_time = cron_utils.next_fire_after(cron_expression, _now())
    _update_state(task_key, schedule_mode=SCHEDULE_MODE_CRON, cron_expression=cron_expression, next_fire_time=next_fire_time)
    return True, {
        'message': '已保存自定义计划',
        'schedule_mode': SCHEDULE_MODE_CRON,
        'cron_expression': cron_expression,
        'schedule_text': cron_utils.describe_cron_expression(cron_expression),
        'next_fire_time': next_fire_time,
    }


def reset_task_schedule(task_key):
    return set_task_schedule(task_key, SCHEDULE_MODE_DEFAULT, '')


def set_task_enabled(task_key, enabled):
    task = registry.get_task(task_key)
    if task is None:
        return False, '未知任务'
    if not task.visible:
        return False, '该任务不允许切换'
    _update_state(task_key, enabled=enabled)
    return True, '已更新任务状态'


def _cleanup_stale_running_rows():
    for row in _running_rows():
        run_id = row.get('run_id')
        if not run_id or run_id in _RUNNING_PROCESSES:
            continue
        pid = row.get('pid')
        start_time = row.get('start_time')
        task_key = row.get('task_key')

        if not pid:
            _finish_run(run_id, STATUS_FAILED, start_time, '运行记录缺少进程ID，自动修正状态')
            continue

        if not _pid_exists(pid):
            _finish_run(run_id, STATUS_FAILED, start_time, '运行进程已不存在，自动修正状态')
            continue

        elapsed = _elapsed_seconds(start_time)
        timeout_seconds = _task_timeout_seconds(task_key)
        if timeout_seconds and elapsed >= timeout_seconds:
            ok, message = _terminate_pid(pid)
            if ok:
                _finish_run(run_id, STATUS_FAILED, start_time, _timeout_message(task_key, elapsed))
            else:
                logging.error(f'task_runner._cleanup_stale_running_rows停止超时任务失败：{run_id}{message}')


def _cleanup_processes():
    finished = []
    for run_id, state in list(_RUNNING_PROCESSES.items()):
        proc = state['process']
        task_key = state.get('task_key')
        timeout_seconds = _task_timeout_seconds(task_key)
        elapsed = _elapsed_seconds(state['start_time'])
        if timeout_seconds and elapsed >= timeout_seconds and proc.poll() is None:
            message = _timeout_message(task_key, elapsed)
            logging.warning(message)
            _terminate_process(proc)
            _finish_run(run_id, STATUS_FAILED, state['start_time'], message)
            try:
                state['log_file'].write(message + '\n')
                state['log_file'].close()
            except Exception:
                pass
            finished.append(run_id)
            continue

        return_code = proc.poll()
        if return_code is None:
            continue
        status = STATUS_SUCCESS if return_code == 0 else STATUS_FAILED
        message = '' if return_code == 0 else f'进程退出码：{return_code}'
        _finish_run(run_id, status, state['start_time'], message)
        try:
            state['log_file'].close()
        except Exception:
            pass
        finished.append(run_id)
    for run_id in finished:
        _RUNNING_PROCESSES.pop(run_id, None)
    _cleanup_stale_running_rows()


def _running_rows():
    return _query(
        "SELECT `run_id`,`task_key`,`task_name`,`category`,`trigger_type`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`status`,`pid`,`lock_group`,`start_time`,`log_path`,`message` "
        "FROM `system_task_run` WHERE `status`=%s ORDER BY `start_time` DESC",
        (STATUS_RUNNING,),
    )


def _last_runs_by_task(limit=200):
    rows = _query(
        "SELECT `run_id`,`task_key`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`status`,`start_time`,`end_time`,`duration_seconds`,`message` "
        "FROM `system_task_run` ORDER BY `created_at` DESC LIMIT %s",
        (int(limit),),
    )
    result = {}
    for row in rows:
        task_key = row.get('task_key')
        if task_key and task_key not in result:
            result[task_key] = row
    return result


def _apply_runtime_fields(task, data, running_row=None, last_run=None):
    running_seconds = _elapsed_seconds(running_row.get('start_time')) if running_row else 0
    timeout_seconds = int(task.timeout_seconds or 0)
    data['running_seconds'] = running_seconds
    data['timeout_seconds'] = timeout_seconds
    data['timed_out'] = bool(timeout_seconds and running_seconds >= timeout_seconds)
    if last_run:
        data['last_status'] = last_run.get('status') or ''
        data['last_start_time'] = last_run.get('start_time') or ''
        data['last_end_time'] = last_run.get('end_time') or ''
        data['last_duration_seconds'] = last_run.get('duration_seconds')
        data['last_message'] = last_run.get('message') or ''
        data['last_run_id'] = data.get('last_run_id') or last_run.get('run_id') or ''
    else:
        data['last_status'] = ''
        data['last_start_time'] = ''
        data['last_end_time'] = ''
        data['last_duration_seconds'] = None
        data['last_message'] = ''
    return data


def _enrich_run_rows(rows):
    task_map = {task.key: task for task in registry.all_tasks(include_internal=True)}
    for row in rows or []:
        if row.get('status') != STATUS_RUNNING:
            row['timed_out'] = False
            continue
        running_seconds = _elapsed_seconds(row.get('start_time'))
        row['duration_seconds'] = running_seconds
        task = task_map.get(row.get('task_key'))
        timeout_seconds = int(task.timeout_seconds or 0) if task else 0
        row['timeout_seconds'] = timeout_seconds
        row['timed_out'] = bool(timeout_seconds and running_seconds >= timeout_seconds)
    return rows


def _lock_conflict(task):
    if not task.lock_group:
        return None
    _cleanup_processes()
    for row in _running_rows():
        if row.get('lock_group') == task.lock_group:
            return row
    return None


def _validate_arg_token(token):
    if not token:
        return False
    try:
        datetime.datetime.strptime(token, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def normalize_date_args(date_arg='', start_date='', end_date=''):
    date_arg = (date_arg or '').strip()
    start_date = (start_date or '').strip()
    end_date = (end_date or '').strip()
    if date_arg:
        parts = [part.strip() for part in date_arg.split(',') if part.strip()]
        if not parts or not all(_validate_arg_token(part) for part in parts):
            raise ValueError('日期参数必须是 YYYY-MM-DD 或逗号分隔日期列表')
        return [','.join(parts)]
    if start_date or end_date:
        if not (start_date and end_date):
            raise ValueError('日期范围需要同时提供开始日期和结束日期')
        if not (_validate_arg_token(start_date) and _validate_arg_token(end_date)):
            raise ValueError('起止日期必须是 YYYY-MM-DD')
        if start_date > end_date:
            raise ValueError('开始日期不能晚于结束日期')
        return [start_date, end_date]
    return []


def _command_for_task(task, args):
    if task.target_type == registry.TARGET_SCRIPT:
        return [_python_executable(), task.script] + list(args), str(_job_dir())
    if task.target_type == registry.TARGET_CALLABLE:
        module_name, func_name = task.callable_path.split(':', 1)
        code = f"from {module_name} import {func_name}; {func_name}()"
        return [_python_executable(), '-c', code], str(_project_root())
    return None, None


def _cleanup_hist_cache():
    cache_dir = (_project_root() / 'instock' / 'cache' / 'hist').resolve()
    allowed = (_project_root() / 'instock' / 'cache' / 'hist').resolve()
    if cache_dir != allowed:
        raise RuntimeError('缓存目录校验失败')
    if not cache_dir.exists():
        return '历史缓存目录不存在，无需清理'
    removed = 0
    for child in cache_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return f'已清理历史缓存项：{removed}'


def _run_notify(task):
    if task.builtin == 'check_daily_pipeline':
        return _check_daily_pipeline(task)
    if task.builtin == 'check_data_quality':
        return _check_data_quality(task)
    return '未配置通知检查'


def _notice_exists(task_key, title):
    rows = _query(
        "SELECT `notice_id` FROM `system_task_notice` WHERE `task_key`=%s AND `title`=%s AND `status`=%s LIMIT 1",
        (task_key, title, NOTICE_STATUS_OPEN),
    )
    return bool(rows)


def _resolve_notices(task_key, title):
    _execute(
        "UPDATE `system_task_notice` SET `status`=%s,`resolved_at`=%s WHERE `task_key`=%s AND `title`=%s AND `status`=%s",
        (NOTICE_STATUS_RESOLVED, _now(), task_key, title, NOTICE_STATUS_OPEN),
    )


def create_notice(task_key, level, title, message):
    if _notice_exists(task_key, title):
        return None
    notice_id = uuid.uuid4().hex
    created_at = _now()
    _execute(
        "INSERT INTO `system_task_notice` (`notice_id`,`level`,`task_key`,`title`,`message`,`status`,`created_at`,`ack_at`,`resolved_at`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (notice_id, level, task_key, title, _short_message(message), NOTICE_STATUS_OPEN, created_at, None, None),
    )
    return notice_id


def _check_daily_pipeline(task):
    now = datetime.datetime.now()
    if now.weekday() > 4 or now.time() < datetime.time(18, 0):
        return '非日终检查窗口'

    notice_title = '今日收盘后全量任务未确认成功'
    task_rows = _query(
        "SELECT `status`,`message` FROM `system_task_run` WHERE `run_date`=%s AND `task_key`=%s ORDER BY `start_time` DESC LIMIT 1",
        (_today(), 'daily_pipeline'),
    )
    if task_rows:
        status = task_rows[0].get('status')
        if status == STATUS_SUCCESS:
            _resolve_notices(task.key, notice_title)
            return '日终主任务已成功'
        if status == STATUS_RUNNING:
            return '日终主任务仍在运行'
        create_notice(task.key, 'warning', notice_title, f'daily_pipeline 今日最新状态为 {status or "未知"}，请在控制台检查运行日志。')
        return '已生成日终任务提醒'

    rows = _query(
        "SELECT `status` FROM `job_run_log` WHERE `run_date`=%s AND `job_name`='daily_report_job' ORDER BY `start_time` DESC LIMIT 1",
        (_today(),),
    )
    if rows and rows[0].get('status') == STATUS_SUCCESS:
        _resolve_notices(task.key, notice_title)
        return '日终作业记录已成功'
    create_notice(task.key, 'warning', notice_title, '18:00 后仍未看到 daily_pipeline 或 daily_report_job 成功记录。')
    return '已生成日终任务提醒'


def _check_data_quality(task):
    rows = _query(
        "SELECT COUNT(*) AS `count` FROM `data_quality_log` WHERE `run_date`=%s AND `passed`=0 AND `level` IN ('error','warning')",
        (_today(),),
    )
    count = int(rows[0].get('count') or 0) if rows else 0
    if count:
        create_notice(task.key, 'warning', '今日存在数据质量异常', f'今日数据质量日志中有 {count} 条未通过检查。')
        return f'发现数据质量异常：{count} 条'
    _resolve_notices(task.key, '今日存在数据质量异常')
    return '未发现数据质量异常'


def start_task(task_key, trigger_type='manual', date_arg='', start_date='', end_date=''):
    task = registry.get_task(task_key)
    if task is None:
        return False, {'message': '未知任务'}
    if not task.visible:
        return False, {'message': '该任务不能直接启动'}
    if trigger_type == 'manual' and not task.allow_manual_start:
        return False, {'message': '任务不允许手动启动'}
    if trigger_type == 'schedule' and not task_enabled(task_key):
        return False, {'message': '任务未启用'}

    try:
        has_date_args = any(str(value or '').strip() for value in (date_arg, start_date, end_date))
        if has_date_args and not task.allow_date_args:
            return False, {'message': '该任务不支持日期参数'}
        args = normalize_date_args(date_arg, start_date, end_date) if task.allow_date_args else []
    except ValueError as exc:
        return False, {'message': str(exc)}

    conflict = _lock_conflict(task)
    if conflict:
        return False, {'message': f"任务互斥：{conflict.get('task_name') or conflict.get('task_key')} 正在运行"}

    run_id = uuid.uuid4().hex
    log_path = _log_dir() / f"{task.key}-{run_id}.log"

    if task.target_type in (registry.TARGET_BUILTIN, registry.TARGET_NOTIFY):
        run_id, start_time = _create_run(task, trigger_type, args, log_path=str(log_path), run_id=run_id, trade_date=_trade_date_from_args(args))
        try:
            if task.target_type == registry.TARGET_BUILTIN and task.builtin == 'cleanup_hist_cache':
                message = _cleanup_hist_cache()
            else:
                message = _run_notify(task)
            log_path.write_text(message + '\n', encoding='utf-8')
            _finish_run(run_id, STATUS_SUCCESS, start_time, message)
            _update_state(task.key, last_run_id=run_id, last_fire_time=start_time)
            return True, {'message': '任务已完成', 'run_id': run_id}
        except Exception as exc:
            logging.exception(f'task_runner.start_task处理异常：{task.key}')
            log_path.write_text(str(exc) + '\n', encoding='utf-8')
            _finish_run(run_id, STATUS_FAILED, start_time, exc)
            return False, {'message': '任务执行失败', 'run_id': run_id}

    command, cwd = _command_for_task(task, args)
    run_id, start_time = _create_run(task, trigger_type, args, log_path=str(log_path), run_id=run_id)
    log_file = None
    try:
        log_file = open(log_path, 'a', encoding='utf-8')
        proc = subprocess.Popen(command, cwd=cwd, stdout=log_file, stderr=subprocess.STDOUT)
        _update_pid(run_id, proc.pid)
        _RUNNING_PROCESSES[run_id] = {'process': proc, 'log_file': log_file, 'start_time': start_time, 'task_key': task.key}
        _update_state(task.key, last_run_id=run_id, last_fire_time=start_time)
        return True, {'message': '任务已启动', 'run_id': run_id, 'pid': proc.pid}
    except Exception as exc:
        logging.exception(f'task_runner.start_task处理异常：{task.key}')
        if log_file is not None:
            try:
                log_file.close()
            except Exception:
                pass
        _finish_run(run_id, STATUS_FAILED, start_time, exc)
        return False, {'message': '任务启动失败', 'run_id': run_id}


def stop_task(run_id='', task_key=''):
    _cleanup_processes()
    target_run_id = run_id
    if not target_run_id and task_key:
        rows = _query(
            "SELECT `run_id` FROM `system_task_run` WHERE `task_key`=%s AND `status`=%s ORDER BY `start_time` DESC LIMIT 1",
            (task_key, STATUS_RUNNING),
        )
        if rows:
            target_run_id = rows[0]['run_id']
    if not target_run_id:
        return False, {'message': '任务未运行'}

    state = _RUNNING_PROCESSES.get(target_run_id)
    if state:
        task = registry.get_task(state['task_key'])
        if task is not None and not task.allow_stop:
            return False, {'message': '该任务不支持停止'}
        proc = state['process']
        _terminate_process(proc)
        _finish_run(target_run_id, STATUS_STOPPED, state['start_time'], '已停止')
        try:
            state['log_file'].close()
        except Exception:
            pass
        _RUNNING_PROCESSES.pop(target_run_id, None)
        return True, {'message': '已发送停止信号'}

    rows = _query("SELECT `pid`,`task_key`,`start_time` FROM `system_task_run` WHERE `run_id`=%s AND `status`=%s", (target_run_id, STATUS_RUNNING))
    if not rows:
        return False, {'message': '任务未运行'}
    row = rows[0]
    pid = row.get('pid')
    row_task_key = row.get('task_key')
    start_time = row.get('start_time')
    task = registry.get_task(row_task_key)
    if task is not None and not task.allow_stop:
        return False, {'message': '该任务不支持停止'}
    if not pid:
        return False, {'message': '任务缺少进程ID'}
    ok, message = _terminate_pid(pid)
    if ok:
        _finish_run(target_run_id, STATUS_STOPPED, start_time, message)
        return True, {'message': message}
    return False, {'message': message}


def overview():
    _cleanup_processes()
    today = _today()
    rows = _query("SELECT `status`, COUNT(*) AS `count` FROM `system_task_run` WHERE `run_date`=%s GROUP BY `status`", (today,))
    summary = {'running': 0, 'success': 0, 'failed': 0, 'stopped': 0, 'skipped': 0, 'total': 0}
    for row in rows:
        status = row.get('status')
        count = int(row.get('count') or 0)
        summary[status] = count
        summary['total'] += count
    notice_rows = _query("SELECT COUNT(*) AS `count` FROM `system_task_notice` WHERE `status`=%s", (NOTICE_STATUS_OPEN,))
    open_notices = int(notice_rows[0].get('count') or 0) if notice_rows else 0
    state_rows = _query("SELECT `updated_at` FROM `system_task_state` ORDER BY `updated_at` DESC LIMIT 1")
    scheduler = scheduler_heartbeat()
    return {
        'today': today.strftime('%Y-%m-%d'),
        'summary': summary,
        'open_notices': open_notices,
        'scheduler_updated_at': _rows_to_dicts(state_rows)[0]['updated_at'] if state_rows else '',
        **scheduler,
    }


def task_payloads():
    _cleanup_processes()
    ensure_task_schema()
    running = {row.get('task_key'): row for row in _running_rows()}
    state_rows = _query(
        "SELECT `task_key`,`enabled`,`last_fire_time`,`next_fire_time`,`schedule_mode`,`cron_expression`,`last_run_id`,`updated_at` FROM `system_task_state`"
    )
    states = {row.get('task_key'): row for row in state_rows}
    last_runs = _last_runs_by_task()
    payload = []
    for task in registry.visible_tasks():
        data = task.to_dict()
        state = states.get(task.key, {})
        running_row = running.get(task.key)
        effective_schedule = effective_schedule_for_task(task, state)
        data['enabled'] = bool(int(state.get('enabled', 1) or 0)) if state else task.enabled_by_default
        data['running'] = running_row is not None
        data['running_run_id'] = running_row.get('run_id') if running_row else ''
        data['last_fire_time'] = state.get('last_fire_time') if state else ''
        data['next_fire_time'] = state.get('next_fire_time') if state else ''
        data['last_run_id'] = state.get('last_run_id') if state else ''
        data['schedule_mode'] = effective_schedule.get('mode')
        data['cron_expression'] = effective_schedule.get('cron_expression')
        data['schedule_customized'] = effective_schedule.get('mode') == SCHEDULE_MODE_CRON
        data['default_schedule_text'] = registry.schedule_text(task.schedule)
        data['effective_schedule_text'] = effective_schedule.get('text') or data.get('schedule_text') or ''
        data['schedule_message'] = effective_schedule.get('message') or ''
        data['schedule_valid'] = bool(effective_schedule.get('valid'))
        _apply_runtime_fields(task, data, running_row, last_runs.get(task.key))
        payload.append(data)
    return _rows_to_dicts(payload)


def recent_runs(limit=30):
    _cleanup_processes()
    rows = _query(
        "SELECT `run_id`,`task_key`,`task_name`,`category`,`trigger_type`,`run_date`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`status`,`pid`,`lock_group`,`start_time`,`end_time`,`duration_seconds`,`log_path`,`message` "
        "FROM `system_task_run` ORDER BY `created_at` DESC LIMIT %s",
        (int(limit),),
    )
    return _rows_to_dicts(_enrich_run_rows(rows))


def recent_job_runs(limit=20):
    rows = _query(
        "SELECT `run_date`,`job_name`,`start_time`,`end_time`,`status`,`duration_seconds`,`rows_written`,`message` FROM `job_run_log` ORDER BY `created_at` DESC LIMIT %s",
        (int(limit),),
    )
    return _rows_to_dicts(rows)


def notices(limit=20, task_key='', status=''):
    where = []
    params = []
    if task_key:
        where.append("`task_key`=%s")
        params.append(task_key)
    if status:
        where.append("`status`=%s")
        params.append(status)
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    params.append(int(limit))
    rows = _query(
        "SELECT `notice_id`,`level`,`task_key`,`title`,`message`,`status`,`created_at`,`ack_at`,`resolved_at` "
        f"FROM `system_task_notice`{where_sql} ORDER BY `created_at` DESC LIMIT %s",
        tuple(params),
    )
    return _rows_to_dicts(rows)


def console_snapshot(run_limit=30, job_limit=20, notice_limit=20):
    ensure_task_schema()
    _cleanup_processes()
    today = _today()
    from instock.lib import database as mdb
    conn = mdb.get_connection()
    if conn is None:
        scheduler = scheduler_heartbeat()
        return {
            'today': today.strftime('%Y-%m-%d'),
            'summary': {'running': 0, 'success': 0, 'failed': 0, 'stopped': 0, 'skipped': 0, 'total': 0},
            'open_notices': 0,
            'scheduler_updated_at': '',
            'tasks': [],
            'recent': [],
            'job_recent': [],
            'notices': [],
            **scheduler,
        }
    with conn:
        with conn.cursor(pymysql.cursors.DictCursor) as db:
            summary = {'running': 0, 'success': 0, 'failed': 0, 'stopped': 0, 'skipped': 0, 'total': 0}
            db.execute("SELECT `status`, COUNT(*) AS `count` FROM `system_task_run` WHERE `run_date`=%s GROUP BY `status`", (today,))
            for row in db.fetchall():
                count = int(row.get('count') or 0)
                summary[row.get('status')] = count
                summary['total'] += count

            db.execute("SELECT COUNT(*) AS `count` FROM `system_task_notice` WHERE `status`=%s", (NOTICE_STATUS_OPEN,))
            notice_row = db.fetchone()
            open_notices = int(notice_row.get('count') or 0) if notice_row else 0

            db.execute("SELECT `updated_at` FROM `system_task_state` ORDER BY `updated_at` DESC LIMIT 1")
            state_updated = db.fetchone()
            scheduler_updated_at = _rows_to_dicts([state_updated])[0]['updated_at'] if state_updated else ''

            db.execute("SELECT `run_id`,`task_key`,`task_name`,`category`,`trigger_type`,`status`,`pid`,`lock_group`,`start_time`,`log_path`,`message` FROM `system_task_run` WHERE `status`=%s ORDER BY `start_time` DESC", (STATUS_RUNNING,))
            running = {row.get('task_key'): row for row in db.fetchall()}

            db.execute("SELECT `task_key`,`enabled`,`last_fire_time`,`next_fire_time`,`schedule_mode`,`cron_expression`,`last_run_id`,`updated_at` FROM `system_task_state`")
            states = {row.get('task_key'): row for row in db.fetchall()}

            db.execute(
                "SELECT `run_id`,`task_key`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`status`,`start_time`,`end_time`,`duration_seconds`,`message` "
                "FROM `system_task_run` ORDER BY `created_at` DESC LIMIT %s",
                (200,),
            )
            last_runs = {}
            for row in db.fetchall():
                task_key = row.get('task_key')
                if task_key and task_key not in last_runs:
                    last_runs[task_key] = row
            tasks = []
            for task in registry.visible_tasks():
                data = task.to_dict()
                state = states.get(task.key, {})
                running_row = running.get(task.key)
                effective_schedule = effective_schedule_for_task(task, state)
                data['enabled'] = bool(int(state.get('enabled', 1) or 0)) if state else task.enabled_by_default
                data['running'] = running_row is not None
                data['running_run_id'] = running_row.get('run_id') if running_row else ''
                data['last_fire_time'] = state.get('last_fire_time') if state else ''
                data['next_fire_time'] = state.get('next_fire_time') if state else ''
                data['last_run_id'] = state.get('last_run_id') if state else ''
                data['schedule_mode'] = effective_schedule.get('mode')
                data['cron_expression'] = effective_schedule.get('cron_expression')
                data['schedule_customized'] = effective_schedule.get('mode') == SCHEDULE_MODE_CRON
                data['default_schedule_text'] = registry.schedule_text(task.schedule)
                data['effective_schedule_text'] = effective_schedule.get('text') or data.get('schedule_text') or ''
                data['schedule_message'] = effective_schedule.get('message') or ''
                data['schedule_valid'] = bool(effective_schedule.get('valid'))
                _apply_runtime_fields(task, data, running_row, last_runs.get(task.key))
                tasks.append(data)

            db.execute(
                "SELECT `run_id`,`task_key`,`task_name`,`category`,`trigger_type`,`run_date`,`trade_date`,`pipeline_run_id`,`parent_run_id`,`attempt`,`skip_reason`,`status`,`pid`,`lock_group`,`start_time`,`end_time`,`duration_seconds`,`log_path`,`message` "
                "FROM `system_task_run` ORDER BY `created_at` DESC LIMIT %s",
                (int(run_limit),),
            )
            recent = db.fetchall()

            db.execute(
                "SELECT `run_date`,`job_name`,`start_time`,`end_time`,`status`,`duration_seconds`,`rows_written`,`message` FROM `job_run_log` ORDER BY `created_at` DESC LIMIT %s",
                (int(job_limit),),
            )
            job_recent = db.fetchall()

            db.execute(
                "SELECT `notice_id`,`level`,`task_key`,`title`,`message`,`status`,`created_at`,`ack_at`,`resolved_at` FROM `system_task_notice` ORDER BY `created_at` DESC LIMIT %s",
                (int(notice_limit),),
            )
            notice_rows = db.fetchall()

    scheduler = scheduler_heartbeat()
    return {
        'today': today.strftime('%Y-%m-%d'),
        'summary': summary,
        'open_notices': open_notices,
        'scheduler_updated_at': scheduler_updated_at,
        'tasks': _rows_to_dicts(tasks),
        'recent': _rows_to_dicts(_enrich_run_rows(list(recent))),
        'job_recent': _rows_to_dicts(job_recent),
        'notices': _rows_to_dicts(notice_rows),
        **scheduler,
    }


def ack_notice(notice_id):
    if not notice_id:
        return False, '缺少通知ID'
    _execute("UPDATE `system_task_notice` SET `status`=%s,`ack_at`=%s WHERE `notice_id`=%s AND `status`=%s", (NOTICE_STATUS_ACK, _now(), notice_id, NOTICE_STATUS_OPEN))
    return True, '已确认通知'


def ack_all_notices(task_key=''):
    params = [NOTICE_STATUS_ACK, _now(), NOTICE_STATUS_OPEN]
    where = "`status`=%s"
    if task_key:
        where += " AND `task_key`=%s"
        params.append(task_key)
    _execute(f"UPDATE `system_task_notice` SET `status`=%s,`ack_at`=%s WHERE {where}", tuple(params))
    return True, '已确认全部通知'


def read_log(run_id, max_chars=12000):
    try:
        max_chars = int(max_chars or 12000)
    except Exception:
        max_chars = 12000
    max_chars = max(1000, min(MAX_LOG_READ_CHARS, max_chars))
    rows = _query("SELECT `run_id`,`status`,`log_path` FROM `system_task_run` WHERE `run_id`=%s", (run_id,))
    if not rows or not rows[0].get('log_path'):
        return False, '未找到日志文件'
    row = rows[0]
    log_path = Path(row.get('log_path')).resolve()
    log_root = _log_dir().resolve()
    if log_root not in log_path.parents and log_path != log_root:
        return False, '日志路径不合法'
    if not log_path.exists():
        return False, '日志文件不存在'
    text = log_path.read_text(encoding='utf-8', errors='replace')
    log_size = len(text)
    truncated = log_size > max_chars
    return True, {
        'run_id': row.get('run_id') or run_id,
        'status': row.get('status') or '',
        'log': text[-max_chars:],
        'log_size': log_size,
        'max_chars': max_chars,
        'truncated': truncated,
    }

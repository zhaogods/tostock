#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json
import logging
from abc import ABC

from tornado import gen

import instock.core.singleton_stock_web_module_data as sswmd
import instock.web.base as webBase
from instock.lib import task_runner


def _json_default(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)


class _JsonMixin:
    def write_json(self, data, status=200):
        self.set_status(status)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        self.write(json.dumps(data, ensure_ascii=False, default=_json_default))

    def write_error_json(self, message, status=400, **extra):
        payload = {'ok': False, 'message': message}
        payload.update(extra)
        self.write_json(payload, status)


class ConsoleHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        self.render(
            'console.html',
            web_module_data=sswmd.stock_web_module_data().get_data('console'),
            leftMenu=webBase.GetLeftMenu(self.request.uri),
        )


class ConsoleOverviewApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            task_runner.ensure_task_states()
            self.write_json({'ok': True, 'overview': task_runner.overview()})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleOverviewApiHandler处理异常：{e}")
            self.write_error_json('获取系统状态失败', 500)


class ConsoleTasksApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            task_runner.ensure_task_states()
            tasks = task_runner.task_payloads()
            groups = {'fixed': [], 'manual': [], 'notify': []}
            for task in tasks:
                groups.setdefault(task.get('category'), []).append(task)
            self.write_json({'ok': True, 'tasks': tasks, 'groups': groups})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleTasksApiHandler处理异常：{e}")
            self.write_error_json('获取任务列表失败', 500)


class ConsoleRunsApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            limit = int(self.get_argument('limit', default='30', strip=False))
            self.write_json({
                'ok': True,
                'runs': task_runner.recent_runs(limit),
                'job_runs': task_runner.recent_job_runs(20),
            })
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleRunsApiHandler处理异常：{e}")
            self.write_error_json('获取运行记录失败', 500)


class ConsoleNoticesApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            limit = int(self.get_argument('limit', default='20', strip=False))
            self.write_json({'ok': True, 'notices': task_runner.notices(limit)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleNoticesApiHandler处理异常：{e}")
            self.write_error_json('获取通知失败', 500)


class ConsoleLogApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            run_id = self.get_argument('run_id', default='', strip=False)
            ok, result = task_runner.read_log(run_id)
            if not ok:
                self.write_error_json(result, 404)
                return
            self.write_json({'ok': True, 'log': result})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleLogApiHandler处理异常：{e}")
            self.write_error_json('读取日志失败', 500)


class ConsoleStatusApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            task_runner.ensure_task_states()
            snapshot = task_runner.console_snapshot()
            self.write_json({
                'ok': True,
                'today': snapshot.get('today'),
                'summary': snapshot.get('summary'),
                'tasks': snapshot.get('tasks'),
                'recent': snapshot.get('recent'),
                'job_recent': snapshot.get('job_recent'),
                'notices': snapshot.get('notices'),
                'overview': {
                    'today': snapshot.get('today'),
                    'summary': snapshot.get('summary'),
                    'open_notices': snapshot.get('open_notices'),
                    'scheduler_enabled': snapshot.get('scheduler_enabled'),
                    'scheduler_alive': snapshot.get('scheduler_alive'),
                    'scheduler_heartbeat_at': snapshot.get('scheduler_heartbeat_at'),
                    'scheduler_heartbeat_age_seconds': snapshot.get('scheduler_heartbeat_age_seconds'),
                    'scheduler_heartbeat_stale_seconds': snapshot.get('scheduler_heartbeat_stale_seconds'),
                    'scheduler_updated_at': snapshot.get('scheduler_updated_at'),
                },
            })
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleStatusApiHandler处理异常：{e}")
            self.write_error_json('获取控制台状态失败', 500)


class ConsoleStartApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            task_key = self.get_argument('task', default='', strip=False) or self.get_argument('task_key', default='', strip=False)
            date_arg = self.get_argument('date', default='', strip=False)
            start_date = self.get_argument('start_date', default='', strip=False)
            end_date = self.get_argument('end_date', default='', strip=False)
            ok, result = task_runner.start_task(task_key, trigger_type='manual', date_arg=date_arg, start_date=start_date, end_date=end_date)
            payload = {'ok': ok}
            payload.update(result)
            self.write_json(payload, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleStartApiHandler处理异常：{e}")
            self.write_error_json('任务启动失败', 500)


class ConsoleStopApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            run_id = self.get_argument('run_id', default='', strip=False)
            task_key = self.get_argument('task', default='', strip=False) or self.get_argument('task_key', default='', strip=False)
            ok, result = task_runner.stop_task(run_id=run_id, task_key=task_key)
            payload = {'ok': ok}
            payload.update(result)
            self.write_json(payload, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleStopApiHandler处理异常：{e}")
            self.write_error_json('停止任务失败', 500)


class ConsoleEnableApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            task_key = self.get_argument('task', default='', strip=False) or self.get_argument('task_key', default='', strip=False)
            enabled = self.get_argument('enabled', default='1', strip=False) in ('1', 'true', 'True', 'yes', 'on')
            ok, message = task_runner.set_task_enabled(task_key, enabled)
            self.write_json({'ok': ok, 'message': message}, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleEnableApiHandler处理异常：{e}")
            self.write_error_json('更新任务启用状态失败', 500)


class ConsoleNoticeAckApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            notice_id = self.get_argument('notice_id', default='', strip=False)
            ok, message = task_runner.ack_notice(notice_id)
            self.write_json({'ok': ok, 'message': message}, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleNoticeAckApiHandler处理异常：{e}")
            self.write_error_json('确认通知失败', 500)

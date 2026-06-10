#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json
import logging
from abc import ABC

from tornado import gen

import instock.web.base as webBase
from instock.lib import console_service
from instock.lib import cron_utils
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


def _get_task_key(handler):
    return handler.get_argument('task_key', default='', strip=False) or handler.get_argument('task', default='', strip=False)


def _parse_bool_arg(value, default=True):
    if value is None or value == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


class ConsoleHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        self.render(
            'console_v2.html',
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
            groups = {}
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
            job_recent = task_runner.recent_job_runs(20)
            self.write_json({
                'ok': True,
                'runs': task_runner.recent_runs(limit),
                'job_recent': job_recent,
                'job_runs': job_recent,
            })
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleRunsApiHandler处理异常：{e}")
            self.write_error_json('获取运行记录失败', 500)


class ConsoleNoticesApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            limit = int(self.get_argument('limit', default='20', strip=False))
            task_key = self.get_argument('task_key', default='', strip=False)
            status = self.get_argument('status', default='', strip=False)
            self.write_json({'ok': True, 'notices': task_runner.notices(limit, task_key=task_key, status=status)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleNoticesApiHandler处理异常：{e}")
            self.write_error_json('获取通知失败', 500)


class ConsoleLogApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            run_id = self.get_argument('run_id', default='', strip=False)
            max_chars = self.get_argument('max_chars', default='12000', strip=False)
            ok, result = task_runner.read_log(run_id, max_chars=max_chars)
            if not ok:
                self.write_error_json(result, 404)
                return
            payload = {'ok': True}
            if isinstance(result, dict):
                payload.update(result)
            else:
                payload['log'] = result
            self.write_json(payload)
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


class ConsoleDashboardApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            date_arg = self.get_argument('date', default='', strip=False)
            self.write_json({'ok': True, 'dashboard': console_service.get_console_dashboard(date_arg)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleDashboardApiHandler处理异常：{e}")
            self.write_error_json('获取控制台总览失败', 500)


class ConsoleHealthApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            self.write_json({'ok': True, 'health': console_service.get_system_health()})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleHealthApiHandler处理异常：{e}")
            self.write_error_json('获取系统健康状态失败', 500)


class ConsoleReportsApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            limit = int(self.get_argument('limit', default='20', strip=False))
            self.write_json({'ok': True, 'reports': console_service.get_recent_reports(limit)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleReportsApiHandler处理异常：{e}")
            self.write_error_json('获取复盘报告列表失败', 500)


class ConsoleQualityApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            date_arg = self.get_argument('date', default='', strip=False)
            self.write_json({'ok': True, 'quality': console_service.get_data_quality_summary(date_arg)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleQualityApiHandler处理异常：{e}")
            self.write_error_json('获取数据质量摘要失败', 500)


class ConsoleAssetsApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            date_arg = self.get_argument('date', default='', strip=False)
            self.write_json({'ok': True, 'data_assets': console_service.get_data_assets(date_arg)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleAssetsApiHandler处理异常：{e}")
            self.write_error_json('获取数据资产状态失败', 500)


class ConsoleStrategiesApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            days = int(self.get_argument('days', default='7', strip=False))
            self.write_json({'ok': True, 'strategies': console_service.get_strategy_performance(days)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleStrategiesApiHandler处理异常：{e}")
            self.write_error_json('获取策略表现失败', 500)


class ConsolePipelineApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            date_arg = self.get_argument('date', default='', strip=False)
            self.write_json({'ok': True, 'pipeline': console_service.get_pipeline_map(date_arg)})
        except Exception as e:
            logging.error(f"consoleHandler.ConsolePipelineApiHandler处理异常：{e}")
            self.write_error_json('获取任务管线失败', 500)


class ConsoleSchedulePreviewApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def get(self):
        try:
            cron_expression = self.get_argument('cron', default='', strip=False)
            ok, message = cron_utils.validate_cron_expression(cron_expression)
            next_fire_time = cron_utils.next_fire_after(cron_expression) if ok else None
            self.write_json({
                'ok': ok,
                'message': message,
                'cron_expression': cron_expression,
                'schedule_text': cron_utils.describe_cron_expression(cron_expression) if ok else '',
                'next_fire_time': next_fire_time,
            }, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleSchedulePreviewApiHandler处理异常：{e}")
            self.write_error_json('校验计划失败', 500)


class ConsoleScheduleApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            task_key = _get_task_key(self)
            schedule_mode = self.get_argument('schedule_mode', default='default', strip=False)
            cron_expression = self.get_argument('cron_expression', default='', strip=False)
            ok, result = task_runner.set_task_schedule(task_key, schedule_mode, cron_expression)
            payload = {'ok': ok}
            payload.update(result)
            self.write_json(payload, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleScheduleApiHandler处理异常：{e}")
            self.write_error_json('保存任务计划失败', 500)


class ConsoleStartApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            task_key = _get_task_key(self)
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
            task_key = _get_task_key(self)
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
            task_key = _get_task_key(self)
            enabled = _parse_bool_arg(self.get_argument('enabled', default='1', strip=False), True)
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


class ConsoleNoticeAckAllApiHandler(webBase.BaseHandler, _JsonMixin, ABC):
    def post(self):
        try:
            task_key = self.get_argument('task_key', default='', strip=False)
            ok, message = task_runner.ack_all_notices(task_key=task_key)
            self.write_json({'ok': ok, 'message': message}, 200 if ok else 400)
        except Exception as e:
            logging.error(f"consoleHandler.ConsoleNoticeAckAllApiHandler处理异常：{e}")
            self.write_error_json('批量确认通知失败', 500)

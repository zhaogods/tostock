#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass, asdict


CATEGORY_FIXED = 'fixed'
CATEGORY_MANUAL = 'manual'
CATEGORY_NOTIFY = 'notify'
CATEGORY_INTERNAL = 'internal'

TARGET_SCRIPT = 'script'
TARGET_CALLABLE = 'callable'
TARGET_BUILTIN = 'builtin'
TARGET_NOTIFY = 'notify'


@dataclass(frozen=True)
class TaskDefinition:
    key: str
    name: str
    category: str
    description: str
    target_type: str
    script: str = ''
    callable_path: str = ''
    builtin: str = ''
    schedule: dict | None = None
    allow_manual_start: bool = False
    allow_stop: bool = False
    allow_date_args: bool = False
    fixed: bool = False
    visible: bool = True
    lock_group: str = ''
    timeout_seconds: int = 0
    warning: str = ''
    display_order: int = 100
    enabled_by_default: bool = True

    def to_dict(self):
        data = asdict(self)
        data['schedule_text'] = schedule_text(self.schedule)
        return data


TASKS = (
    TaskDefinition(
        key='realtime_refresh',
        name='盘中实时刷新',
        category=CATEGORY_FIXED,
        description='刷新个股与 ETF 盘中基础行情。',
        target_type=TARGET_SCRIPT,
        script='realtime_only_job.py',
        schedule={
            'type': 'interval_in_windows',
            'weekdays': [0, 1, 2, 3, 4],
            'windows': [('09:00', '11:30'), ('13:00', '15:30')],
            'interval_minutes': 30,
        },
        allow_manual_start=True,
        allow_stop=True,
        fixed=True,
        visible=True,
        lock_group='market_data_write',
        warning='会刷新当天行情数据，不要和收盘后全量任务同时运行。',
        display_order=10,
    ),
    TaskDefinition(
        key='proxy_refresh',
        name='刷新代理池',
        category=CATEGORY_FIXED,
        description='刷新 Eastmoney 等外部请求可用代理。',
        target_type=TARGET_CALLABLE,
        callable_path='instock.core.proxy_fetcher:refresh_proxy_pool',
        schedule={
            'type': 'interval_in_windows',
            'weekdays': [0, 1, 2, 3, 4],
            'windows': [('09:00', '11:30'), ('13:00', '15:30')],
            'interval_minutes': 30,
        },
        allow_manual_start=True,
        allow_stop=False,
        fixed=True,
        visible=True,
        lock_group='proxy_refresh',
        display_order=20,
    ),
    TaskDefinition(
        key='daily_pipeline',
        name='收盘后全量任务',
        category=CATEGORY_FIXED,
        description='执行完整收盘后数据、指标、策略、排行和日报流程。',
        target_type=TARGET_SCRIPT,
        script='execute_daily_job.py',
        schedule={'type': 'daily_at', 'weekdays': [0, 1, 2, 3, 4], 'time': '17:30'},
        allow_manual_start=True,
        allow_stop=True,
        fixed=True,
        visible=True,
        lock_group='market_data_write',
        timeout_seconds=14400,
        warning='全量任务会写入大量数据，并与盘中实时刷新互斥。',
        display_order=30,
    ),
    TaskDefinition(
        key='hist_cache_cleanup',
        name='清理历史缓存',
        category=CATEGORY_FIXED,
        description='清理历史 K 线缓存目录，让后续任务重新拉取缓存。',
        target_type=TARGET_BUILTIN,
        builtin='cleanup_hist_cache',
        schedule={'type': 'weekly_at', 'weekdays': [2, 5], 'time': '10:30'},
        allow_manual_start=True,
        allow_stop=False,
        fixed=True,
        visible=True,
        lock_group='cache_cleanup',
        warning='只会清理项目内 instock/cache/hist 目录。',
        display_order=40,
    ),
    TaskDefinition(
        key='init_database',
        name='初始化/检查表结构',
        category=CATEGORY_MANUAL,
        description='检查数据库并创建缺失的项目表。',
        target_type=TARGET_SCRIPT,
        script='init_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='database_schema',
        warning='用于首次部署或表结构变更后修复。',
        display_order=110,
    ),
    TaskDefinition(
        key='daily_report_rebuild',
        name='重新生成每日复盘',
        category=CATEGORY_MANUAL,
        description='按指定交易日重新生成 Markdown 每日复盘报告。',
        target_type=TARGET_SCRIPT,
        script='daily_report_job.py',
        allow_manual_start=True,
        allow_stop=False,
        allow_date_args=True,
        visible=True,
        lock_group='report',
        display_order=120,
    ),
    TaskDefinition(
        key='backtest_data_fill',
        name='补齐回测数据',
        category=CATEGORY_MANUAL,
        description='填充策略表 rate_* 回测收益字段。',
        target_type=TARGET_SCRIPT,
        script='backtest_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=True,
        visible=True,
        lock_group='backtest',
        timeout_seconds=21600,
        warning='可能耗时较长，建议在非交易时段运行。',
        display_order=130,
    ),
    TaskDefinition(
        key='backtest_rank_rebuild',
        name='重算回测排行',
        category=CATEGORY_MANUAL,
        description='根据策略表 rate_* 字段重新生成回测排行榜。',
        target_type=TARGET_SCRIPT,
        script='backtest_rank_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        allow_date_args=True,
        visible=True,
        lock_group='backtest',
        warning='建议先完成回测数据补齐。',
        display_order=140,
    ),
    TaskDefinition(
        key='daily_pipeline_monitor',
        name='日终任务监控',
        category=CATEGORY_NOTIFY,
        description='检查工作日日终任务是否成功完成，异常时生成通知。',
        target_type=TARGET_NOTIFY,
        builtin='check_daily_pipeline',
        schedule={'type': 'monitor_interval', 'minutes': 30},
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='notice',
        display_order=210,
    ),
    TaskDefinition(
        key='data_quality_monitor',
        name='数据质量监控',
        category=CATEGORY_NOTIFY,
        description='检查数据质量日志中的 error/warning 并生成通知。',
        target_type=TARGET_NOTIFY,
        builtin='check_data_quality',
        schedule={'type': 'monitor_interval', 'minutes': 30},
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='notice',
        display_order=220,
    ),
    TaskDefinition('basic_data_daily_job', '基础行情子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='basic_data_daily_job.py', visible=False, lock_group='market_data_write', display_order=310),
    TaskDefinition('selection_data_daily_job', '综合选股子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='selection_data_daily_job.py', visible=False, display_order=320),
    TaskDefinition('basic_data_after_close_daily_job', '闭盘数据子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='basic_data_after_close_daily_job.py', visible=False, display_order=330),
    TaskDefinition('basic_data_other_daily_job', '其他基础数据子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='basic_data_other_daily_job.py', visible=False, display_order=340),
    TaskDefinition('indicators_data_daily_job', '指标数据子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='indicators_data_daily_job.py', visible=False, display_order=350),
    TaskDefinition('klinepattern_data_daily_job', 'K线形态子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='klinepattern_data_daily_job.py', visible=False, display_order=360),
    TaskDefinition('strategy_data_daily_job', '策略数据子任务', CATEGORY_INTERNAL, '日终流水线内部阶段。', TARGET_SCRIPT, script='strategy_data_daily_job.py', visible=False, display_order=370),
)


_TASKS_BY_KEY = {task.key: task for task in TASKS}


def get_task(task_key):
    return _TASKS_BY_KEY.get(task_key)


def all_tasks(include_internal=True):
    tasks = TASKS if include_internal else [task for task in TASKS if task.category != CATEGORY_INTERNAL]
    return sorted(tasks, key=lambda task: task.display_order)


def visible_tasks():
    return [task for task in all_tasks(include_internal=False) if task.visible]


def grouped_tasks():
    groups = {CATEGORY_FIXED: [], CATEGORY_MANUAL: [], CATEGORY_NOTIFY: [], CATEGORY_INTERNAL: []}
    for task in all_tasks():
        groups[task.category].append(task)
    return groups


def schedule_text(schedule):
    if not schedule:
        return ''
    schedule_type = schedule.get('type')
    if schedule_type == 'interval_in_windows':
        windows = '，'.join(f"{start}-{end}" for start, end in schedule.get('windows', ()))
        return f"工作日 {windows} 每 {schedule.get('interval_minutes')} 分钟"
    if schedule_type == 'daily_at':
        return f"工作日 {schedule.get('time')}"
    if schedule_type == 'weekly_at':
        weekdays = {'0': '周一', '1': '周二', '2': '周三', '3': '周四', '4': '周五', '5': '周六', '6': '周日'}
        names = '、'.join(weekdays.get(str(day), str(day)) for day in schedule.get('weekdays', ()))
        return f"{names} {schedule.get('time')}"
    if schedule_type == 'monitor_interval':
        return f"每 {schedule.get('minutes')} 分钟检查"
    return schedule_type or ''

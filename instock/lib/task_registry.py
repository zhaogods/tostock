#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass, asdict


STAGE_FETCH = 'fetch'
STAGE_COMPUTE = 'compute'
STAGE_BACKTEST = 'backtest'
STAGE_REPORT = 'report'
STAGE_SYSTEM = 'system'
STAGE_MONITOR = 'monitor'

STAGE_ORDER = [STAGE_FETCH, STAGE_COMPUTE, STAGE_BACKTEST, STAGE_REPORT, STAGE_SYSTEM, STAGE_MONITOR]

STAGE_LABELS = {
    STAGE_FETCH: '数据拉取',
    STAGE_COMPUTE: '数据计算',
    STAGE_BACKTEST: '回测验证',
    STAGE_REPORT: '报告产出',
    STAGE_SYSTEM: '系统维护',
    STAGE_MONITOR: '监控通知',
}

STAGE_DESCRIPTIONS = {
    STAGE_FETCH: '从东方财富、Tushare 等外部 API 拉取原始行情与基本面数据。',
    STAGE_COMPUTE: '基于历史 K 线和 TA-Lib 计算技术指标、K 线形态、策略筛选。',
    STAGE_BACKTEST: '对策略选股结果填充未来 N 日收益率，汇总回测排行。',
    STAGE_REPORT: '根据当日全量数据生成 Markdown 每日复盘报告。',
    STAGE_SYSTEM: '数据库建表、缓存清理、代理池维护等基础设施操作。',
    STAGE_MONITOR: '检查日终管线是否完成、数据质量是否异常，生成通知。',
}

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
    feeds_pages: str = ''

    def to_dict(self):
        data = asdict(self)
        data['schedule_text'] = schedule_text(self.schedule)
        return data


TASKS = (
    TaskDefinition(
        key='daily_pipeline',
        name='收盘后全量任务',
        category=STAGE_FETCH,
        description='一键运行完整管线：数据拉取 → 计算 → 回测 → 报告。',
        target_type=TARGET_SCRIPT,
        script='execute_daily_job.py',
        schedule={'type': 'daily_at', 'weekdays': [0, 1, 2, 3, 4], 'time': '17:30'},
        allow_manual_start=True,
        allow_stop=True,
        fixed=True,
        visible=True,
        lock_group='market_data_write',
        timeout_seconds=21600,
        warning='全量任务会写入大量数据并执行回测，建议只在收盘后运行。',
        display_order=5,
        feeds_pages='全部数据页面',
    ),
    TaskDefinition(
        key='realtime_refresh',
        name='盘中实时刷新',
        category=STAGE_FETCH,
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
        feeds_pages='每日股票数据、每日ETF数据',
    ),
    TaskDefinition(
        key='proxy_refresh',
        name='刷新代理池',
        category=STAGE_FETCH,
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
        key='basic_data_daily_job',
        name='当日行情拉取',
        category=STAGE_FETCH,
        description='拉取全 A 股当日实时行情（价、量、PE/PB/ROE）及 ETF 行情。',
        target_type=TARGET_SCRIPT,
        script='basic_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='market_data_write',
        warning='盘中运行时，数据可能不完整（成交量未最终确定）。',
        display_order=30,
        feeds_pages='每日股票数据、每日ETF数据',
    ),
    TaskDefinition(
        key='selection_data_daily_job',
        name='综合选股数据',
        category=STAGE_FETCH,
        description='拉取东方财富综合选股页面数据（200+ 字段：财务、技术、机构、人气）。',
        target_type=TARGET_SCRIPT,
        script='selection_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        display_order=40,
        feeds_pages='综合选股',
    ),
    TaskDefinition(
        key='basic_data_after_close_daily_job',
        name='收盘后数据拉取',
        category=STAGE_FETCH,
        description='拉取收盘后才有的数据：大宗交易、尾盘抢筹。',
        target_type=TARGET_SCRIPT,
        script='basic_data_after_close_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        warning='大宗交易数据通常在 17:00 后才可获取。',
        display_order=50,
        feeds_pages='尾盘抢筹数据、股票大宗交易',
    ),
    TaskDefinition(
        key='basic_data_other_daily_job',
        name='其他日频数据拉取',
        category=STAGE_FETCH,
        description='拉取资金流向（个股+行业+概念）、龙虎榜、分红配送、早盘抢筹、涨停原因、基本面选股。',
        target_type=TARGET_SCRIPT,
        script='basic_data_other_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='market_data_write',
        display_order=60,
        feeds_pages='股票资金流向、行业资金流向、概念资金流向、股票龙虎榜、股票分红配送、早盘抢筹数据、涨停原因揭密、基本面选股',
    ),
    TaskDefinition(
        key='indicators_data_daily_job',
        name='技术指标计算',
        category=STAGE_COMPUTE,
        description='拉取近 3 年历史 K 线，用 TA-Lib 计算 60+ 技术指标（MACD/KDJ/BOLL/RSI 等），并筛选买卖信号。',
        target_type=TARGET_SCRIPT,
        script='indicators_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=True,
        visible=True,
        timeout_seconds=7200,
        warning='需先完成当日行情拉取，否则指标基于旧数据计算。',
        display_order=110,
        feeds_pages='股票指标数据、股票指标买入、股票指标卖出',
    ),
    TaskDefinition(
        key='klinepattern_data_daily_job',
        name='K线形态识别',
        category=STAGE_COMPUTE,
        description='拉取近 3 年历史 K 线，用 TA-Lib 识别 60+ K 线形态（晨星/三乌鸦/锤头等）。',
        target_type=TARGET_SCRIPT,
        script='klinepattern_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        timeout_seconds=7200,
        warning='需先完成当日行情拉取。',
        display_order=120,
        feeds_pages='股票K线形态',
    ),
    TaskDefinition(
        key='strategy_data_daily_job',
        name='策略筛选',
        category=STAGE_COMPUTE,
        description='运行 10 个交易策略（海龟/均线多头/突破平台/放量上涨等），筛选符合条件的股票。',
        target_type=TARGET_SCRIPT,
        script='strategy_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=True,
        visible=True,
        timeout_seconds=7200,
        warning='需先完成技术指标计算，策略依赖历史 K 线数据。',
        display_order=130,
        feeds_pages='放量上涨、均线多头、停机坪、回踩年线、突破平台、无大幅回撤、海龟交易法则、高而窄的旗形、放量跌停、低ATR成长',
    ),
    TaskDefinition(
        key='backtest_data_fill',
        name='回测收益填充',
        category=STAGE_BACKTEST,
        description='对每行选股结果，拉取 3 年历史 K 线，计算未来 1~100 日收益率（rate_1~rate_100）。',
        target_type=TARGET_SCRIPT,
        script='backtest_data_daily_job.py',
        allow_manual_start=True,
        allow_stop=True,
        visible=True,
        lock_group='market_data_write',
        timeout_seconds=21600,
        warning='依赖策略筛选结果，耗时可能很长。',
        display_order=210,
        feeds_pages='策略回测排行（收益数据）',
    ),
    TaskDefinition(
        key='backtest_rank_rebuild',
        name='回测排行重算',
        category=STAGE_BACKTEST,
        description='根据策略表的 rate_* 字段，按策略汇总计算平均收益、胜率、最佳/最差收益。',
        target_type=TARGET_SCRIPT,
        script='backtest_rank_daily_job.py',
        allow_manual_start=True,
        allow_stop=False,
        allow_date_args=True,
        visible=True,
        lock_group='market_data_write',
        warning='需先完成回测收益填充，否则排行数据为空。',
        display_order=220,
        feeds_pages='策略回测排行',
    ),
    TaskDefinition(
        key='daily_report_rebuild',
        name='生成每日复盘报告',
        category=STAGE_REPORT,
        description='按指定交易日生成 Markdown 每日复盘报告。',
        target_type=TARGET_SCRIPT,
        script='daily_report_job.py',
        allow_manual_start=True,
        allow_stop=False,
        allow_date_args=True,
        visible=True,
        lock_group='report',
        warning='需先完成当日全量数据拉取和计算。',
        display_order=310,
        feeds_pages='每日复盘报告',
    ),
    TaskDefinition(
        key='init_database',
        name='初始化/检查表结构',
        category=STAGE_SYSTEM,
        description='检查数据库并创建缺失的项目表。',
        target_type=TARGET_SCRIPT,
        script='init_job.py',
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='database_schema',
        warning='用于首次部署或表结构变更后修复。',
        display_order=410,
    ),
    TaskDefinition(
        key='hist_cache_cleanup',
        name='清理历史缓存',
        category=STAGE_SYSTEM,
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
        display_order=420,
    ),
    TaskDefinition(
        key='daily_pipeline_monitor',
        name='日终任务监控',
        category=STAGE_MONITOR,
        description='检查工作日日终任务是否成功完成，异常时生成通知。',
        target_type=TARGET_NOTIFY,
        builtin='check_daily_pipeline',
        schedule={'type': 'monitor_interval', 'minutes': 30},
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='notice',
        display_order=510,
    ),
    TaskDefinition(
        key='data_quality_monitor',
        name='数据质量监控',
        category=STAGE_MONITOR,
        description='检查数据质量日志中的 error/warning 并生成通知。',
        target_type=TARGET_NOTIFY,
        builtin='check_data_quality',
        schedule={'type': 'monitor_interval', 'minutes': 30},
        allow_manual_start=True,
        allow_stop=False,
        visible=True,
        lock_group='notice',
        display_order=520,
    ),
)


_TASKS_BY_KEY = {task.key: task for task in TASKS}


def get_task(task_key):
    return _TASKS_BY_KEY.get(task_key)


def all_tasks(include_internal=True):
    return sorted(TASKS, key=lambda task: task.display_order)


def visible_tasks():
    return [task for task in all_tasks() if task.visible]


def grouped_tasks():
    groups = {stage: [] for stage in STAGE_ORDER}
    for task in all_tasks():
        groups.setdefault(task.category, []).append(task)
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

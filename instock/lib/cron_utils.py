#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cron 表达式工具

控制台任务调度使用标准 5 字段 crontab 参数格式：
minute hour day-of-month month day-of-week
"""

import datetime


__author__ = 'Kiro'
__date__ = '2026/06/09'


_FIELD_SPECS = (
    ('分钟', 0, 59),
    ('小时', 0, 23),
    ('日期', 1, 31),
    ('月份', 1, 12),
    ('星期', 0, 7),
)

_WEEKDAY_NAMES = {
    0: '周日',
    1: '周一',
    2: '周二',
    3: '周三',
    4: '周四',
    5: '周五',
    6: '周六',
    7: '周日',
}


def _parse_int(value, field_name):
    try:
        return int(value)
    except Exception:
        raise ValueError(f'{field_name}字段包含非法数字：{value}')


def _range_values(token, field_name, min_value, max_value):
    if token == '*':
        return min_value, max_value
    if '-' in token:
        start_text, end_text = token.split('-', 1)
        start = _parse_int(start_text, field_name)
        end = _parse_int(end_text, field_name)
    else:
        start = end = _parse_int(token, field_name)
    if start < min_value or end > max_value or start > end:
        raise ValueError(f'{field_name}字段范围应为 {min_value}-{max_value}')
    return start, end


def _parse_field(field_text, field_name, min_value, max_value):
    field_text = str(field_text or '').strip()
    if not field_text:
        raise ValueError(f'{field_name}字段不能为空')

    values = set()
    for raw_token in field_text.split(','):
        token = raw_token.strip()
        if not token:
            raise ValueError(f'{field_name}字段包含空片段')
        if '/' in token:
            range_part, step_text = token.split('/', 1)
            step = _parse_int(step_text, field_name)
            if step <= 0:
                raise ValueError(f'{field_name}字段步长必须大于 0')
        else:
            range_part = token
            step = 1
        start, end = _range_values(range_part, field_name, min_value, max_value)
        values.update(range(start, end + 1, step))

    if field_name == '星期' and 7 in values:
        values.add(0)
    return values


def parse_cron_expression(expression):
    """解析 5 字段 Cron 表达式，返回字段取值集合。"""
    parts = str(expression or '').strip().split()
    if len(parts) != 5:
        raise ValueError('Cron 表达式必须为 5 字段：分钟 小时 日期 月份 星期')
    parsed = []
    for value, (field_name, min_value, max_value) in zip(parts, _FIELD_SPECS):
        parsed.append(_parse_field(value, field_name, min_value, max_value))
    return parsed


def validate_cron_expression(expression):
    """校验 Cron 表达式，返回 (是否有效, 消息)。"""
    try:
        parse_cron_expression(expression)
        return True, 'Cron 表达式有效'
    except Exception as exc:
        return False, str(exc)


def _cron_weekday(value):
    # Python: Monday=0；Cron: Sunday=0/7, Monday=1。
    return (value.weekday() + 1) % 7


def cron_matches(expression, value=None):
    """判断指定时间是否命中 Cron 表达式。"""
    value = (value or datetime.datetime.now()).replace(second=0, microsecond=0)
    minute_set, hour_set, day_set, month_set, weekday_set = parse_cron_expression(expression)
    if value.minute not in minute_set or value.hour not in hour_set or value.month not in month_set:
        return False

    day_match = value.day in day_set
    weekday_match = _cron_weekday(value) in weekday_set
    day_any = len(day_set) == 31
    weekday_any = len(weekday_set.intersection(set(range(0, 7)))) == 7
    if not day_any and not weekday_any:
        return day_match or weekday_match
    return day_match and weekday_match


def next_fire_after(expression, after=None, max_days=366):
    """计算 after 之后下一次触发时间；找不到时返回 None。"""
    parse_cron_expression(expression)
    cursor = (after or datetime.datetime.now()).replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    max_minutes = int(max_days * 24 * 60)
    for _ in range(max_minutes):
        if cron_matches(expression, cursor):
            return cursor
        cursor += datetime.timedelta(minutes=1)
    return None


def _field_is_all(field):
    return str(field or '').strip() == '*'


def _weekday_text(field):
    values = _parse_field(field, '星期', 0, 7)
    normalized = sorted(value for value in values if value != 7)
    if normalized == list(range(0, 7)):
        return '每天'
    if normalized == [1, 2, 3, 4, 5]:
        return '工作日'
    return '、'.join(_WEEKDAY_NAMES.get(value, str(value)) for value in normalized)


def describe_cron_expression(expression):
    """生成简短展示文案。"""
    expression = str(expression or '').strip()
    ok, message = validate_cron_expression(expression)
    if not ok:
        return message
    minute, hour, day, month, weekday = expression.split()
    if _field_is_all(day) and _field_is_all(month):
        if minute.startswith('*/') and _field_is_all(hour):
            return f"{_weekday_text(weekday)} 每 {minute[2:]} 分钟"
        if minute.startswith('*/') and hour == '9-15':
            return f"{_weekday_text(weekday)} 9-15 点每 {minute[2:]} 分钟（含午休）"
        if minute.isdigit() and hour.isdigit():
            return f"{_weekday_text(weekday)} {int(hour):02d}:{int(minute):02d}"
    return f'Cron {expression}'

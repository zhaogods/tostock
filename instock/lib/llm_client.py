#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent LLM 客户端封装

LLM 仅作为系统监看摘要和选股报告解释增强；未启用、未安装依赖或调用失败时，
调用方必须继续使用规则化结果。
"""

import json
import logging
import time

from instock.lib import config


__author__ = 'Kiro'
__date__ = '2026/06/10'


_MAX_PROMPT_CHARS = 24000


def _short_text(value, max_chars=4000):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...（已截断 {len(text) - max_chars} 字符）"


def _disabled_result(message):
    return {
        'ok': False,
        'enabled': False,
        'text': '',
        'request_id': '',
        'model': config.get_agent_llm_model(),
        'input_tokens': 0,
        'output_tokens': 0,
        'duration_seconds': 0.0,
        'error': message,
    }


def llm_enabled():
    return config.get_agent_llm_enabled(False)


def _complete_anthropic(system_prompt, user_prompt, model, timeout):
    from anthropic import Anthropic

    api_key = config.get_anthropic_api_key()
    if not api_key:
        return _disabled_result('未配置 ANTHROPIC_API_KEY')

    client = Anthropic(api_key=api_key, timeout=timeout)
    response = client.messages.create(
        model=model,
        max_tokens=config.get_agent_llm_max_tokens(),
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    text_parts = []
    for block in getattr(response, 'content', []) or []:
        block_text = getattr(block, 'text', '')
        if block_text:
            text_parts.append(block_text)
    usage = getattr(response, 'usage', None)
    return {
        'ok': True,
        'enabled': True,
        'text': '\n'.join(text_parts).strip(),
        'request_id': getattr(response, 'id', '') or '',
        'model': model,
        'input_tokens': int(getattr(usage, 'input_tokens', 0) or 0) if usage else 0,
        'output_tokens': int(getattr(usage, 'output_tokens', 0) or 0) if usage else 0,
        'duration_seconds': 0.0,
        'error': '',
    }


def _complete_deepseek(system_prompt, user_prompt, model, timeout):
    import requests as req

    api_key = config.get_deepseek_api_key()
    if not api_key:
        return _disabled_result('未配置 DEEPSEEK_API_KEY')
    base_url = config.get_deepseek_base_url()

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': config.get_agent_llm_max_tokens(),
        'stream': False,
    }
    resp = req.post(f'{base_url}/v1/chat/completions', headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get('choices') or [{}])[0]
    usage = data.get('usage') or {}
    return {
        'ok': True,
        'enabled': True,
        'text': (choice.get('message') or {}).get('content', '').strip(),
        'request_id': data.get('id', '') or '',
        'model': data.get('model', model),
        'input_tokens': usage.get('prompt_tokens', 0),
        'output_tokens': usage.get('completion_tokens', 0),
        'duration_seconds': 0.0,
        'error': '',
    }


def complete_text(system_prompt, user_prompt):
    """调用 LLM API，支持 anthropic / deepseek；异常不会向上抛出。"""
    if not config.get_agent_llm_enabled(False):
        return _disabled_result('AGENT_LLM_ENABLED 未开启')
    provider = (config.get_agent_llm_provider() or '').strip().lower()
    model = config.get_agent_llm_model()
    timeout = config.get_agent_llm_timeout_seconds()
    user_prompt = _short_text(user_prompt, _MAX_PROMPT_CHARS)
    start = time.time()

    try:
        if provider == 'anthropic':
            result = _complete_anthropic(system_prompt, user_prompt, model, timeout)
        elif provider == 'deepseek':
            result = _complete_deepseek(system_prompt, user_prompt, model, timeout)
        else:
            return _disabled_result(f'暂不支持的 LLM provider：{provider}')
        result['duration_seconds'] = round(time.time() - start, 3)
        return result
    except Exception as exc:
        logging.error(f"llm_client.complete_text处理异常：{exc}")
        return {
            'ok': False,
            'enabled': True,
            'text': '',
            'request_id': '',
            'model': model,
            'input_tokens': 0,
            'output_tokens': 0,
            'duration_seconds': round(time.time() - start, 3),
            'error': str(exc)[:1800],
        }


def summarize_system_watch(context, findings):
    system_prompt = (
        '你是 A 股量化系统的运维分析助手。只根据用户提供的结构化 JSON 做摘要，'
        '不要编造未提供的事实，不要要求自动执行命令。输出中文 Markdown，包含：总体状态、关键异常、建议动作。'
    )
    user_prompt = {
        'task': '总结系统监看结果',
        'context': context,
        'findings': findings,
    }
    return complete_text(system_prompt, json.dumps(user_prompt, ensure_ascii=False, default=str))


def explain_selection_report(report_context, candidates):
    system_prompt = (
        '你是 A 股量化选股报告助手。只解释代码已经筛选和打分后的候选结果，'
        '不得新增未在候选列表中的股票，不得给出确定性收益承诺。输出中文 Markdown，'
        '突出数据质量、策略依据、资金流、风险提示，并声明不构成投资建议。'
    )
    user_prompt = {
        'task': '为每日选股报告生成解释性摘要',
        'report_context': report_context,
        'top_candidates': candidates[:20],
    }
    return complete_text(system_prompt, json.dumps(user_prompt, ensure_ascii=False, default=str))

#!/bin/sh

export PYTHONIOENCODING=utf-8
export LANG=zh_CN.UTF-8
export PYTHONPATH=/data/tostock
export LC_CTYPE=zh_CN.UTF-8

/usr/local/bin/python3 /data/tostock/instock/scheduler/scheduler_service.py

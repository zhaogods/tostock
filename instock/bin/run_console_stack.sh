#!/bin/sh

export PYTHONIOENCODING=utf-8
export LANG=zh_CN.UTF-8
export LC_CTYPE=zh_CN.UTF-8

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
export PYTHONPATH="$PROJECT_DIR"

"$PYTHON_BIN" "$PROJECT_DIR/instock/scheduler/scheduler_service.py" &
SCHEDULER_PID=$!

cleanup() {
    kill "$SCHEDULER_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "------调度服务已启动 PID: $SCHEDULER_PID------"
echo "------正在启动Web服务，请不要关闭本窗口------"
echo "访问地址 : http://localhost:9988/"
"$PYTHON_BIN" "$PROJECT_DIR/instock/web/web_service.py"

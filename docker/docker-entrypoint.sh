#!/bin/sh
set -e

# 等待 MariaDB 就绪
echo "等待数据库就绪..."
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python3 -c "
import pymysql, os
try:
    conn = pymysql.connect(
        host=os.environ.get('db_host', 'InStockDbService'),
        port=int(os.environ.get('db_port', 3306)),
        user=os.environ.get('db_user', 'root'),
        password=os.environ.get('db_password', ''),
        connect_timeout=3,
    )
    conn.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; then
        echo "数据库已就绪"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  等待数据库... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 3
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "错误: 数据库在 ${MAX_RETRIES} 次尝试后仍未就绪，继续启动（Web 服务可能会重试）"
fi

# 初始化数据库和表结构
echo "初始化数据库和表结构..."
python3 /data/tostock/instock/job/init_job.py

echo "启动 supervisord..."
exec supervisord -n -c /data/tostock/supervisor/supervisord.conf
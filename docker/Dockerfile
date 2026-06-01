# 基础镜像
# https://hub.docker.com/_/python/tags?page=1&name=3.11-slim-bullseye
FROM docker.io/python:3.11-slim-bullseye

MAINTAINER zhaogods
#增加语言utf-8
ENV LANG=zh_CN.UTF-8
ENV LC_CTYPE=zh_CN.UTF-8
ENV LC_ALL=C
ENV PYTHONPATH=/data/tostock
ENV TASK_SCHEDULER_ENABLED=true
EXPOSE 9988

# 设置时区为上海，安装编译依赖
# apt-get autoremove -y 删除没有用的依赖lib
# apt-get --purge remove 软件包名称 , 删除已安装包（不保留配置文件)
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    apt-get update && \
    apt-get install -y cron gcc make python3-dev default-libmysqlclient-dev build-essential pkg-config curl && \
    pip install --default-timeout=300 supervisor && \
    pip install --default-timeout=300 mysqlclient

COPY tostock/requirements.txt /tmp/requirements.txt
RUN sed '/TA_Lib/d' /tmp/requirements.txt > /tmp/requirements_docker.txt && \
    pip install --default-timeout=300 -r /tmp/requirements_docker.txt && \
    mkdir ta-lib && \
    curl -SL https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz | tar -xz --strip-components=1 -C ./ta-lib && \
    cd ta-lib/ && \
    ./configure && \
    make && \
    make install && \
    cd .. && \
    pip install TA-Lib && \
    rm -rf ta-lib* && \
    apt-get --purge remove -y gcc make python3-dev default-libmysqlclient-dev curl && \
    rm -rf /root/.cache/* && rm -rf /var/lib/apt/lists/* && apt-get clean && apt-get autoclean && apt-get autoremove -y

WORKDIR /data
#tostock软件
COPY tostock /data/tostock
COPY cron/cron.hourly /etc/cron.hourly
COPY cron/cron.workdayly /etc/cron.workdayly
COPY cron/cron.monthly /etc/cron.monthly

#add cron service.
# 任务调度默认由 supervisor 启动 run_scheduler；cron 保留但定时注释停用。
RUN chmod 755 /data/tostock/instock/bin/run_*.sh && \
    chmod 755 /etc/cron.hourly/* && chmod 755 /etc/cron.workdayly/* && chmod 755 /etc/cron.monthly/* && \
    echo "SHELL=/bin/sh \n\
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin \n\
# min hour day month weekday command \n\
# Cron scheduling is disabled; instock/lib/task_scheduler.py is the automatic scheduler. \n\
# */30 9,10,11,13,14,15 * * 1-5 /bin/run-parts /etc/cron.hourly \n\
# 30 17 * * 1-5 /bin/run-parts /etc/cron.workdayly \n\
# 30 10 * * 3,6 /bin/run-parts /etc/cron.monthly \n" > /var/spool/cron/crontabs/root && \
    chmod 600 /var/spool/cron/crontabs/root

ENTRYPOINT ["supervisord","-n","-c","/data/tostock/supervisor/supervisord.conf"]
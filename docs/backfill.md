# 历史数据回填

## 语法

```bash
docker exec InStock bash -c '
cd /data/tostock/instock/job

# 单日
python <job>.py 2026-05-15

# 多日枚举
python <job>.py 2026-05-15,2026-05-16

# 日期区间（自动跳过非交易日）
python <job>.py 2026-05-01 2026-05-31
'
```

## 完整管线（按顺序执行）

```bash
docker exec InStock bash -c '
cd /data/tostock/instock/job

python basic_data_daily_job.py 2026-05-01 2026-05-31
python selection_data_daily_job.py 2026-05-01 2026-05-31
python basic_data_after_close_daily_job.py 2026-05-01 2026-05-31
python basic_data_other_daily_job.py 2026-05-01 2026-05-31
python indicators_data_daily_job.py 2026-05-01 2026-05-31
python klinepattern_data_daily_job.py 2026-05-01 2026-05-31
python strategy_data_daily_job.py 2026-05-01 2026-05-31
python backtest_data_daily_job.py
python backtest_rank_daily_job.py 2026-05-01 2026-05-31
python daily_report_job.py 2026-05-01 2026-05-31
'
```

## 说明

- `backtest_data_daily_job.py` 不需要日期参数，自动扫描缺失回测数据的行并填补
- 各脚本内的 `run_with_args` 会自动跳过非交易日
- 批量回填建议在收盘后执行，避免 `is_cache` 被设为 `False`
- 可通过 `docker exec InStock tail -f /data/tostock/instock/log/stock_execute_job.log` 查看进度

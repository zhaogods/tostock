# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment and common commands

- Full local setup assumes Python 3.11, MySQL/MariaDB, and TA-Lib are installed.
- Install dependencies:
  - `python -m pip install -r requirements.txt`
- Upgrade dependencies after loosening pins in `requirements.txt`:
  - `python -m pip install -r requirements.txt --upgrade`
- The Windows wrapper scripts under `instock/bin/` change into the expected subdirectory before running Python entrypoints.

### Batch jobs

- Main daily pipeline:
  - `instock/bin/run_job.bat`
  - or run directly from `instock/job/`: `python execute_daily_job.py`
- `instock/lib/run_template.py` gives most job scripts the same CLI forms:
  - current trade date: `python execute_daily_job.py`
  - single date: `python execute_daily_job.py 2023-03-01`
  - comma-separated dates: `python execute_daily_job.py 2023-03-01,2023-03-02`
  - date range: `python execute_daily_job.py 2023-03-01 2023-03-21`
- Intraday lightweight refresh (spot prices only, no fund flow / event data):
  - `python realtime_only_job.py`
- Common individual job entrypoints under `instock/job/`:
  - `python init_job.py`
  - `python selection_data_daily_job.py`
  - `python basic_data_daily_job.py`
  - `python basic_data_other_daily_job.py`
  - `python basic_data_after_close_daily_job.py`
  - `python indicators_data_daily_job.py`
  - `python klinepattern_data_daily_job.py`
  - `python strategy_data_daily_job.py`
  - `python backtest_data_daily_job.py`

### Web and trading services

- Start the Tornado web app:
  - `instock/bin/run_web.bat`
  - or from `instock/web/`: `python web_service.py`
  - default URL: `http://localhost:9988/`
- Start the optional trading service:
  - `instock/bin/run_trade.bat`
  - or from `instock/trade/`: `python trade_service.py`

### Docker

- README documents a `docker run` flow rather than a compose-first workflow:
  - `docker network create InStockService`
  - `docker run -d --name InStockDbService --network InStockService -v /data/mariadb/data:/var/lib/instockdb -e MYSQL_ROOT_PASSWORD=root library/mariadb:latest`
  - `docker run -dit --name InStock --network=InStockService -p 9988:9988 -v /data/instockproxy.txt:/data/InStock/instock/config/proxy.txt -v /data/eastmoneycookie.txt:/data/InStock/instock/config/eastmoney_cookie.txt -v /data/tushare.json:/data/InStock/instock/config/tushare.json -e db_host=InStockDbService zsswwz/tostock:latest`
- A compose file exists at `docker/docker-compose.yml` if you want to inspect the default two-container layout.
- `docker/build.sh` is not a generic repo-root build script: it assembles a custom build context using `../../stock` before invoking `docker build`.

### Logs, linting, and tests

- Runtime logs are written under `instock/log/`:
  - batch jobs: `instock/log/stock_execute_job.log`
  - web: `instock/log/stock_web.log`
  - trading: `instock/log/stock_trade.log`
- No verified lint command is defined in this checkout.
- No automated test suite or single-test command was found in this checkout.

## Architecture overview

- `instock/` is the main application package. The codebase is organized around four concerns:
  - `core/`: market-data fetching, normalization, indicators, patterns, shared metadata
  - `job/`: runnable ETL/batch stages
  - `web/`: Tornado handlers, templates, and static assets for the UI
  - `trade/`: optional broker automation and strategy engine
- `instock/core/tablestructure.py` is the central schema and metadata registry. It defines database table structures, field labels, and the bindings used by strategies and candlestick-pattern jobs. When adding a new data table or UI module, start here.
- `instock/core/crawling/` contains source-specific fetchers (many now delegated to AkShare library calls). `instock/core/eastmoney_fetcher.py` is the shared Eastmoney HTTP client with cookie/proxy support, and `instock/core/stockfetch.py` is the normalization layer that converts upstream responses into DataFrames matching `tablestructure.py`.
- `instock/core/tushare_provider.py` is the Tushare adapter — it supplies `cn_stock_spot` (via `daily`+`daily_basic`) and `cn_stock_fund_flow` 今日 window (via `moneyflow`), with field mapping and 000001↔000001.SZ code conversion. Initialized on module import; falls back to crawlers if token is missing.
- Data source layering in `stockfetch.py`: Tushare (stock spot, fund flow 今日) → AkShare (ETF spot, event data like LHB/bonus/blocktrade) → legacy Eastmoney crawlers (selection, sector fund flow, chip race, limit-up reason).
- `instock/core/stockfetch.py` also owns the historical cache under `instock/cache/hist/`. Many higher-level features assume they can reuse cached historical data instead of refetching it.
- `instock/lib/database.py` is the database boundary. It builds the MySQL/MariaDB connection settings from in-code defaults plus environment overrides (`db_host`, `db_user`, `db_password`, `db_database`, `db_port`) and is responsible for inserting DataFrames, then adding primary keys and indexes after table creation.
- `instock/job/*.py` are standalone pipeline stages. `instock/lib/run_template.py` provides the shared “current date / list of dates / date range” CLI behavior and trade-day filtering used by these scripts.
- `instock/job/execute_daily_job.py` is the orchestrator, but do not assume it runs every analytics stage described in the README. In the current code it actively runs database init, realtime basic data, stock selection, “other daily” data, and after-close data; indicator, pattern, strategy, and backtest stages are imported but commented out.
- The web app is server-rendered Tornado, not a separate SPA. `instock/web/web_service.py` wires the routes, stores one shared DB connection on the application object, and serves:
  - generic table pages via `instock/web/dataTableHandler.py`
  - indicator/detail pages via `instock/web/dataIndicatorsHandler.py`
- `instock/core/singleton_stock_web_module_data.py` builds the left-menu and page/table definitions from `tablestructure.py`. This means schema metadata changes directly affect what appears in the UI.
- Indicator/detail pages fetch historical data on demand and render chart output through `instock/core/kline/visualization.py`, rather than reading pre-rendered chart assets from disk.
- `instock/trade/` is an optional automation layer built around `easytrader`. `instock/trade/trade_service.py` boots the strategy engine using `instock/config/trade_client.json`; the README treats this path as Windows-oriented.

## Scheduling and deployment shape

- Containerized deployment uses `supervisor/supervisord.conf` to start three long-lived processes:
  - `instock/bin/run_job.sh`
  - `instock/bin/run_web.sh`
  - `instock/bin/run_cron.sh`
- The cron schedule is baked into `docker/Dockerfile`, not configured at runtime:
  - every 30 minutes during weekday trading hours: `/etc/cron.hourly` → `realtime_only_job.py` (spot prices only, no fund flow / event data)
  - 17:30 on weekdays: `/etc/cron.workdayly` → `execute_daily_job.py` (full end-of-day pipeline)
  - 10:30 on Wednesday/Saturday: `/etc/cron.monthly` → cache cleanup
- The default container shape is app + MariaDB on a bridge network, exposing the web app on port 9988.

## External data and config

- **Tushare** is the primary source for daily stock spot data (`cn_stock_spot`) and individual stock fund flow — today window (`cn_stock_fund_flow`). Token must be configured in `instock/config/tushare.json`. Requires 2000+ 积分. Docker deployment must mount this file as a volume.
- **AkShare** provides ETF spot data (`fund_etf_spot_em`), event data (LHB, bonus, block trade), trade calendar, and historical data fallback. Installed via `requirements.txt`.
- Eastmoney legacy endpoints (push2.eastmoney.com) are still used for stock selection, sector fund flow (industry/concept), chip race, and limit-up reason. These are subject to IP rate-limiting.
- Frequent Eastmoney requests can be rate-limited. Cookie support exists via either:
  - environment variable `EAST_MONEY_COOKIE`
  - file `instock/config/eastmoney_cookie.txt`
- Proxy settings are read from `instock/config/proxy.txt`.
- Optional trading credentials/client settings live in `instock/config/trade_client.json`.

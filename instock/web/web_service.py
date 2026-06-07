#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json
import logging
import os.path
import sys

import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(format='%(asctime)s %(message)s', filename=os.path.join(log_path, 'stock_web.log'))
logging.getLogger().setLevel(logging.ERROR)
from instock.lib import config

__author__ = 'myh '
__date__ = '2023/3/10 '


class Application(tornado.web.Application):
    def __init__(self):
        import instock.lib.torndb as torndb
        import instock.lib.database as mdb
        import instock.web.dataTableHandler as dataTableHandler
        import instock.web.dataIndicatorsHandler as dataIndicatorsHandler
        import instock.web.dailyReportHandler as dailyReportHandler
        import instock.web.consoleHandler as consoleHandler
        import instock.web.data_asset_handler as dataAssetHandler

        web_cfg = config.get_web_config()
        handlers = [
            # 设置路由
            (r"/", HomeHandler),
            (r"/instock/", HomeHandler),
            (r"/health", HealthHandler),
            # 使用datatable 展示报表数据模块。
            (r"/instock/api_data", dataTableHandler.GetStockDataHandler),
            (r"/instock/data", dataTableHandler.GetStockHtmlHandler),
            # 每日复盘正文。
            (r"/instock/report/daily", dailyReportHandler.DailyReportHandler),
            # 控制台。
            (r"/instock/console", consoleHandler.ConsoleHandler),
            (r"/instock/console/api/status", consoleHandler.ConsoleStatusApiHandler),
            (r"/instock/console/api/overview", consoleHandler.ConsoleOverviewApiHandler),
            (r"/instock/console/api/tasks", consoleHandler.ConsoleTasksApiHandler),
            (r"/instock/console/api/runs", consoleHandler.ConsoleRunsApiHandler),
            (r"/instock/console/api/notices", consoleHandler.ConsoleNoticesApiHandler),
            (r"/instock/console/api/log", consoleHandler.ConsoleLogApiHandler),
            (r"/instock/console/api/start", consoleHandler.ConsoleStartApiHandler),
            (r"/instock/console/api/stop", consoleHandler.ConsoleStopApiHandler),
            (r"/instock/console/api/enable", consoleHandler.ConsoleEnableApiHandler),
            (r"/instock/console/api/notice/ack", consoleHandler.ConsoleNoticeAckApiHandler),
            # 数据资产管理。
            (r"/api/data-assets/status", dataAssetHandler.DataAssetsStatusApiHandler),
            (r"/api/data-assets/([^/]+)/detail", dataAssetHandler.DataAssetDetailApiHandler),
            # 获得股票指标数据。
            (r"/instock/data/indicators", dataIndicatorsHandler.GetDataIndicatorsHandler),
            # 加入关注
            (r"/instock/control/attention", dataIndicatorsHandler.SaveCollectHandler),
        ]
        settings = dict(  # 配置
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,  # True,
            # cookie加密，部署时应通过环境变量设置唯一值
            cookie_secret=web_cfg['cookie_secret'],
            debug=web_cfg['debug'],
        )
        super(Application, self).__init__(handlers, **settings)
        # Have one global connection to the blog DB across all handlers
        self.db = torndb.Connection(**mdb.MYSQL_CONN_TORNDB)


# 首页handler。
class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        import instock.lib.version as version
        import instock.web.base as webBase

        self.render("index.html",
                    stockVersion=version.__version__,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        self.write(json.dumps({'status': 'ok'}, ensure_ascii=False))


def main():
    # tornado.options.parse_command_line()
    tornado.options.options.logging = None

    web_cfg = config.get_web_config()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(web_cfg['port'])

    print(f"服务已启动，web地址 : http://localhost:{web_cfg['port']}/")
    logging.error(f"服务已启动，web地址 : http://localhost:{web_cfg['port']}/")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()

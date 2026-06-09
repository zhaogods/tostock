(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    function row(label, value, badgeStatus, title) {
        var valueHtml = badgeStatus ? App.badge(badgeStatus, value) : App.escapeHtml(value);
        return '<div class="list-row" title="' + App.escapeHtml(title || label) + '">'
            + '<span>' + App.escapeHtml(label) + '</span><strong>' + valueHtml + '</strong></div>';
    }

    App.modules.dashboard = {
        render: function () {
            var dashboard = App.state.dashboard || {};
            var health = dashboard.health || {};
            var tasks = dashboard.tasks || {};
            var summary = tasks.summary || {};
            var assets = dashboard.data_assets || {summary: {}};
            var assetSummary = assets.summary || {};
            var strategies = dashboard.strategies || {summary: {}};
            var strategySummary = strategies.summary || {};
            var quality = dashboard.quality || {};
            var reports = dashboard.reports || {};

            $('#dashboardMetrics').html([
                App.metric('运行中', summary.running || 0, '今日任务', '当前仍处于运行状态的系统任务数量'),
                App.metric('成功', summary.success || 0, '今日完成', '今日运行成功的系统任务数量'),
                App.metric('失败', summary.failed || 0, '今日异常', '今日运行失败的系统任务数量'),
                App.metric('数据健康', (assetSummary.healthy || 0) + '/' + (assetSummary.total || 0), '资产状态', '健康数据资产 / 全部数据资产'),
                App.metric('策略样本', strategySummary.with_samples || 0, '有样本策略', '已有回测排行样本的策略数量'),
                App.metric('通知', health.open_notices || 0, '未确认', '未确认或未解决的系统通知数量')
            ].join(''));

            var recentRows = (tasks.recent || []).slice(0, 6).map(function (item) {
                return '<div class="list-row" data-search-text="' + App.escapeHtml((item.task_name || '') + ' ' + (item.status || '')) + '" title="' + App.escapeHtml(item.message || item.run_id || '') + '">'
                    + '<span>' + App.escapeHtml(item.task_name || item.task_key || '-') + '</span>'
                    + '<strong>' + App.badge(item.status, App.statusText(item.status)) + '</strong></div>';
            }).join('') || '<div class="empty-text">暂无运行记录</div>';
            var dbOk = health.db_ok;
            var schedulerAlive = health.scheduler_alive;
            var diskPercent = (health.disk || {}).used_percent;
            $('#dashboardTasks').html(
                row('调度器', schedulerAlive == null ? '-' : (schedulerAlive ? '正常' : '异常'), schedulerAlive == null ? 'muted' : (schedulerAlive ? 'healthy' : 'warning'), '调度器最近心跳：' + App.formatDateTime(health.scheduler_heartbeat_at))
                + row('数据库', dbOk == null ? '-' : (dbOk ? '正常' : '异常'), dbOk == null ? 'muted' : (dbOk ? 'healthy' : 'critical'), '控制台服务层数据库连接检查')
                + '<div class="list-row"><span>磁盘使用</span><strong>' + App.escapeHtml(diskPercent == null ? '-' : diskPercent || 0) + (diskPercent == null ? '' : '%') + '</strong></div>'
                + '<div style="margin-top:8px; font-weight:800; font-size:12px;">最近运行</div>'
                + recentRows
            );

            var best = strategySummary.best_strategy || {};
            var latestReport = reports.latest || {};
            $('#dashboardBusiness').html(
                row('资产完整度', App.formatPercent(assetSummary.avg_completeness || 0), assetSummary.critical ? 'warning' : 'healthy', '全部数据资产平均完整度')
                + row('质量分', Number(assetSummary.avg_quality_score || 0).toFixed(1), quality.status === 'healthy' ? 'healthy' : quality.status || 'muted', '数据资产质量分与数据质量日志综合摘要')
                + row('策略均值', (strategySummary.avg_return_10d || 0) + '%', (strategySummary.avg_return_10d || 0) >= 0 ? 'healthy' : 'warning', '有样本策略的 10 日平均收益')
                + row('最佳策略', best.name || '-', 'info', '当前 10 日平均收益最高的策略')
                + row('最新报告', latestReport.date || '-', latestReport.date ? 'info' : 'muted', latestReport.title || '最近每日复盘报告')
            );
        }
    };
})(window, jQuery);

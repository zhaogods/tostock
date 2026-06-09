(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    function renderAssetRow(asset) {
        var completeness = Number(asset.completeness || 0);
        var status = asset.status || 'critical';
        var searchText = [asset.key, asset.name, asset.source, status, asset.last_update].join(' ');
        var issues = (asset.issues || []).join('\n');
        return '<tr data-search-text="' + App.escapeHtml(searchText) + '" title="' + App.escapeHtml(issues || '数据资产状态') + '">'
            + '<td><strong>' + App.escapeHtml(asset.name) + '</strong><div class="console-muted">' + App.escapeHtml(asset.key) + '</div></td>'
            + '<td>' + App.escapeHtml(asset.source || '-') + '</td>'
            + '<td>' + App.badge(status, App.statusText(status)) + '</td>'
            + '<td>' + App.progress(completeness, status) + '</td>'
            + '<td>' + App.escapeHtml(Number(asset.quality_score || 0).toFixed(1)) + '</td>'
            + '<td>' + App.escapeHtml(asset.actual || 0) + ' / ' + App.escapeHtml(asset.expected || 0) + '</td>'
            + '<td>' + App.escapeHtml(asset.last_update || '-') + '</td>'
            + '</tr>';
    }

    function renderStrategyRow(strategy) {
        var trend = strategy.trend || 'flat';
        var trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';
        var returnValue = Number(strategy.avg_return_10d || 0);
        var status = returnValue > 0 ? 'healthy' : returnValue < 0 ? 'warning' : 'muted';
        var searchText = [strategy.key, strategy.name, trend, strategy.updated_at].join(' ');
        return '<tr data-search-text="' + App.escapeHtml(searchText) + '" title="策略表：' + App.escapeHtml(strategy.key) + '">'
            + '<td><strong>' + App.escapeHtml(strategy.name) + '</strong><div class="console-muted">' + App.escapeHtml(strategy.key) + '</div></td>'
            + '<td>' + App.escapeHtml(strategy.sample_count || 0) + '</td>'
            + '<td>' + App.badge(status, returnValue.toFixed(2) + '%') + '</td>'
            + '<td>' + App.escapeHtml(Number(strategy.win_rate_10d || 0).toFixed(2)) + '%</td>'
            + '<td>' + App.badge(trend === 'up' ? 'healthy' : trend === 'down' ? 'warning' : 'muted', trendIcon + ' ' + App.statusText(trend)) + '</td>'
            + '<td>' + App.escapeHtml(strategy.updated_at || '-') + '</td>'
            + '</tr>';
    }

    function healthRow(label, value, status, title) {
        return '<div class="list-row" title="' + App.escapeHtml(title || label) + '">'
            + '<span>' + App.escapeHtml(label) + '</span><strong>' + (status ? App.badge(status, value) : App.escapeHtml(value)) + '</strong></div>';
    }

    App.modules.monitor = {
        render: function () {
            var dashboard = App.state.dashboard || {};
            var dataAssets = dashboard.data_assets || {};
            var assets = dataAssets.assets || [];
            $('#assetTable tbody').html(assets.map(renderAssetRow).join('') || '<tr><td colspan="7" class="empty-text">暂无数据资产状态</td></tr>');

            var strategies = ((dashboard.strategies || {}).strategies || []).slice().sort(function (a, b) {
                return Number(b.avg_return_10d || 0) - Number(a.avg_return_10d || 0);
            });
            $('#strategyTable tbody').html(strategies.map(renderStrategyRow).join('') || '<tr><td colspan="6" class="empty-text">暂无策略表现数据</td></tr>');

            var health = dashboard.health || {};
            var disk = health.disk || {};
            var dbOk = health.db_ok;
            var schedulerAlive = health.scheduler_alive;
            var healthStatus = health.status || (health.summary ? 'healthy' : 'muted');
            $('#healthPanel').html(
                healthRow('系统状态', App.statusText(healthStatus), healthStatus, '综合数据库、调度器、任务失败和通知判断')
                + healthRow('数据库', dbOk == null ? '-' : (dbOk ? '正常' : '异常'), dbOk == null ? 'muted' : (dbOk ? 'healthy' : 'critical'), '控制台聚合服务数据库连通性')
                + healthRow('调度器', schedulerAlive == null ? '-' : (schedulerAlive ? '心跳正常' : '心跳异常'), schedulerAlive == null ? 'muted' : (schedulerAlive ? 'healthy' : 'warning'), '心跳时间：' + App.formatDateTime(health.scheduler_heartbeat_at))
                + healthRow('磁盘使用', disk.used_percent == null ? '-' : (disk.used_percent || 0) + '%', disk.used_percent == null ? 'muted' : ((disk.used_percent || 0) > 90 ? 'critical' : (disk.used_percent || 0) > 80 ? 'warning' : 'healthy'), '剩余空间：' + (disk.free_gb || 0) + 'GB')
                + healthRow('今日失败', health.failed_tasks_today || 0, health.failed_tasks_today ? 'critical' : 'healthy', '今日 system_task_run 中失败任务数量')
                + healthRow('未确认通知', health.open_notices || 0, health.open_notices ? 'warning' : 'healthy', 'system_task_notice 中 open 状态通知')
            );

            var quality = dashboard.quality || {};
            $('#qualityPanel').html(
                healthRow('质量状态', App.statusText(quality.status), quality.status || 'muted', '来自 data_quality_log 的当日摘要')
                + healthRow('检查总数', quality.total_checks || 0, null, '当日数据质量检查记录数')
                + healthRow('通过', quality.passed_checks || 0, 'healthy', '检查通过数量')
                + healthRow('失败', quality.failed_checks || 0, quality.failed_checks ? 'warning' : 'healthy', '检查失败数量')
                + healthRow('错误', quality.error_count || 0, quality.error_count ? 'critical' : 'healthy', 'error 级别失败数量')
                + healthRow('警告', quality.warning_count || 0, quality.warning_count ? 'warning' : 'healthy', 'warning 级别失败数量')
                + healthRow('最近质量日期', quality.latest_date || '-', quality.latest_date ? 'info' : 'muted', 'data_quality_log 最近写入日期')
            );
        }
    };
})(window, jQuery);

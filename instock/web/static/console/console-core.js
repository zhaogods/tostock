(function (window, $) {
    'use strict';

    var App = {
        state: {
            activePanel: 'dashboard',
            dashboard: {
                health: {},
                tasks: {},
                data_assets: null,
                strategies: null,
                quality: null,
                reports: null
            },
            status: null,
            pipeline: null,
            taskMap: {},
            lastRefresh: null
        },
        modules: {}
    };

    App.apiGet = function (url, data) {
        return $.ajax({
            url: url,
            method: 'GET',
            data: data || {},
            dataType: 'json',
            timeout: 20000
        });
    };

    App.apiPost = function (url, data) {
        return $.ajax({
            url: url,
            method: 'POST',
            data: data || {},
            dataType: 'json',
            timeout: 20000
        });
    };

    App.escapeHtml = function (value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    App.formatSeconds = function (seconds) {
        seconds = Number(seconds || 0);
        if (!seconds) return '-';
        if (seconds < 60) return Math.round(seconds) + '秒';
        if (seconds < 3600) return Math.floor(seconds / 60) + '分' + Math.round(seconds % 60) + '秒';
        return Math.floor(seconds / 3600) + '时' + Math.floor((seconds % 3600) / 60) + '分';
    };

    App.formatDateTime = function (value) {
        if (!value) return '-';
        return String(value).replace('T', ' ').slice(0, 19);
    };

    App.formatPercent = function (value, digits) {
        digits = digits == null ? 1 : digits;
        value = Number(value || 0);
        if (Math.abs(value) <= 1) value = value * 100;
        return value.toFixed(digits) + '%';
    };

    App.clampPercent = function (value) {
        value = Number(value || 0);
        if (value <= 1) value = value * 100;
        return Math.max(0, Math.min(100, value));
    };

    App.statusText = function (status) {
        var map = {
            running: '运行中', success: '成功', failed: '失败', stopped: '已停止', skipped: '跳过',
            healthy: '健康', warning: '警告', critical: '异常', disabled: '禁用', enabled: '启用',
            no_data: '无数据', no_table: '无表', flat: '平', up: '上升', down: '下降',
            default: '默认计划', cron: '自定义计划', open: '待处理', ack: '已确认', resolved: '已解决'
        };
        return map[status] || status || '-';
    };

    App.statusClass = function (status) {
        if (status === 'success' || status === 'healthy' || status === 'enabled') return 'success';
        if (status === 'running' || status === 'cron') return 'running';
        if (status === 'warning') return 'warning';
        if (status === 'failed' || status === 'critical' || status === 'error') return 'critical';
        if (status === 'info') return 'info';
        return 'muted';
    };

    App.badge = function (status, text) {
        return '<span class="badge-v2 ' + App.statusClass(status) + '">' + App.escapeHtml(text || App.statusText(status)) + '</span>';
    };

    App.metric = function (label, value, hint, title) {
        return '<div class="metric-mini" title="' + App.escapeHtml(title || hint || label) + '">'
            + '<span class="label">' + App.escapeHtml(label) + '</span>'
            + '<span class="value">' + App.escapeHtml(value) + '</span>'
            + '<span class="hint">' + App.escapeHtml(hint || '') + '</span>'
            + '</div>';
    };

    App.progress = function (value, status) {
        var percent = App.clampPercent(value);
        return '<div class="progress-mini ' + App.statusClass(status) + '" title="' + percent.toFixed(1) + '%">'
            + '<span style="width:' + percent.toFixed(2) + '%"></span></div>';
    };

    App.toast = function (message, isError) {
        var old = $('#consoleToast');
        old.remove();
        var el = $('<div id="consoleToast"></div>')
            .text(message)
            .css({
                position: 'fixed', right: '18px', bottom: '18px', zIndex: 2000,
                padding: '10px 14px', borderRadius: '10px', color: '#fff',
                background: isError ? '#d94848' : '#172033', boxShadow: '0 10px 28px rgba(0,0,0,.18)',
                fontSize: '12px'
            });
        $('body').append(el);
        setTimeout(function () { el.fadeOut(180, function () { el.remove(); }); }, 2400);
    };

    App.parseAjaxError = function (xhr, fallback) {
        try {
            if (xhr.responseJSON && (xhr.responseJSON.message || xhr.responseJSON.error)) {
                return xhr.responseJSON.message || xhr.responseJSON.error;
            }
            if (xhr.responseText) {
                var data = JSON.parse(xhr.responseText);
                return data.message || data.error || fallback;
            }
        } catch (e) {}
        return fallback || '请求失败';
    };

    App.setActivePanel = function (panel) {
        App.state.activePanel = panel;
        $('.nav-item').removeClass('active');
        $('.nav-item[data-panel="' + panel + '"]').addClass('active');
        $('.console-panel').removeClass('active');
        $('#panel-' + panel).addClass('active');
        var title = $('.nav-item[data-panel="' + panel + '"] span').text() || '控制台';
        $('#panelTitle').text(title);
        App.applySearchFilter();
    };

    App.applySearchFilter = function () {
        var keyword = ($('#consoleSearch').val() || '').trim().toLowerCase();
        var panel = App.state.activePanel;
        var scope = $('#panel-' + panel);
        scope.find('[data-search-text]').each(function () {
            var text = String($(this).data('search-text') || '').toLowerCase();
            $(this).toggle(!keyword || text.indexOf(keyword) >= 0);
        });
    };

    App.renderModule = function (name) {
        if (App.modules[name] && App.modules[name].render) {
            App.modules[name].render();
            App.applySearchFilter();
        }
    };

    App.updateSchedulerPill = function () {
        var health = (App.state.dashboard && App.state.dashboard.health) || (App.state.status && App.state.status.overview) || {};
        var enabled = !!health.scheduler_enabled;
        var alive = !!health.scheduler_alive;
        var status = !enabled ? 'critical' : alive ? 'healthy' : 'warning';
        var text = !enabled ? '调度关闭' : alive ? '调度正常' : '心跳异常';
        $('#schedulerStatus').html('<span class="status-dot ' + status + '"></span><span>' + text + '</span>')
            .attr('title', '最近心跳：' + App.formatDateTime(health.scheduler_heartbeat_at));
    };

    App.refreshOverview = function () {
        return App.apiGet('/instock/console/api/overview').done(function (resp) {
            var overview = resp.overview || {};
            App.state.status = App.state.status || {};
            App.state.status.overview = overview;
            App.state.dashboard = App.state.dashboard || {};
            App.state.dashboard.tasks = $.extend({}, App.state.dashboard.tasks || {}, {
                today: overview.today,
                summary: overview.summary || {},
                open_notices: overview.open_notices || 0
            });
            App.state.dashboard.health = $.extend({}, App.state.dashboard.health || {}, overview, {
                running_tasks: (overview.summary || {}).running || 0,
                failed_tasks_today: (overview.summary || {}).failed || 0,
                open_notices: overview.open_notices || 0
            });
            App.updateSchedulerPill();
            App.renderModule('dashboard');
            App.renderModule('monitor');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '总览刷新失败'), true);
        });
    };

    App.refreshTasks = function () {
        return App.apiGet('/instock/console/api/tasks').done(function (resp) {
            App.state.status = App.state.status || {};
            App.state.status.tasks = resp.tasks || [];
            App.state.status.groups = resp.groups || {};
            App.state.taskMap = {};
            (App.state.status.tasks || []).forEach(function (task) { App.state.taskMap[task.key] = task; });
            App.renderModule('tasks');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '任务列表刷新失败'), true);
        });
    };

    App.refreshPipeline = function () {
        var dateValue = $('#consoleDate').val() || '';
        return App.apiGet('/instock/console/api/pipeline', {date: dateValue}).done(function (resp) {
            App.state.pipeline = resp.pipeline || {};
            App.renderModule('tasks');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '任务管线刷新失败'), true);
        });
    };

    App.refreshHealth = function () {
        return App.apiGet('/instock/console/api/health').done(function (resp) {
            App.state.dashboard.health = resp.health || {};
            App.updateSchedulerPill();
            App.renderModule('dashboard');
            App.renderModule('monitor');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '系统健康刷新失败'), true);
        });
    };

    App.refreshAssets = function () {
        var dateValue = $('#consoleDate').val() || '';
        return App.apiGet('/instock/console/api/assets', {date: dateValue}).done(function (resp) {
            App.state.dashboard.data_assets = resp.data_assets || {summary: {}, assets: []};
            App.renderModule('dashboard');
            App.renderModule('monitor');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '数据资产刷新失败'), true);
        });
    };

    App.refreshStrategies = function () {
        return App.apiGet('/instock/console/api/strategies', {days: 7}).done(function (resp) {
            App.state.dashboard.strategies = resp.strategies || {summary: {}, strategies: []};
            App.renderModule('dashboard');
            App.renderModule('monitor');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '策略表现刷新失败'), true);
        });
    };

    App.refreshQuality = function () {
        var dateValue = $('#consoleDate').val() || '';
        return App.apiGet('/instock/console/api/quality', {date: dateValue}).done(function (resp) {
            App.state.dashboard.quality = resp.quality || {};
            App.renderModule('dashboard');
            App.renderModule('monitor');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '数据质量刷新失败'), true);
        });
    };

    App.refreshReports = function () {
        return App.apiGet('/instock/console/api/reports', {limit: 5}).done(function (resp) {
            App.state.dashboard.reports = resp.reports || {reports: [], latest: null};
            App.renderModule('dashboard');
            App.renderModule('reports');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '报告列表刷新失败'), true);
        });
    };

    App.refreshTimeline = function () {
        var runsReq = App.apiGet('/instock/console/api/runs', {limit: 12});
        var noticesReq = App.apiGet('/instock/console/api/notices', {limit: 8});
        return $.when(runsReq, noticesReq).done(function (runsResp, noticesResp) {
            runsResp = runsResp[0] || {};
            noticesResp = noticesResp[0] || {};
            App.state.status = App.state.status || {};
            App.state.status.recent = runsResp.runs || [];
            App.state.status.job_recent = runsResp.job_recent || runsResp.job_runs || [];
            App.state.status.notices = noticesResp.notices || [];
            App.state.dashboard.tasks = $.extend({}, App.state.dashboard.tasks || {}, {
                recent: App.state.status.recent,
                job_recent: App.state.status.job_recent,
                notices: App.state.status.notices
            });
            App.renderModule('dashboard');
            App.renderModule('timeline');
        }).fail(function (xhr) {
            App.toast(App.parseAjaxError(xhr, '运行记录刷新失败'), true);
        });
    };

    App._waitAll = function (requests, callback) {
        var remaining = requests.length;
        if (!remaining) {
            callback && callback();
            return;
        }
        requests.forEach(function (req) {
            if (req && req.always) {
                req.always(function () {
                    remaining -= 1;
                    if (!remaining && callback) callback();
                });
            } else {
                remaining -= 1;
                if (!remaining && callback) callback();
            }
        });
    };

    App.refreshAll = function () {
        $('#refreshConsole').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> 刷新');
        App.state.lastRefresh = new Date();
        $('#lastRefreshText').text('刷新：' + App.state.lastRefresh.toLocaleTimeString());
        var requests = [
            App.refreshOverview(),
            App.refreshTasks(),
            App.refreshPipeline(),
            App.refreshTimeline(),
            App.refreshHealth(),
            App.refreshAssets(),
            App.refreshStrategies(),
            App.refreshQuality(),
            App.refreshReports()
        ];
        App._waitAll(requests, function () {
            $('#refreshConsole').prop('disabled', false).html('<i class="fa fa-refresh"></i> 刷新');
        });
    };

    App.refreshFast = function () {
        App.state.lastRefresh = new Date();
        $('#lastRefreshText').text('刷新：' + App.state.lastRefresh.toLocaleTimeString());
        App.refreshOverview();
        App.refreshTasks();
        App.refreshTimeline();
    };

    App.bindCoreEvents = function () {
        $('#consoleNav').on('click', '.nav-item', function () {
            App.setActivePanel($(this).data('panel'));
        });
        $('#refreshConsole').on('click', App.refreshAll);
        $('#consoleDate').on('change', App.refreshAll);
        $('#consoleSearch').on('input', App.applySearchFilter);
        $('#toggleDrawer').on('click', function () { $('#consoleDrawer').toggleClass('open'); });
        $('#drawerClose').on('click', function () { $('#consoleDrawer').removeClass('open'); });
        $('.drawer-tabs').on('click', '.drawer-tab', function () {
            var target = $(this).data('drawer');
            $('.drawer-tab').removeClass('active');
            $(this).addClass('active');
            $('.drawer-panel').removeClass('active');
            $('#drawer-' + target).addClass('active');
        });
    };

    App.init = function () {
        $('#consoleDate').val(new Date().toISOString().slice(0, 10));
        App.bindCoreEvents();
        if (App.modules.tasks && App.modules.tasks.bindEvents) App.modules.tasks.bindEvents();
        if (App.modules.timeline && App.modules.timeline.bindEvents) App.modules.timeline.bindEvents();
        App.refreshAll();
        setInterval(function () {
            if (!document.hidden) App.refreshFast();
        }, 30000);
    };

    window.ConsoleApp = App;
})(window, jQuery);

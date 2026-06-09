(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    function renderRun(run) {
        var title = run.task_name || run.task_key || run.job_name || '-';
        var time = run.start_time || run.run_date || '';
        var message = run.message || '';
        var runId = run.run_id || '';
        var attrs = runId ? ' data-run="' + App.escapeHtml(runId) + '" data-title="' + App.escapeHtml(title) + '"' : '';
        return '<div class="timeline-row" data-search-text="' + App.escapeHtml([title, run.status, message].join(' ')) + '" title="' + App.escapeHtml(message || title) + '">'
            + '<div><strong>' + App.escapeHtml(title) + '</strong><div class="console-muted">' + App.escapeHtml(App.formatDateTime(time)) + ' · ' + App.escapeHtml(App.formatSeconds(run.duration_seconds)) + '</div></div>'
            + '<div>' + App.badge(run.status, App.statusText(run.status))
            + (runId ? ' <button class="console-btn js-drawer-log"' + attrs + ' title="查看日志"><i class="fa fa-file-text-o"></i></button>' : '')
            + '</div></div>';
    }

    function renderJobRun(run) {
        return '<div class="timeline-row" data-search-text="' + App.escapeHtml([run.job_name, run.status, run.message].join(' ')) + '" title="' + App.escapeHtml(run.message || run.job_name || '') + '">'
            + '<div><strong>' + App.escapeHtml(run.job_name || '-') + '</strong><div class="console-muted">' + App.escapeHtml(App.formatDateTime(run.start_time || run.run_date)) + ' · 写入 ' + App.escapeHtml(run.rows_written == null ? '-' : run.rows_written) + '</div></div>'
            + '<div>' + App.badge(run.status, App.statusText(run.status)) + '</div></div>';
    }

    function renderNotice(notice) {
        var level = notice.level === 'error' ? 'critical' : 'warning';
        var ackButton = notice.status === 'open'
            ? ' <button class="console-btn js-ack-notice" data-notice="' + App.escapeHtml(notice.notice_id) + '" title="确认该通知"><i class="fa fa-check"></i></button>'
            : '';
        return '<div class="notice-row" data-search-text="' + App.escapeHtml([notice.title, notice.message, notice.task_key].join(' ')) + '" title="' + App.escapeHtml(notice.message || notice.title || '') + '">'
            + '<div><strong>' + App.escapeHtml(notice.title || '-') + '</strong><div class="console-muted">' + App.escapeHtml(notice.task_key || '-') + ' · ' + App.escapeHtml(App.formatDateTime(notice.created_at)) + '</div></div>'
            + '<div>' + App.badge(level, notice.level || 'notice') + ackButton + '</div></div>';
    }

    var currentLogRunId = '';
    var currentLogTitle = '';

    App.modules.timeline = {
        render: function () {
            var tasks = ((App.state.dashboard || {}).tasks || {});
            var runs = tasks.recent || [];
            var jobs = tasks.job_recent || [];
            var notices = tasks.notices || [];
            var html = '';
            if (runs.length) {
                html += '<div style="font-weight:800; font-size:12px; margin:4px 0 6px;">系统任务</div>' + runs.map(renderRun).join('');
            }
            if (jobs.length) {
                html += '<div style="font-weight:800; font-size:12px; margin:12px 0 6px;">作业记录</div>' + jobs.slice(0, 8).map(renderJobRun).join('');
            }
            $('#drawer-timeline').html(html || '<div class="empty-text">暂无运行记录</div>');
            var noticeHtml = notices.length
                ? '<div style="text-align:right; margin:0 0 8px;"><button class="console-btn js-ack-all-notices" title="确认所有待处理通知"><i class="fa fa-check-square-o"></i> 全部确认</button></div>'
                : '';
            noticeHtml += notices.map(renderNotice).join('') || '<div class="empty-text">暂无通知</div>';
            $('#drawer-notices').html(noticeHtml);
        },

        bindEvents: function () {
            $(document).on('click', '.js-drawer-log', function () {
                App.modules.timeline.openLog($(this).data('run'), $(this).data('title'));
            });
            $(document).on('click', '.js-ack-notice', function () {
                var noticeId = $(this).data('notice');
                App.apiPost('/instock/console/api/notice/ack', {notice_id: noticeId}).done(function (resp) {
                    App.toast(resp.message || '已确认通知');
                    App.refreshAll();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '确认通知失败'), true);
                });
            });
            $(document).on('click', '.js-ack-all-notices', function () {
                if (!confirm('确认所有待处理通知？')) return;
                App.apiPost('/instock/console/api/notice/ack_all', {}).done(function (resp) {
                    App.toast(resp.message || '已确认全部通知');
                    App.refreshAll();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '批量确认通知失败'), true);
                });
            });
            $(document).on('click', '.js-refresh-log', function () {
                App.modules.timeline.openLog(currentLogRunId, currentLogTitle);
            });
        },

        openLog: function (runId, title) {
            if (!runId) return;
            currentLogRunId = runId;
            currentLogTitle = title || '任务日志';
            $('#consoleDrawer').addClass('open');
            $('.drawer-tab').removeClass('active');
            $('.drawer-tab[data-drawer="log"]').addClass('active');
            $('.drawer-panel').removeClass('active');
            $('#drawer-log').addClass('active');
            $('#drawerTitle').text(currentLogTitle);
            $('#drawer-log .console-log').text('日志加载中...');
            App.apiGet('/instock/console/api/log', {run_id: runId, max_chars: 50000}).done(function (resp) {
                var hint = '运行状态：' + App.statusText(resp.status) + ' · 日志大小：' + App.escapeHtml(resp.log_size || 0) + ' 字符';
                if (resp.truncated) hint += ' · 仅显示末尾内容';
                var toolbar = '<div class="log-toolbar"><span class="console-muted">' + hint + '</span>'
                    + '<button class="console-btn js-refresh-log" title="刷新当前日志"><i class="fa fa-refresh"></i> 刷新日志</button></div>';
                $('#drawer-log').find('.log-toolbar').remove();
                $('#drawer-log').prepend(toolbar);
                $('#drawer-log .console-log').text(resp.log || '日志为空');
            }).fail(function (xhr) {
                $('#drawer-log .console-log').text(App.parseAjaxError(xhr, '读取日志失败'));
            });
        }
    };
})(window, jQuery);

(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    function renderReport(report) {
        var searchText = [report.date, report.title, report.summary].join(' ');
        return '<a class="report-row" href="' + App.escapeHtml(report.url || '/instock/report/daily') + '" data-search-text="' + App.escapeHtml(searchText) + '" title="' + App.escapeHtml(report.summary || report.title || '') + '">'
            + '<div class="report-title"><span>' + App.escapeHtml(report.title || '每日复盘报告') + '</span>' + App.badge('info', report.date || '-') + '</div>'
            + '<div class="report-summary">' + App.escapeHtml(report.summary || '暂无摘要') + '</div>'
            + '<div class="console-muted" style="margin-top:6px;">生成：' + App.escapeHtml(App.formatDateTime(report.created_at)) + '</div>'
            + '</a>';
    }

    App.modules.reports = {
        render: function () {
            var reports = (((App.state.dashboard || {}).reports || {}).reports || []);
            $('#reportList').html(reports.map(renderReport).join('') || '<div class="empty-text">暂无复盘报告</div>');
        }
    };
})(window, jQuery);

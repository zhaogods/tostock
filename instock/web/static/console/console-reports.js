(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    function renderReport(report, typeLabel, fallbackUrl, fallbackTitle) {
        var searchText = [typeLabel, report.date, report.title, report.summary, report.top_codes].join(' ');
        var meta = '生成：' + App.escapeHtml(App.formatDateTime(report.created_at));
        if (report.candidate_count != null) meta += ' · 候选：' + App.escapeHtml(report.candidate_count || 0);
        if (report.llm_enabled) meta += ' · LLM';
        return '<a class="report-row" href="' + App.escapeHtml(report.url || fallbackUrl) + '" data-search-text="' + App.escapeHtml(searchText) + '" title="' + App.escapeHtml(report.summary || report.title || '') + '">'
            + '<div class="report-title"><span>' + App.escapeHtml(report.title || fallbackTitle) + '</span>' + App.badge('info', typeLabel + ' · ' + (report.date || '-')) + '</div>'
            + '<div class="report-summary">' + App.escapeHtml(report.summary || '暂无摘要') + '</div>'
            + '<div class="console-muted" style="margin-top:6px;">' + meta + '</div>'
            + '</a>';
    }

    App.modules.reports = {
        render: function () {
            var dailyReports = (((App.state.dashboard || {}).reports || {}).reports || []);
            var selectionReports = (((App.state.dashboard || {}).selection_reports || {}).reports || []);
            var dailyHtml = dailyReports.map(function (report) {
                return renderReport(report, '复盘', '/instock/report/daily', '每日复盘报告');
            }).join('') || '<div class="empty-text">暂无复盘报告</div>';
            var selectionHtml = selectionReports.map(function (report) {
                return renderReport(report, '选股', '/instock/report/selection', '每日选股报告');
            }).join('') || '<div class="empty-text">暂无选股报告</div>';
            $('#reportList').html(
                '<div class="box-header" style="margin-bottom:8px;"><span>每日选股报告</span></div>'
                + selectionHtml
                + '<div class="box-header" style="margin:16px 0 8px;"><span>每日复盘报告</span></div>'
                + dailyHtml
            );
        }
    };
})(window, jQuery);

(function (window, $) {
    'use strict';
    var App = window.ConsoleApp;

    var currentScheduleMode = 'picker';
    var currentDateMode = 'list';
    var schedulePreviewTimer = null;

    function actionButton(cls, icon, text, title, attrs) {
        return '<button class="console-btn ' + cls + '" title="' + App.escapeHtml(title || text) + '" ' + (attrs || '') + '>'
            + '<i class="fa ' + icon + '"></i> ' + App.escapeHtml(text) + '</button>';
    }

    function mergedTask(definition) {
        var runtime = App.state.taskMap[definition.key] || {};
        return $.extend({}, runtime, definition);
    }

    function findTask(key) {
        var task = App.state.taskMap[key] || {};
        if (task.key) return task;
        (App.state.pipeline && App.state.pipeline.stages || []).forEach(function (stage) {
            (stage.tasks || []).forEach(function (item) {
                if (item.key === key) task = item;
            });
        });
        return task;
    }

    function safeJoin(values) {
        return (values || []).map(function (value) { return value == null ? '' : String(value); }).join(' ');
    }

    function renderTaskRow(task) {
        var status = task.running ? (task.timed_out ? 'warning' : 'running') : (task.last_status || (task.enabled ? 'enabled' : 'disabled'));
        var statusText = task.running ? (task.timed_out ? '运行超时' : '运行中') : (task.last_status ? App.statusText(task.last_status) : (task.enabled ? '待命' : '禁用'));
        var schedule = task.effective_schedule_text || task.schedule_text || '-';
        var scheduleStatus = task.schedule_customized ? 'cron' : 'muted';
        var duration = task.running ? App.formatSeconds(task.running_seconds) : App.formatSeconds(task.last_duration_seconds);
        var tooltip = [
            task.description || '',
            task.warning ? '警告：' + task.warning : '',
            task.feeds_pages ? '关联页面：' + task.feeds_pages : '',
            task.lock_group ? '互斥组：' + task.lock_group : '',
            task.timeout_seconds ? '超时阈值：' + App.formatSeconds(task.timeout_seconds) : '',
            task.timed_out ? '当前已超过超时阈值，系统会尝试自动停止。' : '',
            task.next_fire_time ? '下次触发：' + App.formatDateTime(task.next_fire_time) : '',
            task.cron_expression ? 'Cron：' + task.cron_expression : ''
        ].filter(Boolean).join('\n');
        var searchText = safeJoin([task.key, task.name, task.category, task.description, task.feeds_pages, task.last_status, schedule, task.cron_expression]);
        var startDisabled = !task.allow_manual_start || task.running ? 'disabled' : '';
        var stopDisabled = !task.allow_stop || !task.running ? 'disabled' : '';
        var logDisabled = !(task.running_run_id || task.last_run_id) ? 'disabled' : '';
        var logRunId = task.running_run_id || task.last_run_id || '';

        return '<tr data-search-text="' + App.escapeHtml(searchText) + '">'
            + '<td class="task-name-cell" title="' + App.escapeHtml(tooltip || task.name) + '">'
            + App.escapeHtml(task.name)
            + (task.warning ? ' <i class="fa fa-exclamation-triangle" title="' + App.escapeHtml(task.warning) + '"></i>' : '')
            + '</td>'
            + '<td>' + App.badge(status, statusText) + '</td>'
            + '<td><label class="switch-mini" title="启用或禁用该调度任务"><input type="checkbox" class="js-toggle-task" data-task="' + App.escapeHtml(task.key) + '" ' + (task.enabled ? 'checked' : '') + '>启用</label></td>'
            + '<td title="' + App.escapeHtml('当前计划：' + schedule + (task.next_fire_time ? '\n下次触发：' + App.formatDateTime(task.next_fire_time) : '')) + '">'
            + App.badge(scheduleStatus, task.schedule_customized ? '自定义' : '默认') + ' ' + App.escapeHtml(schedule)
            + '</td>'
            + '<td title="最近启动：' + App.escapeHtml(App.formatDateTime(task.last_start_time || task.last_fire_time)) + '">' + App.escapeHtml(duration) + '</td>'
            + '<td>' + App.escapeHtml(task.lock_group || '-') + '</td>'
            + '<td><div class="task-actions">'
            + actionButton('js-start-task', 'fa-play', '启动', task.warning || '启动任务', 'data-task="' + App.escapeHtml(task.key) + '" ' + startDisabled)
            + actionButton('js-schedule-task', 'fa-clock-o', '计划', '调整任务计划', 'data-task="' + App.escapeHtml(task.key) + '"')
            + actionButton('danger js-stop-task', 'fa-stop', '停止', '停止运行中的任务', 'data-task="' + App.escapeHtml(task.key) + '" data-run="' + App.escapeHtml(task.running_run_id || '') + '" ' + stopDisabled)
            + actionButton('js-task-log', 'fa-file-text-o', '日志', '查看最近运行日志', 'data-run="' + App.escapeHtml(logRunId) + '" data-title="' + App.escapeHtml(task.name) + '" ' + logDisabled)
            + '</div></td>'
            + '</tr>';
    }

    function fillSelect(id, start, end, step, formatter) {
        var html = '';
        step = step || 1;
        for (var value = start; value <= end; value += step) {
            html += '<option value="' + value + '">' + App.escapeHtml(formatter ? formatter(value) : value) + '</option>';
        }
        $(id).html(html);
    }

    function initSchedulePickerOptions() {
        fillSelect('#scheduleHour', 0, 23, 1, function (value) { return (value < 10 ? '0' : '') + value + ' 时'; });
        fillSelect('#scheduleMinute', 0, 59, 1, function (value) { return (value < 10 ? '0' : '') + value + ' 分'; });
        $('#scheduleWeekday').html([
            '<option value="1">周一</option>',
            '<option value="2">周二</option>',
            '<option value="3">周三</option>',
            '<option value="4">周四</option>',
            '<option value="5">周五</option>',
            '<option value="6">周六</option>',
            '<option value="0">周日</option>'
        ].join(''));
        $('#scheduleInterval').html([
            '<option value="5">每 5 分钟</option>',
            '<option value="10">每 10 分钟</option>',
            '<option value="15">每 15 分钟</option>',
            '<option value="30" selected>每 30 分钟</option>',
            '<option value="60">每 60 分钟</option>'
        ].join(''));
        $('#scheduleHour').val('17');
        $('#scheduleMinute').val('30');
    }

    function cronFromPicker() {
        var preset = $('#schedulePreset').val();
        var hour = Number($('#scheduleHour').val() || 0);
        var minute = Number($('#scheduleMinute').val() || 0);
        var weekday = $('#scheduleWeekday').val() || '1';
        var interval = Number($('#scheduleInterval').val() || 30);
        if (preset === 'daily') return minute + ' ' + hour + ' * * *';
        if (preset === 'weekly') return minute + ' ' + hour + ' * * ' + weekday;
        if (preset === 'interval') return '*/' + interval + ' * * * *';
        if (preset === 'market_interval') return '*/' + interval + ' 9-15 * * 1-5';
        return minute + ' ' + hour + ' * * 1-5';
    }

    function activeCronExpression() {
        if (currentScheduleMode === 'manual') {
            return ($('#scheduleCronInput').val() || '').trim();
        }
        return cronFromPicker();
    }

    function syncSchedulePreview() {
        var cron = activeCronExpression();
        $('#scheduleCronPreview').text(cron || '-');
        $('#scheduleCronInput').val(cron);
        $('#scheduleValidationText').removeClass('valid invalid').addClass('muted').text('校验中...');
        if (schedulePreviewTimer) clearTimeout(schedulePreviewTimer);
        schedulePreviewTimer = setTimeout(function () {
            if (!cron) {
                $('#scheduleValidationText').removeClass('valid').addClass('invalid').text('Cron 表达式不能为空');
                return;
            }
            App.apiGet('/instock/console/api/schedule/preview', {cron: cron}).done(function (resp) {
                $('#scheduleValidationText').removeClass('muted invalid').addClass('valid')
                    .text((resp.schedule_text || resp.message || '表达式有效') + '，下次触发：' + App.formatDateTime(resp.next_fire_time));
            }).fail(function (xhr) {
                $('#scheduleValidationText').removeClass('muted valid').addClass('invalid')
                    .text(App.parseAjaxError(xhr, 'Cron 表达式无效'));
            });
        }, 260);
    }

    function setScheduleMode(mode) {
        currentScheduleMode = mode;
        $('.schedule-mode-tab').removeClass('active');
        $('.schedule-mode-tab[data-mode="' + mode + '"]').addClass('active');
        $('.schedule-mode-panel').removeClass('active');
        if (mode === 'manual') {
            $('#scheduleManualPanel').addClass('active');
        } else {
            $('#schedulePickerPanel').addClass('active');
        }
        syncSchedulePreview();
    }

    function setDateMode(mode) {
        currentDateMode = mode || 'list';
        $('.date-arg-tabs .schedule-mode-tab').removeClass('active');
        $('.date-arg-tabs .schedule-mode-tab[data-date-mode="' + currentDateMode + '"]').addClass('active');
        $('.date-arg-panel').removeClass('active');
        if (currentDateMode === 'range') {
            $('#dateRangePanel').addClass('active');
        } else {
            $('#dateListPanel').addClass('active');
        }
    }

    App.modules.tasks = {
        render: function () {
            var pipeline = App.state.pipeline || {};
            var stages = pipeline.stages || [];
            var html = '';
            stages.forEach(function (stage) {
                var rows = (stage.tasks || []).map(function (definition) {
                    return renderTaskRow(mergedTask(definition));
                }).join('') || '<tr><td colspan="7" class="empty-text">暂无任务</td></tr>';
                html += '<section class="pipeline-stage" data-search-text="' + App.escapeHtml(stage.label + ' ' + stage.description) + '">'
                    + '<div class="stage-header">'
                    + '<span class="stage-title">' + App.escapeHtml(stage.label) + ' ' + App.badge('info', stage.task_count + '项') + '</span>'
                    + '<i class="fa fa-info-circle" title="' + App.escapeHtml(stage.description || '') + '"></i>'
                    + '</div>'
                    + '<div class="stage-body"><table class="task-compact-table">'
                    + '<thead><tr><th>任务</th><th>状态</th><th>调度</th><th>计划</th><th>耗时</th><th>锁组</th><th>操作</th></tr></thead>'
                    + '<tbody>' + rows + '</tbody></table></div>'
                    + '</section>';
            });
            $('#taskPipeline').html(html || '<div class="empty-text">暂无任务定义</div>');
            var summary = pipeline.summary || {};
            $('#pipelineSummary').text('阶段 ' + (summary.stage_count || 0) + ' / 任务 ' + (summary.task_count || 0) + ' / 可手动 ' + (summary.manual_count || 0));
        },

        bindEvents: function () {
            initSchedulePickerOptions();

            $(document).on('click', '.js-start-task', function () {
                var key = $(this).data('task');
                App.modules.tasks.openStartModal(findTask(key));
            });

            $(document).on('click', '.js-schedule-task', function () {
                App.modules.tasks.openScheduleModal(findTask($(this).data('task')));
            });

            $(document).on('click', '.js-stop-task', function () {
                var taskKey = $(this).data('task');
                var runId = $(this).data('run') || '';
                if (!confirm('确认停止该任务？')) return;
                App.apiPost('/instock/console/api/stop', {task_key: taskKey, run_id: runId}).done(function (resp) {
                    App.toast(resp.message || '已发送停止信号');
                    App.refreshFast();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '停止任务失败'), true);
                });
            });

            $(document).on('click', '.js-task-log', function () {
                var runId = $(this).data('run');
                var title = $(this).data('title') || '任务日志';
                if (App.modules.timeline && App.modules.timeline.openLog) {
                    App.modules.timeline.openLog(runId, title);
                }
            });

            $(document).on('change', '.js-toggle-task', function () {
                var input = $(this);
                var taskKey = input.data('task');
                var enabled = input.is(':checked') ? '1' : '0';
                App.apiPost('/instock/console/api/enable', {task_key: taskKey, enabled: enabled}).done(function (resp) {
                    App.toast(resp.message || '已更新任务状态');
                    App.refreshFast();
                }).fail(function (xhr) {
                    input.prop('checked', !input.is(':checked'));
                    App.toast(App.parseAjaxError(xhr, '更新任务状态失败'), true);
                });
            });

            $('#confirmStartTask').on('click', function () {
                var taskKey = $('#startTaskKey').val();
                var payload = {task_key: taskKey, date: '', start_date: '', end_date: ''};
                if ($('#dateArgGroup').is(':visible')) {
                    if (currentDateMode === 'range') {
                        payload.start_date = $('#startTaskStartDate').val();
                        payload.end_date = $('#startTaskEndDate').val();
                    } else {
                        payload.date = $('#startTaskDate').val();
                    }
                }
                $('#confirmStartTask').prop('disabled', true).text('启动中...');
                App.apiPost('/instock/console/api/start', payload).done(function (resp) {
                    $('#taskStartModal').modal('hide');
                    App.toast(resp.message || '任务已启动');
                    App.refreshFast();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '任务启动失败'), true);
                }).always(function () {
                    $('#confirmStartTask').prop('disabled', false).text('启动');
                });
            });

            $('.schedule-mode-tab').on('click', function () {
                var mode = $(this).data('mode');
                if (mode) setScheduleMode(mode);
            });
            $('.date-arg-tabs').on('click', '.schedule-mode-tab', function () {
                setDateMode($(this).data('date-mode'));
            });
            $('#schedulePreset,#scheduleHour,#scheduleMinute,#scheduleWeekday,#scheduleInterval').on('change', syncSchedulePreview);
            $('#scheduleCronInput').on('input', function () {
                if (currentScheduleMode === 'manual') syncSchedulePreview();
            });
            $('#saveTaskSchedule').on('click', function () {
                var taskKey = $('#scheduleTaskKey').val();
                var cron = activeCronExpression();
                $('#saveTaskSchedule').prop('disabled', true).text('保存中...');
                App.apiPost('/instock/console/api/schedule', {
                    task_key: taskKey,
                    schedule_mode: 'cron',
                    cron_expression: cron
                }).done(function (resp) {
                    $('#taskScheduleModal').modal('hide');
                    App.toast(resp.message || '已保存计划');
                    App.refreshTasks();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '保存计划失败'), true);
                }).always(function () {
                    $('#saveTaskSchedule').prop('disabled', false).text('保存计划');
                });
            });
            $('#resetTaskSchedule').on('click', function () {
                var taskKey = $('#scheduleTaskKey').val();
                App.apiPost('/instock/console/api/schedule', {
                    task_key: taskKey,
                    schedule_mode: 'default',
                    cron_expression: ''
                }).done(function (resp) {
                    $('#taskScheduleModal').modal('hide');
                    App.toast(resp.message || '已恢复默认计划');
                    App.refreshTasks();
                }).fail(function (xhr) {
                    App.toast(App.parseAjaxError(xhr, '恢复默认计划失败'), true);
                });
            });
        },

        openStartModal: function (task) {
            task = task || {};
            $('#startTaskKey').val(task.key || '');
            $('#startTaskName').text(task.name || task.key || '任务');
            $('#startTaskDate').val('');
            $('#startTaskStartDate').val('');
            $('#startTaskEndDate').val('');
            setDateMode('list');
            $('#dateArgGroup').toggle(!!task.allow_date_args);
            if (task.warning) {
                $('#startTaskWarning').text(task.warning).show();
            } else {
                $('#startTaskWarning').hide().text('');
            }
            $('#taskStartModal').modal('show');
        },

        openScheduleModal: function (task) {
            task = task || {};
            $('#scheduleTaskKey').val(task.key || '');
            $('#scheduleTaskName').text(task.name || task.key || '任务');
            $('#scheduleDefaultText').text(task.default_schedule_text || task.schedule_text || '无默认计划');
            $('#scheduleCurrentText').text(task.effective_schedule_text || task.schedule_text || '无计划');
            $('#scheduleCronInput').val(task.cron_expression || '30 17 * * 1-5');
            setScheduleMode(task.cron_expression ? 'manual' : 'picker');
            $('#taskScheduleModal').modal('show');
        }
    };
})(window, jQuery);

# SpreadJS → AG Grid Community 迁移方案

## 1. 目标

将 `stock_web.html` 中的 SpreadJS TableSheet 替换为 AG Grid Community (MIT)，Excel 导出由 SheetJS 补充。

### 1.1 变更范围

| 层级 | 变更 |
|---|---|
| 前端 | `stock_web.html` 重写 JS，新增 SheetJS |
| 后端 | `dataTableHandler.py` MyEncoder 日期格式改为 ISO |
| 静态资源 | 删除 5 个 SpreadJS 文件，新增 2 个文件 |

---

## 2. 依赖变更

### 移除（~7.5MB）

```
instock/web/static/js/gc.spread.sheets.all.min.js        4.9MB
instock/web/static/js/gc.spread.excelio.min.js            1.5MB
instock/web/static/js/gc.spread.sheets.tablesheet.min.js  465KB
instock/web/static/js/gc.spread.sheets.resources.zh.min.js 295KB
instock/web/static/css/gc.spread.sheets.excel2013white.css 437KB
```

### 新增（~900KB）

```
instock/web/static/js/ag-grid-community.min.js    ~850KB (从 CDN 下载本地化)
instock/web/static/js/sheetjs.xlsx.min.js          ~500KB (SheetJS Excel 导出)
```

AG Grid 零外部依赖，不需要 React、RxJS 等附加库。

### 保留

```
jquery.min-3.7.1.js
bootstrap.min-3.4.1.js
bootstrap-datepicker.min.js + bootstrap-datepicker.zh-CN.min.js
FileSaver.js                  ← 不再需要（SheetJS 自带下载）
```

---

## 3. API 映射表

| 当前 SpreadJS | 迁移后 AG Grid Community |
|---|---|
| `new GC.Spread.Sheets.Workbook(el)` | `agGrid.createGrid(el, gridOptions)` |
| `spread.dataManager().addTable()` + remote URL | `fetch(url)` → `gridApi.setGridOption('rowData', data)` |
| `productTable.addView("v", colInfos)` | 不需要（columnDefs 直接定义） |
| `sheet.setDataView(myView)` | 不需要（rowData 绑定自动渲染） |
| `myView.fetch()` | `loadData()` 重取数据 |
| `sheet.togglePinnedColumns([0,1,2])` | `pinned: 'left'` 在 columnDef 中声明 |
| `GC.Spread.Sheets.CellTypes.HyperLink()` | `cellRenderer: params => \`<a href="...">...</a>\`` |
| `sheet.options.allowAddNew = false` | 默认不开启编辑 |
| `sheet.applyTableTheme(light18)` | `theme: agGrid.themeQuartz` |
| `GC.Spread.Excel.IO().save()` | `XLSX.writeFile(wb, filename)` |
| `StatusBar` + `RecordCountItem` | `statusBar.statusPanels` 内建组件 |
| `spread.suspendPaint()` / `resumePaint()` | 不需要（自动批处理） |
| `ResizeObserver` + `spread.refresh()` | 不需要（自适应容器） |

---

## 4. 代码改造

### 4.1 后端：`dataTableHandler.py`

只改一行 — MyEncoder 日期格式：

```python
# 改前（第 24-25 行）
delta = datetime.datetime.combine(obj, datetime.time.min) - datetime.datetime(1899, 12, 30)
return f'/OADate({float(delta.days) + (float(delta.seconds) / 86400)})/'

# 改后
return obj.isoformat()
```

`isoformat()` 原本就是注释掉的备用方案（第 26 行），现在已经可以直接启用。

### 4.2 前端：`stock_web.html` 完整重写

#### HTML 结构

```html
{% extends "layout/default.html" %}

{% block main_content %}
<link rel="stylesheet" href="/static/css/bootstrap-datepicker3.min.css" />
<!-- AG Grid 主题 -->
<link rel="stylesheet" href="/static/css/ag-grid-theme.css" />
<!-- 或直接内联主题：AG Grid v33+ 的 Quartz 主题可通过 JS theme 对象设置 -->

<script src="/static/js/ag-grid-community.min.js"></script>
<script src="/static/js/sheetjs.xlsx.min.js"></script>
<script src="/static/js/bootstrap-datepicker.min.js"></script>
<script src="/static/js/bootstrap-datepicker.zh-CN.min.js"></script>

<div style="height:100%;display:flex;flex-direction:column;">
    <div style="padding:4px 8px;display:flex;justify-content:space-between;align-items:center;background:#f5f5f5;border-bottom:1px solid #ddd;">
        <div>
            <span style="font-weight:bold;">{{ web_module_data.name }}</span>
            <span style="margin-left:16px;">日期：</span>
            <input type="text" value="{{ date_now }}" id="dateid"
                   class="input-group-sm form-control date-picker" style="display:inline-block;width:120px;">
        </div>
        <div>
            <button id="resetFilter" class="btn btn-sm btn-primary">重置筛选</button>
            <button id="saveExcel" class="btn btn-sm btn-primary">保存 Excel</button>
        </div>
    </div>
    <div id="instock-data" style="flex:1;" class="ag-theme-quartz"></div>
    <div id="statusBar" style="padding:2px 8px;background:#f0f0f0;border-top:1px solid #ddd;font-size:12px;">
        <i class="fa fa-commenting-o"></i>
        总记录/筛选记录：<b id="totalRecords">0</b> / <b id="filteredRecords">0</b> 条
        - 当前位置：第 <b id="currentRow">0</b> 行
    </div>
</div>
```

#### JavaScript 核心逻辑

```javascript
// ===== 1. 全局变量 =====
const nameParam = $.getUrlVar('table_name');
let dateParam = "{{ date_now }}";
const colInfos = {% raw web_module_data.column_names %};
let gridApi;

// ===== 2. 列定义转换 =====
// colInfos 格式: [{value: "code", caption: "代码", width: 60, headerStyle: {...}}, ...]
// columnDefs 格式: [{field: "code", headerName: "代码", width: 60, ...}, ...]
function buildColumnDefs() {
    return colInfos.map(col => {
        const def = {
            field: col.value,
            headerName: col.caption,
            width: col.width || 100,
            sortable: true,
            filter: true,
            resizable: true,
        };

        // 前 3 列冻结（date, code, name）
        if (['date', 'code', 'name'].includes(col.value)) {
            def.pinned = 'left';
        }

        // code 列渲染为超链接
        if (col.value === 'code') {
            def.cellRenderer = params => {
                if (!params.value) return '';
                const date = params.data.date || dateParam;
                const name = params.data.name || '';
                return `<a href="/instock/data/indicators?code=${params.value}&date=${date}&name=${name}"
                           target="_blank" style="color:#1a0dab;">${params.value}</a>`;
            };
        }

        // change_rate 列：涨红跌绿
        if (col.value === 'change_rate') {
            def.cellClassRules = {
                'ag-cell-positive': params => params.value > 0,
                'ag-cell-negative': params => params.value < 0,
            };
        }

        return def;
    });
}

// ===== 3. 数据加载 =====
async function loadData(date) {
    const resp = await fetch(`/instock/api_data?name=${nameParam}&date=${date}`);
    const data = await resp.json();
    gridApi.setGridOption('rowData', data);
    updateStatusBar();
}

// ===== 4. 状态栏更新 =====
function updateStatusBar() {
    if (!gridApi) return;
    const total = gridApi.getDisplayedRowCount();
    document.getElementById('totalRecords').textContent = total;
    document.getElementById('filteredRecords').textContent = total; // 筛选后与展示数相同
}

// ===== 5. Excel 导出（SheetJS） =====
function exportExcel() {
    const rowData = [];
    gridApi.forEachNodeAfterFilterAndSort(node => rowData.push(node.data));

    const headers = colInfos.map(c => c.caption);
    const keys = colInfos.map(c => c.value);
    const exportData = rowData.map(row => {
        const obj = {};
        keys.forEach((k, i) => obj[headers[i]] = row[k] ?? '');
        return obj;
    });

    const ws = XLSX.utils.json_to_sheet(exportData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, nameParam);
    XLSX.writeFile(wb, `${nameParam}${dateParam}.xlsx`);
}

// ===== 6. 初始化 =====
$(document).ready(function () {
    const gridOptions = {
        columnDefs: buildColumnDefs(),
        rowData: [],
        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true,
            floatingFilter: true,  // 列头下方快速筛选框
        },
        // 禁止编辑（只读展示）
        editable: false,
        // 行选择
        rowSelection: 'single',
        // 分页（可选，大量数据时开启）
        // pagination: true,
        // paginationPageSize: 100,
        // 事件
        onGridReady: () => {
            loadData(dateParam);
        },
        onSelectionChanged: () => {
            const selected = gridApi.getSelectedNodes();
            if (selected.length > 0) {
                document.getElementById('currentRow').textContent = selected[0].rowIndex + 1;
            }
        },
        onFilterChanged: updateStatusBar,
        onSortChanged: updateStatusBar,
    };

    const gridDiv = document.querySelector('#instock-data');
    gridApi = agGrid.createGrid(gridDiv, gridOptions);

    // ===== 7. 日期选择器 =====
    $('.date-picker').datepicker({
        language: 'zh-CN',
        format: 'yyyy-mm-dd',
        autoclose: true,
        todayHighlight: true,
    }).on('changeDate', function (ev) {
        dateParam = $('#dateid').val();
        loadData(dateParam);
    });

    // ===== 8. 按钮事件 =====
    document.getElementById('saveExcel').onclick = exportExcel;
    document.getElementById('resetFilter').onclick = () => {
        gridApi.setFilterModel(null);
    };
});
```

#### 补充 CSS（涨跌颜色）

```css
.ag-cell-positive { color: #ff0000 !important; }  /* 涨为红色 */
.ag-cell-negative { color: #00aa00 !important; }  /* 跌为绿色 */
```

---

## 5. 文件变更清单

| 操作 | 文件 | 说明 |
|---|---|---|
| ✏️ 修改 | `instock/web/templates/stock_web.html` | 完整重写 HTML + JS |
| ✏️ 修改 | `instock/web/dataTableHandler.py` L24-25 | OADate → ISO 日期 |
| ✏️ 修改 | `instock/web/templates/common/meta.html` L2 | 删除 `<meta name="spreadjs culture">` |
| ➕ 新增 | `instock/web/static/js/ag-grid-community.min.js` | 从 CDN 下载 |
| ➕ 新增 | `instock/web/static/js/sheetjs.xlsx.min.js` | 从 CDN 下载 |
| ❌ 删除 | `instock/web/static/js/gc.spread.sheets.all.min.js` | |
| ❌ 删除 | `instock/web/static/js/gc.spread.sheets.tablesheet.min.js` | |
| ❌ 删除 | `instock/web/static/js/gc.spread.sheets.resources.zh.min.js` | |
| ❌ 删除 | `instock/web/static/js/gc.spread.excelio.min.js` | |
| ❌ 删除 | `instock/web/static/css/gc.spread.sheets.excel2013white.css` | |

---

## 6. 实施步骤

### 步骤 1：下载静态资源

```bash
# AG Grid Community
curl -o instock/web/static/js/ag-grid-community.min.js \
  https://cdn.jsdelivr.net/npm/ag-grid-community@35.0.0/dist/ag-grid-community.min.js

# SheetJS
curl -o instock/web/static/js/sheetjs.xlsx.min.js \
  https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js
```

### 步骤 2：修改后端

`dataTableHandler.py` 第 24-25 行改为 `return obj.isoformat()`。

### 步骤 3：重写 stock_web.html

按第 4.2 节的完整代码替换。

### 步骤 4：删除 SpreadJS 文件

删除 5 个 `gc.spread.*` 文件。

### 步骤 5：功能验证

- [ ] 页面加载：grid 正常渲染，列冻结生效，数据正确展示
- [ ] 列筛选：列头筛选菜单正常，floating filter 可用
- [ ] 列排序：点击列头排序正常
- [ ] 超链接：code 列可点击，新窗口打开指标页
- [ ] Excel 导出：导出文件内容完整，列名正确
- [ ] 日期切换：日期选择器切换后数据刷新
- [ ] 重置筛选：筛选后点击重置恢复全部数据
- [ ] 涨跌颜色：change_rate 列正值红色、负值绿色
- [ ] 状态栏：行数、筛选数、当前位置更新正确
- [ ] 响应式：窗口缩放 grid 自适应

---

## 7. 工作量估算

| 阶段 | 内容 | 预估时间 |
|---|---|---|
| 准备 | 下载静态资源 + 后端改一行 | 0.5h |
| 核心改造 | 重写 stock_web.html（HTML + JS + CSS） | 2-3h |
| 测试 | 功能验证（10 项 checklist） | 1h |
| **合计** | | **3.5-4.5h** |

远低于 Univer 方案的 1-2 人日，因为：
- AG Grid 的数据模型与后端 JSON 直接匹配，无需转换层
- 列定义与现有 colInfos 几乎 1:1
- 零外部依赖，无 React/RxJS 配置
- 稳定 API，无需摸索

---

## 8. 风险

| 风险 | 级别 | 说明 |
|---|---|---|
| Excel 导出 | 🟢 | SheetJS 成熟方案，AG Grid Community 的 `forEachNodeAfterFilterAndSort` 精确获取导出数据 |
| 列定义兼容 | 🟢 | `colInfos` → `columnDefs` 一行 `map` 完成 |
| 超链接 | 🟢 | `cellRenderer` 返回 HTML 字符串，浏览器原生 `<a>` 行为 |
| AG Grid 版本升级 | 🟢 | v34+ 稳定 API，CDN 版本号锁定 |
| 性能 | 🟢 | 虚拟化渲染，万行数据 < 100ms |

**无阻断性风险。**

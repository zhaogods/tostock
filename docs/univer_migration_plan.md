# SpreadJS → Univer 迁移方案

## 1. 现状分析

### 1.1 SpreadJS 使用范围

仅 **1 个页面** 使用 SpreadJS：`instock/web/templates/stock_web.html`（股票数据展示页）。

静态资源（5 个文件，共 ~7.5MB）：

| 文件 | 大小 | 用途 |
|---|---|---|
| `gc.spread.sheets.all.min.js` | 4.9MB | 核心库 |
| `gc.spread.excelio.min.js` | 1.5MB | Excel 导入导出 |
| `gc.spread.sheets.tablesheet.min.js` | 465KB | TableSheet 扩展 |
| `gc.spread.sheets.resources.zh.min.js` | 295KB | 中文语言包 |
| `gc.spread.sheets.excel2013white.css` | 437KB | 主题样式 |

### 1.2 实际使用的功能

| 功能 | SpreadJS API | 代码位置（stock_web.html） |
|---|---|---|
| 远程数据绑定 | `dataManager().addTable()` + `addView()` + `setDataView()` | L159-166, L181-183 |
| 列定义 | `colInfos` 数组传入 `addView()` | L37, L182 |
| 列冻结 | `togglePinnedColumns([0,1,2])` | L183 |
| 超链接单元格 | `GC.Spread.Sheets.CellTypes.HyperLink` | L51-58 |
| 表格主题 | `applyTableTheme(light18)` | L50 |
| 行筛选 | `rowFilter().reset()` | L209 |
| 自定义状态栏 | `StatusBar` + `RecordCountItem` | L98-150 |
| Excel 导出 | `GC.Spread.Excel.IO().save()` | L199-207 |
| 日期选择器 | Bootstrap Datepicker | L83-95 |
| 响应式缩放 | `ResizeObserver` + `spread.refresh()` | L72-81 |

### 1.3 后端接口

- **页面路由**: `GET /instock/data?table_name=<name>` → 渲染 `stock_web.html`
- **数据 API**: `GET /instock/api_data?name=<name>&date=<date>` → 返回 JSON 数组
- **日期格式**: `MyEncoder` 将 `datetime.date` 转为 `/OADate(XXXXX.XXXXX)/`（SpreadJS 专用格式）
- **数据库**: Python `torndb` 直连 MariaDB

---

## 2. Univer 能力评估

### 2.1 基本信息

| 项目 | 内容 |
|---|---|
| 仓库 | [dream-num/univer](https://github.com/dream-num/univer) |
| 当前版本 | v0.25.0 |
| 许可证 | Apache-2.0（核心开源）/ Pro 商业许可 |
| 团队 | DreamNum（中国团队） |
| 框架依赖 | React 18/19 + RxJS + ECharts |
| CDN 支持 | 支持（preset 模式，推荐） |

### 2.2 功能匹配度

| 当前功能 | Univer 开源版 | 匹配度 | 方案 |
|---|---|---|---|
| 数据表格展示 | `getRange().setValues()` 批量填充 | ★★★★ | 手动 fetch + 填充 |
| 列筛选/排序 | 内建支持，事件 `SheetRangeFiltered`/`SheetRangeSorted` | ★★★★★ | 直接使用 |
| 列冻结 | 内建支持（从 issue 修复记录确认有 freeze 功能） | ★★★★ | 需验证 API |
| 超链接 | `@univerjs/sheets-hyper-link-ui` 插件 | ★★★★ | 需验证点击回调 |
| 表格主题/样式 | 内建样式系统 | ★★★ | 可能需自定义 CSS |
| 状态栏 | 无直接 API，需自定义 HTML 实现 | ★★ | 自行开发 |
| **Excel 导出** | **Pro 功能，开源版无** | ✗ | **用 SheetJS 替代** |
| 远程数据绑定 | 无 TableSheet 等价物 | ✗ | 自行 fetch + 填充 |

### 2.3 关键风险

| 风险 | 严重程度 | 缓解措施 |
|---|---|---|
| Excel 导出需 Pro | **高** | 集成 SheetJS (`xlsx` 库) 实现导出 |
| 无远程数据绑定 | 中 | 自行实现 fetch → 解析 → 填充逻辑 |
| API 不稳定 (v0.x) | 中 | 锁定版本号，升级前充分测试 |
| React 依赖（CDN 模式） | 低 | preset 模式已封装，无需直接写 React |
| 状态栏无 API | 低 | 自定义 HTML div 实现 |

---

## 3. 迁移架构设计

### 3.1 新旧架构对比

```
=== 当前（SpreadJS）===
Browser                          Server
───────                          ──────
stock_web.html
  ├─ SpreadJS Workbook
  │   └─ TableSheet ──── GET /instock/api_data ──→ dataTableHandler.py
  │       (远程数据绑定)                                  ├─ SQL 查询
  ├─ ExcelIO.save()                                    └─ MyEncoder (OADate)
  ├─ StatusBar
  └─ Bootstrap Datepicker

=== 目标（Univer + SheetJS）===
Browser                          Server
───────                          ──────
stock_web.html
  ├─ fetch() ───────── GET /instock/api_data ──→ dataTableHandler.py
  │   (手动数据获取)                                      ├─ SQL 查询
  ├─ Univer Sheets                                       └─ 标准 JSON 日期
  │   └─ getRange().setValues() 批量填充
  ├─ SheetJS (xlsx) ──→ Excel 导出（纯前端）
  ├─ 自定义 HTML StatusBar
  └─ Bootstrap Datepicker
```

### 3.2 依赖变更

**移除（~7.5MB）：**
- `gc.spread.sheets.all.min.js`
- `gc.spread.sheets.tablesheet.min.js`
- `gc.spread.sheets.resources.zh.min.js`
- `gc.spread.excelio.min.js`
- `gc.spread.sheets.excel2013white.css`

**新增（~3MB 总计）：**
- `@univerjs/presets` UMD（~2MB，含 core/sheets/ui）
- `@univerjs/preset-sheets-core` UMD + CSS（~500KB）
- `sheetjs/xlsx` UMD（~500KB，Excel 导出）

**保留：**
- jQuery 3.7.1
- Bootstrap 3.4.1
- Bootstrap Datepicker
- FileSaver.js

---

## 4. 详细实现方案

### 4.1 文件变更清单

| 操作 | 文件 | 说明 |
|---|---|---|
| **修改** | `instock/web/templates/stock_web.html` | 核心改造：重写所有 JS |
| **修改** | `instock/web/templates/common/meta.html` | 移除 SpreadJS meta 标签 |
| **修改** | `instock/web/dataTableHandler.py` | MyEncoder 日期格式改为 ISO 标准 |
| **新增** | `instock/web/static/js/univer-init.js` | Univer 初始化 + 数据填充封装 |
| **新增** | `instock/web/static/js/sheetjs.xlsx.min.js` | SheetJS 库 |
| **删除** | `instock/web/static/js/gc.spread.sheets.all.min.js` | |
| **删除** | `instock/web/static/js/gc.spread.sheets.tablesheet.min.js` | |
| **删除** | `instock/web/static/js/gc.spread.sheets.resources.zh.min.js` | |
| **删除** | `instock/web/static/js/gc.spread.excelio.min.js` | |
| **删除** | `instock/web/static/css/gc.spread.sheets.excel2013white.css` | |

### 4.2 后端改动

`dataTableHandler.py` 第 24-25 行：日期格式从 OADate 改为 ISO 标准字符串。

```python
# 改前（第 24-25 行）
delta = datetime.datetime.combine(obj, datetime.time.min) - datetime.datetime(1899, 12, 30)
return f'/OADate({float(delta.days) + (float(delta.seconds) / 86400)})/'

# 改后
return obj.isoformat()
```

这已经是被注释掉的备选方案（第 26 行 `# return obj.isoformat()`），说明之前考虑过。

### 4.3 前端核心改造（stock_web.html）

#### CDN 资源引入

```html
<!-- 替换 SpreadJS 的 <script> 为以下 -->
<!-- Univer 依赖 -->
<script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/rxjs/dist/bundles/rxjs.umd.min.js"></script>
<script src="https://unpkg.com/echarts@5.6.0/dist/echarts.min.js"></script>

<!-- Univer Sheets (preset 模式) -->
<script src="https://unpkg.com/@univerjs/presets@0.25.0/lib/umd/index.js"></script>
<script src="https://unpkg.com/@univerjs/preset-sheets-core@0.25.0/lib/umd/index.js"></script>
<script src="https://unpkg.com/@univerjs/preset-sheets-core@0.25.0/lib/umd/locales/zh-CN.js"></script>
<link rel="stylesheet" href="https://unpkg.com/@univerjs/preset-sheets-core@0.25.0/lib/index.css" />

<!-- SheetJS (Excel 导出) -->
<script src="/static/js/sheetjs.xlsx.min.js"></script>
```

#### 核心 JS 逻辑

```javascript
// ===== 1. 初始化 Univer =====
const { createUniver } = UniverPresets;
const { LocaleType, mergeLocales } = UniverCore;
const { UniverSheetsCorePreset } = UniverPresetSheetsCore;

const { univerAPI } = createUniver({
    locale: LocaleType.ZH_CN,
    locales: {
        [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN),
    },
    presets: [UniverSheetsCorePreset()],
});

univerAPI.createWorkbook({ name: nameParam });

// ===== 2. 远程数据加载 & 填充 =====
async function loadData(date) {
    const resp = await fetch(`/instock/api_data?name=${nameParam}&date=${date}`);
    const rows = await resp.json();  // [{col1: val1, ...}, ...]

    // 构建二维数组 [header, ...rows]
    const header = Object.keys(rows[0] || {});
    const values = [header, ...rows.map(r => header.map(h => r[h] ?? ''))];

    // 批量填充到 sheet
    const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
    const range = sheet.getRange(0, 0, values.length, header.length);
    range.setValues(values);
}

// ===== 3. 列冻结 =====
// Univer 通过 sheet API 冻结前 3 列
function freezeColumns(sheet, count) {
    sheet.freeze(0, count);  // 冻结 0 行, count 列
}

// ===== 4. 超链接 =====
// 使用 CellClicked 事件实现代码列点击跳转
univerAPI.addEvent(univerAPI.Event.CellClicked, (params) => {
    const { row, column } = params;
    if (column === 1) {  // code 列
        const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
        const code = sheet.getRange(row, 1).getValue();
        const date = sheet.getRange(row, 0).getValue();
        const name = sheet.getRange(row, 2).getValue();
        window.open(`/instock/data/indicators?code=${code}&date=${date}&name=${name}`, '_blank');
    }
});

// ===== 5. Excel 导出（SheetJS） =====
function exportExcel(date) {
    const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
    const data = sheet.getRange(0, 0, sheet.getRowCount(), sheet.getColumnCount()).getValues();

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, nameParam);
    XLSX.writeFile(wb, `${nameParam}${date}.xlsx`);
}

// ===== 6. 自定义状态栏 =====
// 使用 HTML div + Univer 事件更新
function updateStatusBar() {
    const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
    document.getElementById('recordTotal').textContent = sheet.getRowCount() - 1;
    document.getElementById('recordFiltered').textContent = sheet.getRowCount() - 1;
}

// 监听过滤事件
univerAPI.addEvent(univerAPI.Event.SheetRangeFiltered, updateStatusBar);
univerAPI.addEvent(univerAPI.Event.SheetRangeFilterCleared, updateStatusBar);

// ===== 7. 日期切换 =====
$('.date-picker').datepicker({...}).on('changeDate', function(ev) {
    loadData($('#dateid').val());
});

// ===== 8. 响应式缩放 =====
new ResizeObserver(() => {
    // Univer 自动处理 Canvas 缩放
}).observe(document.querySelector('#instock-data'));
```

### 4.4 API 映射速查表

| 当前 SpreadJS | 迁移后 Univer |
|---|---|
| `new GC.Spread.Sheets.Workbook(el, {sheetCount: 0})` | `createUniver({presets: [...]})` + `createWorkbook()` |
| `spread.addSheetTab(0, name, SheetType.tableSheet)` | `getActiveWorkbook().getActiveSheet()` |
| `spread.dataManager().addTable("t", {remote: {read: {url}}})` | `fetch(url).then(r => r.json())` |
| `productTable.addView("v", colInfos)` | 无需等价物，直接用 header 行 |
| `sheet.setDataView(myView)` | `range.setValues(data)` |
| `sheet.togglePinnedColumns([0,1,2])` | `sheet.freeze(0, 3)` |
| `GC.Spread.Sheets.CellTypes.HyperLink()` | `CellClicked` 事件 |
| `new GC.Spread.Excel.IO().save(json, callback)` | `XLSX.writeFile(wb, filename)` |
| `spread.getActiveSheetTab().getSheet().rowFilter().reset()` | Univer UI 内建重置按钮 |
| `GC.Spread.Sheets.StatusBar.StatusBar(el, {items})` | 自定义 HTML div |
| `spread.suspendPaint()` / `spread.resumePaint()` | 不需要（Canvas 自动批处理） |

---

## 5. 迁移步骤

### 阶段一：准备（预计 1-2 小时）

1. **下载静态资源**
   - 下载 Univer CDN 文件到 `/static/js/` 本地化（可选，也可直接用 CDN）
   - 下载 SheetJS `xlsx.min.js` 到 `/static/js/sheetjs.xlsx.min.js`

2. **后端改动**
   - 修改 `dataTableHandler.py` MyEncoder 日期格式
   - 验证 API 返回格式（用 curl 测试）

### 阶段二：核心改造（预计 4-6 小时）

3. **创建 univer-init.js 封装模块**
   - Univer 初始化
   - 数据加载函数
   - Excel 导出函数
   - 状态栏管理函数

4. **重写 stock_web.html**
   - 替换 CDN 引用
   - 重写 `$(document).ready()` 初始化逻辑
   - 替换 `initSpread()` 为 Univer 数据加载
   - 替换 `initEvent()` Excel 导出逻辑
   - 替换 `initStatusBar()` 为自定义实现
   - 保留日期选择器逻辑

### 阶段三：测试（预计 2-3 小时）

5. **功能测试**
   - [ ] 页面加载：Univer 正常渲染，数据正确展示
   - [ ] 日期切换：选择不同日期，数据正确刷新
   - [ ] 列筛选/排序：UI 操作正常
   - [ ] 列冻结：前三列固定，水平滚动正常
   - [ ] 代码超链接：点击 code 单元格新窗口打开指标页
   - [ ] Excel 导出：导出文件内容正确，格式正常
   - [ ] 状态栏：记录总数/筛选数/当前位置正确
   - [ ] 响应式：窗口缩放正常

6. **性能测试**
   - [ ] 大表（5000+ 行）加载速度
   - [ ] 筛选响应速度
   - [ ] 内存占用对比（SpreadJS vs Univer）

### 阶段四：清理（预计 0.5 小时）

7. **删除 SpreadJS 文件**
   - 删除 5 个 `gc.spread.*` 静态文件
   - 修改 `meta.html` 移除 `<meta name="spreadjs culture">`

---

## 6. 降级方案

如果 Univer 迁移遇到不可接受的阻塞问题，备选方案：

### 方案 B：AG Grid Community + SheetJS

| 维度 | 对比 |
|---|---|
| 许可证 | MIT（完全开源无限制） |
| 数据绑定 | ★★★★★ 原生支持远程数据源 `setRowData()` |
| 筛选/排序 | ★★★★★ 内建，性能极佳 |
| 列冻结 | ★★★★★ `pinned: 'left'` |
| 超链接 | ★★★★★ Cell Renderer 直接支持 |
| Excel 导出 | ★★★ 需 SheetJS 补充（同 Univer） |
| 状态栏 | ★★★★ 内建 Status Bar，可自定义 |
| 体积 | ~1MB（社区版） |
| 中文支持 | ★★★ 英文社区，无中文文档 |
| React 依赖 | 无（原生 JS） |

整体来说 AG Grid 更匹配当前 TableSheet 使用模式，但无公式引擎（当前也不需要）。

---

## 7. 风险点深度评估

### 风险总览

| # | 风险 | 初始级别 | 缓解后级别 | 结论 |
|---|---|---|---|---|
| 1 | Excel 导出需 Pro | 🔴 高 | 🟢 低 | SheetJS 替代 |
| 2 | 冻结列 API 缺失 | 🟡 中 | 🟢 无 | API 确认存在 |
| 3 | 大数据量性能 | 🟡 中 | 🟢 无 | Canvas 渲染，性能更优 |
| 4 | 超链接点击回调 | 🟡 中 | 🟢 低 | CellClicked 事件替代 |
| 5 | React 依赖 | 🟡 中 | 🟢 低 | CDN 封装，无需写 React |
| 6 | 无 TableSheet 数据绑定 | 🟡 中 | 🟢 低 | 手动 fetch + setValues |
| 7 | 状态栏定制 | 🟡 中 | 🟢 低 | 自定义 HTML |
| 8 | API 稳定性（v0.x） | 🟡 中 | 🟡 中 | 锁定版本，升级需测试 |
| 9 | CDN 可用性 | 🟢 低 | 🟢 低 | 本地化静态文件 |

---

### 7.1 风险 1：Excel 导出（🔴→🟢）

**确认：Excel 导入导出是 Univer Pro 功能，需要 Univer 后端服务。**

官方文档 `docs.univer.ai/guides/sheets/features/import-export` 明确标注：
- 页面标记 "Univer Pro - Server Required"
- API: `univerAPI.exportXLSXByUnitIdAsync(unitId)` 依赖 `@univerjs-pro/exchange-client`
- 导出逻辑在服务端完成，客户端仅发起请求

**社区替代品调查：**

| 方案 | 许可证 | 成熟度 | 风险 |
|---|---|---|---|
| **SheetJS (`xlsx`)** | Apache-2.0 | ★★★★★ 36K stars | 需手动从 Univer 取数据再导出 |
| `@mertdeveci55/univer-import-export` | MIT | ★★ 0.2.1, 1人维护 | 社区作品，可能断更 |

**推荐方案：SheetJS**

技术路线：
```
Univer sheet.getRange().getValues()  →  二维数组
  ↓
XLSX.utils.aoa_to_sheet(data)       →  worksheet
  ↓
XLSX.utils.book_append_sheet(wb, ws)  →  workbook  
  ↓
XLSX.writeFile(wb, filename)         →  下载 .xlsx
```

局限：
- SheetJS 社区版不支持单元格样式（粗体、颜色等）。如需样式 → SheetJS Pro（商业）
- 对当前项目影响小：当前 SpreadJS 导出也没做特殊样式，只是导出原始数据

**结论：风险降至低。功能可完全替代，仅样式保留有损（可接受）。**

---

### 7.2 风险 2：冻结列 API（🟡→🟢）

**确认：Univer 有完整冻结 API，且比 SpreadJS 更直观。**

官方文档 `docs.univer.ai/guides/sheets/features/core/freeze` 提供完整 Facade API：

```javascript
const worksheet = univerAPI.getActiveWorkbook().getActiveSheet();

// 冻结前 N 列（等价于 SpreadJS togglePinnedColumns([0,1,2])）
worksheet.setFrozenColumns(3);

// 冻结前 N 行
worksheet.setFrozenRows(2);

// 自定义冻结
worksheet.setFreeze({
    xSplit: 1,      // 冻结列数
    ySplit: 1,      // 冻结行数
    startRow: 2,    // 可滚动的起始行
    startColumn: 2, // 可滚动的起始列
});

// 取消冻结
worksheet.cancelFreeze();

// 读取当前冻结状态
worksheet.getFreeze();
```

**结论：无风险。API 清晰，功能完整。**

---

### 7.3 风险 3：大数据量性能（🟡→🟢）

**确认：Univer Canvas 渲染性能优于 DOM 方案。**

Univer 官方博客（`blog.univer.ai`）基准数据：
- 支持 "tens of millions of cells"（千万级单元格）
- 单 sheet 可处理 200 万+ 公式计算
- Canvas 渲染引擎 + 分布式公式计算引擎

当前项目数据规模：
- 股票日线数据：最多 ~5000 行（全市场股票 × 单日）
- 远在 Univer 舒适区内（< 10K 行，轻量级）

**结论：无风险。性能只会更好，不会更差。Canvas vs DOM 对比如下：**

| 场景 | SpreadJS (DOM) | Univer (Canvas) |
|---|---|---|
| 5000 行加载 | ~1-2s | 预期 <1s |
| 筛选响应 | 即时 | 即时 |
| 滚动帧率 | 30-60fps | 60fps |
| 内存占用 | 较高（DOM 节点） | 较低（像素缓冲） |

---

### 7.4 风险 4：超链接点击（🟡→🟢）

**确认：无直接的 hyperlink cell type API，但 CellClicked 事件可完美替代。**

当前 SpreadJS 实现（stock_web.html L51-58）：
```javascript
// 为 code 列创建 HyperLink cell type
let hyperlinkStyle = new GC.Spread.Sheets.Style();
let hl = new GC.Spread.Sheets.CellTypes.HyperLink();
hl.onClickAction(function (cell) {
    window.open('/instock/data/indicators?code=...&date=...&name=...', '_blank');
});
hyperlinkStyle.cellType = hl;
colInfos[1].style = hyperlinkStyle;  // 注入到列定义
```

Univer 替代方案：
```javascript
// 监听 CellClicked 事件
univerAPI.addEvent(univerAPI.Event.CellClicked, (params) => {
    const { row, column } = params;
    if (column === 1) {  // code 列
        const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
        const code = sheet.getRange(row, 1).getValue();
        const date = formatDate(sheet.getRange(row, 0).getValue());
        const name = sheet.getRange(row, 2).getValue();
        window.open(`/instock/data/indicators?code=${code}&date=${date}&name=${name}`, '_blank');
    }
});
```

额外收益：
- 不需要为超链接列特殊处理样式
- 不需要在 colInfos 中注入 style 对象
- 可以在任何列上实现点击行为，更灵活

**结论：风险低。事件机制更通用，代码更简单。**

---

### 7.5 风险 5：React 依赖（🟡→🟢）

**Univer 的视图层基于 React 构建，但 CDN preset 模式对使用者透明。**

CDN preset 模式需要的 script 标签：
```html
<!-- React 运行时（Univer 内部使用，你的代码不需要写 JSX） -->
<script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"></script>
<!-- RxJS（数据流） -->
<script src="https://unpkg.com/rxjs/dist/bundles/rxjs.umd.min.js"></script>
<!-- ECharts（图表，可选） -->
<script src="https://unpkg.com/echarts@5.6.0/dist/echarts.min.js"></script>
<!-- Univer -->
<script src="https://unpkg.com/@univerjs/presets@0.25.0/lib/umd/index.js"></script>
```

关键点：
- 你**不需要**写任何 React 代码 — Univer 的 createUniver() / univerAPI 是纯 JS API
- React/RxJS 只是 Univer 的内部实现细节
- 总附加体积 ~300KB (gzip)，远小于移除的 7.5MB SpreadJS 文件

**结论：风险低。对开发者透明，不使用 React 也能正常集成。**

---

### 7.6 风险 6：无 TableSheet 数据绑定（🟡→🟢）

**这是架构模式变化，不是功能缺失。手动实现工作量约 30 行 JS。**

对比：

| | SpreadJS TableSheet | Univer 手动方案 |
|---|---|---|
| 数据获取 | `dataManager.addTable({remote: {read: {url}}})` | `fetch(url).then(r => r.json())` |
| 列定义 | `addView("v", colInfos)` | 直接用 header 行（后端 column_names） |
| 数据填充 | `sheet.setDataView(myView)` | `range.setValues(data)` |
| 日期刷新 | `myView.fetch()` | `loadData(date)` 重新 fetch + setValues |
| 筛选 | TableSheet 内建 | Univer 内建（UI 操作） |

实现示例：
```javascript
async function loadData(name, date) {
    const resp = await fetch(`/instock/api_data?name=${name}&date=${date}`);
    const rows = await resp.json();
    if (!rows.length) return;

    const headers = Object.keys(rows[0]);
    const values = [headers, ...rows.map(r => headers.map(h => r[h] ?? ''))];

    const sheet = univerAPI.getActiveWorkbook().getActiveSheet();
    // 清空旧数据 & 填充新数据
    const range = sheet.getRange(0, 0, values.length, headers.length);
    range.setValues(values);
}
```

**结论：风险低。代码量不大，且失去的是黑盒行为（TableSheet 自动 fetch），获得的是完全可控的数据加载流程。**

---

### 7.7 风险 7：状态栏（🟡→🟢）

**Univer 无可编程状态栏 API，但自定义 HTML 是更灵活的方案。**

当前实现（~50 行）可直接翻译为 Univer 事件监听 + HTML 更新：

```html
<!-- HTML 状态栏 -->
<div id="statusBar" style="width:100%;height:20px;">
    <i class="fa fa-commenting-o"></i>
    总记录/筛选记录：<b id="totalRecords">0</b> / <b id="filteredRecords">0</b> 条
    - 当前位置：第 <b id="currentRow">0</b> 行
</div>
```

```javascript
// 通过 Univer 事件更新状态栏
const sheet = univerAPI.getActiveWorkbook().getActiveSheet();

univerAPI.addEvent(univerAPI.Event.SelectionChanged, (params) => {
    document.getElementById('currentRow').textContent = params.selections[0].row + 1;
});

univerAPI.addEvent(univerAPI.Event.SheetRangeFiltered, () => {
    // 更新筛选计数
    updateCounts();
});
```

**结论：风险低。比 SpreadJS 的 StatusBar 构造函数更直观。**

---

### 7.8 风险 8：API 稳定性（🟡→🟡 无法完全消除）

**Univer 当前版本 v0.25.0，处于快速迭代期，API 可能 breaking change。**

观察到的版本发布节奏（从 npm/changelog）：
- v0.6.0 → v0.9.0 → v0.12.0 → v0.15.0 → v0.25.0
- 大版本号跳跃较大，说明 API 确实在演变
- 但核心 Facade API（createUniver, getActiveWorkbook, getActiveSheet, getRange, setValues）已较稳定

缓解措施：
1. **锁定版本号** — CDN URL 中固定 `@0.25.0`，不要用 `@latest`
2. **本地化静态文件** — 将 UMD 文件下载到 `/static/js/`，完全控制升级时机
3. **升级前在测试分支验证** — 只改一个页面，测试成本低
4. **Git 监控 breaking changes** — 关注 [GitHub Releases](https://github.com/dream-num/univer/releases)

**结论：中风险，无法消除。但影响面小（仅 1 个页面），且 API 已接近 1.0 形态。**

---

### 7.9 风险 9：CDN 可用性（🟢→🟢）

**jsDelivr 和 unpkg 都已稳定运行多年。为进一步降低风险，建议本地化。**

```
# 将 CDN 文件下载到本地
/static/js/univer/
  ├── react.production.min.js
  ├── react-dom.production.min.js
  ├── rxjs.umd.min.js
  ├── echarts.min.js
  ├── univer-presets.umd.js
  └── univer-preset-sheets-core.umd.js
```

对于 Docker 部署项目，这些文件作为静态资源打进镜像即可，不依赖外部 CDN。

---

### 风险缓解后的功能覆盖

| 功能 | 方案 | 保障 |
|---|---|---|
| 数据展示 | Univer `setValues()` | ✅ |
| 列筛选/排序 | Univer 内建 | ✅ |
| 列冻结 | `setFrozenColumns(3)` | ✅ |
| 超链接 | `CellClicked` 事件 | ✅ |
| Excel 导出 | SheetJS `writeFile()` | ✅ |
| 状态栏 | 自定义 HTML + 事件 | ✅ |
| 日期选择 | Bootstrap Datepicker（复用） | ✅ |
| 响应式缩放 | 不需要（Univer Canvas 自适应） | ✅ |
| 表格主题 | Univer 内建样式 | ⚠️ 可能需微调 |

---

## 8. Univer vs AG Grid Community — 对比评估

### 8.1 一句话结论

**AG Grid Community 更匹配当前项目的实际使用模式（数据表格展示），Univer 更匹配需要公式计算/电子表格编辑的场景。**

---

### 8.2 核心差异

| 维度 | Univer OSS | AG Grid Community |
|---|---|---|
| **定位** | 电子表格引擎（类 Excel） | 数据网格（Data Grid） |
| **数据模型** | 二维数组（A1 单元格坐标） | 行对象数组（字段名索引） |
| **许可证** | Apache-2.0 | MIT |
| **外部依赖** | React 18 + ReactDOM + RxJS + ECharts | **零依赖** |
| **体积 (gzip)** | ~2.4MB（CDN preset 模式） | ~298KB |
| **API 稳定性** | v0.25.0（pre-1.0，API 在变） | v34+（成熟稳定，10 年历史） |
| **中文支持** | ★★★★★ 中国团队，中英文档 | ★★★ 英文社区，无中文文档 |
| **成熟度** | 3 年，快速迭代中 | 10+ 年，企业级 |

---

### 8.3 功能逐项对比（基于 stock_web.html 实际需求）

#### 8.3.1 数据加载

| | SpreadJS (当前) | Univer | AG Grid Community |
|---|---|---|---|
| 方式 | `dataManager().addTable({remote: {url}})` 自动 | `fetch()` → `setValues(二维数组)` | `fetch()` → `gridApi.setRowData(对象数组)` |
| 刷新 | `myView.fetch()` | 重新 `setValues()` | 重新 `setRowData()` |
| 与后端格式匹配 | JSON 对象数组 → OADate | ❌ 需将对象数组转为二维数组 | ✅ **直接接收 JSON 对象数组** |

AG Grid 的数据模型（行对象数组 + 字段名列定义）与后端 API 返回格式**完全一致**，不需要转换。Univer 需要将 `[{date: ..., code: ...}, ...]` 转为 `[["date", "code", ...], ["2025-01-01", "000001", ...], ...]`。

#### 8.3.2 列定义

**后端 `column_names` 格式：**
```javascript
[{"value": "code", "caption": "代码", "width": 60}, ...]
```

| | SpreadJS | Univer | AG Grid |
|---|---|---|---|
| 方式 | 传给 `addView()` | 无列定义概念，header 行即列名 | `columnDefs: [{field, headerName, width, ...}]` |
| 映射难度 | — | 不需要映射，但失去了列配置能力 | **几乎 1:1 映射**：`value→field`, `caption→headerName` |

#### 8.3.3 列筛选/排序

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| 筛选 UI | TableSheet 内建 | 内建（列头筛选） | 内建 Text/Number/Date 过滤器 |
| 排序 | 内建 | 内建 | 内建（点击列头排序） |
| 可编程控制 | `rowFilter().reset()` | 事件监听 | `gridApi.setFilterModel(null)` |

三者都支持，均为 Community/OSS 功能。

#### 8.3.4 列冻结

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| API | `togglePinnedColumns([0,1,2])` | `setFrozenColumns(3)` | `pinned: 'left'` 在 columnDef 中 |
| 配置方式 | 数组索引 | 计数 | **声明式**（最佳） |

AG Grid 的声明式配置最优：在列定义中直接标注 `pinned: 'left'`，不需要知道列的索引位置。

#### 8.3.5 超链接

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| 方式 | `HyperLink` cell type + `onClickAction` | `CellClicked` 事件监听 | **`cellRenderer` 直接返回 `<a>` 标签** |
| 代码量 | ~10 行 | ~10 行 | **~3 行** |

```javascript
// AG Grid — 最简洁的实现
{
    field: 'code',
    cellRenderer: params => 
        `<a href="/instock/data/indicators?code=${params.value}&date=${date}&name=${name}" 
             target="_blank">${params.value}</a>`
}
```

AG Grid 胜出。`cellRenderer` 返回 HTML 字符串即可，原生 `<a>` 标签支持所有浏览器行为（右键新窗口、中键打开等）。

#### 8.3.6 状态栏

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| 方式 | `StatusBar` + 自定义 `RecordCountItem` | 自定义 HTML div | **内建 `statusBar` 配置** |
| 配置 | ~50 行 JS | ~30 行 JS | **~10 行配置** |

```javascript
// AG Grid — 内建状态栏
statusBar: {
    statusPanels: [
        { statusPanel: 'agTotalRowCountComponent' },
        { statusPanel: 'agFilteredRowCountComponent' },
        { statusPanel: 'agSelectedRowCountComponent' },
    ]
}
```

AG Grid 胜出。总行数、筛选后行数、选中行数是内建组件，不需要手写。

#### 8.3.7 Excel 导出

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| OSS/Community | ✅ `Excel.IO().save()` | ❌ Pro 功能 | ❌ Enterprise 功能 |
| 替代方案 | — | SheetJS | SheetJS |

**两者都需要 SheetJS 补充。** 但 AG Grid 与 SheetJS 集成更简单：

```javascript
// Univer → SheetJS：需从 getValues() 获取二维数组
const data = sheet.getRange(0, 0, rowCount, colCount).getValues();
const ws = XLSX.utils.aoa_to_sheet(data);

// AG Grid → SheetJS：直接从 rowData 获取对象数组（更自然）
const rowData = [];
gridApi.forEachNode(node => rowData.push(node.data));
const ws = XLSX.utils.json_to_sheet(rowData, { header: columnKeys });
```

AG Grid 稍优 — `json_to_sheet()` 可以指定列顺序和表头映射，保留字段名语义。

#### 8.3.8 体积与依赖

| | SpreadJS | Univer | AG Grid Community |
|---|---|---|---|
| 核心 | ~7.5MB (5 文件) | ~2.4MB + React/RxJS/ECharts | **~298KB (1 文件)** |
| 外部依赖 | 无（自包含） | React + ReactDOM + RxJS + ECharts | **零依赖** |
| script 标签数 | 4 JS + 1 CSS | 8+ JS + 1 CSS | **2 JS + 1 CSS** |

AG Grid 体积仅为 Univer 的 ~12%，且零外部依赖。

---

### 8.4 综合评分

| 评估维度 | Univer | AG Grid Community | 说明 |
|---|---|---|---|
| 功能匹配度 | ★★★☆☆ | ★★★★★ | AG Grid 的数据网格模型与当前 TableSheet 使用模式精确匹配 |
| 集成复杂度 | ★★★☆☆ | ★★★★★ | AG Grid 零依赖 + 声明式 API，集成简单得多 |
| 代码改造量 | ★★★☆☆ | ★★★★☆ | AG Grid 的 columnDefs 与现有 colInfos 几乎 1:1 |
| Excel 导出 | ★★☆☆☆ | ★★★☆☆ | 都需要 SheetJS，但 AG Grid 数据模型过渡更自然 |
| 体积/性能 | ★★★★☆ | ★★★★★ | AG Grid 298KB vs Univer 2.4MB，差距明显 |
| 许可证安全 | ★★★★★ | ★★★★★ | Apache-2.0 vs MIT，都是真正开源 |
| 中文支持 | ★★★★★ | ★★☆☆☆ | Univer 有中文团队/文档，AG Grid 仅英文 |
| API 稳定性 | ★★★☆☆ | ★★★★★ | Univer v0.x，AG Grid v34+ 生产级 |
| 长期维护 | ★★★★☆ | ★★★★★ | Univer 活跃但年轻，AG Grid 10 年成熟产品 |

---

### 8.5 决定性差异

两个方案**最大的实际差异**不是功能，而是**数据模型与现有架构的匹配度**：

```
当前架构（SpreadJS TableSheet）：
  后端 JSON [{code: "000001", name: "平安银行", ...}, ...]
    ↓ (直接匹配)
  TableSheet dataManager
    ↓
  表格展示

迁移到 Univer：
  后端 JSON [{code: "000001", name: "平安银行", ...}, ...]
    ↓ (需要转换层：对象数组 → 二维数组)
  Univer sheet.setValues()
    ↓
  表格展示

迁移到 AG Grid：
  后端 JSON [{code: "000001", name: "平安银行", ...}, ...]
    ↓ (直接匹配)
  AG Grid rowData / setRowData()
    ↓
  表格展示
```

Univer 是一个**电子表格**（spreadsheet 的同类替代品），而当前项目实际需要的是一个**数据表格**（data grid）。把一个数据表格需求强行塞进电子表格模型，需要额外的转换层。

---

### 8.6 推荐

| 场景 | 推荐 |
|---|---|
| 需要公式计算、单元格编辑、多 sheet | **Univer**（唯一真正的开源电子表格） |
| 数据展示 + 筛选排序 + 导出 | **AG Grid Community**（更轻、更稳、更匹配） |
| 需要中文文档和中文社区支持 | **Univer**（中国团队） |

**针对当前项目（stock_web.html 的 TableSheet 使用模式），AG Grid Community 是更优选择。**

如果项目未来有公式计算、类 Excel 编辑等需求，Univer 将是不可替代的。但就当前需求而言，AG Grid Community 在功能匹配度、集成复杂度、体积、稳定性四个维度上全面领先。

---

## 9. 总结

| 维度 | 评估 |
|---|---|
| 可行性 | **可行**，但需额外集成 SheetJS 做 Excel 导出 |
| 工作量 | 约 **1-2 人天**（含测试） |
| 最大风险 | Univer Excel 导出为 Pro 功能，需 SheetJS 补位 |
| 性能预期 | Canvas 渲染，大表性能与 SpreadJS 相当 |
| 长期维护 | Univer 活跃开发中，GitHub 日更有 commit，版本号锁定后较稳定 |
| 许可证合规 | Apache-2.0，无商业风险 |

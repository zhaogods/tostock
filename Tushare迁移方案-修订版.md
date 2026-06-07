# Tushare 数据源迁移方案（修订版）

## 一、迁移背景与目标

### 1.1 核心问题

**东方财富反爬严重**，影响数据稳定性：
- 频繁触发反爬验证
- 需要维护代理池和Cookie
- 熔断器频繁触发
- 数据获取成功率不稳定

### 1.2 迁移目标

✅ **减少东方财富依赖** - 能用Tushare替代的全部迁移  
✅ **提升数据完整性** - 补齐Tushare现有接口的缺失字段  
✅ **保持计算逻辑不变** - 仅替换数据源，不改变业务逻辑  
✅ **保留新浪数据** - 新浪接口稳定，无需迁移  

### 1.3 迁移原则

1. **数据结构兼容** - 新接口输出格式与现有完全一致
2. **平滑过渡** - 支持降级，不影响现有功能
3. **优先级驱动** - 优先迁移高频、反爬严重的接口

---

## 二、当前东方财富使用情况分析

### 2.1 主要使用场景

| 模块 | 接口 | 使用频率 | 反爬影响 | 是否可迁移 |
|-----|------|---------|---------|-----------|
| stock_hist_em.py | 实时行情 | 高 | 高 | ✅ 已部分实现 |
| stock_hist_em.py | 历史K线 | 高 | 高 | ✅ 已部分实现 |
| stock_fund_em.py | 资金流向 | 高 | 高 | ⚠️ 部分可迁移 |
| stock_selection.py | 选股器 | 中 | 高 | ❌ 无法迁移 |
| stock_lhb_em.py | 龙虎榜 | 低 | 中 | ❌ 无法迁移 |
| stock_dzjy_em.py | 大宗交易 | 低 | 中 | ❌ 无法迁移 |
| fund_etf_em.py | ETF行情 | 中 | 中 | ❌ 建议保留 |
| stock_fhps_em.py | 分红配送 | 低 | 低 | ✅ 可迁移 |
| stock_chip_race.py | 筹码竞赛 | 低 | 低 | ❌ 无法迁移 |
| stock_limitup_reason.py | 涨停原因 | 低 | 低 | ❌ 无法迁移 |
| stock_cpbd.py | 操盘必读 | 低 | 低 | ❌ 无法迁移 |

### 2.2 当前降级策略

```python
# stockfetch.py 中的降级逻辑
fetch_stocks(date):
  1. 尝试 Tushare
  2. 失败 → 降级东方财富 stock_zh_a_spot_em()
  3. 熔断器触发 → 返回 None
```

**问题**: 当Tushare数据不完整时（缺失19个财务字段），仍然依赖东方财富降级

---


## 三、Tushare 2000积分可迁移的东方财富数据

### 3.1 股票实时行情补全（高优先级）

#### 当前状态
- **Tushare获取**: daily + daily_basic（60%完整度）
- **缺失19个字段**: 全部来自东方财富
- **降级策略**: Tushare失败 → 东方财富

#### 可补全的财务字段（via fina_indicator）

```python
# Tushare fina_indicator 接口可提供：
eps                    → basic_eps          # 每股收益
bps                    → bvps               # 每股净资产  
capital_rese_ps        → per_capital_reserve # 每股公积金
undist_profit_ps       → per_unassign_profit # 每股未分配利润
roe_waa                → roe_weight          # 加权净资产收益率
grossprofit_margin     → sale_gpr            # 毛利率
debt_to_assets         → debt_asset_ratio    # 资产负债率
or_yoy                 → toi_yoy_ratio       # 营业收入同比增长
```

#### 可补全的基础字段（via stock_basic扩展）

```python
# 当前仅获取 ts_code, name
# 可扩展获取：
industry               → industry            # 所处行业
list_date              → listing_date        # 上市时间
```

#### 无法从Tushare获取的字段

```python
# 这些字段东方财富有，但不影响核心功能，可保持为0
speed_increase         # 涨速（实时计算）
speed_increase_5       # 5分钟涨跌（实时计算）
speed_increase_60      # 60日涨跌幅（需历史计算）
speed_increase_all     # 年初至今涨跌幅（需历史计算）
total_operate_income   # 营业收入（可从income接口获取，但非实时）
parent_netprofit       # 归属净利润（可从income接口获取，但非实时）
netprofit_yoy_ratio    # 净利润同比（可计算，但非实时）
report_date            # 报告期（可从财务数据获取）
```


#### 迁移效果

**迁移前**: 
- Tushare完整度 60% → 东方财富降级获取剩余40%

**迁移后**:
- Tushare完整度 85%（补齐8个核心财务字段 + 2个基础字段）
- 东方财富降级保留，但触发频率大幅降低

**收益**:
- ✅ 减少80%的东方财富行情接口调用
- ✅ 降低反爬影响
- ✅ 数据质量提升（财务数据更标准）

---

### 3.2 分红配送数据替换（中优先级）

#### 当前状态
- **数据源**: AkShare → 东方财富（二次封装）
- **接口**: `stock_fhps_em.py`
- **反爬影响**: 低（但仍依赖东方财富）

#### Tushare替代方案

**接口**: `pro.dividend()`  
**积分**: 2000+  
**优势**: 官方数据，更标准

**字段映射**:
```python
# Tushare → 项目字段
div_proc        → 分红进度
stk_div         → 每股送股
stk_bo_rate     → 每股转增
cash_div        → 每股派息
record_date     → 股权登记日
ex_date         → 除权除息日
```

**实施要点**:
- 保持输出格式与现有完全一致
- 作业文件: `basic_data_other_daily_job.py`


---

### 3.3 资金流向数据（部分可迁移）

#### 当前状态
- **数据源**: Tushare（今日）+ 东方财富（3/5/10日）
- **接口**: `stock_fund_em.py`
- **反爬影响**: 高

#### 迁移策略

**已迁移**: 
- ✅ 今日资金流向（Tushare moneyflow接口）

**无法迁移**:
- ❌ 3日/5日/10日资金流向 - Tushare无对应接口
- ❌ 板块资金流向 - Tushare无对应接口

**保持现状**: 
- 今日数据优先Tushare，失败降级东方财富
- 多日数据继续使用东方财富

**降低影响**:
- 多日资金流向使用频率较低
- 可通过缓存降低调用频率


---

## 四、无法迁移的东方财富数据（保留）

### 4.1 必须保留的东方财富接口

| 数据类型 | 原因 | 影响 |
|---------|------|------|
| 选股器（200+字段） | Tushare无综合选股接口 | 高频使用 |
| 龙虎榜 | Tushare无对应接口 | 低频，可接受 |
| 大宗交易 | Tushare无对应接口 | 低频，可接受 |
| 涨停原因 | Tushare无对应接口 | 低频，可接受 |
| 筹码竞赛 | Tushare无对应接口 | 低频，可接受 |
| 操盘必读 | Tushare无对应接口 | 低频，可接受 |
| 3/5/10日资金流 | Tushare仅支持今日 | 中频使用 |
| 板块资金流 | Tushare无对应接口 | 中频使用 |

### 4.2 保留策略

**优化方向**:
1. **增加缓存** - 降低实时请求频率
2. **错峰请求** - 避开高峰时段
3. **保持熔断器** - 防止连续失败
4. **监控告警** - 及时发现反爬问题

**不建议迁移ETF**:
- AkShare封装更完整
- Tushare基金数据偏向公募
- ETF数据获取相对稳定


---

## 五、实施方案

### 5.1 Phase 1: 补齐财务字段（P0，1-2天）

#### 目标
完全消除对东方财富实时行情接口的依赖（降级场景除外）

#### 实施步骤

**Step 1: 扩展 stock_basic 获取**

修改 `tushare_provider.py:_get_stock_names()`:
```python
def _get_stock_info(self):
    """获取股票基本信息（扩展版）"""
    result = self._call_with_retry(
        'stock_basic',
        'stock_basic(extended)',
        lambda: self.pro.stock_basic(
            exchange='', 
            list_status='L', 
            fields='ts_code,symbol,name,industry,list_date'
        )
    )
    if result.is_success:
        df = result.data
        df['code'] = df['ts_code'].apply(self.from_ts_code)
        # 返回 {code: {'name': ..., 'industry': ..., 'list_date': ...}}
        return df.set_index('code')[['name', 'industry', 'list_date']].to_dict('index')
    return {}
```


**Step 2: 新增财务指标缓存获取**

在 `tushare_provider.py` 新增方法:
```python
def fetch_fina_indicator_batch(self, period):
    """
    批量获取财务指标（按报告期）
    period: YYYYMMDD格式，如 20231231
    """
    result = self._call_with_retry(
        'fina_indicator',
        f'fina_indicator({period})',
        lambda: self.pro.fina_indicator(period=period)
    )
    if not result.is_success:
        return None
    
    df = result.data
    df['code'] = df['ts_code'].apply(self.from_ts_code)
    
    # 仅保留需要的字段并重命名
    field_mapping = {
        'eps': 'basic_eps',
        'bps': 'bvps',
        'capital_rese_ps': 'per_capital_reserve',
        'undist_profit_ps': 'per_unassign_profit',
        'roe_waa': 'roe_weight',
        'grossprofit_margin': 'sale_gpr',
        'debt_to_assets': 'debt_asset_ratio',
        'or_yoy': 'toi_yoy_ratio',
    }
    
    result_df = pd.DataFrame()
    result_df['code'] = df['code']
    for tushare_field, project_field in field_mapping.items():
        result_df[project_field] = pd.to_numeric(
            df.get(tushare_field, 0), errors='coerce'
        ).fillna(0.0)
    
    return result_df
```


**Step 3: 添加财务数据缓存机制**

```python
# 在 tushare_provider.py 添加
def _get_latest_report_period(self, date):
    """获取最近的报告期"""
    year = date.year
    month = date.month
    if month <= 3:
        return f"{year-1}1231"
    elif month <= 6:
        return f"{year}0331"
    elif month <= 9:
        return f"{year}0630"
    else:
        return f"{year}0930"

def get_fina_indicator_cached(self, date):
    """获取财务指标（带缓存）"""
    period = self._get_latest_report_period(date)
    cache_file = f"instock/cache/fina/{period[:4]}/fina_{period}.pkl"
    
    # 检查缓存
    if os.path.exists(cache_file):
        return pd.read_pickle(cache_file)
    
    # 获取数据
    df = self.fetch_fina_indicator_batch(period)
    if df is not None:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_pickle(cache_file)
    
    return df
```


**Step 4: 修改 fetch_stock_spot 合并财务数据**

```python
# 在 tushare_provider.py 修改 fetch_stock_spot
def fetch_stock_spot(self, date):
    # ... 原有逻辑获取 daily + daily_basic ...
    
    # 补充财务指标
    try:
        fina_df = self.get_fina_indicator_cached(date)
        if fina_df is not None:
            result = result.merge(fina_df, on='code', how='left')
    except Exception as e:
        logging.warning(f"财务指标获取失败，使用默认值: {e}")
    
    # 补充基础信息（industry, list_date）
    stock_info = self._get_stock_info()
    result['industry'] = result['code'].map(
        lambda c: stock_info.get(c, {}).get('industry', '')
    )
    result['listing_date'] = result['code'].map(
        lambda c: stock_info.get(c, {}).get('list_date', None)
    )
    
    # 填充仍然缺失的字段为0（保持兼容）
    for field in ['speed_increase', 'speed_increase_5', 
                  'speed_increase_60', 'speed_increase_all']:
        if field not in result.columns:
            result[field] = 0.0
    
    return FetchResult(FetchStatus.SUCCESS, result)
```


**Step 5: 配置限流**

在 `.env` 添加:
```bash
TUSHARE_FINA_INDICATOR_RATE=200
```

**预期效果**:
- ✅ 补齐10个字段（8个财务 + 2个基础）
- ✅ 完整度 60% → 85%
- ✅ 降级频率显著降低

---

### 5.2 Phase 2: 替换分红配送（P1，1天）

#### 实施步骤

**Step 1: 新增 Tushare 分红接口**

在 `tushare_provider.py` 新增:
```python
def fetch_dividend(self, date):
    """获取分红配送数据"""
    date_str = date.strftime('%Y%m%d')
    result = self._call_with_retry(
        'dividend',
        f'dividend({date_str})',
        lambda: self.pro.dividend(record_date=date_str)
    )
    if not result.is_success:
        return result
    
    df = result.data
    if df is None or df.empty:
        return FetchResult(FetchStatus.EMPTY)
    
    # 转换为项目格式
    # ... 字段映射逻辑 ...
    return FetchResult(FetchStatus.SUCCESS, transformed_df)
```


**Step 2: 修改作业文件**

修改 `basic_data_other_daily_job.py`:
```python
def fetch_stocks_bonus(date):
    try:
        # 优先使用 Tushare
        if ts_provider is not None:
            result = ts_provider.fetch_dividend(date)
            if result.is_success:
                return result.data
        
        # 降级到 AkShare
        data = sfe.stock_fhps_em(date=trd.get_bonus_report_date())
        # ... 原有逻辑 ...
    except Exception as e:
        logging.error(f"分红配送获取异常：{e}")
    return None
```

**预期效果**:
- ✅ 移除对 AkShare 的依赖
- ✅ 数据更标准化


---

## 六、数据结构兼容性保证

### 6.1 关键原则

**零破坏性变更**:
- 输出字段名称完全一致
- 字段顺序保持不变
- 数据类型完全兼容
- 缺失值处理方式一致

### 6.2 兼容性检查清单

**Phase 1 检查**:
- [ ] fetch_stock_spot() 返回的 DataFrame 列顺序不变
- [ ] 所有字段类型与原有一致（float/int/str/date）
- [ ] NaN/None 处理方式与原有相同
- [ ] _quality 标记字段保留

**Phase 2 检查**:
- [ ] fetch_dividend() 返回格式与 AkShare 版本完全一致
- [ ] 日期格式统一（YYYY-MM-DD）


---

## 七、降级与容错

### 7.1 降级策略

**原则**: 所有新增Tushare接口失败时，保持原有逻辑

**实施**:
```python
# 财务数据获取失败 → 字段填充0（与现有一致）
try:
    fina_df = self.get_fina_indicator_cached(date)
    result = result.merge(fina_df, on='code', how='left')
except Exception:
    # 保持原有缺失字段为0的逻辑
    for field in ['basic_eps', 'bvps', ...]:
        result[field] = 0.0

# 分红数据获取失败 → 降级AkShare
try:
    data = ts_provider.fetch_dividend(date)
except Exception:
    data = sfe.stock_fhps_em(date)  # 原有逻辑
```

### 7.2 监控指标

**关键指标**:
- Tushare 财务数据获取成功率
- 东方财富降级触发频率
- 数据完整度统计


---

## 八、效益分析

### 8.1 减少东方财富依赖

| 接口类型 | 迁移前调用频率 | 迁移后调用频率 | 降低 |
|---------|--------------|--------------|------|
| 股票实时行情 | 高（每日） | 极低（仅降级） | -80% |
| 分红配送 | 低（季度） | 无（完全替代） | -100% |
| 资金流向-今日 | 高（每日） | 低（仅降级） | -50% |

### 8.2 数据质量提升

**财务数据**:
- 标准化程度: 东方财富爬取 → Tushare官方
- 更新及时性: 提升
- 数据准确性: 提升

### 8.3 成本分析

**积分**: 2000积分（已满足）  
**开发成本**: 2-3天  
**维护成本**: 降低（减少反爬处理）


---

## 九、总结

### 9.1 迁移重点

**✅ 优先迁移**:
1. **股票实时行情财务字段** - 补齐8个核心财务指标
2. **分红配送** - 完全替代AkShare

**✅ 保留不变**:
1. **新浪交易日历** - 稳定，无需迁移
2. **东方财富事件数据** - 龙虎榜、大宗交易等（Tushare无接口）
3. **AkShare ETF** - 数据更全面

### 9.2 核心原则

- **零破坏** - 不改变现有计算逻辑和数据结构
- **渐进式** - 分阶段实施，保持降级兼容
- **减依赖** - 重点减少东方财富高频接口调用


### 9.3 最终数据源架构

```
数据源架构（迁移后）
├─ Tushare (主力，2000积分)
│  ├─ 股票日线 + 财务指标 ✅ (增强)
│  ├─ 资金流向-今日 ✅
│  └─ 分红配送 ✅ (新增)
│
├─ 东方财富 (补充+降级)
│  ├─ 选股器 ⭐ (必保留)
│  ├─ 龙虎榜/大宗交易/涨停原因 ⭐ (必保留)
│  ├─ 3/5/10日资金流 ⭐ (必保留)
│  └─ 降级备份 (Tushare失败时)
│
├─ 新浪财经 (保留)
│  └─ 交易日历 ⭐ (稳定)
│
└─ AkShare
   └─ ETF数据 ⭐ (保留)
```


### 9.4 实施路线图

**Phase 1** (P0, 1-2天):
- 扩展 stock_basic 获取 industry, list_date
- 新增 fina_indicator 获取并缓存
- 修改 fetch_stock_spot 合并财务数据
- 配置限流和测试

**预期**: 完整度 60% → 85%，东方财富调用 -80%

**Phase 2** (P1, 1天):
- 新增 dividend 接口
- 修改 basic_data_other_daily_job
- 测试和验证

**预期**: 移除 AkShare 分红依赖


---

## 十、验证检查清单

### Phase 1 验证
- [ ] 财务字段正确填充（8个字段非0）
- [ ] industry 和 list_date 正确填充
- [ ] 字段顺序与原有完全一致
- [ ] 降级逻辑正常工作
- [ ] 缓存机制正常
- [ ] API频次未超限
- [ ] 与东方财富数据对比验证

### Phase 2 验证
- [ ] 分红数据格式正确
- [ ] 日期字段格式一致
- [ ] 降级到AkShare正常
- [ ] 历史数据回归测试通过

---

**文档版本**: v2.0 (修订版)  
**更新日期**: 2026-06-07  
**修订要点**: 保留新浪，重点替换东方财富，不改变现有逻辑


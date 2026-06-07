# Docker配置更新说明

## 更新日期
2026-06-07

## 更新内容

### 1. docker-compose.yml

#### 新增环境变量
```yaml
- TUSHARE_FINA_INDICATOR_RATE=${TUSHARE_FINA_INDICATOR_RATE:-160}
```

**说明**：财务指标接口限流配置，默认160次/分钟

#### 新增缓存目录挂载
```yaml
- ./data/cache/fina:/data/tostock/instock/cache/fina
```

**说明**：持久化财务数据缓存，避免重复API调用

---

## 完整更新的环境变量列表

```yaml
environment:
  - TUSHARE_TOKEN=${TUSHARE_TOKEN}
  - TUSHARE_DAILY_RATE=${TUSHARE_DAILY_RATE:-400}
  - TUSHARE_DAILY_BASIC_RATE=${TUSHARE_DAILY_BASIC_RATE:-150}
  - TUSHARE_MONEYFLOW_RATE=${TUSHARE_MONEYFLOW_RATE:-150}
  - TUSHARE_STOCK_BASIC_RATE=${TUSHARE_STOCK_BASIC_RATE:-40}
  - TUSHARE_FINA_INDICATOR_RATE=${TUSHARE_FINA_INDICATOR_RATE:-160}  # 新增
  - TUSHARE_RATE_LIMIT=${TUSHARE_RATE_LIMIT:-180}
```

---

## 完整更新的挂载目录列表

```yaml
volumes:
  - ./data/instockproxy.txt:/data/tostock/instock/config/proxy.txt
  - ./data/eastmoneycookie.txt:/data/tostock/instock/config/eastmoney_cookie.txt
  - ./data/cache/hist:/data/tostock/instock/cache/hist
  - ./data/cache/fina:/data/tostock/instock/cache/fina  # 新增
  - ./docker/docker-entrypoint.sh:/docker-entrypoint.sh:ro
```

---

## 使用方法

### 1. 更新配置
```bash
# 确保 .env 文件包含新配置
echo "TUSHARE_FINA_INDICATOR_RATE=160" >> .env
```

### 2. 重新构建并启动
```bash
# 停止现有容器
docker compose down

# 重新构建镜像
docker compose build

# 启动服务
docker compose up -d
```

### 3. 验证
```bash
# 查看容器日志
docker compose logs -f instock

# 检查缓存目录
ls -la ./data/cache/fina/
```

---

## 注意事项

1. **首次运行**：财务缓存目录会自动创建
2. **缓存持久化**：./data/cache/fina 目录会保存在宿主机
3. **季度更新**：缓存每季度自动更新，无需手动清理

---

**更新完成** ✅

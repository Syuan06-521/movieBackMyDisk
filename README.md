# filmTransfer

Stremio 目录追踪 + 夸克网盘自动/半自动转存工具

## 项目架构

```
filmTransfer/
├── config.yaml              # 配置文件（必填 quark.cookie）
├── main.py                  # CLI 入口
├── pipeline.py              # 核心流水线（串联所有模块）
├── utils.py                 # 公共工具：解析分辨率/大小/编码
├── requirements.txt
│
├── stremio/
│   ├── fetcher.py           # 解析 manifest + 分页抓取 catalog
│   └── tracker.py           # 与数据库对比，检测新内容，入队
│
├── searcher/
│   ├── models.py            # ResourceResult 数据类
│   ├── quark_search.py      # 搜索聚合器（b.funletu.com API）
│   └── filter.py            # 按分辨率/大小/编码评分过滤
│
├── quark/
│   ├── client.py            # 夸克网盘 API（认证/目录/分享转存）
│   └── browser.py           # Playwright 浏览器自动化
│
├── storage/
│   ├── database.py          # SQLite：catalog_items + transfer_tasks
│   └── sync_history.py      # 同步历史记录管理（按日期记录）
│
├── data/
│   └── filmTransfer.db      # SQLite 数据库（运行后自动创建）
├── sync_logs/               # 同步历史记录（按日期分文件）
├── failed_transfers/        # 失败记录（按日期分文件）
└── logs/
    └── filmTransfer.log     # 滚动日志（运行后自动创建）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`，**必须填写**的两项：

```yaml
quark:
  cookie: "your_quark_cookie_here"   # 从浏览器复制夸克网盘 Cookie
  # 转存路径列表（按优先级排序，自动模式使用）
  save_folders:
    - "filmTransfer"           # 主路径
    - "filmTransfer_backup"    # 备用路径 1
    - "filmTransfer_alt"       # 备用路径 2
  auto_create_folder: true     # 自动创建文件夹
```

**如何获取夸克网盘 Cookie：**
1. 浏览器访问 [pan.quark.cn](https://pan.quark.cn) 并登录
2. 按 F12 → Application → Cookies → pan.quark.cn
3. 将所有 cookie 条目拼接成 `key=value; key2=value2` 格式粘贴

### 3. 测试

```bash
# 验证 Cookie 是否有效
python main.py test-cookie

# 测试资源搜索
python main.py search "流浪地球 2023"
```

### 4. 运行

```bash
# 执行一次（手动触发）
python main.py run

# 启动定时调度器（按 config.yaml 中 check_interval_minutes 间隔自动运行）
python main.py schedule

# 查看任务状态统计
python main.py status
```

### 5. 半自动模式（推荐）

**半自动模式**：自动搜索资源并导出到 Excel，手动转存（合规性更好）

```bash
# 半自动模式运行（搜索结果导出到 Excel，不调用夸克 API）
python main.py run-semi

# 查看生成的 Excel 文件
# filmTransfer_pending.xlsx
```

**Excel 文件包含**：
- 影视名称、年份、类型
- 资源标题、分辨率、大小、编码
- 评分排序（分数越高越推荐）
- 分享链接（复制后手动去夸克官网转存）

**使用场景**：
- 想要自动化搜索和筛选，但手动选择转存内容
- 降低合规风险（无人工干预的批量转存）
- 定期运行，积累资源列表后批量手动处理

## 处理流程

```
Stremio manifest.json
        │
        ▼
  分页抓取所有 catalog 条目（movie/series）
        │
        ▼
  对比 SQLite，找出新增条目
        │
        ▼
  多关键词搜索（片名 / 片名 + 年份 / IMDb ID）
  └── b.funletu.com (JSON API，带质量评分)
        │
        ▼
  过滤 + 评分排序
  （分辨率 / 文件大小 / 视频编码）
        │
        ▼
  ┌─────────────────────────────────┐
  │      模式选择                    │
  ├─────────────────────────────────┤
  │ 全自动模式：                     │
  │ → 调用夸克网盘 API 转存最优资源    │
  │ → 保存到 save_folder/movies      │
  │ → 更新任务状态 + 推送通知         │
  ├─────────────────────────────────┤
  │ 半自动模式：                     │
  │ → 导出到 filmTransfer_pending.xlsx│
  │ → 手动转存（推荐，合规性更好）     │
  └─────────────────────────────────┘
```

## 命令行用法

```bash
# 基础命令
python main.py run              # 执行一次（根据 config.yaml 中的 mode 设置）
python main.py run-auto         # 强制全自动模式
python main.py run-semi         # 强制半自动模式（导出 Excel）
python main.py run-movie        # 只处理电影
python main.py run-series       # 只处理剧集
python main.py schedule         # 启动定时调度器
python main.py status           # 查看任务状态统计

# 历史记录查询
python main.py history          # 查看今日同步记录
python main.py history --failed # 查看今日失败记录

# 测试与调试
python main.py test-cookie      # 测试夸克 Cookie 是否有效
python main.py search "关键词"   # 测试资源搜索
python main.py debug-html "关键词" # 保存搜索结果 HTML（调试用）

# 帮助
python main.py --help           # 显示帮助信息
```

## 配置说明

### 添加更多 Stremio 插件

```yaml
stremio_addons:
  - name: "Netflix Catalog"
    manifest_url: "https://xxx/manifest.json"
    enabled: true
  - name: "Another Addon"
    manifest_url: "https://yyy/manifest.json"
    watch_types: ["movie"]   # 只监控电影
    enabled: true
```

### 分辨率和大小过滤

```yaml
filter:
  preferred_resolutions: ["2160p", "1080p", "720p"]
  min_resolution: "720p"
  min_size_gb: 0.5
  max_size_gb: 60.0
```

### 通知推送（可选）

支持 Bark（iOS）和 Telegram：

```yaml
notification:
  enabled: true
  type: "bark"
  bark_key: "your_bark_key"
```

## 注意事项

- 搜索源使用 b.funletu.com 的 JSON API，响应速度快且自带质量评分
- 夸克网盘 Cookie 有效期约 30 天，过期后需重新填写
- 建议搭配 `schedule` 模式在服务器上长期运行
- **半自动模式（run-semi）**：推荐用于降低合规风险，自动搜索 + Excel 导出，手动转存
- **同步历史记录**：运行记录保存在 `sync_logs/` 和 `failed_transfers/` 目录，按日期分文件
- **搜索关键词**：支持中文和英文，使用英文关键词通常能获得更准确的结果

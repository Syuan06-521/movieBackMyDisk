# Film Transfer - 影视抓取后台管理系统

基于 Flask + Vue 3 的影视资源抓取和转存管理系统，支持 MySQL 数据库存储。

## 功能特性

- **用户认证**: JWT Token 认证，支持多用户和 RBAC 权限管理
- **Web 管理界面**: 基于 Vue 3 + Element Plus 的现代化管理界面
- **影视目录**: 展示从 Stremio 插件收录的影视资源
- **转存任务**: 管理和跟踪影视资源的搜索和转存状态
- **同步历史**: 记录和查询同步历史，支持导出
- **系统设置**: 配置夸克网盘、资源过滤、通知等参数
- **用户管理**: 管理员可以管理用户账户

## 技术栈

### 后端
- Flask 3.x - Web 框架
- SQLAlchemy 2.x - ORM 框架
- Flask-JWT-Extended - JWT 认证
- PyMySQL - MySQL 驱动
- MySQL 8.0 - 数据库

### 前端
- Vue 3 - 渐进式 JavaScript 框架
- Element Plus - UI 组件库
- Pinia - 状态管理
- Vue Router - 路由管理
- Axios - HTTP 客户端

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+ (用于前端开发)
- MySQL 8.0+

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

#### Windows
```bash
bash scripts/init_db.bat
```

#### Linux/Mac
```bash
bash scripts/init_db.sh
```

或者手动执行 MySQL 命令：
```bash
mysql -h localhost -P 3307 -u root -p < scripts/init_db.sql
```

### 4. 配置

编辑 `.env` 文件（已包含默认配置）：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=root
MYSQL_PASSWORD=Mysql123!
MYSQL_DATABASE=film_transfer
```

### 5. 启动服务

#### 后端 API 服务
```bash
python main_server.py
```

后端服务将在 http://localhost:5000 启动

#### 前端开发服务器
```bash
cd frontend
npm install
npm run dev
```

前端开发服务器将在 http://localhost:3000 启动

### 6. 默认账号

```
用户名：admin
密码：admin123
```

**请首次登录后立即修改密码！**

## 项目架构

```
movieBackMyDisk/
├── api/                    # API 路由
├── core/                   # 核心配置和工具
├── models/                 # SQLAlchemy 模型
├── storage/                # 数据持久层
├── scripts/                # 脚本文件
├── frontend/               # 前端项目
├── main_server.py          # Flask 服务入口
├── main.py                 # CLI 入口
├── app.py                  # Flask 应用工厂
├── requirements.txt        # Python 依赖
└── config.yaml             # 应用配置
```

## API 端点

### 认证
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `POST /api/auth/refresh` - 刷新 Token
- `GET /api/auth/me` - 获取当前用户

### 用户
- `GET /api/users` - 用户列表
- `POST /api/users` - 创建用户
- `PUT /api/users/{id}` - 更新用户
- `DELETE /api/users/{id}` - 删除用户

### 影视目录
- `GET /api/catalog` - 目录列表
- `GET /api/catalog/stats` - 统计信息

### 任务
- `GET /api/tasks` - 任务列表
- `GET /api/tasks/stats` - 任务统计
- `PUT /api/tasks/{id}` - 更新任务

### 同步历史
- `GET /api/history` - 历史记录
- `GET /api/history/stats` - 统计信息
- `GET /api/history/export` - 导出 CSV

### 设置
- `GET /api/settings` - 获取所有设置
- `PUT /api/settings` - 更新设置

## 保留 CLI 功能

原有的 CLI 命令仍然可用：

```bash
python main.py run              # 执行一次
python main.py run-auto         # 强制全自动模式
python main.py run-semi         # 强制半自动模式
python main.py run-movie        # 只处理电影
python main.py run-series       # 只处理剧集
python main.py schedule         # 启动定时调度器
python main.py status           # 查看任务状态统计
python main.py history          # 查看今日同步记录
python main.py test-cookie      # 测试夸克 Cookie 是否有效
python main.py search "关键词"   # 测试资源搜索
```

## 安全建议

1. 修改 `.env` 中的默认密钥
2. 修改默认管理员密码
3. 生产环境关闭 DEBUG 模式
4. 使用 HTTPS 部署

## 许可证

MIT License

# Film Transfer 部署说明

## 部署步骤

### 第一步：MySQL 数据库配置

1. 确保 MySQL 8.0 已安装并运行
2. 检查端口配置（默认 3307）
3. 确认用户权限

### 第二步：初始化数据库

执行以下命令创建数据库和表结构：

```bash
# Windows
scripts\init_db.bat

# Linux/Mac
bash scripts/init_db.sh
```

或者使用 MySQL 命令手动执行：

```bash
mysql -h localhost -P 3307 -u root -pMysql123! < scripts/init_db.sql
```

### 第三步：后端部署

1. 安装 Python 依赖：

```bash
pip install -r requirements.txt
```

2. 配置 `.env` 文件：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=root
MYSQL_PASSWORD=Mysql123!
MYSQL_DATABASE=film_transfer
JWT_SECRET_KEY=your-secret-key-change-this-in-production
SECRET_KEY=your-flask-secret-key
FLASK_ENV=production
FLASK_DEBUG=False
```

3. 启动后端服务：

```bash
# 开发环境
python main_server.py

# 生产环境（使用 Gunicorn）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### 第四步：前端部署

#### 开发环境

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

#### 生产环境

1. 构建前端：

```bash
cd frontend
npm install
npm run build
```

2. 使用 Nginx 部署：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 第五步：配置夸克网盘

1. 登录 Film Transfer 后台管理系统
2. 访问「系统设置」页面
3. 填写夸克网盘 Cookie
4. 配置保存文件夹列表

**获取夸克网盘 Cookie 步骤：**

1. 浏览器访问 [pan.quark.cn](https://pan.quark.cn) 并登录
2. 按 F12 打开开发者工具
3. 进入 Application → Cookies → pan.quark.cn
4. 复制所有 Cookie 条目，拼接成 `key=value; key2=value2` 格式
5. 粘贴到系统设置的 Cookie 输入框

### 第六步：配置 Stremio 插件

编辑 `config.yaml` 文件，添加 Stremio 插件配置：

```yaml
stremio_addons:
  - name: "Netflix Catalog"
    manifest_url: "https://your-addon-url/manifest.json"
    enabled: true
    watch_types: ["movie", "series"]
```

## 系统服务配置（Linux）

### Systemd 服务配置

创建 `/etc/systemd/system/film-transfer.service`：

```ini
[Unit]
Description=Film Transfer API Service
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/movieBackMyDisk
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable film-transfer
sudo systemctl start film-transfer
sudo systemctl status film-transfer
```

## 安全加固

### 1. 修改默认密码

首次登录后，立即修改 admin 用户的默认密码。

### 2. 修改密钥

编辑 `.env` 文件：

```env
# 生成随机密钥（Python）
python -c "import secrets; print(secrets.token_hex(32))"

# 使用生成的密钥替换以下配置
JWT_SECRET_KEY=<生成的密钥>
SECRET_KEY=<生成的密钥>
```

### 3. 配置 HTTPS

使用 Let's Encrypt 配置免费 SSL 证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 4. 防火墙配置

仅开放必要端口：

```bash
# 仅开放 80 (HTTP) 和 443 (HTTPS)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 监控和维护

### 日志查看

```bash
# 后端日志
tail -f logs/api.log
tail -f logs/filmTransfer.log

# Systemd 服务日志
sudo journalctl -u film-transfer -f
```

### 数据库备份

```bash
# 创建备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -h localhost -P 3307 -u root -pMysql123! film_transfer > /backups/film_transfer_$DATE.sql

# 添加到 crontab（每天凌晨 2 点备份）
0 2 * * * /path/to/backup_script.sh
```

### 健康检查

访问以下端点检查服务状态：

- API 状态：`GET http://your-domain.com/`
- 登录页面：`GET http://your-domain.com/login`

## 故障排查

### 问题 1：数据库连接失败

检查 MySQL 是否运行：

```bash
# Windows
netstat -an | findstr 3307

# Linux
netstat -tlnp | grep 3307
```

### 问题 2：前端无法连接 API

检查 Nginx 配置：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 问题 3：Cookie 无效

1. 重新登录夸克网盘
2. 清除浏览器缓存
3. 重新获取 Cookie 并更新配置

## 升级指南

1. 备份数据库和配置文件
2. 拉取最新代码
3. 安装新的依赖
4. 执行数据库迁移（如有）
5. 重启服务

```bash
# 备份
cp -r . /backup/movieBackMyDisk_$(date +%Y%m%d)

# 拉取代码
git pull

# 安装依赖
pip install -r requirements.txt

# 重启服务
sudo systemctl restart film-transfer
```

## 技术支持

如有问题，请查看日志文件或联系技术支持。

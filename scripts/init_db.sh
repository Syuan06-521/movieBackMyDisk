#!/bin/bash
# 数据库初始化脚本
# 使用方法：bash scripts/init_db.sh

echo "========================================"
echo "Film Transfer Database Initialization"
echo "========================================"

# MySQL 配置
MYSQL_HOST="localhost"
MYSQL_PORT="3307"
MYSQL_USER="root"
MYSQL_PASSWORD="Mysql123!"
MYSQL_DATABASE="film_transfer"

# 检查 MySQL 连接
echo "Checking MySQL connection..."
mysql -h$MYSQL_HOST -P$MYSQL_PORT -u$MYSQL_USER -p$MYSQL_PASSWORD -e "SELECT 1" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Cannot connect to MySQL server"
    echo "Please check your MySQL configuration and make sure the server is running"
    exit 1
fi

echo "MySQL connection successful!"

# 执行初始化 SQL
echo "Executing initialization SQL..."
mysql -h$MYSQL_HOST -P$MYSQL_PORT -u$MYSQL_USER -p$MYSQL_PASSWORD < scripts/init_db.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "Database initialization completed!"
    echo "========================================"
    echo ""
    echo "Database: $MYSQL_DATABASE"
    echo ""
    echo "Default admin account:"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo ""
    echo "Please change the default password after first login!"
    echo "========================================"
else
    echo "ERROR: Database initialization failed"
    exit 1
fi

@echo off
REM 数据库初始化脚本 (Windows 版本)
REM 使用方法：init_db.bat

echo ========================================
echo Film Transfer Database Initialization
echo ========================================

REM MySQL 配置
set MYSQL_HOST=localhost
set MYSQL_PORT=3306
set MYSQL_USER=root
set MYSQL_PASSWORD=123456
set MYSQL_DATABASE=film_transfer
set MYSQL_BIN=mysql

REM 检查 MySQL 连接
echo Checking MySQL connection...
%MYSQL_BIN% -h%MYSQL_HOST% -P%MYSQL_PORT% -u%MYSQL_USER% -p%MYSQL_PASSWORD% -e "SELECT 1" > nul 2>&1

if errorlevel 1 (
    echo ERROR: Cannot connect to MySQL server
    echo Please check your MySQL configuration and make sure the server is running
    echo Make sure mysql.exe is in your PATH or set MYSQL_BIN variable
    pause
    exit /b 1
)

echo MySQL connection successful!

REM 执行初始化 SQL
echo Executing initialization SQL...
%MYSQL_BIN% -h%MYSQL_HOST% -P%MYSQL_PORT% -u%MYSQL_USER% -p%MYSQL_PASSWORD% < scripts\init_db.sql

if errorlevel 1 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Database initialization completed!
echo ========================================
echo.
echo Database: %MYSQL_DATABASE%
echo.
echo Default admin account:
echo   Username: admin
echo   Password: admin123
echo.
echo Please change the default password after first login!
echo ========================================
echo.
pause

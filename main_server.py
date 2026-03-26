"""
main_server.py - Flask 服务器主入口

启动命令：
    python main_server.py

或者使用环境变量：
    FLASK_ENV=production python main_server.py
"""
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import create_app
from core.config import settings

# 配置日志
log_path = Path("logs/api.log")
log_path.parent.mkdir(parents=True, exist_ok=True)

handler = RotatingFileHandler(
    str(log_path),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

# 配置 werkzeug 日志
logger = logging.getLogger("werkzeug")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 配置应用日志
app_logger = logging.getLogger("pipeline")
app_logger.addHandler(handler)
app_logger.setLevel(logging.INFO)

app_logger.info("=" * 50)
app_logger.info("Server started - logging initialized")
app_logger.info("=" * 50)

# 创建应用
app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("Film Transfer API Server")
    print("=" * 60)
    print(f"Environment: {settings.flask.env}")
    print(f"Debug Mode: {settings.flask.debug}")
    print(f"Server: http://{settings.flask.host}:{settings.flask.port}")
    print("=" * 60)
    print("Default admin account:")
    print("  Username: admin")
    print("  Password: admin123")
    print("=" * 60)
    print("Starting server...")
    print("=" * 60)

    app.run(
        host=settings.flask.host,
        port=settings.flask.port,
        debug=settings.flask.debug,
        threaded=True
    )

"""
config.py - 配置管理模块

从环境变量和 config.yaml 加载配置
"""
import os
import yaml
from pathlib import Path
from typing import Optional, List, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础目录
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"


class MySQLSettings:
    """MySQL 数据库配置"""
    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "123456")
    database: str = os.getenv("MYSQL_DATABASE", "film_transfer")

    @property
    def connection_url(self) -> str:
        """返回 SQLAlchemy 连接 URL"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"

    @property
    def sync_connection_url(self) -> str:
        """返回同步连接 URL（不带 async）"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"


class JWTSettings:
    """JWT 认证配置"""
    secret_key: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
    access_token_expires: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600"))
    refresh_token_expires: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "604800"))
    algorithm: str = "HS256"


class FlaskSettings:
    """Flask 应用配置"""
    secret_key: str = os.getenv("SECRET_KEY", "your-flask-secret-key")
    debug: bool = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    env: str = os.getenv("FLASK_ENV", "development")
    host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    port: int = int(os.getenv("SERVER_PORT", "5000"))


class Settings:
    """应用配置总览"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.mysql = MySQLSettings()
        self.jwt = JWTSettings()
        self.flask = FlaskSettings()

        # 加载 YAML 配置
        self._yaml_config = self._load_yaml_config()

    def _load_yaml_config(self) -> dict:
        """加载 YAML 配置文件"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    @property
    def mode(self) -> str:
        """运行模式"""
        return self._yaml_config.get("mode", "auto")

    @property
    def stremio_addons(self) -> list:
        """Stremio 插件配置"""
        return self._yaml_config.get("stremio_addons", [])

    @property
    def quark(self) -> dict:
        """夸克网盘配置"""
        return self._yaml_config.get("quark", {})

    @property
    def filter(self) -> dict:
        """资源过滤配置"""
        return self._yaml_config.get("filter", {})

    @property
    def search_sites(self) -> dict:
        """搜索站点配置"""
        return self._yaml_config.get("search_sites", {})

    @property
    def logging(self) -> dict:
        """日志配置"""
        return self._yaml_config.get("logging", {})

    @property
    def check_interval_minutes(self) -> int:
        """检查间隔"""
        return self._yaml_config.get("check_interval_minutes", "60")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._yaml_config.get(key, default)


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings

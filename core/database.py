"""
database.py - SQLAlchemy 数据库连接管理
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from core.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.mysql.sync_connection_url,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,  # 生产环境关闭 SQL 日志
)

# 创建会话工厂
SessionFactory = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 创建会话（线程安全）
db_session = scoped_session(SessionFactory)

# 基础模型类
Base = declarative_base()
Base.query = db_session.query_property()

# 元数据（用于创建表）
metadata = MetaData()


def init_db():
    """初始化数据库，创建所有表"""
    from models.user import User
    from models.catalog import CatalogItem, TransferTask, AddonSnapshot
    from models.history import SyncHistory, FailedTransfer
    from models.setting import SystemSetting, OperationLog

    # 导入所有模型后创建表
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    获取数据库会话依赖（用于 Flask）

    Usage:
        db = next(get_db())
        try:
            ...
        finally:
            db.close()
    """
    try:
        db = db_session()
        yield db
    finally:
        db_session.remove()


def get_db_session():
    """直接获取数据库会话（用于非 Flask 场景）"""
    return db_session()


def close_db():
    """关闭数据库连接"""
    db_session.remove()
    engine.dispose()

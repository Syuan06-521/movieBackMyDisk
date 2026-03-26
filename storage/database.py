"""
storage/database.py - 数据库持久化层（MySQL 版本）

兼容旧版 API，内部使用 SQLAlchemy ORM 实现
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.database import get_db_session
from models.catalog import CatalogItem, TransferTask
from storage.repositories import CatalogRepository, TaskRepository

logger = logging.getLogger(__name__)


def init_db():
    """初始化数据库（使用 core.database 中的初始化）"""
    from core.database import init_db as core_init_db
    core_init_db()
    logger.info("Database initialized")


# ============================================
# CatalogDB - 兼容旧版 API
# ============================================

class CatalogDB:
    """目录条目的增删查（兼容旧版 API）"""

    @staticmethod
    def exists(item_id: str, addon_name: str) -> bool:
        """检查条目是否存在"""
        db = get_db_session()
        try:
            repo = CatalogRepository(db)
            return repo.exists(item_id, addon_name)
        finally:
            db.close()

    @staticmethod
    def insert(item: Dict[str, Any], addon_name: str):
        """插入目录条目"""
        db = get_db_session()
        try:
            repo = CatalogRepository(db)
            repo.insert(item, addon_name)
        finally:
            db.close()

    @staticmethod
    def get_all(addon_name: Optional[str] = None) -> List[Dict]:
        """获取目录列表"""
        db = get_db_session()
        try:
            repo = CatalogRepository(db)
            items = repo.get_all(addon_name=addon_name)
            return [item.to_dict() for item in items]
        finally:
            db.close()

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """获取统计信息"""
        db = get_db_session()
        try:
            repo = CatalogRepository(db)
            return repo.get_stats()
        finally:
            db.close()


# ============================================
# TaskDB - 兼容旧版 API
# ============================================

class TaskDB:
    """转存任务的增删查改（兼容旧版 API）"""

    @staticmethod
    def has_any_task(item_id: str, addon_name: str) -> bool:
        """检查是否已有任务（避免重复创建）"""
        db = get_db_session()
        try:
            repo = TaskRepository(db)
            return repo.has_any_task(item_id, addon_name)
        finally:
            db.close()

    @staticmethod
    def create(item_id: str, addon_name: str) -> int:
        """创建任务"""
        db = get_db_session()
        try:
            repo = TaskRepository(db)
            task = repo.create(item_id, addon_name)
            return task.task_id
        finally:
            db.close()

    @staticmethod
    def update(task_id: int, **kwargs):
        """更新任务"""
        db = get_db_session()
        try:
            repo = TaskRepository(db)
            repo.update(task_id, **kwargs)
        finally:
            db.close()

    @staticmethod
    def get_by_status(status: str) -> List[Dict]:
        """根据状态获取任务"""
        db = get_db_session()
        try:
            repo = TaskRepository(db)
            tasks = repo.get_by_status(status)
            return [task.to_dict() for task in tasks]
        finally:
            db.close()

    @staticmethod
    def get_stats() -> Dict[str, int]:
        """获取任务统计"""
        db = get_db_session()
        try:
            repo = TaskRepository(db)
            return repo.get_stats()
        finally:
            db.close()


# ============================================
# 新增 ORM 风格的数据库访问
# ============================================

class CatalogDBv2:
    """目录条目管理（新版本，使用 ORM）"""

    def __init__(self):
        self.db = get_db_session()

    def close(self):
        self.db.close()

    def exists(self, item_id: str, addon_name: str) -> bool:
        return CatalogRepository(self.db).exists(item_id, addon_name)

    def insert(self, item: Dict[str, Any], addon_name: str):
        return CatalogRepository(self.db).insert(item, addon_name)

    def get_all(self, skip: int = 0, limit: int = 100,
                addon_name: Optional[str] = None,
                item_type: Optional[str] = None,
                search: Optional[str] = None) -> List[Dict]:
        items = CatalogRepository(self.db).get_all(
            skip=skip, limit=limit, addon_name=addon_name,
            item_type=item_type, search=search
        )
        return [item.to_dict() for item in items]

    def count(self, addon_name: Optional[str] = None,
              item_type: Optional[str] = None) -> int:
        return CatalogRepository(self.db).count(
            addon_name=addon_name, item_type=item_type
        )

    def get_stats(self) -> Dict[str, Any]:
        return CatalogRepository(self.db).get_stats()


class TaskDBv2:
    """转存任务管理（新版本，使用 ORM）"""

    def __init__(self):
        self.db = get_db_session()

    def close(self):
        self.db.close()

    def has_any_task(self, item_id: str, addon_name: str) -> bool:
        return TaskRepository(self.db).has_any_task(item_id, addon_name)

    def create(self, item_id: str, addon_name: str,
               status: str = 'pending') -> int:
        task = TaskRepository(self.db).create(item_id, addon_name, status)
        return task.task_id

    def update(self, task_id: int, **kwargs):
        return TaskRepository(self.db).update(task_id, **kwargs)

    def get_by_id(self, task_id: int) -> Optional[Dict]:
        """根据 task_id 获取任务"""
        task = TaskRepository(self.db).get_by_id(task_id)
        return task.to_dict() if task else None

    def get_by_status(self, status: str, skip: int = 0,
                      limit: int = 100) -> List[Dict]:
        tasks = TaskRepository(self.db).get_by_status(status, skip, limit)
        return [task.to_dict() for task in tasks]

    def get_all(self, skip: int = 0, limit: int = 100,
                status: Optional[str] = None) -> List[Dict]:
        tasks = TaskRepository(self.db).get_all(skip, limit, status)
        return [task.to_dict() for task in tasks]

    def get_stats(self) -> Dict[str, int]:
        return TaskRepository(self.db).get_stats()

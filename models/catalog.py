"""
catalog.py - 影视目录相关模型
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Index, JSON, text
from sqlalchemy.sql import func

from core.database import Base


class CatalogItem(Base):
    """影视目录条目模型"""
    __tablename__ = 'catalog_items'

    id = Column(String(100), primary_key=True, nullable=False)
    addon_name = Column(String(100), primary_key=True, nullable=False)
    item_type = Column(String(20), nullable=False, index=True)  # 'movie' or 'series'
    name = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True, index=True)
    imdb_id = Column(String(50), nullable=True)
    poster = Column(String(500), nullable=True)
    raw_meta = Column(JSON, nullable=True)
    first_seen = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index('idx_item_type', 'item_type'),
        Index('idx_year', 'year'),
        Index('idx_first_seen', 'first_seen'),
    )

    def __repr__(self):
        return f"<CatalogItem(id={self.id}, name='{self.name}', type={self.item_type})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'addon_name': self.addon_name,
            'item_type': self.item_type,
            'name': self.name,
            'year': self.year,
            'imdb_id': self.imdb_id,
            'poster': self.poster,
            'raw_meta': self.raw_meta,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
        }


class TransferTaskStatus(enum.Enum):
    """转存任务状态枚举"""
    PENDING = 'pending'
    SEARCHING = 'searching'
    FOUND = 'found'
    SAVING = 'saving'
    DONE = 'done'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    PENDING_MANUAL = 'pending_manual'


class TransferTask(Base):
    """转存任务模型"""
    __tablename__ = 'transfer_tasks'

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_item_id = Column(String(100), nullable=False, index=True)
    addon_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default='pending', index=True)
    resource_name = Column(String(500), nullable=True)
    resource_url = Column(String(500), nullable=True)
    resolution = Column(String(20), nullable=True)
    size_gb = Column(Integer, nullable=True)
    codec = Column(String(20), nullable=True)
    quark_share_id = Column(String(100), nullable=True)
    quark_save_path = Column(String(500), nullable=True)
    error_msg = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TransferTask(task_id={self.task_id}, status={self.status})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'catalog_item_id': self.catalog_item_id,
            'addon_name': self.addon_name,
            'status': self.status,
            'resource_name': self.resource_name,
            'resource_url': self.resource_url,
            'resolution': self.resolution,
            'size_gb': self.size_gb,
            'codec': self.codec,
            'quark_share_id': self.quark_share_id,
            'quark_save_path': self.quark_save_path,
            'error_msg': self.error_msg,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AddonSnapshot(Base):
    """插件快照模型"""
    __tablename__ = 'addon_snapshots'

    addon_name = Column(String(100), primary_key=True, nullable=False)
    catalog_id = Column(String(100), primary_key=True, nullable=False)
    snapshot_at = Column(DateTime, primary_key=True, server_default=func.now())
    item_count = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<AddonSnapshot(addon={self.addon_name}, catalog={self.catalog_id})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'addon_name': self.addon_name,
            'catalog_id': self.catalog_id,
            'snapshot_at': self.snapshot_at.isoformat() if self.snapshot_at else None,
            'item_count': self.item_count,
        }

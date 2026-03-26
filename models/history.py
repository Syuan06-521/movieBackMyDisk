"""
history.py - 同步历史相关模型
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Enum, DateTime, Date, Index, JSON, Text
from sqlalchemy.sql import func

from core.database import Base


class SyncHistory(Base):
    """同步历史模型"""
    __tablename__ = 'sync_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(100), nullable=False, index=True)
    addon_name = Column(String(100), nullable=False, index=True)
    item_name = Column(String(255), nullable=True)
    item_type = Column(String(20), nullable=True, index=True)  # 'movie' or 'series'
    resource_title = Column(String(500), nullable=True)
    resource_url = Column(String(500), nullable=True)
    save_path = Column(String(500), nullable=True)
    resolution = Column(String(20), nullable=True)
    size_gb = Column(Integer, nullable=True)
    codec = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, index=True)  # saved, skipped, failed, pending_manual
    sync_date = Column(Date, nullable=False, index=True, default=date.today)
    sync_time = Column(DateTime, server_default=func.now())
    error_reason = Column(Text, nullable=True)
    tried_resources = Column(JSON, nullable=True)
    attempted_paths = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_item_id_addon', 'item_id', 'addon_name'),
        Index('idx_sync_date', 'sync_date'),
        Index('idx_status', 'status'),
        Index('idx_item_type', 'item_type'),
    )

    def __repr__(self):
        return f"<SyncHistory(item_id={self.item_id}, status={self.status})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'addon_name': self.addon_name,
            'item_name': self.item_name,
            'item_type': self.item_type,
            'resource_title': self.resource_title,
            'resource_url': self.resource_url,
            'save_path': self.save_path,
            'resolution': self.resolution,
            'size_gb': self.size_gb,
            'codec': self.codec,
            'status': self.status,
            'sync_date': self.sync_date.isoformat() if self.sync_date else None,
            'sync_time': self.sync_time.isoformat() if self.sync_time else None,
            'error_reason': self.error_reason,
            'tried_resources': self.tried_resources,
            'attempted_paths': self.attempted_paths,
        }


class FailedTransfer(Base):
    """失败转存记录模型"""
    __tablename__ = 'failed_transfers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(100), nullable=False, index=True)
    addon_name = Column(String(100), nullable=False, index=True)
    item_name = Column(String(255), nullable=True)
    item_type = Column(String(20), nullable=True)  # 'movie' or 'series'
    attempted_paths = Column(JSON, nullable=True)
    error_reason = Column(Text, nullable=True)
    tried_resources = Column(JSON, nullable=True)
    failed_date = Column(Date, nullable=False, index=True, default=date.today)
    failed_time = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_failed_item_id_addon', 'item_id', 'addon_name'),
        Index('idx_failed_date', 'failed_date'),
    )

    def __repr__(self):
        return f"<FailedTransfer(item_id={self.item_id})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'addon_name': self.addon_name,
            'item_name': self.item_name,
            'item_type': self.item_type,
            'attempted_paths': self.attempted_paths,
            'error_reason': self.error_reason,
            'tried_resources': self.tried_resources,
            'failed_date': self.failed_date.isoformat() if self.failed_date else None,
            'failed_time': self.failed_time.isoformat() if self.failed_time else None,
        }

"""
setting.py - 系统设置和操作日志模型
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey, Index, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from core.database import Base


class SettingType(enum.Enum):
    """设置类型枚举"""
    STRING = 'string'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    JSON = 'json'


class SystemSetting(Base):
    """系统设置模型"""
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)
    setting_type = Column(String(20), default='string')
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemSetting(key={self.setting_key}, value={self.setting_value})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'setting_type': self.setting_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_typed_value(self):
        """获取类型化的值"""
        if self.setting_type == 'number':
            try:
                return float(self.setting_value)
            except (ValueError, TypeError):
                return self.setting_value
        elif self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            try:
                return json.loads(self.setting_value)
            except (json.JSONDecodeError, TypeError):
                return self.setting_value
        return self.setting_value


class OperationLogStatus(enum.Enum):
    """操作日志状态枚举"""
    SUCCESS = 'success'
    FAILURE = 'failure'


class OperationLog(Base):
    """操作日志模型"""
    __tablename__ = 'operation_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    status = Column(String(20), default='success', index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # 关联用户
    user = relationship("User", back_populates="operation_logs")

    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_action', 'action'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<OperationLog(action={self.action}, user_id={self.user_id})>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

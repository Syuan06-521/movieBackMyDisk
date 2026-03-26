"""
user.py - 用户模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, TIMESTAMP, func
from sqlalchemy.orm import relationship
import enum

from core.database import Base


class UserRole(enum.Enum):
    """用户角色枚举"""
    ADMIN = 'admin'
    USER = 'user'
    VIEWER = 'viewer'


class UserStatus(enum.Enum):
    """用户状态枚举"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    BANNED = 'banned'


class User(Base):
    """用户模型"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), nullable=True)
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), default=UserRole.USER, index=True)
    status = Column(Enum(UserStatus, values_callable=lambda x: [e.value for e in x]), default=UserStatus.ACTIVE, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_login = Column(TIMESTAMP, nullable=True)

    # 关联操作日志
    operation_logs = relationship("OperationLog", back_populates="user", lazy="select")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role.value})>"

    def to_dict(self, exclude_password: bool = True) -> dict:
        """转换为字典"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        return data

    @property
    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.role == UserRole.ADMIN

    @property
    def is_active(self) -> bool:
        """是否激活"""
        return self.status == UserStatus.ACTIVE

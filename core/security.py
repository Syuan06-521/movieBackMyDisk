"""
security.py - 安全工具模块

密码加密、JWT Token 生成与验证
"""
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
import jwt

from core.config import settings


def hash_password(password: str) -> str:
    """
    对密码进行 bcrypt 加密

    Args:
        password: 原始密码

    Returns:
        加密后的密码哈希
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码

    Args:
        password: 原始密码
        password_hash: 存储的密码哈希

    Returns:
        验证是否通过
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    except (ValueError, AttributeError):
        return False


def create_access_token(subject: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问 Token

    Args:
        subject: 用户 ID
        expires_delta: 过期时间增量，默认使用配置值

    Returns:
        JWT Token 字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=settings.jwt.access_token_expires)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.utcnow()
    }

    return jwt.encode(
        to_encode,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm
    )


def create_refresh_token(subject: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建刷新 Token

    Args:
        subject: 用户 ID
        expires_delta: 过期时间增量，默认使用配置值

    Returns:
        JWT Token 字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=settings.jwt.refresh_token_expires)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.utcnow()
    }

    return jwt.encode(
        to_encode,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm
    )


def decode_token(token: str, token_type: str = "access") -> Optional[int]:
    """
    解码 Token

    Args:
        token: JWT Token 字符串
        token_type: 期望的 Token 类型（access 或 refresh）

    Returns:
        用户 ID，如果 Token 无效则返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm]
        )

        # 验证 Token 类型
        if payload.get("type") != token_type:
            return None

        subject = payload.get("sub")
        if subject is None:
            return None

        return int(subject)

    except jwt.ExpiredSignatureError:
        # Token 已过期
        return None
    except jwt.InvalidTokenError:
        # Token 无效
        return None


def verify_token(token: str, token_type: str = "access") -> bool:
    """
    验证 Token 是否有效

    Args:
        token: JWT Token 字符串
        token_type: 期望的 Token 类型

    Returns:
        是否有效
    """
    return decode_token(token, token_type) is not None

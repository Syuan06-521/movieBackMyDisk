"""
repositories.py - 数据访问层（Repository 模式）

封装所有数据库操作，提供统一的接口
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload

from models.user import User, UserRole, UserStatus
from models.catalog import CatalogItem, TransferTask, TransferTaskStatus, AddonSnapshot
from models.history import SyncHistory, FailedTransfer
from models.setting import SystemSetting, OperationLog, OperationLogStatus


# ============================================
# 用户仓库
# ============================================

class UserRepository:
    """用户数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        role: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[User]:
        """获取用户列表"""
        query = self.db.query(User)

        if role:
            query = query.filter(User.role == UserRole(role))
        if status:
            query = query.filter(User.status == UserStatus(status))

        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    def create(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        role: str = 'user'
    ) -> User:
        """创建用户"""
        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            role=UserRole(role)
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: int, **kwargs) -> Optional[User]:
        """更新用户信息"""
        user = self.get_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: int) -> bool:
        """删除用户"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True

    def update_last_login(self, user_id: int):
        """更新最后登录时间"""
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()


# ============================================
# 目录仓库
# ============================================

class CatalogRepository:
    """影视目录数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: str, addon_name: str) -> Optional[CatalogItem]:
        """根据 ID 获取目录条目"""
        return self.db.query(CatalogItem).filter(
            and_(CatalogItem.id == item_id, CatalogItem.addon_name == addon_name)
        ).first()

    def get_item_full(self, item_id: str, addon_name: str) -> Optional[Dict]:
        """获取目录条目完整信息（包含 task）"""
        item = self.get_by_id(item_id, addon_name)
        if not item:
            return None
        return {
            "id": item.id,
            "name": item.name,
            "type": item.item_type,
            "year": item.year,
            "imdbId": item.imdb_id,
            "poster": item.poster,
            "_addon": addon_name,
        }

    def exists(self, item_id: str, addon_name: str) -> bool:
        """检查条目是否存在"""
        return self.db.query(CatalogItem).filter(
            and_(CatalogItem.id == item_id, CatalogItem.addon_name == addon_name)
        ).first() is not None

    def insert(self, item: Dict[str, Any], addon_name: str) -> Optional[CatalogItem]:
        """插入目录条目（如果不存在）"""
        existing = self.exists(item.get("id"), addon_name)
        if existing:
            return None

        # 解析年份：处理 "2013–2022" 或 "2013-2022" 格式，只取起始年份
        year_value = None
        raw_year = item.get("year")
        if raw_year is not None:
            try:
                # 如果是整数直接使用
                if isinstance(raw_year, int):
                    year_value = raw_year
                else:
                    # 字符串格式，提取第一个 4 位数字年份
                    year_str = str(raw_year)
                    # 处理范围格式 "2013–2022" 或 "2013-2022"
                    if '–' in year_str:
                        year_str = year_str.split('–')[0]
                    elif '-' in year_str:
                        year_str = year_str.split('-')[0]
                    # 提取数字
                    match = re.search(r'\d{4}', year_str)
                    if match:
                        year_value = int(match.group())
            except (ValueError, AttributeError):
                year_value = None

        catalog_item = CatalogItem(
            id=item.get("id"),
            addon_name=addon_name,
            item_type=item.get("type"),
            name=item.get("name"),
            year=year_value,
            imdb_id=item.get("imdbId"),
            poster=item.get("poster"),
            raw_meta=item,
        )
        self.db.add(catalog_item)
        self.db.commit()
        self.db.refresh(catalog_item)
        return catalog_item

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        addon_name: Optional[str] = None,
        item_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[CatalogItem]:
        """获取目录列表"""
        query = self.db.query(CatalogItem)

        if addon_name:
            query = query.filter(CatalogItem.addon_name == addon_name)
        if item_type:
            query = query.filter(CatalogItem.item_type == item_type)
        if search:
            query = query.filter(CatalogItem.name.like(f"%{search}%"))

        return query.order_by(desc(CatalogItem.first_seen)).offset(skip).limit(limit).all()

    def count(self, addon_name: Optional[str] = None, item_type: Optional[str] = None) -> int:
        """获取总数"""
        query = self.db.query(func.count(CatalogItem.id))
        if addon_name:
            query = query.filter(CatalogItem.addon_name == addon_name)
        if item_type:
            query = query.filter(CatalogItem.item_type == item_type)
        return query.scalar()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.db.query(func.count(CatalogItem.id)).scalar()
        movies = self.db.query(func.count(CatalogItem.id)).filter(
            CatalogItem.item_type == 'movie'
        ).scalar()
        series = self.db.query(func.count(CatalogItem.id)).filter(
            CatalogItem.item_type == 'series'
        ).scalar()

        return {
            'total': total,
            'movies': movies,
            'series': series,
        }


# ============================================
# 任务仓库
# ============================================

class TaskRepository:
    """转存任务数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: int) -> Optional[TransferTask]:
        """根据 ID 获取任务"""
        return self.db.query(TransferTask).filter(TransferTask.task_id == task_id).first()

    def get_by_task_id(self, task_id: int) -> Optional[TransferTask]:
        """根据 task_id 获取任务（别名）"""
        return self.get_by_id(task_id)

    def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[TransferTask]:
        """根据状态获取任务"""
        return self.db.query(TransferTask).filter(
            TransferTask.status == status
        ).order_by(desc(TransferTask.created_at)).offset(skip).limit(limit).all()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        item_type: Optional[str] = None
    ) -> List[TransferTask]:
        """获取任务列表"""
        query = self.db.query(TransferTask)

        if status:
            query = query.filter(TransferTask.status == status)

        return query.order_by(desc(TransferTask.created_at)).offset(skip).limit(limit).all()

    def create(
        self,
        catalog_item_id: str,
        addon_name: str,
        status: str = 'pending'
    ) -> TransferTask:
        """创建任务"""
        task = TransferTask(
            catalog_item_id=catalog_item_id,
            addon_name=addon_name,
            status=status
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update(self, task_id: int, **kwargs) -> Optional[TransferTask]:
        """更新任务"""
        task = self.get_by_id(task_id)
        if not task:
            return None

        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return task

    def has_any_task(self, item_id: str, addon_name: str) -> bool:
        """检查是否已有任务（避免重复创建）

        检查所有状态，如果任务已存在则不创建新任务
        失败的任务需要用户手动重试
        """
        return self.db.query(TransferTask).filter(
            and_(
                TransferTask.catalog_item_id == item_id,
                TransferTask.addon_name == addon_name
            )
        ).first() is not None

    def get_stats(self) -> Dict[str, int]:
        """获取任务统计"""
        query = self.db.query(TransferTask.status, func.count(TransferTask.task_id)).group_by(
            TransferTask.status
        )
        return {status: count for status, count in query.all()}

    def count(self, status: str = None) -> int:
        """获取任务总数"""
        query = self.db.query(func.count(TransferTask.task_id))
        if status:
            query = query.filter(TransferTask.status == status)
        return query.scalar()

    def get_pending_tasks(self, content_type: str = None) -> List[TransferTask]:
        """获取所有待处理任务"""
        query = self.db.query(TransferTask).filter(
            TransferTask.status == 'pending'
        )
        if content_type:
            # 需要关联 CatalogItem 过滤类型
            query = query.join(CatalogItem, and_(
                CatalogItem.id == TransferTask.catalog_item_id,
                CatalogItem.addon_name == TransferTask.addon_name,
                CatalogItem.item_type == content_type
            ))
        return query.order_by(TransferTask.created_at).all()


# ============================================
# 同步历史仓库
# ============================================

class SyncHistoryRepository:
    """同步历史数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def is_synced(self, item_id: str, addon_name: str) -> bool:
        """检查是否已同步"""
        today = date.today()
        return self.db.query(SyncHistory).filter(
            and_(
                SyncHistory.item_id == item_id,
                SyncHistory.addon_name == addon_name,
                SyncHistory.sync_date == today
            )
        ).first() is not None

    def record_sync(
        self,
        item_id: str,
        addon_name: str,
        item_name: str,
        item_type: str,
        resource_title: str,
        resource_url: str,
        save_path: str,
        status: str = 'saved',
        resolution: str = None,
        size_gb: float = None,
        codec: str = None
    ) -> SyncHistory:
        """记录同步"""
        record = SyncHistory(
            item_id=item_id,
            addon_name=addon_name,
            item_name=item_name,
            item_type=item_type,
            resource_title=resource_title,
            resource_url=resource_url,
            save_path=save_path,
            status=status,
            sync_date=date.today(),
            resolution=resolution,
            size_gb=int(size_gb) if size_gb else None,
            codec=codec,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def record_failure(
        self,
        item_id: str,
        addon_name: str,
        item_name: str,
        item_type: str,
        attempted_paths: List[str],
        error_reason: str,
        tried_resources: List[Dict] = None
    ) -> SyncHistory:
        """记录失败"""
        record = SyncHistory(
            item_id=item_id,
            addon_name=addon_name,
            item_name=item_name,
            item_type=item_type,
            status='failed',
            sync_date=date.today(),
            error_reason=error_reason,
            attempted_paths=attempted_paths,
            tried_resources=tried_resources or [],
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_today_records(self) -> List[SyncHistory]:
        """获取今日同步记录"""
        today = date.today()
        return self.db.query(SyncHistory).filter(
            and_(
                SyncHistory.sync_date == today,
                SyncHistory.status != 'failed'
            )
        ).all()

    def get_today_failures(self) -> List[SyncHistory]:
        """获取今日失败记录"""
        today = date.today()
        return self.db.query(SyncHistory).filter(
            and_(
                SyncHistory.sync_date == today,
                SyncHistory.status == 'failed'
            )
        ).all()

    def get_history(
        self,
        start_date: date,
        end_date: date,
        skip: int = 0,
        limit: int = 100,
        status: str = None
    ) -> List[SyncHistory]:
        """获取历史同步记录"""
        query = self.db.query(SyncHistory).filter(
            and_(
                SyncHistory.sync_date >= start_date,
                SyncHistory.sync_date <= end_date
            )
        )
        if status:
            query = query.filter(SyncHistory.status == status)
        return query.order_by(desc(SyncHistory.sync_time)).offset(skip).limit(limit).all()

    def count(
        self,
        start_date: date,
        end_date: date,
        status: str = None
    ) -> int:
        """获取符合条件的记录总数"""
        query = self.db.query(func.count(SyncHistory.id)).filter(
            and_(
                SyncHistory.sync_date >= start_date,
                SyncHistory.sync_date <= end_date
            )
        )
        if status:
            query = query.filter(SyncHistory.status == status)
        return query.scalar()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        today = date.today()
        today_records = self.db.query(SyncHistory).filter(
            SyncHistory.sync_date == today
        ).all()

        # pending_manual 不算作已同步，因为还没有真正转存
        return {
            'today_synced': len([r for r in today_records if r.status not in ['failed', 'pending_manual']]),
            'today_failed': len([r for r in today_records if r.status == 'failed']),
            'today_saved': len([r for r in today_records if r.status == 'saved']),
            'today_skipped': len([r for r in today_records if r.status == 'skipped']),
            'today_pending_manual': len([r for r in today_records if r.status == 'pending_manual']),
        }


# ============================================
# 系统设置仓库
# ============================================

class SettingRepository:
    """系统设置数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> Optional[SystemSetting]:
        """根据键获取设置"""
        return self.db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()

    def get_value(self, key: str, default: Any = None) -> Any:
        """获取设置值"""
        setting = self.get_by_key(key)
        if setting:
            return setting.get_typed_value()
        return default

    def set_value(
        self,
        key: str,
        value: Any,
        setting_type: str = 'string',
        description: str = None
    ) -> SystemSetting:
        """设置值"""
        setting = self.get_by_key(key)

        if setting:
            setting.setting_value = str(value)
            setting.setting_type = setting_type
            if description:
                setting.description = description
        else:
            setting = SystemSetting(
                setting_key=key,
                setting_value=str(value),
                setting_type=setting_type,
                description=description
            )
            self.db.add(setting)

        self.db.commit()
        self.db.refresh(setting)
        return setting

    def get_all(self) -> List[SystemSetting]:
        """获取所有设置"""
        return self.db.query(SystemSetting).all()

    def get_as_dict(self) -> Dict[str, Any]:
        """以字典形式获取所有设置"""
        settings = self.get_all()
        return {s.setting_key: s.get_typed_value() for s in settings}


# ============================================
# 操作日志仓库
# ============================================

class OperationLogRepository:
    """操作日志数据访问仓库"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: str = None,
        resource_id: str = None,
        details: Dict = None,
        ip_address: str = None,
        user_agent: str = None,
        status: str = 'success'
    ) -> OperationLog:
        """创建操作日志"""
        log = OperationLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[OperationLog]:
        """获取操作日志列表"""
        query = self.db.query(OperationLog)

        if user_id:
            query = query.filter(OperationLog.user_id == user_id)
        if action:
            query = query.filter(OperationLog.action == action)
        if status:
            query = query.filter(OperationLog.status == status)

        return query.order_by(desc(OperationLog.created_at)).offset(skip).limit(limit).all()

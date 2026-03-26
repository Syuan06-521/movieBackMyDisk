"""
storage/sync_history.py - 同步历史管理（MySQL 数据库版本）

用于记录每次同步的内容，避免重复保存
支持按日期存储和查询历史记录
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from core.database import get_db_session
from storage.repositories import SyncHistoryRepository

logger = logging.getLogger(__name__)


class SyncHistory:
    """
    同步历史管理器（MySQL 数据库版本）

    使用 MySQL 数据库存储同步历史，替代之前的 JSON 文件方案
    """

    def __init__(self):
        self.db = get_db_session()
        self._repo = SyncHistoryRepository(self.db)

    def close(self):
        """关闭数据库会话"""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_synced(self, item_id: str, addon_name: str) -> bool:
        """
        检查指定 item 是否已同步

        Args:
            item_id: 影视资源 ID
            addon_name: 插件名称

        Returns:
            是否已同步
        """
        try:
            return self._repo.is_synced(item_id, addon_name)
        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return False

    def record_sync(self, item_id: str, addon_name: str, item_name: str,
                    item_type: str, resource_title: str, resource_url: str,
                    save_path: str, status: str = "saved",
                    resolution: str = None, size_gb: float = None,
                    codec: str = None):
        """
        记录同步成功

        Args:
            item_id: 影视资源 ID
            addon_name: 插件名称
            item_name: 影视名称
            item_type: 类型 (movie/series)
            resource_title: 资源标题
            resource_url: 分享链接
            save_path: 保存路径
            status: 状态 (saved/skipped/failed)
            resolution: 分辨率
            size_gb: 文件大小 (GB)
            codec: 编码
        """
        try:
            # 检查是否已存在（避免重复记录）
            if self._repo.is_synced(item_id, addon_name):
                logger.debug(f"Record already exists for {item_id}, skipping duplicate")
                return

            self._repo.record_sync(
                item_id=item_id,
                addon_name=addon_name,
                item_name=item_name,
                item_type=item_type,
                resource_title=resource_title,
                resource_url=resource_url,
                save_path=save_path,
                status=status,
                resolution=resolution,
                size_gb=size_gb,
                codec=codec,
            )
            logger.info(f"Sync recorded: {item_name} -> {save_path}")
        except Exception as e:
            logger.error(f"Error recording sync: {e}")

    def record_failure(self, item_id: str, addon_name: str, item_name: str,
                       item_type: str, attempted_paths: List[str],
                       error_reason: str, tried_resources: List[Dict] = None):
        """
        记录同步失败

        Args:
            item_id: 影视资源 ID
            addon_name: 插件名称
            item_name: 影视名称
            item_type: 类型 (movie/series)
            attempted_paths: 尝试过的保存路径列表
            error_reason: 失败原因
            tried_resources: 尝试过的资源列表
        """
        try:
            self._repo.record_failure(
                item_id=item_id,
                addon_name=addon_name,
                item_name=item_name,
                item_type=item_type,
                attempted_paths=attempted_paths,
                error_reason=error_reason,
                tried_resources=tried_resources,
            )
            logger.warning(f"Failure recorded: {item_name} - {error_reason}")
        except Exception as e:
            logger.error(f"Error recording failure: {e}")

    def get_today_records(self) -> List[Dict]:
        """获取今日所有同步记录"""
        try:
            records = self._repo.get_today_records()
            return [record.to_dict() for record in records]
        except Exception as e:
            logger.error(f"Error getting today's records: {e}")
            return []

    def get_today_failures(self) -> List[Dict]:
        """获取今日所有失败记录"""
        try:
            failures = self._repo.get_today_failures()
            return [failure.to_dict() for failure in failures]
        except Exception as e:
            logger.error(f"Error getting today's failures: {e}")
            return []

    def get_history(self, start_date: str, end_date: str,
                    skip: int = 0, limit: int = 100) -> List[Dict]:
        """
        获取指定日期范围的同步记录

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            skip: 跳过记录数
            limit: 返回记录数限制

        Returns:
            同步记录列表
        """
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

            records = self._repo.get_history(start, end, skip=skip, limit=limit)
            return [record.to_dict() for record in records]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            return self._repo.get_stats()
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "today_synced": 0,
                "today_failed": 0,
                "today_saved": 0,
                "today_skipped": 0,
                "today_pending_manual": 0,
            }

    def get_success_synced_items(self) -> set:
        """
        获取所有已同步成功的项目 ID 集合（用于去重）

        Returns:
            已同步成功的项目 ID 集合，格式为 {(item_id, addon_name), ...}
        """
        try:
            from sqlalchemy import and_
            from models.history import SyncHistory as SyncHistoryModel

            records = self.db.query(SyncHistoryModel).filter(
                and_(
                    SyncHistoryModel.status.in_(['saved', 'skipped'])
                )
            ).all()

            return {(r.item_id, r.addon_name) for r in records}
        except Exception as e:
            logger.error(f"Error getting success synced items: {e}")
            return set()


# 为了方便导入，创建全局实例
_sync_history: Optional[SyncHistory] = None


def get_sync_history() -> SyncHistory:
    """获取 SyncHistory 单例实例"""
    global _sync_history
    if _sync_history is None:
        _sync_history = SyncHistory()
    return _sync_history


def close_sync_history():
    """关闭全局 SyncHistory 实例"""
    global _sync_history
    if _sync_history:
        _sync_history.close()
        _sync_history = None

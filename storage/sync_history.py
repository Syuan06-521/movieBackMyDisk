"""
storage/sync_history.py - 同步历史管理（文件版本）

用于记录每次同步的内容，避免重复保存
支持按日期存储和查询历史记录

注意：这是数据库接入前的临时方案，后期可无缝切换到数据库版本
"""
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

SYNC_LOGS_DIR = Path("sync_logs")
FAILED_TRANSFERS_DIR = Path("failed_transfers")


class SyncHistory:
    """
    同步历史管理器（文件版本，后期可替换为数据库）

    日志文件结构:
        sync_logs/sync_YYYY-MM-DD.json
        failed_transfers/failed_YYYY-MM-DD.json
    """

    def __init__(self, log_dir: str = "sync_logs", failed_dir: str = "failed_transfers"):
        self.log_dir = Path(log_dir)
        self.failed_dir = Path(failed_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self._today_cache: Optional[Dict] = None
        self._cache_date: Optional[date] = None

    def _get_today_file(self) -> Path:
        """获取今日日志文件路径"""
        today = date.today()
        return self.log_dir / f"sync_{today.isoformat()}.json"

    def _get_failed_today_file(self) -> Path:
        """获取今日失败日志文件路径"""
        today = date.today()
        return self.failed_dir / f"failed_{today.isoformat()}.json"

    def _load_today_data(self) -> Dict:
        """加载今日数据（带缓存）"""
        today = date.today()
        if self._cache_date == today and self._today_cache is not None:
            return self._today_cache

        file_path = self._get_today_file()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load sync log: {e}")
                data = {"date": today.isoformat(), "records": []}
        else:
            data = {"date": today.isoformat(), "records": []}

        self._today_cache = data
        self._cache_date = today
        return data

    def _save_today_data(self, data: Dict):
        """保存今日数据"""
        file_path = self._get_today_file()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._today_cache = data
            self._cache_date = date.today()
        except IOError as e:
            logger.error(f"Failed to save sync log: {e}")

    def _load_failed_today_data(self) -> Dict:
        """加载今日失败日志数据"""
        file_path = self._get_failed_today_file()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load failed transfer log: {e}")
                data = {"date": date.today().isoformat(), "failures": []}
        else:
            data = {"date": date.today().isoformat(), "failures": []}
        return data

    def _save_failed_today_data(self, data: Dict):
        """保存今日失败日志数据"""
        file_path = self._get_failed_today_file()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save failed transfer log: {e}")

    def is_synced(self, item_id: str, addon_name: str) -> bool:
        """
        检查指定 item 是否已同步

        Args:
            item_id: 影视资源 ID
            addon_name: 插件名称

        Returns:
            是否已同步
        """
        data = self._load_today_data()
        for record in data.get("records", []):
            if record.get("item_id") == item_id and record.get("addon_name") == addon_name:
                return True
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
        data = self._load_today_data()

        # 检查是否已存在（避免重复记录）
        for record in data.get("records", []):
            if record.get("item_id") == item_id and record.get("addon_name") == addon_name:
                logger.debug(f"Record already exists for {item_id}, skipping duplicate")
                return

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "item_id": item_id,
            "addon_name": addon_name,
            "item_name": item_name,
            "item_type": item_type,
            "resource_title": resource_title,
            "resource_url": resource_url,
            "save_path": save_path,
            "status": status,
        }

        # 可选字段
        if resolution:
            record["resolution"] = resolution
        if size_gb:
            record["size_gb"] = size_gb
        if codec:
            record["codec"] = codec

        data["records"].append(record)
        self._save_today_data(data)
        logger.info(f"Sync recorded: {item_name} -> {save_path}")

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
        data = self._load_failed_today_data()

        # 检查是否已存在（避免重复记录）
        for failure in data.get("failures", []):
            if failure.get("item_id") == item_id and failure.get("addon_name") == addon_name:
                logger.debug(f"Failure record already exists for {item_id}, skipping duplicate")
                return

        failure = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "item_id": item_id,
            "addon_name": addon_name,
            "item_name": item_name,
            "item_type": item_type,
            "attempted_paths": attempted_paths,
            "error_reason": error_reason,
            "tried_resources": tried_resources or [],
        }

        data["failures"].append(failure)
        self._save_failed_today_data(data)
        logger.warning(f"Failure recorded: {item_name} - {error_reason}")

    def get_today_records(self) -> List[Dict]:
        """获取今日所有同步记录"""
        data = self._load_today_data()
        return data.get("records", [])

    def get_today_failures(self) -> List[Dict]:
        """获取今日所有失败记录"""
        data = self._load_failed_today_data()
        return data.get("failures", [])

    def get_history(self, start_date: str, end_date: str) -> List[Dict]:
        """
        获取指定日期范围的同步记录

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            同步记录列表
        """
        records = []
        current = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        while current <= end:
            file_path = self.log_dir / f"sync_{current.isoformat()}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        records.extend(data.get("records", []))
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load {file_path}: {e}")
            current = current + timedelta(days=1)

        return sorted(records, key=lambda x: x.get("timestamp", ""))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        data = self._load_today_data()
        failed_data = self._load_failed_today_data()

        records = data.get("records", [])
        failures = failed_data.get("failures", [])

        return {
            "today_synced": len(records),
            "today_failed": len(failures),
            "today_saved": sum(1 for r in records if r.get("status") == "saved"),
            "today_skipped": sum(1 for r in records if r.get("status") == "skipped"),
        }


# 为了方便导入，创建全局实例
_sync_history: Optional[SyncHistory] = None


def get_sync_history() -> SyncHistory:
    """获取 SyncHistory 单例实例"""
    global _sync_history
    if _sync_history is None:
        _sync_history = SyncHistory()
    return _sync_history

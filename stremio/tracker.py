"""
stremio/tracker.py - 追踪 Stremio 插件的新增内容，结合数据库去重
"""
import logging
from typing import List, Tuple, Dict, Any

from storage.database import CatalogDB, TaskDB, init_db
from storage.sync_history import SyncHistory
from stremio.fetcher import StremioFetcher

logger = logging.getLogger(__name__)


class CatalogTracker:
    """
    负责：
    1. 调用 StremioFetcher 拉取最新 catalog
    2. 与数据库对比，找出新内容
    3. 将新内容入库，创建待处理任务

    注意：
    - catalog_items 表只记录已同步完成的项目
    - 待处理/失败/待手动的任务不记录到 catalog_items
    """

    def __init__(self, addon_config: Dict[str, Any]):
        self.addon_config = addon_config
        self.addon_name = addon_config.get("name", "unknown")
        self.fetcher = StremioFetcher(
            manifest_url=addon_config["manifest_url"],
            watch_types=addon_config.get("watch_types", []),
            watch_catalogs=addon_config.get("watch_catalogs", []),
        )

    def check_and_queue(self) -> List[Dict[str, Any]]:
        """
        检查新内容并加入任务队列
        返回本次新增的 catalog 条目列表

        逻辑：
        1. 从 sync_history 获取已同步成功的项目（用于去重）
        2. 从 addon 拉取新内容
        3. 跳过已同步成功的项目
        4. 为新内容创建任务（但不记录到 catalog_items）
        """
        logger.info("[%s] Starting catalog check...", self.addon_name)

        try:
            self.fetcher.fetch_manifest()
        except Exception as e:
            logger.error("[%s] Failed to fetch manifest: %s", self.addon_name, e)
            return []

        # 获取已同步成功的项目 ID（用于去重）
        sync_history = SyncHistory()
        synced_items = sync_history.get_success_synced_items()
        logger.info("[%s] Synced items count: %d", self.addon_name, len(synced_items))

        # 获取该插件已知的所有 item id（catalog_items 表中的记录）
        existing = CatalogDB.get_all(self.addon_name)
        seen_ids = {row["id"] for row in existing}
        logger.info("[%s] Catalog items count: %d", self.addon_name, len(seen_ids))

        # 合并已同步和已知的 ID，用于去重
        all_seen_ids = seen_ids | {item_id for item_id, _ in synced_items}

        new_items_with_addon = self.fetcher.fetch_all_new_items(all_seen_ids)
        if not new_items_with_addon:
            logger.info("[%s] No new items", self.addon_name)
            return []

        queued = []
        for item, addon_name in new_items_with_addon:
            item_id = item.get("id", "")
            if not item_id:
                continue

            # 检查是否已同步成功，如果已同步则跳过（不创建任务）
            if (item_id, addon_name) in synced_items:
                logger.debug("Already synced for %s, skip", item_id)
                continue

            # 检查是否已有任务（包括 failed），如果有则不创建新任务
            if TaskDB.has_any_task(item_id, addon_name):
                logger.debug("Task already exists for %s, skip", item_id)
                continue

            # 创建待处理任务（不记录到 catalog_items）
            task_id = TaskDB.create(item_id, addon_name)
            logger.info(
                "[%s] New item queued: [%s] %s (task_id=%d)",
                addon_name, item_id, item.get("name", "?"), task_id
            )
            queued.append({**item, "_task_id": task_id, "_addon": addon_name})

        logger.info("[%s] Queued %d new tasks", self.addon_name, len(queued))
        return queued

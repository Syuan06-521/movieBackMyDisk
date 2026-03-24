"""
stremio/tracker.py - 追踪 Stremio 插件的新增内容，结合数据库去重
"""
import logging
from typing import List, Tuple, Dict, Any

from storage.database import CatalogDB, TaskDB, init_db
from stremio.fetcher import StremioFetcher

logger = logging.getLogger(__name__)


class CatalogTracker:
    """
    负责：
    1. 调用 StremioFetcher 拉取最新 catalog
    2. 与数据库对比，找出新内容
    3. 将新内容入库，创建待处理任务
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
        """
        logger.info("[%s] Starting catalog check...", self.addon_name)

        try:
            self.fetcher.fetch_manifest()
        except Exception as e:
            logger.error("[%s] Failed to fetch manifest: %s", self.addon_name, e)
            return []

        # 获取该插件已知的所有 item id
        existing = CatalogDB.get_all(self.addon_name)
        seen_ids = {row["id"] for row in existing}
        logger.info("[%s] Known items: %d", self.addon_name, len(seen_ids))

        new_items_with_addon = self.fetcher.fetch_all_new_items(seen_ids)
        if not new_items_with_addon:
            logger.info("[%s] No new items", self.addon_name)
            return []

        queued = []
        for item, addon_name in new_items_with_addon:
            item_id = item.get("id", "")
            if not item_id:
                continue

            # 存入 catalog_items 表
            CatalogDB.insert(item, addon_name)

            # 检查是否已有处理任务（防止重复）
            if TaskDB.has_pending_or_done(item_id, addon_name):
                logger.debug("Task already exists for %s, skip", item_id)
                continue

            # 创建待处理任务
            task_id = TaskDB.create(item_id, addon_name)
            logger.info(
                "[%s] New item queued: [%s] %s (task_id=%d)",
                addon_name, item_id, item.get("name", "?"), task_id
            )
            queued.append({**item, "_task_id": task_id, "_addon": addon_name})

        logger.info("[%s] Queued %d new tasks", self.addon_name, len(queued))
        return queued

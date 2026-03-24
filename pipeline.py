"""
pipeline.py - 核心处理流水线
串联：catalog 检测 → 搜索 → 过滤 → 夸克转存
支持两种模式:
  - auto: 全自动转存 (默认)
  - semi-auto: 半自动，保存到 Excel 供手动处理

优化 (2026-03-23):
  - 支持多备用转存路径
  - 同步历史记录检查，避免重复保存
  - 失败记录到文件
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from stremio.tracker import CatalogTracker
from searcher.quark_search import AggregatedSearcher
from searcher.filter import ResourceFilter
from searcher.models import ResourceResult
from quark.client import QuarkClient, QuarkError
from storage.database import TaskDB
from storage.sync_history import SyncHistory

logger = logging.getLogger(__name__)


class TransferPipeline:
    """
    主流水线，对每个 catalog addon 执行一次完整检查 + 处理
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.quark_config: Dict = config.get("quark", {})
        self.filter_config: Dict = config.get("filter", {})
        self.site_config: Dict = config.get("search_sites", {})

        # 支持多路径配置 (兼容旧的 save_folder 单一路径)
        save_folders = self.quark_config.get("save_folders", [])
        if not save_folders:
            # 兼容旧配置
            old_folder = self.quark_config.get("save_folder", "filmTransfer")
            save_folders = [old_folder]
        self.save_folders: List[str] = save_folders

        # 运行模式：auto(全自动) 或 semi-auto(半自动保存到 Excel)
        self.mode = config.get("mode", "auto")

        # 同步历史管理器
        self.sync_history = SyncHistory()

        self.searcher = AggregatedSearcher(self.site_config)
        self.resource_filter = ResourceFilter(self.filter_config)

    def run_once(self):
        """执行一次完整的检查和处理流程"""
        logger.info("=" * 60)
        logger.info("Pipeline run started (mode: %s)", self.mode)
        logger.info("Save folders configured: %s", self.save_folders)

        # Step 1: 检查所有 addon，发现新内容
        new_items = self._discover_new_items()
        if not new_items:
            logger.info("No new items to process")
            return

        # Step 2: 处理每个新条目
        stats = {"found": 0, "saved": 0, "skipped": 0, "failed": 0}
        for item_info in new_items:
            result = self._process_item(item_info)
            stats[result] = stats.get(result, 0) + 1

        logger.info(
            "Pipeline run completed: found=%d saved=%d skipped=%d failed=%d",
            stats["found"], stats["saved"], stats["skipped"], stats["failed"]
        )

        # 通知
        if stats["saved"] > 0:
            self._notify(f"filmTransfer: 本次新保存 {stats['saved']} 个资源")

    def _discover_new_items(self) -> List[Dict]:
        """从所有 addon 发现新内容"""
        all_new = []
        for addon_conf in self.config.get("stremio_addons", []):
            if not addon_conf.get("enabled", True):
                continue
            try:
                tracker = CatalogTracker(addon_conf)
                new = tracker.check_and_queue()
                all_new.extend(new)
            except Exception as e:
                logger.error("Addon '%s' error: %s", addon_conf.get("name"), e)
        return all_new

    def _process_item(self, item: Dict) -> str:
        """
        处理单个新条目：搜索→过滤→保存
        返回状态字符串：found/saved/skipped/failed
        """
        item_id = item.get("id", "")
        item_name = item.get("name", item_id)
        item_year = item.get("year", "")
        item_type = item.get("type", "")
        task_id = item.get("_task_id")
        addon_name = item.get("_addon", "")

        logger.info("Processing: [%s] %s", item_id, item_name)

        # Step 0: 检查同步历史，避免重复保存
        if self.sync_history.is_synced(item_id, addon_name):
            logger.info("Already synced (historical record exists), skipping: %s", item_name)
            return "skipped"

        # 更新任务状态为 searching
        if task_id:
            TaskDB.update(task_id, status="searching")

        # Step 1: 搜索
        keywords = self.searcher.build_keywords(item)
        all_results: List[ResourceResult] = []
        for kw in keywords:
            results = self.searcher.search(kw)
            all_results.extend(results)
            if results:
                break  # 第一个有结果的关键词即可

        if not all_results:
            logger.info("No resources found for: %s", item_name)
            if task_id:
                TaskDB.update(task_id, status="skipped",
                              error_msg="No resources found")
            return "skipped"

        # Step 2: 过滤排序，获取所有候选资源
        ranked_results = self.resource_filter.filter_and_rank(all_results)
        if not ranked_results:
            logger.info("All resources filtered out for: %s", item_name)
            if task_id:
                TaskDB.update(task_id, status="skipped",
                              error_msg="No resources passed filter")
            return "skipped"

        best = ranked_results[0]
        logger.info(
            "Best match for '%s': [%s] res=%s size=%.2fGB codec=%s score=%d",
            item_name, best.title[:50], best.resolution,
            best.size_gb or 0, best.codec, best.score
        )

        if task_id:
            TaskDB.update(
                task_id, status="saving",
                resource_name=best.title[:200],
                resource_url=best.share_url,
                resolution=best.resolution,
                size_gb=best.size_gb,
                codec=best.codec,
            )

        # 根据模式选择处理方式
        if self.mode == "semi-auto":
            # 半自动模式：保存到 Excel
            return self._save_to_excel(item, ranked_results, task_id)
        else:
            # 全自动模式：尝试保存到夸克网盘
            return self._save_to_quark(item, ranked_results, task_id)

    def _save_to_quark(self, item: Dict, ranked_results: List[ResourceResult],
                       task_id: Optional[str] = None) -> str:
        """
        全自动模式：保存到夸克网盘
        支持:
          - 多资源重试 (最多 5 个)
          - 多路径重试 (按配置优先级)
        """
        item_id = item.get("id", "")
        item_name = item.get("name", "")
        item_type = item.get("type", "")
        addon_name = item.get("_addon", "")
        cookie = self.quark_config.get("cookie", "")

        if not cookie:
            logger.warning("Quark cookie not configured, skipping save")
            if task_id:
                TaskDB.update(task_id, status="failed",
                              error_msg="Quark cookie not configured")
            return "failed"

        # 尝试每个候选资源，直到成功
        max_attempts = min(len(ranked_results), 5)  # 最多尝试 5 个资源
        attempted_paths = []
        tried_resources = []

        for resource_idx, resource in enumerate(ranked_results[:max_attempts]):
            logger.info("Resource attempt %d/%d: %s",
                       resource_idx + 1, max_attempts, resource.title[:50])

            tried_resources.append({
                "url": resource.share_url,
                "title": resource.title[:200]
            })

            # 尝试每个配置的保存路径
            for path_idx, base_save_folder in enumerate(self.save_folders):
                save_path = self._build_save_path(item, base_save_folder)

                if save_path in attempted_paths:
                    logger.debug("Path already attempted, skipping: %s", save_path)
                    continue

                attempted_paths.append(save_path)
                logger.info("Trying path %d/%d: %s",
                           path_idx + 1, len(self.save_folders), save_path)

                try:
                    with QuarkClient(cookie) as qc:
                        if self.quark_config.get("auto_create_folder", True):
                            qc.ensure_folder(save_path)
                        success = qc.save_share(resource.share_url, save_path)
                except Exception as e:
                    logger.error("Quark save error for '%s' on path '%s': %s",
                                item_name, save_path, e)
                    success = False

                if success:
                    logger.info("Saved '%s' -> %s", item_name, save_path)

                    # 更新任务状态
                    if task_id:
                        TaskDB.update(task_id, status="done",
                                      resource_name=resource.title[:200],
                                      resource_url=resource.share_url,
                                      quark_save_path=save_path)

                    # 记录同步历史
                    self.sync_history.record_sync(
                        item_id=item_id,
                        addon_name=addon_name,
                        item_name=item_name,
                        item_type=item_type,
                        resource_title=resource.title,
                        resource_url=resource.share_url,
                        save_path=save_path,
                        status="saved",
                        resolution=resource.resolution,
                        size_gb=resource.size_gb,
                        codec=resource.codec,
                    )

                    return "saved"
                else:
                    logger.warning("Resource failed on path '%s': %s",
                                  save_path, resource.share_url)

            # 当前资源在所有路径上都失败，继续尝试下一个资源
            if resource_idx < max_attempts - 1:
                logger.info("Current resource failed on all paths, trying next resource...")
                continue

        # 所有尝试都失败
        logger.error("All resources and paths failed for: %s", item_name)

        if task_id:
            TaskDB.update(task_id, status="failed",
                          error_msg=f"All {max_attempts} resources on all paths failed")

        # 记录失败到文件
        self.sync_history.record_failure(
            item_id=item_id,
            addon_name=addon_name,
            item_name=item_name,
            item_type=item_type,
            attempted_paths=attempted_paths,
            error_reason="All resources failed (likely invalid share links)",
            tried_resources=tried_resources,
        )

        return "failed"

    def _save_to_excel(self, item: Dict, ranked_results: List[ResourceResult],
                       task_id: Optional[str] = None) -> str:
        """
        半自动模式：将影视信息和分享链接保存到 Excel
        """
        import pandas as pd
        from pathlib import Path
        import datetime

        item_id = item.get("id", "")
        item_name = item.get("name", "")
        item_year = item.get("year", "")
        item_type = item.get("type", "")
        addon_name = item.get("_addon", "")

        # 检查是否已同步
        if self.sync_history.is_synced(item_id, addon_name):
            logger.info("Already synced, skipping Excel save: %s", item_name)
            return "skipped"

        # 准备数据
        records = []
        for i, res in enumerate(ranked_results[:10], 1):  # 最多保存前 10 个资源
            records.append({
                "日期": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "影视 ID": item_id,
                "影视名称": item_name,
                "年份": item_year,
                "类型": "电影" if item_type == "movie" else "剧集",
                "排名": i,
                "资源标题": res.title,
                "分辨率": res.resolution or "",
                "大小 (GB)": res.size_gb or 0,
                "编码": res.codec or "",
                "评分": res.score,
                "分享链接": res.share_url,
                "来源": res.source,
                "状态": "待处理",
            })

        # 保存到 Excel
        excel_path = Path("filmTransfer_pending.xlsx")

        # 如果文件已存在，追加数据
        if excel_path.exists():
            try:
                existing_df = pd.read_excel(excel_path)
                new_df = pd.DataFrame(records)
                df = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception:
                df = pd.DataFrame(records)
        else:
            df = pd.DataFrame(records)

        df.to_excel(excel_path, index=False, engine="openpyxl")
        logger.info("Saved %d resources to %s for manual processing", len(records), excel_path)

        # 记录同步历史 (标记为半自动待处理)
        base_save_folder = self.save_folders[0] if self.save_folders else "filmTransfer"
        save_path = self._build_save_path(item, base_save_folder)

        self.sync_history.record_sync(
            item_id=item_id,
            addon_name=addon_name,
            item_name=item_name,
            item_type=item_type,
            resource_title=ranked_results[0].title if ranked_results else "",
            resource_url=ranked_results[0].share_url if ranked_results else "",
            save_path=save_path,
            status="pending_manual",
            resolution=ranked_results[0].resolution if ranked_results else None,
            size_gb=ranked_results[0].size_gb if ranked_results else None,
            codec=ranked_results[0].codec if ranked_results else None,
        )

        if task_id:
            TaskDB.update(task_id, status="pending_manual",
                          error_msg=f"Saved to {excel_path}")

        return "found"  # 表示找到资源但需要手动处理

    def _build_save_path(self, item: Dict, base_folder: str) -> str:
        """
        构建夸克网盘保存路径
        格式：save_folder/movies 或 save_folder/series
        """
        item_type = item.get("type", "")
        if item_type == "movie":
            return f"{base_folder}/movies"
        elif item_type == "series":
            return f"{base_folder}/series"
        return base_folder

    def _notify(self, msg: str):
        """发送通知（根据配置）"""
        notif_conf = self.config.get("notification", {})
        if not notif_conf.get("enabled", False):
            return
        notif_type = notif_conf.get("type", "")
        try:
            if notif_type == "bark":
                self._notify_bark(msg, notif_conf.get("bark_key", ""))
            elif notif_type == "telegram":
                self._notify_telegram(
                    msg,
                    notif_conf.get("telegram_bot_token", ""),
                    notif_conf.get("telegram_chat_id", ""),
                )
        except Exception as e:
            logger.warning("Notification failed: %s", e)

    def _notify_bark(self, msg: str, key: str):
        import httpx
        if not key:
            return
        url = f"https://api.day.app/{key}/{msg}"
        httpx.get(url, timeout=10)
        logger.info("Bark notification sent")

    def _notify_telegram(self, msg: str, token: str, chat_id: str):
        import httpx
        if not token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        httpx.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
        logger.info("Telegram notification sent")

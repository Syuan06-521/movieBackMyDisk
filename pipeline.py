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

优化 (2026-03-25):
  - 支持处理数据库中已有的 pending 任务
  - 增加进度追踪回调
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from stremio.tracker import CatalogTracker
from searcher.quark_search import AggregatedSearcher
from searcher.filter import ResourceFilter
from searcher.models import ResourceResult
from quark.client import QuarkClient, QuarkError
from storage.database import TaskDB, TaskDBv2
from storage.sync_history import SyncHistory
from storage.repositories import TaskRepository, CatalogRepository

logger = logging.getLogger(__name__)


# 全局停止标志检查函数（由 check.py 设置）
_should_stop_callback: Optional[Callable] = None


def set_should_stop_callback(callback: Callable):
    """设置停止标志检查回调函数"""
    global _should_stop_callback
    _should_stop_callback = callback


def _should_stop() -> bool:
    """检查是否应该停止执行"""
    if _should_stop_callback:
        return _should_stop_callback()
    return False


# 全局进度回调
_progress_callback: Optional[Callable] = None


def set_progress_callback(callback: Callable):
    """设置进度回调函数"""
    global _progress_callback
    _progress_callback = callback


def _report_progress(status: str, progress: int = 0, message: str = "", current_item: str = ""):
    """报告进度"""
    if _progress_callback:
        _progress_callback(status=status, progress=progress, message=message, current_item=current_item)


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

    def run_once(self, content_type: str = None):
        """执行一次完整的检查和处理流程

        Args:
            content_type: 内容类型过滤 ('movie' 或 'series')
        """
        logger.info("=" * 60)
        logger.info("Pipeline run started (mode: %s)", self.mode)
        logger.info("Save folders configured: %s", self.save_folders)

        # Step 0: 先处理数据库中已有的 pending 任务
        pending_tasks_processed = self._process_pending_tasks(content_type)

        # 检查是否被停止
        if _should_stop():
            logger.info("Pipeline stopped by user after processing pending tasks")
            _report_progress("stopped", 0, "任务已被用户停止")
            return

        # Step 1: 检查所有 addon，发现新内容
        new_items = self._discover_new_items()
        if not new_items:
            logger.info("No new items to process")
            _report_progress("running", 0, "无新发现影视内容")
        else:
            # Step 2: 处理每个新条目
            stats = {"found": 0, "saved": 0, "skipped": 0, "failed": 0}
            for idx, item_info in enumerate(new_items):
                # 检查是否被停止
                if _should_stop():
                    logger.info("Pipeline stopped by user while processing items")
                    _report_progress("stopped", int((idx + 1) / len(new_items) * 100), f"任务已被用户停止 (已处理 {idx}/{len(new_items)})")
                    break

                # 报告进度
                progress = int((idx + 1) / len(new_items) * 100)
                item_name = item_info.get("name", item_info.get("id", ""))
                _report_progress(
                    "running",
                    progress,
                    f"正在处理新发现影视 {idx + 1}/{len(new_items)} - {item_name[:50]}",
                    f"ID: {item_info.get('id', '')}"
                )

                result = self._process_item(item_info)
                stats[result] = stats.get(result, 0) + 1

                # 报告单个处理完成状态
                status_msg = {"saved": "已保存", "skipped": "已跳过", "failed": "失败", "found": "已找到"}.get(result, result)
                _report_progress(
                    "running",
                    progress,
                    f"影视 {idx + 1}/{len(new_items)} 处理完成 - {status_msg}",
                    f"ID: {item_info.get('id', '')}"
                )

            # 如果不是因为停止而退出，记录完成日志
            if not _should_stop():
                logger.info(
                    "Pipeline run completed: found=%d saved=%d skipped=%d failed=%d",
                    stats["found"], stats["saved"], stats["skipped"], stats["failed"]
                )

                # 通知
                if stats["saved"] > 0:
                    self._notify(f"filmTransfer: 本次新保存 {stats['saved']} 个资源")
                    _report_progress(
                        "completed",
                        100,
                        f"新发现影视处理完成 - 共{len(new_items)}个，成功{stats['saved']}个，跳过{stats['skipped']}个，失败{stats['failed']}个"
                    )
                else:
                    _report_progress(
                        "completed",
                        100,
                        f"新发现影视处理完成 - 共{len(new_items)}个，成功{stats['saved']}个，跳过{stats['skipped']}个，失败{stats['failed']}个"
                    )

        # 汇总结果
        if pending_tasks_processed == 0 and not new_items:
            logger.info("本次检查无更新内容（无待处理任务，无新发现影视）")
            _report_progress("completed", 100, "本次检查无更新内容")
        elif pending_tasks_processed > 0 and not new_items:
            # 只处理了 pending 任务，没有新发现
            pass  # 已在 _process_pending_tasks 中报告完成

    def _process_pending_tasks(self, content_type: str = None) -> int:
        """
        处理数据库中已有的 pending 任务

        Args:
            content_type: 内容类型过滤

        Returns:
            处理的任务数量
        """
        db = TaskDBv2()
        try:
            # 只处理 pending 任务，失败任务需要用户手动重试
            pending_tasks = db.get_all(status='pending')

            # 按类型过滤
            if content_type:
                # 需要获取 catalog 信息来过滤
                filtered_tasks = []
                for task in pending_tasks:
                    # 这里简单处理，实际需要关联 catalog
                    filtered_tasks.append(task)
                pending_tasks = filtered_tasks

            if not pending_tasks:
                logger.info("No pending tasks to process")
                return 0

            logger.info("=" * 50)
            logger.info("Starting to process %d pending tasks...", len(pending_tasks))
            logger.info("=" * 50)

            _report_progress("running", 0, f"发现 {len(pending_tasks)} 个待处理任务")

            # 处理每个待处理任务
            stats = {"found": 0, "saved": 0, "skipped": 0, "failed": 0}
            for idx, task_data in enumerate(pending_tasks):
                task_id = task_data.get('task_id')
                catalog_item_id = task_data.get('catalog_item_id')
                addon_name = task_data.get('addon_name')

                logger.info("-" * 40)
                logger.info("[%d/%d] Processing task %s, catalog %s",
                           idx + 1, len(pending_tasks), task_id, catalog_item_id)

                # 报告进度
                progress = int((idx + 1) / len(pending_tasks) * 100)
                _report_progress(
                    "running",
                    progress,
                    f"正在处理待处理任务 {idx + 1}/{len(pending_tasks)}",
                    f"ID: {catalog_item_id}"
                )

                # 重新处理任务
                try:
                    result = self._process_task(task_id)
                    stats[result] = stats.get(result, 0) + 1
                    logger.info("[%d/%d] Task %s completed with result: %s",
                               idx + 1, len(pending_tasks), task_id, result)

                    # 报告单个任务完成状态
                    status_msg = {"saved": "已保存", "skipped": "已跳过", "failed": "失败", "found": "已找到"}.get(result, result)
                    _report_progress(
                        "running",
                        progress,
                        f"任务 {idx + 1}/{len(pending_tasks)} 处理完成 - {status_msg}",
                        f"ID: {catalog_item_id}"
                    )
                except Exception as e:
                    logger.error("Failed to process pending task %s: %s", task_id, e, exc_info=True)
                    db.update(task_id, status='failed', error_msg=str(e))
                    stats["failed"] += 1
                    _report_progress(
                        "running",
                        progress,
                        f"任务 {idx + 1}/{len(pending_tasks)} 处理失败 - {str(e)}",
                        f"ID: {catalog_item_id}"
                    )

            logger.info("=" * 50)
            logger.info("Pending tasks processing completed:")
            logger.info("  Total: %d, Saved: %d, Skipped: %d, Failed: %d",
                       len(pending_tasks), stats["saved"], stats["skipped"], stats["failed"])
            logger.info("=" * 50)

            # 所有任务处理完成
            _report_progress(
                "completed",
                100,
                f"待处理任务处理完成 - 共{len(pending_tasks)}个，成功{stats['saved']}个，跳过{stats['skipped']}个，失败{stats['failed']}个"
            )

            return len(pending_tasks)
        finally:
            db.close()

    def _process_task(self, task_id: int) -> str:
        """
        处理单个待处理任务
        从任务中获取影视信息，然后执行搜索和保存

        Args:
            task_id: 任务 ID

        Returns:
            状态字符串：found/saved/skipped/failed
        """
        from storage.database import CatalogDBv2

        db = TaskDBv2()
        catalog_db = CatalogDBv2()
        try:
            # 获取任务
            task_repo = TaskRepository(db.db)
            task = task_repo.get_by_id(task_id)
            if not task:
                logger.warning("Task %s not found", task_id)
                return "failed"

            # 获取 catalog 信息
            catalog_repo = CatalogRepository(catalog_db.db)
            catalog_item = catalog_repo.get_by_id(task.catalog_item_id, task.addon_name)
            if not catalog_item:
                logger.warning("Catalog item %s/%s not found", task.catalog_item_id, task.addon_name)
                return "skipped"

            # 重建 item 数据结构
            item = {
                "id": catalog_item.id,
                "name": catalog_item.name,
                "type": catalog_item.item_type,
                "year": catalog_item.year,
                "imdbId": catalog_item.imdb_id,
                "poster": catalog_item.poster,
                "_task_id": task_id,
                "_addon": task.addon_name,
                "_skip_sync_check": True,  # 标记跳过同步历史检查（待处理任务需要重新处理）
            }

            # 调用 _process_item 处理
            return self._process_item(item)
        finally:
            db.close()
            catalog_db.close()
            catalog_db.close()

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
        skip_sync_check = item.get("_skip_sync_check", False)  # 待处理任务跳过同步检查

        logger.info("Processing: [%s] %s", item_id, item_name)

        # Step 0: 检查同步历史，避免重复保存（待处理任务跳过此检查）
        if not skip_sync_check and self.sync_history.is_synced(item_id, addon_name):
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
        failure_details = []  # 记录每个资源的失败原因

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
                    failure_details.append({
                        "resource": resource.share_url,
                        "path": save_path,
                        "error": str(e)
                    })

                if success:
                    logger.info("Saved '%s' -> %s", item_name, save_path)

                    # 记录到 catalog_items 表（已同步完成的项目）
                    from storage.database import CatalogDBv2
                    catalog_db = CatalogDBv2()
                    try:
                        catalog_db.insert(item, addon_name)
                    finally:
                        catalog_db.close()

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
                    failure_details.append({
                        "resource": resource.share_url,
                        "path": save_path,
                        "error": "Save returned False"
                    })

            # 当前资源在所有路径上都失败，继续尝试下一个资源
            if resource_idx < max_attempts - 1:
                logger.info("Current resource failed on all paths, trying next resource...")
                continue

        # 所有尝试都失败
        logger.error("All resources and paths failed for: %s", item_name)

        # 分析失败原因
        failure_reason = self._analyze_failure(failure_details, tried_resources)

        if task_id:
            TaskDB.update(task_id, status="failed",
                          error_msg=failure_reason)

        # 记录失败到文件
        self.sync_history.record_failure(
            item_id=item_id,
            addon_name=addon_name,
            item_name=item_name,
            item_type=item_type,
            attempted_paths=attempted_paths,
            error_reason=failure_reason,
            tried_resources=tried_resources,
        )

        return "failed"

    def _analyze_failure(self, failure_details: List[Dict], tried_resources: List[Dict]) -> str:
        """
        分析失败原因，返回详细的错误信息

        Args:
            failure_details: 失败详情列表
            tried_resources: 尝试过的资源列表

        Returns:
            失败原因字符串
        """
        if not failure_details:
            return "未知错误，未记录到失败详情"

        # 检查是否有分享链接失效的错误
        link_invalid_keywords = ["分享已失效", "链接不存在", "文件已删除", "分享已删除", "资源不存在", "无法访问"]
        for detail in failure_details:
            error_msg = detail.get("error", "")
            if any(keyword in error_msg for keyword in link_invalid_keywords):
                # 返回第一个失效的链接
                return f"分享链接失效：{detail.get('resource', '未知链接')}"

        # 如果是浏览器自动化问题
        browser_keywords = ["浏览器", "Playwright", "timeout", "超时", "Cannot find save button"]
        for detail in failure_details:
            error_msg = detail.get("error", "")
            if any(keyword in error_msg for keyword in browser_keywords):
                return f"浏览器自动化失败：{error_msg[:100]}"

        # 默认返回通用错误信息
        return f"所有 {len(tried_resources)} 个资源都尝试失败，请检查分享链接是否有效"

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

        # 半自动模式不记录同步历史（因为还没有真正转存）
        # 只在用户手动处理或点击"标记为已同步"时才记录

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

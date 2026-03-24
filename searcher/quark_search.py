"""
searcher/quark_search.py - 搜索夸克网盘资源

搜索源：
  1. b.funletu.com (唯一搜索源，JSON API)
"""
import httpx
import logging
import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from searcher.models import ResourceResult
from utils import parse_resolution, parse_size_gb, parse_codec

logger = logging.getLogger(__name__)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

TIMEOUT = httpx.Timeout(20.0)

# 夸克分享链接正则
QUARK_SHARE_RE = re.compile(r"https?://pan\.quark\.cn/s/[a-zA-Z0-9]+")


# ─────────────────────────────────────────────
# 搜索源：b.funletu.com (API)
# ─────────────────────────────────────────────
class FunletuSearcher:
    """
    b.funletu.com 夸克网盘资源搜索
    API: https://b.funletu.com/search
    参数：{keyword, page, categoryid, filetypeid, courseid, pageSize, sortBy}
    """
    SOURCE = "funletu"
    API_URL = "https://b.funletu.com/search"

    def search(self, keyword: str, max_results: int = 15) -> List[ResourceResult]:
        results = []
        try:
            with httpx.Client(
                headers=BASE_HEADERS, timeout=TIMEOUT,
                follow_redirects=True
            ) as client:
                # POST 请求 JSON 数据
                payload = {
                    "keyword": keyword,
                    "page": 1,
                    "pageSize": max_results,
                    "categoryid": 0,
                    "filetypeid": 0,
                    "courseid": 1,
                    "sortBy": "sort"
                }
                resp = client.post(self.API_URL, json=payload)
                resp.raise_for_status()

                data = resp.json()
                results = self._parse_json(data, max_results)

        except httpx.HTTPError as e:
            logger.warning("b.funletu.com HTTP error: %s", e)
        except Exception as e:
            logger.warning("b.funletu.com search error: %s", e, exc_info=True)

        logger.info("b.funletu.com: found %d results for '%s'", len(results), keyword)
        return results

    def _parse_json(self, data: Dict[str, Any], max_results: int) -> List[ResourceResult]:
        """解析 JSON 响应"""
        results = []

        # 检查响应状态
        if data.get("code") != 200:
            logger.warning("API returned non-200 code: %s", data.get("msg"))
            return results

        # 提取结果列表
        data_section = data.get("data", {})
        item_list = data_section.get("list", [])

        if not item_list:
            logger.debug("No results in API response")
            return results

        # 按质量排序：score 和 viewshistory/views
        def sort_key(item):
            score = item.get("score", 0) or 0
            views = item.get("viewshistory") or item.get("views") or 0
            return (score, views)

        sorted_list = sorted(item_list, key=sort_key, reverse=True)

        for item in sorted_list[:max_results]:
            title = item.get("title", "")
            if not title:
                continue

            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title)

            # 获取分享链接（直接从 url 字段）
            share_url = item.get("url") or ""

            # 提取元数据
            size_text = item.get("size") or ""
            full_text = f"{title} {size_text}"

            results.append(ResourceResult(
                title=title,
                source=self.SOURCE,
                share_url=share_url,
                resolution=parse_resolution(full_text),
                size_gb=parse_size_gb(full_text),
                codec=parse_codec(full_text),
                raw_size_text=full_text[:200],
                extra_info=f"score={item.get('score')} views={item.get('viewshistory') or item.get('views')} uploader={item.get('uploaderid')}",
            ))

        return results


# ─────────────────────────────────────────────
# 聚合搜索器
# ─────────────────────────────────────────────
class AggregatedSearcher:
    """聚合搜索源（目前只有 funletu）"""

    def __init__(self, site_config: Dict[str, Any]):
        # 只使用 funletu 作为搜索源
        self.searchers = [FunletuSearcher()]
        self.max_per_site = site_config.get("max_results_per_site", 15)

    def search(self, keyword: str) -> List[ResourceResult]:
        all_results: List[ResourceResult] = []
        seen_urls = set()

        for searcher in self.searchers:
            try:
                res = searcher.search(keyword, self.max_per_site)
                for r in res:
                    if r.share_url and r.share_url not in seen_urls:
                        seen_urls.add(r.share_url)
                        all_results.append(r)
            except Exception as e:
                logger.error("Searcher %s failed: %s",
                             getattr(searcher, "SOURCE", "?"), e)

        logger.info("Aggregated search '%s': %d unique results",
                    keyword, len(all_results))
        return all_results

    def build_keywords(self, item: Dict[str, Any]) -> List[str]:
        """构建搜索关键词列表"""
        name = item.get("name", "") or item.get("title", "")
        year = item.get("year")
        keywords = []
        if name:
            keywords.append(name)
            if year:
                keywords.append(f"{name} {year}")
        imdb_id = item.get("imdbId") or item.get("id", "")
        if imdb_id and imdb_id.startswith("tt"):
            keywords.append(imdb_id)
        return keywords

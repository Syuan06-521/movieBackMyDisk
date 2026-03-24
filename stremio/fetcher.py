"""
stremio/fetcher.py - 抓取 Stremio 插件的 manifest 和 catalog 列表
"""
import httpx
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; filmTransfer/1.0)",
    "Accept": "application/json",
}

TIMEOUT = httpx.Timeout(30.0)


class StremioFetcher:
    """
    解析 Stremio 插件 manifest，遍历所有 catalog 端点，返回影视条目列表。

    Stremio Catalog API 格式：
      manifest:  GET {base}/manifest.json
      catalog:   GET {base}/catalog/{type}/{id}.json
                 GET {base}/catalog/{type}/{id}/skip={N}.json  (分页)
    """

    def __init__(self, manifest_url: str, watch_types: List[str] = None,
                 watch_catalogs: List[str] = None):
        self.manifest_url = manifest_url
        self.base_url = self._get_base_url(manifest_url)
        self.watch_types = [t.lower() for t in watch_types] if watch_types else []
        self.watch_catalogs = watch_catalogs or []
        self.manifest: Optional[Dict] = None

    @staticmethod
    def _get_base_url(manifest_url: str) -> str:
        """从 manifest URL 推导出插件的 base URL"""
        parsed = urlparse(manifest_url)
        path = parsed.path
        if path.endswith("/manifest.json"):
            path = path[: -len("/manifest.json")]
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def fetch_manifest(self) -> Dict[str, Any]:
        """获取并解析 manifest.json"""
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = client.get(self.manifest_url)
            resp.raise_for_status()
            self.manifest = resp.json()
            logger.info(
                "Manifest loaded: %s v%s, catalogs: %d",
                self.manifest.get("name"),
                self.manifest.get("version"),
                len(self.manifest.get("catalogs", []))
            )
            return self.manifest

    def get_active_catalogs(self) -> List[Dict]:
        """返回需要监控的 catalog 列表"""
        if not self.manifest:
            self.fetch_manifest()
        catalogs = self.manifest.get("catalogs", [])
        result = []
        for cat in catalogs:
            cat_type = cat.get("type", "").lower()
            cat_id = cat.get("id", "")
            # 类型过滤
            if self.watch_types and cat_type not in self.watch_types:
                continue
            # catalog id 过滤
            if self.watch_catalogs and cat_id not in self.watch_catalogs:
                continue
            result.append(cat)
        logger.info("Active catalogs to monitor: %d", len(result))
        return result

    def fetch_catalog_items(self, cat_type: str, cat_id: str,
                             max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        分页抓取一个 catalog 的全部条目
        每页默认 100 条（Stremio 标准），skip 步长 100
        """
        items = []
        skip = 0
        page_size = 100

        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            for page in range(max_pages):
                if skip == 0:
                    url = f"{self.base_url}/catalog/{cat_type}/{cat_id}.json"
                else:
                    url = f"{self.base_url}/catalog/{cat_type}/{cat_id}/skip={skip}.json"

                try:
                    resp = client.get(url)
                    if resp.status_code == 404:
                        logger.debug("No more pages at skip=%d", skip)
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as e:
                    logger.warning("HTTP error fetching catalog page: %s", e)
                    break
                except json.JSONDecodeError as e:
                    logger.warning("JSON decode error: %s", e)
                    break

                page_items = data.get("metas", [])
                if not page_items:
                    logger.debug("Empty page at skip=%d, stopping", skip)
                    break

                items.extend(page_items)
                logger.debug(
                    "Catalog %s/%s page %d: +%d items (total %d)",
                    cat_type, cat_id, page + 1, len(page_items), len(items)
                )

                if len(page_items) < page_size:
                    break  # 最后一页
                skip += page_size

        logger.info("Catalog %s/%s: %d items fetched", cat_type, cat_id, len(items))
        return items

    def fetch_all_new_items(self, seen_ids: set) -> List[Tuple[Dict, str]]:
        """
        抓取所有 catalog 的新条目（不在 seen_ids 中的）
        返回 [(item_meta, addon_name), ...]
        """
        if not self.manifest:
            self.fetch_manifest()

        addon_name = self.manifest.get("name", self.manifest_url)
        new_items = []

        for cat in self.get_active_catalogs():
            cat_type = cat.get("type")
            cat_id = cat.get("id")
            try:
                items = self.fetch_catalog_items(cat_type, cat_id)
            except Exception as e:
                logger.error("Failed to fetch catalog %s/%s: %s", cat_type, cat_id, e)
                continue

            for item in items:
                item_id = item.get("id", "")
                if item_id and item_id not in seen_ids:
                    new_items.append((item, addon_name))

        logger.info("Total new items found: %d", len(new_items))
        return new_items

    def fetch_meta(self, item_type: str, item_id: str) -> Optional[Dict]:
        """获取单个条目的详细元信息"""
        url = f"{self.base_url}/meta/{item_type}/{item_id}.json"
        try:
            with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json().get("meta", {})
        except Exception as e:
            logger.warning("Failed to fetch meta for %s/%s: %s", item_type, item_id, e)
            return None

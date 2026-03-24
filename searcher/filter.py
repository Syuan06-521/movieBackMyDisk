"""
searcher/filter.py - 对搜索结果按分辨率、大小、编码进行评分和过滤
"""
import logging
from typing import List, Dict, Any, Optional

from searcher.models import ResourceResult
from utils import get_resolution_priority, get_resolution_pixels

logger = logging.getLogger(__name__)


def _codec_score(codec: Optional[str], preferred: List[str]) -> int:
    if not codec:
        return 0
    for i, c in enumerate(preferred):
        if c.upper() in codec.upper():
            return len(preferred) - i
    return 0


class ResourceFilter:
    """
    对 ResourceResult 列表进行评分 + 过滤，返回排序后的候选列表
    """

    def __init__(self, filter_config: Dict[str, Any]):
        self.preferred_resolutions: List[str] = [
            r.lower() for r in filter_config.get("preferred_resolutions", ["1080p", "720p"])
        ]
        self.min_resolution: str = filter_config.get("min_resolution", "720p").lower()
        self.min_size_gb: Optional[float] = filter_config.get("min_size_gb")
        self.max_size_gb: Optional[float] = filter_config.get("max_size_gb")
        self.preferred_codecs: List[str] = filter_config.get(
            "preferred_codecs", ["HEVC", "H264"]
        )
        self.prefer_languages: List[str] = filter_config.get("prefer_languages", [])

    def _passes_minimum(self, r: ResourceResult) -> bool:
        """检查是否满足最低要求"""
        # 分辨率下限
        min_pixels = get_resolution_pixels(self.min_resolution)
        if r.resolution:
            pixels = get_resolution_pixels(r.resolution)
            if pixels > 0 and pixels < min_pixels:
                logger.debug("Filter: %s rejected by resolution %s < %s",
                             r.title[:40], r.resolution, self.min_resolution)
                return False

        # 文件大小范围
        if r.size_gb is not None:
            if self.min_size_gb and r.size_gb < self.min_size_gb:
                logger.debug("Filter: %s rejected by size %.2f < %.2f GB",
                             r.title[:40], r.size_gb, self.min_size_gb)
                return False
            if self.max_size_gb and r.size_gb > self.max_size_gb:
                logger.debug("Filter: %s rejected by size %.2f > %.2f GB",
                             r.title[:40], r.size_gb, self.max_size_gb)
                return False
        return True

    def _compute_score(self, r: ResourceResult) -> int:
        score = 0

        # 分辨率得分（匹配优选列表的位置）
        if r.resolution:
            for i, res in enumerate(self.preferred_resolutions):
                if res == r.resolution.lower():
                    score += (len(self.preferred_resolutions) - i) * 10
                    break
            else:
                # 未在优选列表但通过了最低要求，给基础分
                score += get_resolution_priority(r.resolution) * 3

        # 编码格式得分
        score += _codec_score(r.codec, self.preferred_codecs) * 5

        # 语言偏好得分
        for lang in self.prefer_languages:
            if lang in r.title:
                score += 8
                break

        # 有大小信息的加分（信息更完整）
        if r.size_gb is not None:
            score += 2

        return score

    def filter_and_rank(self, results: List[ResourceResult]) -> List[ResourceResult]:
        """过滤不合格项，对通过的结果评分排序"""
        passed = [r for r in results if self._passes_minimum(r)]
        for r in passed:
            r.score = self._compute_score(r)

        ranked = sorted(passed, key=lambda r: r.score, reverse=True)
        logger.info(
            "Filter: %d/%d results passed, top score: %s",
            len(ranked), len(results),
            ranked[0].score if ranked else "N/A"
        )
        return ranked

    def pick_best(self, results: List[ResourceResult]) -> Optional[ResourceResult]:
        """返回评分最高的资源"""
        ranked = self.filter_and_rank(results)
        return ranked[0] if ranked else None

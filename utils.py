"""
filmTransfer - 公共工具函数和常量
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 分辨率优先级映射（越高越优先）
RESOLUTION_PRIORITY = {
    "2160p": 5, "4k": 5, "uhd": 5,
    "1080p": 4, "fhd": 4,
    "720p": 3, "hd": 3,
    "480p": 2,
    "360p": 1,
}

# 分辨率像素映射（用于过滤）
RESOLUTION_PIXELS = {
    "2160p": 2160, "4k": 2160, "uhd": 2160,
    "1080p": 1080, "fhd": 1080,
    "720p": 720, "hd": 720,
    "480p": 480,
    "360p": 360,
}

# 常用分辨率正则
RESOLUTION_PATTERN = re.compile(
    r'(4k|uhd|2160p|1080p|fhd|720p|hd|480p|360p)', re.IGNORECASE
)

# 编码格式正则
CODEC_PATTERN = re.compile(
    r'(HEVC|H\.?265|H\.?264|AVC|AV1|VP9|x265|x264)', re.IGNORECASE
)

# 文件大小正则（支持 GB/MB/TB）
SIZE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(TB|GB|MB|KB)', re.IGNORECASE
)


def parse_resolution(text: str) -> Optional[str]:
    """从文本中提取分辨率标识"""
    match = RESOLUTION_PATTERN.search(text)
    if match:
        return match.group(1).lower()
    return None


def parse_size_gb(text: str) -> Optional[float]:
    """从文本中提取文件大小（统一转为 GB）"""
    match = SIZE_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "TB":
        return value * 1024
    elif unit == "GB":
        return value
    elif unit == "MB":
        return value / 1024
    elif unit == "KB":
        return value / (1024 * 1024)
    return None


def parse_codec(text: str) -> Optional[str]:
    """从文本中提取视频编码格式"""
    match = CODEC_PATTERN.search(text)
    if match:
        raw = match.group(1).upper()
        # 标准化
        if raw in ("H265", "H.265", "X265", "HEVC"):
            return "HEVC"
        elif raw in ("H264", "H.264", "X264", "AVC"):
            return "H264"
        return raw
    return None


def get_resolution_priority(resolution: Optional[str]) -> int:
    """获取分辨率优先级"""
    if not resolution:
        return 0
    return RESOLUTION_PRIORITY.get(resolution.lower(), 0)


def get_resolution_pixels(resolution: Optional[str]) -> int:
    """获取分辨率像素高度"""
    if not resolution:
        return 0
    return RESOLUTION_PIXELS.get(resolution.lower(), 0)

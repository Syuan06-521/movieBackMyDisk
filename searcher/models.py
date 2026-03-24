"""
searcher/models.py - 搜索结果数据模型
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResourceResult:
    """代表一个搜索到的网盘资源"""
    title: str                        # 资源标题
    source: str                       # 来源站点标识
    share_url: str                    # 分享链接
    resolution: Optional[str] = None  # 分辨率标识，如 1080p
    size_gb: Optional[float] = None   # 文件大小 GB
    codec: Optional[str] = None       # 视频编码
    raw_size_text: str = ""           # 原始大小文字
    extra_info: str = ""              # 其他信息
    score: int = 0                    # 综合评分（过滤后填充）

    def __repr__(self):
        return (
            f"ResourceResult(title={self.title!r}, "
            f"resolution={self.resolution}, size={self.size_gb}GB, "
            f"source={self.source}, score={self.score})"
        )

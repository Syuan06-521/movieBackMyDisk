"""
quark/client.py - 夸克网盘 API 客户端

API 说明（逆向工程，非官方）：
  账号接口 base: https://pan.quark.cn/1/clouddrive
  文件接口 base: https://drive.quark.cn/1/clouddrive
  所有请求需携带 Cookie 和固定参数 pr=ucpro&fr=pc
"""
import httpx
import logging
import re
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# 账号/用户相关 API（member info 在 pan.quark.cn）
PAN_API = "https://pan.quark.cn/1/clouddrive"
# 文件操作 API（file/sort, share/* 在 drive.quark.cn）
DRIVE_API = "https://drive.quark.cn/1/clouddrive"

# 所有请求必须携带的固定参数
BASE_PARAMS = {"pr": "ucpro", "fr": "pc"}

# 夸克分享链接格式：https://pan.quark.cn/s/xxxxxx
SHARE_URL_RE = re.compile(r"pan\.quark\.cn/s/([a-zA-Z0-9]+)")


class QuarkError(Exception):
    """夸克 API 调用错误"""
    def __init__(self, code: int, msg: str):
        super().__init__(f"Quark API error {code}: {msg}")
        self.code = code
        self.msg = msg


class QuarkClient:
    """
    夸克网盘 HTTP API 客户端

    使用方法：
        client = QuarkClient(cookie="your_cookie_string")
        client.ensure_folder("filmTransfer")
        client.save_share("https://pan.quark.cn/s/xxxxx", "filmTransfer")
    """

    def __init__(self, cookie: str):
        if not cookie:
            raise ValueError("夸克网盘 Cookie 不能为空，请在 config.yaml 中填写")
        self.cookie = cookie
        self._folder_cache: Dict[str, str] = {}
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie,
            "Referer": "https://pan.quark.cn/",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ──────────────────────────────────────────
    # 内部工具方法
    # ──────────────────────────────────────────

    def _get(self, base: str, path: str, **extra_params) -> Dict:
        url = f"{base}{path}"
        params = {**BASE_PARAMS, **extra_params}
        resp = self._client.get(url, params=params)
        return self._parse(resp)

    def _post(self, base: str, path: str, body: Any,
              **extra_params) -> Dict:
        url = f"{base}{path}"
        params = {**BASE_PARAMS, **extra_params}
        resp = self._client.post(url, params=params, json=body)
        return self._parse(resp)

    def _parse(self, resp: httpx.Response) -> Dict:
        # HTTP 层面只允许 2xx（raise_for_status 已覆盖）
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code", 0)
        # 夸克 API：code=0 表示成功（status 字段仅做参考）
        if code != 0:
            msg = data.get("message") or data.get("msg") or str(data)
            raise QuarkError(code, msg)
        return data

    # ──────────────────────────────────────────
    # 用户信息
    # ──────────────────────────────────────────

    def get_user_info(self) -> Dict:
        """验证 Cookie 有效性，返回容量信息"""
        # 原端点 /member/info 已废弃，改用 /capacity/detail 验证
        data = self._get(PAN_API, "/capacity/detail")
        info = {"raw": data.get("data", {})}

        # 计算总容量（从 expired 列表汇总）
        total = 0
        for item in data.get("data", {}).get("expired", []):
            total += item.get("capacity", 0)
        info["total_capacity"] = total

        logger.info(
            "Quark cookie valid, total capacity: %.2f GB",
            total / 1024**3,
        )
        return info

    # ──────────────────────────────────────────
    # 文件/目录操作
    # ──────────────────────────────────────────

    def list_files(self, parent_fid: str = "0") -> List[Dict]:
        """列出目录下的文件和文件夹"""
        data = self._get(
            DRIVE_API, "/file/sort",
            pdir_fid=parent_fid,
            _page=1,
            _size=100,
            _fetch_total=1,
            _sort="file_name:asc",
            _fetch_sub_dirs=0,
        )
        return data.get("data", {}).get("list", [])

    def find_folder(self, name: str, parent_fid: str = "0") -> Optional[str]:
        """在指定目录下查找文件夹，返回 fid（未找到返回 None）"""
        files = self.list_files(parent_fid)
        for f in files:
            if f.get("file_name") == name and f.get("dir"):
                return f["fid"]
        return None

    def create_folder(self, name: str, parent_fid: str = "0") -> str:
        """创建文件夹，返回新 fid"""
        data = self._post(DRIVE_API, "/file", {
            "file_name": name,
            "pdir_fid": parent_fid,
            "dir_init_lock": False,
        })
        fid = data.get("data", {}).get("fid")
        logger.info("Created folder '%s' fid=%s", name, fid)
        return fid

    def ensure_folder(self, path: str) -> str:
        """
        递归确保路径存在，返回最终目录的 fid
        path 格式：'filmTransfer' 或 'filmTransfer/电影/2024'
        """
        if path in self._folder_cache:
            return self._folder_cache[path]

        parts = [p for p in path.split("/") if p]
        current_fid = "0"

        for part in parts:
            fid = self.find_folder(part, current_fid)
            if not fid:
                fid = self.create_folder(part, current_fid)
            current_fid = fid

        self._folder_cache[path] = current_fid
        logger.info("Folder ensured: '%s' -> fid=%s", path, current_fid)
        return current_fid

    # ──────────────────────────────────────────
    # 分享链接处理
    # ──────────────────────────────────────────

    def _extract_share_id(self, share_url: str) -> str:
        """从分享 URL 提取 share_id（pwd_id）"""
        m = SHARE_URL_RE.search(share_url)
        if m:
            return m.group(1)
        if re.match(r"^[a-zA-Z0-9]+$", share_url):
            return share_url
        raise ValueError(f"无法解析夸克分享链接: {share_url}")

    def get_share_token(self, share_url: str, pwd: str = "") -> Tuple[str, str]:
        """
        获取分享访问 stoken
        返回 (share_id, stoken)
        """
        share_id = self._extract_share_id(share_url)
        data = self._post(DRIVE_API, "/share/sharepage/token", {
            "pwd_id": share_id,
            "passcode": pwd,
        })
        stoken = data.get("data", {}).get("stoken", "")
        logger.info("Got stoken for share %s", share_id)
        return share_id, stoken

    def list_share_files(self, share_id: str, stoken: str,
                          pdir_fid: str = "0") -> List[Dict]:
        """列出分享链接中的文件"""
        data = self._get(
            DRIVE_API, "/share/sharepage/detail",
            pwd_id=share_id,
            stoken=stoken,
            pdir_fid=pdir_fid,
            _page=1,
            _size=50,
            _fetch_total=1,
        )
        return data.get("data", {}).get("list", [])

    def save_share_files(self, share_id: str, stoken: str,
                          fids: List[str], to_fid: str) -> Dict:
        """将分享文件转存到自己的网盘"""
        data = self._post(DRIVE_API, "/share/sharepage/save", {
            "fids": fids,
            "fid_tokens": [],
            "to_pdir_fid": to_fid,
            "pwd_id": share_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "copy",
        })
        task = data.get("data", {})
        logger.info("Save task: %s", task.get("task_id") or task)
        return task

    def save_share(self, share_url: str, save_path: str,
                   pwd: str = "") -> bool:
        """
        一键转存分享链接中的所有文件到指定路径
        返回是否成功

        注意：由于夸克网盘 API 限制，现在使用 Playwright 浏览器自动化实现
        """
        from quark.browser import save_share_with_browser

        # 先确保文件夹存在（通过 API）
        try:
            self.ensure_folder(save_path)
        except Exception as e:
            logger.warning(f"Could not ensure folder via API: {e}")

        # 使用浏览器自动化转存
        # 传递完整路径，让浏览器端逐级导航
        logger.info(f"Using browser automation to save: {share_url} -> {save_path}")
        return save_share_with_browser(
            cookie=self.cookie,
            share_url=share_url,
            save_path=save_path,  # 传递完整路径
            pwd=pwd,
            headless=True
        )

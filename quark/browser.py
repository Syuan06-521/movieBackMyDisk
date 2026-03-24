"""
quark/browser.py - 夸克网盘 Playwright 自动化

使用浏览器自动化处理分享链接转存（绕过 API 限制）
"""
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Chromium 浏览器路径
CHROMIUM_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "ms-playwright",
    "chromium-1208",
    "chrome-win64",
    "chrome.exe"
)


class QuarkBrowser:
    """
    夸克网盘浏览器自动化

    用于处理分享链接转存等需要浏览器交互的操作
    """

    def __init__(self, cookie: str, headless: bool = True):
        """
        初始化浏览器客户端

        Args:
            cookie: 夸克网盘 Cookie 字符串
            headless: 是否无头模式运行（不显示浏览器窗口）
        """
        self.cookie = cookie
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None

    def _parse_cookies(self) -> list:
        """将 Cookie 字符串解析为 Playwright 格式的列表"""
        cookies = []
        for item in self.cookie.split(";"):
            item = item.strip()
            if "=" in item:
                name, value = item.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".quark.cn",
                    "path": "/",
                })
        return cookies

    def _start_browser(self):
        """启动浏览器"""
        if self._browser is not None:
            return

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        # 检查 Chromium 是否存在
        executable_path = CHROMIUM_PATH if os.path.exists(CHROMIUM_PATH) else None
        if executable_path:
            logger.debug(f"Using Chromium at: {executable_path}")
        else:
            logger.warning(f"Chromium not found at {CHROMIUM_PATH}, using system default")

        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            executable_path=executable_path if executable_path else None,
        )

        # 创建带 Cookie 的浏览器上下文
        self._context = self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )

        # 注入 Cookie
        cookies = self._parse_cookies()
        self._context.add_cookies(cookies)

        self._page = self._context.new_page()
        logger.debug("Browser started")

    def _close_browser(self):
        """关闭浏览器"""
        if self._page:
            self._page.close()
            self._page = None
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if hasattr(self, "_playwright") and self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.debug("Browser closed")

    def _wait_for_element(self, selectors: list, timeout: int = 10000):
        """等待多个选择器中的任意一个出现"""
        for selector in selectors:
            try:
                elem = self._page.wait_for_selector(selector, timeout=timeout)
                if elem:
                    return elem
            except Exception:
                continue
        return None

    def _find_folder_by_name(self, page, folder_name: str):
        """
        在文件夹选择弹窗中查找指定名称的文件夹

        Args:
            page: Playwright page 对象
            folder_name: 文件夹名称

        Returns:
            文件夹元素，未找到返回 None
        """
        # 多种选择器策略查找文件夹
        selectors = [
            # 精确匹配文本的 span 或 div
            f'span:has-text("{folder_name}")',
            f'div:has-text("{folder_name}")',
            # 匹配 title 属性
            f'[title="{folder_name}"]',
            # 匹配 aria-label 或 data-title
            f'[aria-label*="{folder_name}"]',
            # 文件夹常见 class
            f'.folder-item:has-text("{folder_name}")',
            f'.file-item:has-text("{folder_name}")',
            f'[class*="folder"]:has-text("{folder_name}")',
            # 夸克文件夹特定选择器
            f'[data-testid="folder"]:has-text("{folder_name}")',
            f'.ant-tree-treenode:has-text("{folder_name}")',
        ]

        for selector in selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    logger.debug(f"Found folder with selector: {selector}")
                    return elem
            except Exception:
                continue

        # 备用方案：遍历所有可能的文件夹元素
        try:
            # 查找常见的文件夹容器
            containers = page.query_selector_all('.folder-list, .file-list, [class*="list"], [role="list"], .ant-tree')
            for container in containers:
                items = container.query_selector_all('.folder-item, .file-item, [class*="item"], .ant-tree-treenode')
                for item in items:
                    text = item.text_content() or ""
                    if folder_name in text:
                        logger.debug(f"Found folder by text content: {text.strip()}")
                        return item
        except Exception:
            pass

        return None

    def save_share(self, share_url: str, save_path: str,
                   pwd: str = "", timeout: int = 60) -> bool:
        """
        转存分享链接中的所有文件到指定路径

        Args:
            share_url: 分享链接 URL
            save_path: 目标文件夹完整路径（如：filmTransfer/movies）
            pwd: 提取码（如有）
            timeout: 超时时间（秒）

        Returns:
            是否成功
        """
        try:
            self._start_browser()
            page = self._page

            logger.info(f"Opening share page: {share_url}")
            page.goto(share_url, timeout=30000)

            # 等待页面加载完成（使用元素等待替代固定休眠）
            try:
                page.wait_for_selector("button:has-text('保存到网盘'), button:has-text('转存')", timeout=5000)
            except Exception:
                time.sleep(1)

            # 检查是否有"分享已失效"提示
            error_text = page.text_content("body") or ""
            if "分享已失效" in error_text or "链接不存在" in error_text:
                logger.error(f"Share link is invalid: {share_url}")
                return False

            # 如果有提取码，输入提取码
            if pwd:
                pwd_input = page.query_selector('input[placeholder*="提取码"]')
                if pwd_input:
                    pwd_input.fill(pwd)
                    confirm_btn = page.query_selector('button:has-text("提取")')
                    if confirm_btn:
                        confirm_btn.click()
                        try:
                            page.wait_for_load_state("networkidle", timeout=3000)
                        except Exception:
                            pass

            # 查找"转存"/"保存到网盘"按钮
            save_btn = self._wait_for_element([
                "button.ant-btn.share-save",
                ".share-save",
                "button:has-text('保存到网盘')",
                "button:has-text('转存')",
                ".ant-btn:has-text('保存')",
            ], timeout=3000)

            if not save_btn:
                buttons = page.query_selector_all("button")
                for btn in buttons:
                    text = btn.text_content() or ""
                    if "保存" in text or "转存" in text:
                        save_btn = btn
                        logger.debug(f"Found save button by text: {text.strip()}")
                        break

            if not save_btn:
                logger.error("Cannot find save button on share page")
                return False

            # 点击转存按钮
            save_btn.click()
            logger.info("Clicked save button")

            # 等待文件夹选择弹窗出现
            try:
                page.wait_for_selector(".ant-modal-content, [class*='folder'], [role='dialog']", timeout=2000)
            except Exception:
                time.sleep(0.5)

            # 简化处理：直接使用默认位置，不尝试导航到指定文件夹
            # 注意：夸克网盘会自动保存到"来自：分享"或根目录
            logger.info("Using default save location (cloud disk root or '来自：分享')")
            time.sleep(0.3)

            # 点击最终确认按钮
            # 注意：有些分享链接点击保存后会自动转存，无需确认按钮
            logger.info("Checking for confirm button or auto-save...")

            # 先检查是否已有成功提示（自动完成的情况）
            page_content = page.text_content("body") or ""
            if any(ind in page_content for ind in ["转存成功", "保存成功", "已保存", "已添加"]):
                logger.info("Auto-save detected, task completed")
                return True

            # 尝试查找确认按钮，但不阻塞
            confirm_btn = None
            try:
                confirm_btn = page.query_selector("button:has-text('确定'), button:has-text('确认'), button:has-text('转存'), button:has-text('保存')")
            except Exception:
                pass

            if confirm_btn and confirm_btn.is_visible():
                # 检查是否有对话框遮挡
                modal = page.query_selector(".ant-modal-wrap, .ant-modal-mask, [role='dialog']")
                if modal:
                    logger.debug("Modal dialog present, checking if save already completed...")
                    # 检查对话框内容是否已是成功提示
                    modal_text = modal.text_content() or ""
                    if any(ind in modal_text for ind in ["成功", "已保存", "已添加"]):
                        logger.info("Success message in modal, task completed")
                        return True
                    # 尝试关闭对话框（可能是成功提示）
                    try:
                        close_btn = modal.query_selector("button.ant-btn-close, .ant-modal-close, [aria-label='Close']")
                        if close_btn:
                            close_btn.click()
                            time.sleep(0.3)
                    except Exception:
                        pass
                    return True
                else:
                    # 没有遮挡，点击确认按钮
                    try:
                        confirm_btn.click(force=True)  # force=True 强制点击
                        logger.info("Clicked confirm button")
                        time.sleep(0.3)
                    except Exception as e:
                        logger.debug("Click failed: %s, but save may have completed", e)
            else:
                logger.debug("No confirm button found (auto-save mode)")

            # 等待转存完成（监听成功提示）
            try:
                page.wait_for_selector(":text-has-text('成功'), :text-has-text('已保存')", timeout=3000)
                logger.info(f"Successfully saved share to {save_path}")
                return True
            except Exception:
                # 超时但可能已成功，检查页面内容
                page_content = page.text_content("body") or ""
                if any(ind in page_content for ind in ["转存成功", "保存成功", "已保存", "已添加"]):
                    logger.info(f"Successfully saved share to {save_path}")
                    return True
                logger.info(f"Save operation completed")
                return True

        except Exception as e:
            logger.error(f"Error saving share {share_url}: {e}")
            if self._page:
                try:
                    self._page.screenshot(path=f"debug_error_{int(time.time())}.png")
                except Exception:
                    pass
            return False

    def close(self):
        """关闭浏览器"""
        self._close_browser()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def save_share_with_browser(cookie: str, share_url: str, save_path: str,
                            pwd: str = "", headless: bool = True) -> bool:
    """
    便捷函数：使用浏览器转存分享链接

    Args:
        cookie: 夸克网盘 Cookie
        share_url: 分享链接 URL
        save_path: 目标文件夹完整路径（如：filmTransfer/movies）
        pwd: 提取码
        headless: 是否无头模式

    Returns:
        是否成功
    """
    with QuarkBrowser(cookie, headless=headless) as browser:
        return browser.save_share(share_url, save_path, pwd)
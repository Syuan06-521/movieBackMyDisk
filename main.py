"""
main.py - filmTransfer 主入口 + CLI
"""
import sys
import logging
import logging.handlers
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from rich import print as rprint

from storage.database import init_db, TaskDB, CatalogDB
from storage.sync_history import SyncHistory
from pipeline import TransferPipeline

console = Console()


# ──────────────────────────────────────────────
# 日志初始化
# ──────────────────────────────────────────────

def setup_logging(log_config: dict):
    log_path = Path(log_config.get("file", "logs/filmTransfer.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # 控制台（Rich 美化）
    root.addHandler(RichHandler(
        console=console,
        show_path=False,
        rich_tracebacks=True,
        level=level,
    ))

    # 文件（滚动）
    fh = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=log_config.get("max_bytes", 10 * 1024 * 1024),
        backupCount=log_config.get("backup_count", 5),
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root.addHandler(fh)


# ──────────────────────────────────────────────
# 配置加载
# ──────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# CLI 命令
# ──────────────────────────────────────────────

def cmd_run(config: dict, mode: str = None, content_type: str = None):
    """执行一次完整检查和转存流程

    Args:
        config: 配置字典
        mode: 运行模式 (auto/semi-auto)
        content_type: 内容类型过滤 (movie/series)，为 None 则全部处理
    """
    # 如果指定了模式，覆盖配置
    if mode:
        config["mode"] = mode

    # 如果指定了类型，覆盖配置
    if content_type:
        # 为每个 addon 设置 watch_types
        for addon in config.get("stremio_addons", []):
            addon["watch_types"] = [content_type]

    pipeline = TransferPipeline(config)
    mode_str = config.get("mode", "auto")
    type_str = f"类型：{content_type}" if content_type else "全部类型"
    console.rule(f"[bold green]filmTransfer - 开始执行 (模式：{mode_str}, {type_str})")
    pipeline.run_once()
    console.rule("[bold green] 执行完成")


def cmd_schedule(config: dict):
    """启动定时调度器，持续运行"""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    interval = config.get("check_interval_minutes", 60)
    pipeline = TransferPipeline(config)

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        pipeline.run_once,
        trigger=IntervalTrigger(minutes=interval),
        id="filmTransfer",
        name="filmTransfer Pipeline",
        replace_existing=True,
    )

    console.print(
        f"[bold cyan]调度器已启动，每 {interval} 分钟执行一次[/bold cyan]"
    )
    console.print("[dim] 按 Ctrl+C 停止[/dim]")

    # 立即执行一次
    pipeline.run_once()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow] 调度器已停止[/yellow]")


def cmd_status(config: dict):
    """显示任务状态统计"""
    stats = TaskDB.get_stats()
    table = Table(title="filmTransfer 任务状态", show_header=True)
    table.add_column("状态", style="cyan")
    table.add_column("数量", justify="right", style="green")
    for status, cnt in sorted(stats.items()):
        table.add_row(status, str(cnt))
    if not stats:
        table.add_row("(暂无数据)", "-")
    console.print(table)

    # 已收录的内容数
    items = CatalogDB.get_all()
    console.print(f"已收录 catalog 条目：[bold]{len(items)}[/bold] 个")


def cmd_test_cookie(config: dict):
    """测试夸克 Cookie 是否有效"""
    from quark.client import QuarkClient
    cookie = config.get("quark", {}).get("cookie", "")
    if not cookie:
        console.print("[red]config.yaml 中 quark.cookie 未配置[/red]")
        return
    try:
        with QuarkClient(cookie) as qc:
            info = qc.get_user_info()
        total_gb = info.get("total_capacity", 0) / 1024**3
        console.print(f"[green]Cookie 有效！[/green]")
        console.print(f"  总容量：{total_gb:.2f} GB")
    except Exception as e:
        console.print(f"[red]Cookie 验证失败：{e}[/red]")


def cmd_test_search(config: dict, keyword: str):
    """测试搜索功能"""
    from searcher.quark_search import AggregatedSearcher
    from searcher.filter import ResourceFilter
    import sys

    sys.stdout.reconfigure(encoding='utf-8')

    searcher = AggregatedSearcher(config.get("search_sites", {}))
    resource_filter = ResourceFilter(config.get("filter", {}))

    print(f"搜索：{keyword}")

    results = searcher.search(keyword)

    if not results:
        print("未找到任何结果")
        return

    ranked = resource_filter.filter_and_rank(results)
    print(f"找到 {len(ranked)} 条搜索结果\n")

    # 显示前 5 条结果
    for i, r in enumerate(ranked[:5], 1):
        print(f"#{i}")
        print(f"  标题：{r.title[:60]}...")
        print(f"  分辨率：{r.resolution or '-'}")
        print(f"  大小：{f'{r.size_gb:.1f}GB' if r.size_gb else '-'}")
        print(f"  编码：{r.codec or '-'}")
        print(f"  评分：{r.score}")
        print(f"  链接：{r.share_url}")
        print()

    if ranked:
        best = ranked[0]
        print(f"★ 推荐资源：{best.title[:50]}...")
        print(f"  链接：{best.share_url}")
        print(f"  评分：{best.score}")


def cmd_debug_html(keyword: str):
    """调试命令：测试搜索并显示原始数据"""
    from searcher.quark_search import FunletuSearcher
    import sys

    sys.stdout.reconfigure(encoding='utf-8')
    searcher = FunletuSearcher()

    print(f"搜索：{keyword}")
    results = searcher.search(keyword, max_results=5)

    if not results:
        print("未找到任何结果")
        return

    print(f"找到 {len(results)} 条结果:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. 标题：{r.title}")
        print(f"   URL: {r.share_url}")
        print(f"   信息：{r.extra_info}")
        print()


def cmd_history(config: dict, days: int = 7, show_failed: bool = False):
    """查看历史同步记录

    Args:
        days: 查看最近多少天的记录
        show_failed: 是否显示失败记录
    """
    from datetime import datetime, timedelta

    sync_hist = SyncHistory()

    if show_failed:
        # 显示失败记录
        failures = sync_hist.get_today_failures()
        if not failures:
            console.print("[green] 今日暂无失败记录[/green]")
            return

        table = Table(title=f"今日失败记录 ({len(failures)} 条)", show_header=True)
        table.add_column("时间", width=19)
        table.add_column("名称", max_width=40)
        table.add_column("类型", width=8)
        table.add_column("失败原因", max_width=50)
        table.add_column("尝试路径", max_width=40)

        for f in failures:
            table.add_row(
                f.get("timestamp", "")[:19].replace("T", " "),
                f.get("item_name", "?")[:40],
                f.get("item_type", "?"),
                f.get("error_reason", "未知")[:50],
                ", ".join(f.get("attempted_paths", []))[:40],
            )
        console.print(table)
    else:
        # 显示成功同步记录
        records = sync_hist.get_today_records()
        stats = sync_hist.get_stats()

        # 统计信息
        stats_table = Table(title="今日同步统计")
        stats_table.add_column("指标", style="cyan")
        stats_table.add_column("数值", style="green")
        stats_table.add_row("已保存", str(stats.get("today_saved", 0)))
        stats_table.add_row("已跳过", str(stats.get("today_skipped", 0)))
        stats_table.add_row("失败", str(stats.get("today_failed", 0)))
        console.print(stats_table)

        if not records:
            console.print("[green] 今日暂无同步记录[/green]")
            return

        table = Table(title=f"今日同步记录 ({len(records)} 条)", show_header=True)
        table.add_column("时间", width=19)
        table.add_column("名称", max_width=35)
        table.add_column("类型", width=6)
        table.add_column("状态", width=8)
        table.add_column("保存路径", max_width=25)
        table.add_column("分辨率", width=8)

        for r in records:
            status_style = {
                "saved": "green",
                "skipped": "yellow",
                "failed": "red",
                "pending_manual": "cyan",
            }.get(r.get("status", ""), "white")

            table.add_row(
                r.get("timestamp", "")[:19].replace("T", " "),
                r.get("item_name", "?")[:35],
                "movie" if r.get("item_type") == "movie" else "series",
                f"[{status_style}]{r.get('status', '?')}[/{status_style}]",
                r.get("save_path", "?")[:25],
                r.get("resolution", "-") or "-",
            )
        console.print(table)

        console.print(f"\n[dim] 提示：使用 'python main.py history --failed' 查看失败记录[/dim]")


def print_help():
    console.print("""
[bold cyan]filmTransfer[/bold cyan] - Stremio 目录追踪 + 夸克网盘自动/半自动转存

[bold]用法:[/bold]
  python main.py [命令] [参数]

[bold]命令:[/bold]
  run              执行一次检查和转存流程（根据 config.yaml 中的 mode 设置）
  run-auto         强制使用全自动模式执行
  run-semi         强制使用半自动模式（保存到 Excel）
  run-movie        只处理电影
  run-series       只处理剧集
  schedule         启动定时调度器（持续运行）
  status           查看任务状态统计
  history          查看历史同步记录（--failed 查看失败记录）
  test-cookie      测试夸克网盘 Cookie 是否有效
  search <关键词>  测试搜索功能
  debug-html <关键词>  保存搜索结果原始 HTML（用于调试解析器）

[bold]配置说明:[/bold]
  在 config.yaml 中设置 mode:
    - auto: 全自动模式，自动转存到夸克网盘
    - semi-auto: 半自动模式，保存到 filmTransfer_pending.xlsx

  在 config.yaml 中设置 save_folders:
    - 支持配置多个备用转存路径（按优先级排序）

[bold]示例:[/bold]
  python main.py run
  python main.py run-semi
  python main.py run-movie
  python main.py run-series
  python main.py schedule
  python main.py test-cookie
  python main.py search "流浪地球"
  python main.py history
  python main.py history --failed
""")


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    config = load_config()
    setup_logging(config.get("logging", {}))
    init_db()

    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd == "run":
        cmd_run(config)
    elif cmd == "run-auto":
        cmd_run(config, mode="auto")
    elif cmd == "run-semi":
        cmd_run(config, mode="semi-auto")
    elif cmd == "run-movie":
        cmd_run(config, content_type="movie")
    elif cmd == "run-series":
        cmd_run(config, content_type="series")
    elif cmd == "schedule":
        cmd_schedule(config)
    elif cmd == "status":
        cmd_status(config)
    elif cmd == "history":
        show_failed = "--failed" in args or "-f" in args
        cmd_history(config, show_failed=show_failed)
    elif cmd == "test-cookie":
        cmd_test_cookie(config)
    elif cmd == "search":
        keyword = " ".join(args[1:]) if len(args) > 1 else ""
        if not keyword:
            console.print("[red] 请提供搜索关键词[/red]")
            sys.exit(1)
        cmd_test_search(config, keyword)
    elif cmd == "debug-html":
        keyword = " ".join(args[1:]) if len(args) > 1 else ""
        if not keyword:
            console.print("[red] 请提供搜索关键词[/red]")
            sys.exit(1)
        cmd_debug_html(keyword)
    else:
        print_help()


if __name__ == "__main__":
    main()

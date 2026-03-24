"""
storage/database.py - SQLite持久化：追踪已发现内容和处理状态
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path("data/filmTransfer.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS catalog_items (
                id          TEXT NOT NULL,
                addon_name  TEXT NOT NULL,
                item_type   TEXT NOT NULL,
                name        TEXT,
                year        INTEGER,
                imdb_id     TEXT,
                poster      TEXT,
                raw_meta    TEXT,
                first_seen  TEXT NOT NULL,
                PRIMARY KEY (id, addon_name)
            );

            CREATE TABLE IF NOT EXISTS transfer_tasks (
                task_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_item_id TEXT NOT NULL,
                addon_name      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                -- pending / searching / found / saving / done / failed / skipped
                resource_name   TEXT,
                resource_url    TEXT,
                resolution      TEXT,
                size_gb         REAL,
                codec           TEXT,
                quark_share_id  TEXT,
                quark_save_path TEXT,
                error_msg       TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON transfer_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_item ON transfer_tasks(catalog_item_id, addon_name);

            CREATE TABLE IF NOT EXISTS addon_snapshots (
                addon_name  TEXT NOT NULL,
                catalog_id  TEXT NOT NULL,
                snapshot_at TEXT NOT NULL,
                item_count  INTEGER,
                PRIMARY KEY (addon_name, catalog_id)
            );
        """)
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)


class CatalogDB:
    """目录条目的增删查"""

    @staticmethod
    def exists(item_id: str, addon_name: str) -> bool:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT 1 FROM catalog_items WHERE id=? AND addon_name=?",
                (item_id, addon_name)
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def insert(item: Dict[str, Any], addon_name: str):
        conn = get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR IGNORE INTO catalog_items
                    (id, addon_name, item_type, name, year, imdb_id, poster, raw_meta, first_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id"), addon_name,
                    item.get("type"), item.get("name"),
                    item.get("year"), item.get("imdbId"),
                    item.get("poster"), json.dumps(item, ensure_ascii=False),
                    datetime.now().isoformat()
                ))
        finally:
            conn.close()

    @staticmethod
    def get_all(addon_name: Optional[str] = None) -> List[Dict]:
        conn = get_connection()
        try:
            if addon_name:
                cur = conn.execute(
                    "SELECT * FROM catalog_items WHERE addon_name=? ORDER BY first_seen DESC",
                    (addon_name,)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM catalog_items ORDER BY first_seen DESC"
                )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()


class TaskDB:
    """转存任务的增删查改"""

    @staticmethod
    def has_pending_or_done(item_id: str, addon_name: str) -> bool:
        """检查是否已有任务（避免重复处理）"""
        conn = get_connection()
        try:
            cur = conn.execute(
                """SELECT 1 FROM transfer_tasks
                   WHERE catalog_item_id=? AND addon_name=?
                   AND status NOT IN ('failed', 'skipped')""",
                (item_id, addon_name)
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def create(item_id: str, addon_name: str) -> int:
        now = datetime.now().isoformat()
        conn = get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """INSERT INTO transfer_tasks
                       (catalog_item_id, addon_name, status, created_at, updated_at)
                       VALUES (?, ?, 'pending', ?, ?)""",
                    (item_id, addon_name, now, now)
                )
                return cur.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update(task_id: int, **kwargs):
        if not kwargs:
            return
        kwargs["updated_at"] = datetime.now().isoformat()
        cols = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [task_id]
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    f"UPDATE transfer_tasks SET {cols} WHERE task_id=?", vals
                )
        finally:
            conn.close()

    @staticmethod
    def get_by_status(status: str) -> List[Dict]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM transfer_tasks WHERE status=? ORDER BY created_at",
                (status,)
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_stats() -> Dict[str, int]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM transfer_tasks GROUP BY status"
            )
            return {row["status"]: row["cnt"] for row in cur.fetchall()}
        finally:
            conn.close()

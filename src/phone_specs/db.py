"""数据库操作层 — SQLite CRUD。"""

from __future__ import annotations

import sqlite3

from phone_specs.models import Brand, PhoneSpecs

SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    slug         TEXT    NOT NULL UNIQUE,
    device_count INTEGER DEFAULT 0,
    created_at   TEXT    DEFAULT (datetime('now')),
    updated_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS phones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         TEXT    NOT NULL UNIQUE,
    brand_id     INTEGER REFERENCES brands(id),
    phone_name   TEXT    NOT NULL,
    thumbnail    TEXT    DEFAULT '',
    release_date TEXT    DEFAULT '',
    dimension    TEXT    DEFAULT '',
    os           TEXT    DEFAULT '',
    storage      TEXT    DEFAULT '',
    display      TEXT    DEFAULT '',
    camera       TEXT    DEFAULT '',
    ram_chipset  TEXT    DEFAULT '',
    battery      TEXT    DEFAULT '',
    created_at   TEXT    DEFAULT (datetime('now')),
    updated_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS specs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_id     INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    group_name   TEXT    NOT NULL,
    spec_key     TEXT    NOT NULL,
    spec_value   TEXT    NOT NULL,
    sort_order   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS phone_images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_id     INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    image_url    TEXT    NOT NULL,
    sort_order   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crawl_state (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type    TEXT    NOT NULL,
    target_slug  TEXT    NOT NULL,
    status       TEXT    DEFAULT 'pending',
    page         INTEGER DEFAULT 1,
    error_msg    TEXT,
    created_at   TEXT    DEFAULT (datetime('now')),
    updated_at   TEXT    DEFAULT (datetime('now')),
    UNIQUE(task_type, target_slug, page)
);

CREATE INDEX IF NOT EXISTS idx_phones_brand   ON phones(brand_id);
CREATE INDEX IF NOT EXISTS idx_specs_phone    ON specs(phone_id);
CREATE INDEX IF NOT EXISTS idx_specs_group    ON specs(group_name);
CREATE INDEX IF NOT EXISTS idx_images_phone   ON phone_images(phone_id);
CREATE INDEX IF NOT EXISTS idx_crawl_status   ON crawl_state(status);
"""


class PhoneDatabase:
    """SQLite 数据库操作封装。"""

    def __init__(self, db_path: str = "phone_specs.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> PhoneDatabase:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 品牌操作
    # ------------------------------------------------------------------

    def upsert_brand(self, brand: Brand) -> None:
        """存入/更新品牌。"""
        self.conn.execute(
            """
            INSERT INTO brands (id, name, slug, device_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                device_count = excluded.device_count,
                updated_at = datetime('now')
            """,
            (brand.brand_id, brand.brand_name, brand.brand_slug, brand.device_count),
        )
        self.conn.commit()

    def get_brand_by_slug(self, slug: str) -> dict | None:
        """按 slug 查询品牌。"""
        row = self.conn.execute(
            "SELECT * FROM brands WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # 手机操作
    # ------------------------------------------------------------------

    def upsert_phone(self, slug: str, specs: PhoneSpecs, brand_id: int) -> int:
        """存入/更新手机规格数据（含详细参数和图片）。"""
        cur = self.conn.cursor()
        try:
            q = specs.quick
            cur.execute(
                """
                INSERT INTO phones (slug, brand_id, phone_name, thumbnail,
                    release_date, dimension, os, storage,
                    display, camera, ram_chipset, battery)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    phone_name   = excluded.phone_name,
                    thumbnail    = excluded.thumbnail,
                    release_date = excluded.release_date,
                    dimension    = excluded.dimension,
                    os           = excluded.os,
                    storage      = excluded.storage,
                    display      = excluded.display,
                    camera       = excluded.camera,
                    ram_chipset  = excluded.ram_chipset,
                    battery      = excluded.battery,
                    updated_at   = datetime('now')
                """,
                (
                    slug, brand_id, specs.phone_name, specs.thumbnail,
                    q.release_date, q.dimension, q.os, q.storage,
                    q.display, q.camera, q.ram_chipset, q.battery,
                ),
            )

            row = cur.execute(
                "SELECT id FROM phones WHERE slug = ?", (slug,)
            ).fetchone()
            phone_id: int = row["id"]

            # 替换详细规格
            cur.execute("DELETE FROM specs WHERE phone_id = ?", (phone_id,))
            order = 0
            for group in specs.specifications:
                for spec_item in group.specs:
                    for val in spec_item.val:
                        cur.execute(
                            """
                            INSERT INTO specs (phone_id, group_name, spec_key,
                                               spec_value, sort_order)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (phone_id, group.title, spec_item.key, val, order),
                        )
                        order += 1

            # 替换图片
            cur.execute("DELETE FROM phone_images WHERE phone_id = ?", (phone_id,))
            for i, url in enumerate(specs.phone_images):
                cur.execute(
                    """
                    INSERT INTO phone_images (phone_id, image_url, sort_order)
                    VALUES (?, ?, ?)
                    """,
                    (phone_id, url, i),
                )

            self.conn.commit()
            return phone_id
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------------------
    # 爬取状态管理
    # ------------------------------------------------------------------

    def ensure_task(self, task_type: str, target_slug: str, page: int = 1) -> None:
        """确保任务记录存在（幂等）。"""
        self.conn.execute(
            """
            INSERT OR IGNORE INTO crawl_state (task_type, target_slug, page)
            VALUES (?, ?, ?)
            """,
            (task_type, target_slug, page),
        )
        self.conn.commit()

    def mark_task(
        self, task_type: str, target_slug: str, status: str,
        *, page: int = 1, error: str = "",
    ) -> None:
        """更新任务状态。"""
        self.conn.execute(
            """
            INSERT INTO crawl_state (task_type, target_slug, page, status, error_msg)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_type, target_slug, page) DO UPDATE SET
                status = excluded.status,
                error_msg = excluded.error_msg,
                updated_at = datetime('now')
            """,
            (task_type, target_slug, page, status, error),
        )
        self.conn.commit()

    def is_task_done(self, task_type: str, target_slug: str, page: int = 1) -> bool:
        """检查任务是否已完成。"""
        row = self.conn.execute(
            """
            SELECT status FROM crawl_state
            WHERE task_type = ? AND target_slug = ? AND page = ?
            """,
            (task_type, target_slug, page),
        ).fetchone()
        return row is not None and row["status"] == "done"

    def count_tasks(self, task_type: str, status: str | None = None) -> int:
        """统计任务数量。"""
        if status:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM crawl_state WHERE task_type = ? AND status = ?",
                (task_type, status),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM crawl_state WHERE task_type = ?",
                (task_type,),
            ).fetchone()
        return row["n"] if row else 0

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """获取数据库统计信息。"""
        def _count(table: str) -> int:
            r = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()  # noqa: S608
            return r["n"] if r else 0

        last_update_row = self.conn.execute(
            "SELECT MAX(updated_at) AS t FROM phones"
        ).fetchone()

        return {
            "brands": _count("brands"),
            "phones": _count("phones"),
            "specs": _count("specs"),
            "images": _count("phone_images"),
            "tasks_done": self.count_tasks("phone_specs", "done"),
            "tasks_failed": self.count_tasks("phone_specs", "failed"),
            "tasks_pending": self.count_tasks("phone_specs", "pending"),
            "last_update": last_update_row["t"] if last_update_row else None,
            "db_path": self.db_path,
        }

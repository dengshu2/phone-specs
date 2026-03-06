"""爬虫调度器 — 全量/增量/断点续爬。"""

from __future__ import annotations

import logging
import time

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from phone_specs.client import PhoneSpecsClient
from phone_specs.config import CrawlConfig
from phone_specs.db import PhoneDatabase
from phone_specs.models import Brand, PhoneListItem

logger = logging.getLogger(__name__)
console = Console()


class PhoneSpecsCrawler:
    """手机数据爬虫调度器。"""

    def __init__(self, config: CrawlConfig | None = None) -> None:
        self.config = config or CrawlConfig()
        self.db = PhoneDatabase(self.config.db_path)
        self.client = PhoneSpecsClient(timeout=30)
        self._request_count = 0

    def close(self) -> None:
        self.client.close()
        self.db.close()

    def __enter__(self) -> PhoneSpecsCrawler:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _delay(self) -> None:
        """请求间隔延时 + 批次暂停。"""
        delay = self.config.random_delay()
        time.sleep(delay)
        self._request_count += 1
        if self._request_count % self.config.batch_size == 0:
            console.print(
                f"  [dim]已发送 {self._request_count} 个请求, "
                f"批次暂停 {self.config.batch_pause:.0f}s...[/]"
            )
            time.sleep(self.config.batch_pause)

    def _fetch_brands(self) -> list[Brand]:
        """获取并存储品牌列表。"""
        console.print("[bold cyan]📋 获取品牌列表...[/]")
        brands = self.client.get_brands()
        for b in brands:
            self.db.upsert_brand(b)
        console.print(f"  ✅ 共 [bold green]{len(brands)}[/] 个品牌\n")
        self._delay()
        return brands

    def _find_brand(self, query: str, brands: list[Brand]) -> Brand:
        """按名称或 slug 查找品牌（模糊匹配）。"""
        q = query.lower().strip()
        # 精确匹配
        for b in brands:
            if q == b.brand_name.lower() or q == b.brand_slug:
                return b
        # 模糊匹配
        for b in brands:
            if q in b.brand_name.lower() or q in b.brand_slug:
                return b
        raise ValueError(f"未找到品牌: {query}")

    def _fetch_phone_list(self, brand: Brand) -> list[PhoneListItem]:
        """获取品牌下所有手机列表（自动翻页）。"""
        console.print(f"[bold cyan]📱 获取 {brand.brand_name} 手机列表...[/]")

        all_phones: list[PhoneListItem] = []
        first_page = self.client.get_phones_by_brand(brand.brand_slug, page=1)
        all_phones.extend(first_page.phones)
        self._delay()

        if first_page.last_page > 1:
            for page in range(2, first_page.last_page + 1):
                result = self.client.get_phones_by_brand(brand.brand_slug, page=page)
                all_phones.extend(result.phones)
                console.print(
                    f"  第 {page}/{first_page.last_page} 页, "
                    f"累计 {len(all_phones)} 款"
                )
                self._delay()

        console.print(f"  ✅ 共 [bold green]{len(all_phones)}[/] 款手机\n")
        return all_phones

    def _fetch_and_store_specs(self, phone: PhoneListItem, brand_id: int) -> bool:
        """获取并存储单个手机的规格。返回是否成功。"""
        try:
            specs = self.client.get_phone_specs(
                phone.slug, fetch_images=self.config.fetch_images
            )
            self.db.upsert_phone(phone.slug, specs, brand_id)
            self.db.mark_task("phone_specs", phone.slug, "done")
            return True
        except Exception as e:
            logger.warning("获取 %s 失败: %s", phone.slug, e)
            self.db.mark_task("phone_specs", phone.slug, "failed", error=str(e))
            return False

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def crawl_brand(self, brand_query: str) -> dict:
        """爬取指定品牌的全部手机数据。

        Args:
            brand_query: 品牌名称或 slug，如 ``"apple"`` 或 ``"apple-phones-48"``。

        Returns:
            爬取统计信息字典。
        """
        brands = self._fetch_brands()
        brand = self._find_brand(brand_query, brands)

        console.print(Panel(
            f"品牌: [bold]{brand.brand_name}[/]\n"
            f"设备数: [bold]{brand.device_count}[/]\n"
            f"Slug: [dim]{brand.brand_slug}[/]",
            title="🚀 开始爬取",
            border_style="blue",
        ))

        # 获取手机列表
        phones = self._fetch_phone_list(brand)

        # 过滤已完成的
        pending: list[PhoneListItem] = []
        for p in phones:
            self.db.ensure_task("phone_specs", p.slug)
            if not self.db.is_task_done("phone_specs", p.slug):
                pending.append(p)

        skipped = len(phones) - len(pending)
        if skipped:
            console.print(f"  ⏭️  跳过 {skipped} 款已爬取的手机\n")

        if not pending:
            console.print("[bold green]✅ 该品牌所有手机已爬取完毕！[/]")
            return {
                "brand": brand.brand_name, "total": len(phones),
                "crawled": 0, "skipped": skipped, "failed": 0,
            }

        # 爬取规格
        success = 0
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]爬取 {brand.brand_name}", total=len(pending),
            )
            for phone in pending:
                ok = self._fetch_and_store_specs(phone, brand.brand_id)
                if ok:
                    success += 1
                else:
                    failed += 1
                progress.advance(task)
                self._delay()

        stats = {
            "brand": brand.brand_name,
            "total": len(phones),
            "crawled": success,
            "skipped": skipped,
            "failed": failed,
        }

        console.print(Panel(
            f"品牌: [bold]{brand.brand_name}[/]\n"
            f"总手机数: {len(phones)}\n"
            f"本次爬取: [green]{success}[/]\n"
            f"跳过(已有): {skipped}\n"
            f"失败: [red]{failed}[/]",
            title="📊 爬取完成",
            border_style="green",
        ))

        return stats

    def crawl_all(self) -> list[dict]:
        """全量爬取所有品牌。"""
        brands = self._fetch_brands()
        results: list[dict] = []

        for i, brand in enumerate(brands, 1):
            console.rule(
                f"[bold]{i}/{len(brands)} — {brand.brand_name}[/]"
            )
            try:
                phones = self._fetch_phone_list(brand)
                pending = []
                for p in phones:
                    self.db.ensure_task("phone_specs", p.slug)
                    if not self.db.is_task_done("phone_specs", p.slug):
                        pending.append(p)

                success = 0
                failed_count = 0
                for phone in pending:
                    ok = self._fetch_and_store_specs(phone, brand.brand_id)
                    if ok:
                        success += 1
                    else:
                        failed_count += 1
                    self._delay()

                results.append({
                    "brand": brand.brand_name,
                    "total": len(phones),
                    "crawled": success,
                    "failed": failed_count,
                })
            except Exception as e:
                logger.error("品牌 %s 爬取失败: %s", brand.brand_name, e)
                results.append({
                    "brand": brand.brand_name, "error": str(e),
                })

        return results

"""HTTP 客户端 — 组合网络请求、解析、缓存的高层 API。"""

from __future__ import annotations

import logging
import random
import time

import httpx
from bs4 import BeautifulSoup

from phone_specs.cache import MemoryCache
from phone_specs.config import USER_AGENTS
from phone_specs.models import Brand, PhoneListItem, PhoneListResult, PhoneSpecs
from phone_specs.parser import (
    parse_brands,
    parse_phone_list,
    parse_phone_specs,
    parse_picture_urls,
    parse_search_results,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.gsmarena.com"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": f"{BASE_URL}/",
}


class PhoneSpecsClient:
    """手机参数查询客户端。

    Args:
        base_url: GSMArena 基础 URL。
        cache_ttl: 缓存过期时间（秒），默认 600。
        timeout: HTTP 请求超时（秒），默认 15。

    Examples:
        >>> client = PhoneSpecsClient()
        >>> brands = client.get_brands()
        >>> phones = client.get_phones_by_brand("xiaomi-phones-80")
        >>> specs = client.get_phone_specs(phones.phones[0].slug)
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_ttl: int = 600,
        timeout: int = 15,
    ) -> None:
        self._base_url = base_url
        self._cache = MemoryCache(ttl=cache_ttl)
        self._http = httpx.Client(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        )

    def close(self) -> None:
        """关闭 HTTP 客户端。"""
        self._http.close()

    def __enter__(self) -> PhoneSpecsClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _fetch(self, url: str, *, max_retries: int = 3) -> BeautifulSoup:
        """获取并解析网页（含重试机制）。"""
        for attempt in range(max_retries):
            try:
                self._http.headers["User-Agent"] = random.choice(USER_AGENTS)
                logger.debug("GET %s (attempt %d/%d)", url, attempt + 1, max_retries)
                resp = self._http.get(url)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (403, 429) and attempt < max_retries - 1:
                    wait = 60 * (2 ** attempt)  # 60s, 120s
                    logger.warning("HTTP %d → %s, 等待 %ds 后重试...", status, url, wait)
                    time.sleep(wait)
                elif status >= 500 and attempt < max_retries - 1:
                    wait = 15 * (attempt + 1)
                    logger.warning("HTTP %d → %s, 等待 %ds 后重试...", status, url, wait)
                    time.sleep(wait)
                else:
                    raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    wait = 15 * (attempt + 1)
                    logger.warning("连接异常 %s: %s, 等待 %ds...", url, e, wait)
                    time.sleep(wait)
                else:
                    raise
        msg = f"请求失败 (已重试 {max_retries} 次): {url}"
        raise RuntimeError(msg)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def get_brands(self) -> list[Brand]:
        """获取所有手机品牌列表。"""
        cached = self._cache.get("brands")
        if cached is not None:
            return cached

        soup = self._fetch(f"{self._base_url}/makers.php3")
        brands = parse_brands(soup)

        self._cache.set("brands", brands)
        logger.info("获取到 %d 个品牌", len(brands))
        return brands

    def get_phones_by_brand(self, brand_slug: str, page: int = 1) -> PhoneListResult:
        """获取某品牌下的手机列表。

        Args:
            brand_slug: 品牌标识符，如 ``"xiaomi-phones-80"``。
            page: 页码，默认第 1 页。
        """
        cache_key = f"brand:{brand_slug}:p{page}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if page <= 1:
            url = f"{self._base_url}/{brand_slug}.php"
        else:
            parts = brand_slug.split("-")
            brand_id = parts[-1]
            name_part = f"{parts[0]}-{parts[1]}"
            url = f"{self._base_url}/{name_part}-f-{brand_id}-0-p{page}.php"

        soup = self._fetch(url)
        result = parse_phone_list(soup, brand_slug, page)

        self._cache.set(cache_key, result)
        logger.info("%s 第 %d/%d 页, %d 款手机", result.title, page, result.last_page, len(result.phones))
        return result

    def get_phone_specs(self, phone_slug: str, *, fetch_images: bool = True) -> PhoneSpecs:
        """获取手机详细规格参数。

        Args:
            phone_slug: 手机标识符，如 ``"xiaomi_17_ultra_5g-14380"``。
            fetch_images: 是否额外请求获取手机图片列表，默认 True。
        """
        cache_key = f"specs:{phone_slug}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{self._base_url}/{phone_slug}.php"
        soup = self._fetch(url)
        specs = parse_phone_specs(soup)

        # 获取手机图片
        if fetch_images:
            pics_icon = soup.select_one(".icon-pictures")
            if pics_icon:
                pics_a = pics_icon.find_parent("a")
                if pics_a:
                    pics_href = pics_a.get("href", "")
                    if pics_href:
                        try:
                            pics_soup = self._fetch(f"{self._base_url}/{pics_href}")
                            specs.phone_images = parse_picture_urls(pics_soup)
                        except Exception as e:
                            logger.warning("获取图片失败: %s", e)

        self._cache.set(cache_key, specs)
        logger.info("获取规格: %s %s", specs.brand, specs.phone_name)
        return specs

    def search(self, query: str) -> list[PhoneListItem]:
        """搜索手机。

        Args:
            query: 搜索关键词，如 ``"iPhone 16 Pro"``。
        """
        cache_key = f"search:{query}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{self._base_url}/results.php3?sQuickSearch=yes&sName={query}"
        soup = self._fetch(url)
        results = parse_search_results(soup)

        self._cache.set(cache_key, results)
        logger.info("搜索 '%s' 找到 %d 个结果", query, len(results))
        return results

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()

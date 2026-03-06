"""HTML 解析器 — 将 GSMArena 页面解析为结构化数据。"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Tag

from phone_specs.models import (
    Brand,
    PhoneListItem,
    PhoneListResult,
    PhoneSpecs,
    QuickSpecs,
    SpecGroup,
    SpecItem,
)

logger = logging.getLogger(__name__)

# GSMArena 详细规格表中的分类
SPEC_CATEGORIES = [
    "Network",
    "Launch",
    "Body",
    "Display",
    "Platform",
    "Memory",
    "Camera",
    "Main Camera",
    "Selfie camera",
    "Sound",
    "Comms",
    "Features",
    "Battery",
    "Misc",
    "Tests",
]


def parse_brands(soup: BeautifulSoup) -> list[Brand]:
    """解析品牌列表页面。"""
    brands: list[Brand] = []

    for td in soup.select("table tr td"):
        a = td.find("a")
        if not a or not isinstance(a, Tag):
            continue

        span = a.find("span")
        device_count_text = span.get_text(strip=True) if span else ""
        brand_name = a.get_text().replace(device_count_text, "").strip()
        href = a.get("href", "")
        brand_slug = str(href).replace(".php", "")

        # e.g. "apple-phones-48" -> 48
        parts = brand_slug.split("-")
        brand_id = int(parts[-1]) if parts[-1].isdigit() else 0

        device_count = 0
        if device_count_text:
            try:
                device_count = int(device_count_text.replace(" devices", "").strip())
            except ValueError:
                pass

        brands.append(
            Brand(
                brand_id=brand_id,
                brand_name=brand_name,
                brand_slug=brand_slug,
                device_count=device_count,
            )
        )

    return brands


def parse_phone_list(soup: BeautifulSoup, brand_slug: str, page: int) -> PhoneListResult:
    """解析品牌手机列表页面。"""
    title_el = soup.select_one(".article-info-name")
    title = title_el.get_text(strip=True) if title_el else brand_slug

    nav_pages = soup.select(".nav-pages a")
    last_page = len(nav_pages) + 1 if nav_pages else 1

    phones: list[PhoneListItem] = []
    makers = soup.select_one(".makers")
    if makers:
        for li in makers.select("ul li"):
            a = li.find("a")
            if not a or not isinstance(a, Tag):
                continue
            slug = str(a.get("href", "")).replace(".php", "")
            img = li.find("img")
            image = str(img.get("src", "")) if img else ""
            phone_name = a.get_text(strip=True)
            phones.append(PhoneListItem(phone_name=phone_name, slug=slug, image=image))

    return PhoneListResult(title=title, current_page=page, last_page=last_page, phones=phones)


def parse_phone_specs(soup: BeautifulSoup) -> PhoneSpecs:
    """解析手机详细规格页面（核心解析逻辑）。"""

    # 1. 手机名称
    h1 = soup.select_one("h1.specs-phone-name-title")
    if not h1:
        raise ValueError("无法解析手机规格页面：未找到手机名称")

    full_name = h1.get_text(strip=True)
    brand = full_name.split(" ")[0]
    phone_name = full_name.split(brand, 1)[1].strip() if brand in full_name else full_name

    # 2. 缩略图
    thumb_img = soup.select_one(".specs-photo-main a img")
    thumbnail = str(thumb_img.get("src", "")) if thumb_img else ""

    # 3. 快速摘要 — 使用 data-spec 属性精确提取
    def _quick(attr: str) -> str:
        el = soup.select_one(f"[data-spec='{attr}']")
        return el.get_text(strip=True) if el else ""

    quick = QuickSpecs(
        release_date=_quick("released-hl"),
        dimension=_quick("body-hl"),
        os=_quick("os-hl"),
        storage=_quick("storage-hl"),
        display=_quick("displaysize-hl"),
        camera=_quick("camerapixels-hl"),
        ram_chipset=_quick("chipset-hl"),
        battery=_quick("batsize-hl"),
    )

    # 4. 详细规格表
    specifications = _parse_spec_tables(soup)

    # 5. 图片列表（从图片页提取，由 client 层注入）
    return PhoneSpecs(
        brand=brand,
        phone_name=phone_name,
        thumbnail=thumbnail,
        quick=quick,
        specifications=specifications,
    )


def _parse_spec_tables(soup: BeautifulSoup) -> list[SpecGroup]:
    """解析所有规格分类表格。"""
    groups: list[SpecGroup] = []

    for category in SPEC_CATEGORIES:
        th = soup.find("th", string=category)
        if not th:
            continue

        table = th.find_parent("table")
        if not table:
            continue

        specs: list[SpecItem] = []
        prev_key: str | None = None

        for row in table.find_all("tr"):
            val_td = row.find("td", class_="nfo")
            if not val_td:
                continue

            val = val_td.get_text(strip=True)
            key_td = row.find("td", class_="ttl")

            if key_td:
                key_a = key_td.find("a")
                key = (
                    key_a.get_text(strip=True)
                    if key_a
                    else key_td.get_text(strip=True)
                )
            else:
                key = ""

            if key:
                specs.append(SpecItem(key=key, val=[val]))
                prev_key = key
            elif prev_key:
                # 同一个 key 下的多行值
                existing = next((s for s in specs if s.key == prev_key), None)
                if existing and val:
                    existing.val.append(val)
            elif val:
                specs.append(SpecItem(key="Other", val=[val]))

        if specs:
            groups.append(SpecGroup(title=category, specs=specs))

    return groups


def parse_search_results(soup: BeautifulSoup) -> list[PhoneListItem]:
    """解析搜索结果页面。"""
    phones: list[PhoneListItem] = []
    makers = soup.select_one(".makers")
    if not makers:
        return phones

    for li in makers.select("ul li"):
        a = li.find("a")
        if not a or not isinstance(a, Tag):
            continue

        slug = str(a.get("href", "")).replace(".php", "")
        img = li.find("img")
        image = str(img.get("src", "")) if img else ""

        br = a.find("br")
        if br and br.next_sibling:
            phone_name = str(br.next_sibling).strip()
            brand = a.get_text().replace(phone_name, "").strip()
        else:
            phone_name = a.get_text(strip=True)
            brand = phone_name.split(" ")[0] if " " in phone_name else ""

        phones.append(
            PhoneListItem(brand=brand, phone_name=phone_name, slug=slug, image=image)
        )

    return phones


def parse_picture_urls(soup: BeautifulSoup) -> list[str]:
    """解析手机图片列表页面。"""
    urls: list[str] = []
    for img in soup.select("#pictures-list img"):
        src = img.get("src", "")
        if src:
            urls.append(str(src))
    return urls

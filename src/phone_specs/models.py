"""数据模型 — 用于类型标注和结构化返回值。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Brand:
    """手机品牌。"""

    brand_id: int
    brand_name: str
    brand_slug: str
    device_count: int


@dataclass
class PhoneListItem:
    """品牌手机列表中的条目。"""

    phone_name: str
    slug: str
    image: str = ""
    brand: str = ""


@dataclass
class PhoneListResult:
    """品牌手机列表查询结果（含分页）。"""

    title: str
    current_page: int
    last_page: int
    phones: list[PhoneListItem] = field(default_factory=list)


@dataclass
class SpecItem:
    """单个规格条目（如 "Technology": ["GSM / HSPA / LTE / 5G"]）。"""

    key: str
    val: list[str] = field(default_factory=list)


@dataclass
class SpecGroup:
    """规格分组（如 Network / Display / Battery）。"""

    title: str
    specs: list[SpecItem] = field(default_factory=list)


@dataclass
class QuickSpecs:
    """快速摘要信息。"""

    release_date: str = ""
    dimension: str = ""
    os: str = ""
    storage: str = ""
    display: str = ""
    camera: str = ""
    ram_chipset: str = ""
    battery: str = ""


@dataclass
class PhoneSpecs:
    """手机完整规格参数。"""

    brand: str
    phone_name: str
    thumbnail: str = ""
    phone_images: list[str] = field(default_factory=list)
    quick: QuickSpecs = field(default_factory=QuickSpecs)
    specifications: list[SpecGroup] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典（便于序列化）。"""
        return {
            "brand": self.brand,
            "phone_name": self.phone_name,
            "thumbnail": self.thumbnail,
            "phone_images": self.phone_images,
            "release_date": self.quick.release_date,
            "dimension": self.quick.dimension,
            "os": self.quick.os,
            "storage": self.quick.storage,
            "display": self.quick.display,
            "camera": self.quick.camera,
            "ram_chipset": self.quick.ram_chipset,
            "battery": self.quick.battery,
            "specifications": [
                {
                    "title": g.title,
                    "specs": [{"key": s.key, "val": s.val} for s in g.specs],
                }
                for g in self.specifications
            ],
        }

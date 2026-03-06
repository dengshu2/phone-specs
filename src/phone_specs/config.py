"""配置管理 — 爬虫和全局配置。"""

from __future__ import annotations

import random
from dataclasses import dataclass

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.2 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
]


@dataclass
class CrawlConfig:
    """爬虫配置。"""

    delay_min: float = 2.0
    delay_max: float = 5.0
    max_retries: int = 3
    batch_size: int = 50
    batch_pause: float = 30.0
    db_path: str = "phone_specs.db"
    fetch_images: bool = True
    update_threshold_days: int = 30

    def random_delay(self) -> float:
        """返回一个随机延时值（秒）。"""
        return random.uniform(self.delay_min, self.delay_max)

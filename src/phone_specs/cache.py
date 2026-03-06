"""内存缓存 — 带 TTL 的简单键值缓存。"""

from __future__ import annotations

import time
from typing import Any


class MemoryCache:
    """线程安全的带 TTL 内存缓存。

    Args:
        ttl: 缓存过期时间（秒），默认 600s（10 分钟）。
    """

    def __init__(self, ttl: int = 600) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期则返回 None。"""
        if key in self._store:
            data, ts = self._store[key]
            if time.time() - ts < self._ttl:
                return data
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """设置缓存值。"""
        self._store[key] = (value, time.time())

    def clear(self) -> None:
        """清空全部缓存。"""
        self._store.clear()

    @property
    def size(self) -> int:
        """当前缓存条目数量。"""
        return len(self._store)

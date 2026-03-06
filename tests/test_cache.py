"""cache 模块单元测试。"""

import time

from phone_specs.cache import MemoryCache


def test_set_and_get():
    cache = MemoryCache(ttl=60)
    cache.set("key1", {"data": 123})
    assert cache.get("key1") == {"data": 123}


def test_get_missing_key():
    cache = MemoryCache(ttl=60)
    assert cache.get("nonexistent") is None


def test_ttl_expiry():
    cache = MemoryCache(ttl=1)  # 1 秒过期
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    time.sleep(1.1)
    assert cache.get("key1") is None


def test_clear():
    cache = MemoryCache(ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.size == 2

    cache.clear()
    assert cache.size == 0
    assert cache.get("a") is None


def test_overwrite():
    cache = MemoryCache(ttl=60)
    cache.set("key1", "old")
    cache.set("key1", "new")
    assert cache.get("key1") == "new"

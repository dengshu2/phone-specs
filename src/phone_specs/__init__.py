"""
phone-specs: 手机型号基础信息查询工具

从 GSMArena 获取全球手机型号的详细规格参数，支持品牌浏览、型号搜索、参数查询。
"""

from phone_specs.client import PhoneSpecsClient

__version__ = "0.1.0"
__all__ = ["PhoneSpecsClient"]

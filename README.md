# 📱 phone-specs

手机型号基础信息查询工具 — 从 [GSMArena](https://www.gsmarena.com) 获取全球手机参数规格。

## 功能

- 🏷️ **品牌浏览** — 获取所有手机品牌及设备数量
- 📋 **型号列表** — 按品牌浏览手机列表，支持分页
- 🔍 **参数查询** — 获取手机详细规格参数（13 大类、50+ 字段）
- 🔎 **搜索** — 按关键词搜索手机型号
- ⚡ **内存缓存** — 自带 TTL 缓存，避免重复请求
- 🗄️ **数据库存储** — 爬取数据存入 SQLite，支持断点续爬
- 🔄 **增量更新** — 已爬取的手机自动跳过

## 快速开始

```bash
# 安装依赖
uv sync

# 查看帮助
uv run phone-specs --help

# 运行在线演示
uv run phone-specs demo

# 运行测试
uv run pytest
```

## 爬取数据

```bash
# 爬取某个品牌的全部手机数据到 SQLite
uv run phone-specs crawl --brand apple

# 全量爬取所有品牌（耗时较长）
uv run phone-specs crawl --full

# 自定义参数
uv run phone-specs crawl --brand xiaomi --db my_data.db --delay-min 3 --delay-max 6

# 查看数据库统计
uv run phone-specs stats
```

## 作为库使用

```python
from phone_specs import PhoneSpecsClient

with PhoneSpecsClient() as client:
    # 搜索手机
    results = client.search("Xiaomi 15")
    print(results[0].phone_name)  # "15"

    # 获取详细参数
    specs = client.get_phone_specs(results[0].slug)
    print(specs.quick.ram_chipset)  # "Snapdragon 8 Elite"
    print(specs.quick.battery)     # "5500"

    # 遍历完整规格
    for group in specs.specifications:
        print(f"\n[{group.title}]")
        for item in group.specs:
            print(f"  {item.key}: {', '.join(item.val)}")
```

## 项目结构

```
phone-specs/
├── pyproject.toml                  # 项目配置 (uv)
├── src/
│   └── phone_specs/
│       ├── __init__.py             # 包入口
│       ├── models.py               # 数据模型 (dataclass)
│       ├── cache.py                # 内存缓存
│       ├── parser.py               # HTML 解析器
│       ├── client.py               # HTTP 客户端 (高层 API)
│       ├── config.py               # 爬虫配置
│       ├── db.py                   # SQLite 数据库层
│       ├── crawler.py              # 爬虫调度器
│       └── cli.py                  # 命令行工具
└── tests/
    ├── test_cache.py               # 缓存测试
    └── test_models.py              # 模型测试
```

## 开发

```bash
# 安装开发依赖
uv sync --group dev

# 运行测试
uv run pytest

# 代码检查
uv run ruff check src/
```

## 许可证

ISC

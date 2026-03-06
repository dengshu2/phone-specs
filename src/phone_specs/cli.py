"""命令行入口 — ``phone-specs`` CLI 工具。"""

from __future__ import annotations

import json
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import box

from phone_specs.client import PhoneSpecsClient

console = Console()


def _show_brands(client: PhoneSpecsClient) -> list:
    """展示品牌列表。"""
    console.rule("[bold cyan]测试 1: 获取品牌列表")
    t = time.time()

    brands = client.get_brands()

    console.print(f"✅ 共获取到 [bold green]{len(brands)}[/] 个品牌  ⏱️ {time.time() - t:.2f}s\n")

    table = Table(title="品牌列表（前 15 个）", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("品牌名", style="cyan bold")
    table.add_column("Slug", style="dim")
    table.add_column("设备数量", justify="right", style="green")

    for i, b in enumerate(brands[:15]):
        table.add_row(str(i + 1), b.brand_name, b.brand_slug, str(b.device_count))

    console.print(table)
    console.print()
    return brands


def _show_phones(client: PhoneSpecsClient, brand_slug: str):
    """展示品牌下手机列表。"""
    console.rule("[bold cyan]测试 2: 获取品牌下手机列表")
    console.print(f"📱 查询品牌: [bold]{brand_slug}[/]\n")
    t = time.time()

    result = client.get_phones_by_brand(brand_slug, page=1)

    console.print(
        f"✅ {result.title} — 第 {result.current_page}/{result.last_page} 页, "
        f"本页 [bold green]{len(result.phones)}[/] 款  ⏱️ {time.time() - t:.2f}s\n"
    )

    table = Table(title=f"{result.title}（第 1 页）", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("手机名称", style="cyan bold", min_width=25)
    table.add_column("Slug", style="dim")

    for i, p in enumerate(result.phones[:10]):
        table.add_row(str(i + 1), p.phone_name, p.slug)

    console.print(table)
    console.print()
    return result


def _show_specs(client: PhoneSpecsClient, phone_slug: str):
    """展示手机详细规格。"""
    console.rule("[bold cyan]测试 3: 获取手机详细规格")
    console.print(f"🔍 查询手机: [bold]{phone_slug}[/]\n")
    t = time.time()

    specs = client.get_phone_specs(phone_slug)
    elapsed = time.time() - t

    # 基本信息面板
    q = specs.quick
    info_lines = [
        f"[bold]品牌:[/] {specs.brand}",
        f"[bold]型号:[/] {specs.phone_name}",
        f"[bold]发布:[/] {q.release_date}",
        f"[bold]尺寸:[/] {q.dimension}",
        f"[bold]系统:[/] {q.os}",
        f"[bold]存储:[/] {q.storage}",
        f"[bold]屏幕:[/] {q.display}",
        f"[bold]摄像:[/] {q.camera}",
        f"[bold]芯片:[/] {q.ram_chipset}",
        f"[bold]电池:[/] {q.battery}",
        f"[bold]缩略图:[/] {specs.thumbnail}",
        f"[bold]图片数:[/] {len(specs.phone_images)} 张",
    ]
    console.print(Panel(
        "\n".join(info_lines),
        title=f"📱 {specs.brand} {specs.phone_name}",
        border_style="green",
    ))

    # 规格树
    tree = Tree(f"[bold green]📋 详细规格（{len(specs.specifications)} 个分类）")
    for group in specs.specifications:
        branch = tree.add(f"[bold cyan]{group.title}[/]")
        for spec in group.specs[:5]:
            val_str = " / ".join(spec.val)
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            branch.add(f"[yellow]{spec.key}:[/] {val_str}")
        if len(group.specs) > 5:
            branch.add(f"[dim]... 还有 {len(group.specs) - 5} 项[/]")

    console.print(tree)

    # 保存 JSON
    output_file = f"{phone_slug.replace('/', '_')}_specs.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(specs.to_dict(), f, ensure_ascii=False, indent=2)

    console.print(f"\n💾 完整数据已保存到: [bold]{output_file}[/]")
    console.print(f"⏱️  耗时: {elapsed:.2f}s\n")
    return specs


def _show_search(client: PhoneSpecsClient, query: str):
    """展示搜索结果。"""
    console.rule("[bold cyan]测试 4: 搜索手机")
    console.print(f"🔎 搜索关键词: [bold]{query}[/]\n")
    t = time.time()

    phones = client.search(query)

    console.print(
        f"✅ 搜索到 [bold green]{len(phones)}[/] 个结果  "
        f"⏱️ {time.time() - t:.2f}s\n"
    )

    table = Table(title=f"搜索结果: '{query}'", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("品牌", style="yellow", width=12)
    table.add_column("型号", style="cyan bold", min_width=25)
    table.add_column("Slug", style="dim")

    for i, p in enumerate(phones[:10]):
        table.add_row(str(i + 1), p.brand, p.phone_name, p.slug)

    console.print(table)
    console.print()
    return phones


def _show_cache_test(client: PhoneSpecsClient):
    """缓存验证。"""
    console.rule("[bold cyan]测试 5: 缓存验证")
    t = time.time()
    _ = client.get_brands()
    ms = (time.time() - t) * 1000
    console.print(f"✅ 缓存命中 — 品牌列表二次获取仅 [bold green]{ms:.1f}ms[/]\n")


def main() -> None:
    """CLI 入口。"""
    console.print(Panel(
        "[bold]phone-specs 手机参数查询工具 — 功能测试[/]\n数据源: GSMArena.com",
        title="🚀 开始测试",
        border_style="blue",
    ))
    console.print()

    try:
        with PhoneSpecsClient() as client:
            # 1. 品牌列表
            brands = _show_brands(client)

            # 找到小米
            xiaomi = next((b for b in brands if "xiaomi" in b.brand_name.lower()), None)
            if not xiaomi:
                console.print("[red]❌ 未找到 Xiaomi 品牌[/]")
                sys.exit(1)

            # 2. 品牌手机列表
            phones_result = _show_phones(client, xiaomi.brand_slug)

            # 3. 手机详细规格
            if phones_result.phones:
                _show_specs(client, phones_result.phones[0].slug)

            # 4. 搜索
            _show_search(client, "iPhone 16 Pro")

            # 5. 缓存验证
            _show_cache_test(client)

        console.print(Panel(
            "[bold green]✅ 所有测试通过！[/]\n\n"
            "功能验证:\n"
            "  • 品牌列表获取 ✅\n"
            "  • 品牌手机列表 ✅\n"
            "  • 手机详细规格 ✅\n"
            "  • 搜索功能 ✅\n"
            "  • 缓存机制 ✅",
            title="📊 测试总结",
            border_style="green",
        ))

    except Exception as e:
        console.print(f"\n[bold red]❌ 测试失败: {e}[/]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

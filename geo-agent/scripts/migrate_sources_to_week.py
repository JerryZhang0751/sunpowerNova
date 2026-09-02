#!/usr/bin/env python3
"""把 data/sources/ 顶层 12 位 hex 名目录迁入 w3/（2026-09-02 L3 周目录隔离
一次性迁移的幂等复刻，stdlib-only）。

规则:
- 顶层目录名为 12 位十六进制（sha1 前缀）→ 移入 w3/<hex>；
  w3/<hex> 已存在则按文件并入（同名文件以 w3 现行为准、跳过迁移项并打印）。
- `w*` 周目录与非目录文件一律跳过。
- 幂等:重复运行零动作、exit 0。

用法:
    python3 scripts/migrate_sources_to_week.py [SOURCES_DIR] [--week N]
    SOURCES_DIR 缺省为 <repo>/data/sources。
"""
from __future__ import annotations
import argparse
import re
import shutil
import sys
from pathlib import Path

HEX12 = re.compile(r"^[0-9a-f]{12}$")


def migrate_dir(src: Path, dst: Path) -> list[str]:
    """把 src 目录并入 dst:逐文件 move;dst 同名文件已存在则保留现行为(跳过)。
    返回实际移动的文件名列表;src 变空后删除。"""
    moved = []
    for f in sorted(src.iterdir()):
        target = dst / f.name
        if target.exists():
            print(f"  skipped (dst 已存在,保留 w3 现行): {src.name}/{f.name}")
            continue
        dst.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(target))
        moved.append(f.name)
    if not any(src.iterdir()):
        src.rmdir()
    return moved


def migrate(sources: Path, week: int = 3) -> list[tuple[str, int]]:
    """迁移顶层 12-hex 目录进 w{week}/;返回 (hex名, 移动文件数) 清单。"""
    target_root = sources / f"w{week}"
    manifest = []
    for entry in sorted(sources.iterdir()):
        if not entry.is_dir() or not HEX12.match(entry.name):
            continue                     # w* 目录 / 文件 / 非 12-hex 名 → 跳过
        if (target_root / entry.name).is_dir():
            moved = migrate_dir(entry, target_root / entry.name)
        else:
            moved = sorted(f.name for f in entry.iterdir())
            shutil.move(str(entry), str(target_root / entry.name))
        manifest.append((entry.name, len(moved)))
    return manifest


def main() -> int:
    default = Path(__file__).resolve().parents[1] / "data" / "sources"
    ap = argparse.ArgumentParser(description="data/sources 顶层 12-hex 目录 → w3/ 幂等迁移")
    ap.add_argument("sources", nargs="?", type=Path, default=default,
                    help="sources 根目录(默认 <repo>/data/sources)")
    ap.add_argument("--week", type=int, default=3, help="目标周目录(默认 3)")
    a = ap.parse_args()
    if not a.sources.is_dir():
        print(f"sources 目录不存在: {a.sources}", file=sys.stderr)
        return 1
    manifest = migrate(a.sources, a.week)
    if not manifest:
        print("无可迁移项(已幂等,零动作)")
        return 0
    for name, n in manifest:
        print(f"migrated: {name} -> w{a.week}/{name} ({n} 个文件)")
    print(f"共迁移 {len(manifest)} 个目录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

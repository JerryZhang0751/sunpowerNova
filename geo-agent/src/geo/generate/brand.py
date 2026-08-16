from __future__ import annotations
import re
import yaml
from pathlib import Path

REQUIRED_KEYS = ("entity", "products", "faqs", "glossary", "banned")

class BrandError(Exception):
    pass

def load_brand(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise BrandError(f"brand.yaml 不存在: {path}；先运行 --bootstrap-brand")
    brand = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(brand.get("version"), int) or brand["version"] < 1:
        raise BrandError(f"brand.yaml version 非法: {brand.get('version')!r}")
    missing = [k for k in REQUIRED_KEYS if k not in brand]
    if missing:
        raise BrandError(f"brand.yaml 缺少顶层键: {missing}")
    return brand

def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s or "untitled"

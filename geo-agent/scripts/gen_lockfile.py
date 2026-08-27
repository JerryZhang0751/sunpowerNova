"""冻结当前环境为 geo-agent/requirements.lock。
用法: python3.12 scripts/gen_lockfile.py --path /tmp/pylibs312
环境须为刚跑过全量套件的绿环境(锁=该环境的确切版本集)。"""
from __future__ import annotations
import argparse
import importlib.metadata
import time
from pathlib import Path

SKIP = {"pip", "setuptools", "wheel", "pkg-resources"}

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/pylibs312", help="site-packages 风格的目标目录")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    pins = sorted(
        (f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions(path=[a.path])
         if d.metadata["Name"] and d.metadata["Name"].lower() not in SKIP),
        key=str.lower)
    out = Path(a.out) if a.out else Path(__file__).resolve().parents[1] / "requirements.lock"
    header = (f"# Frozen {time.strftime('%Y-%m-%d')} from {a.path}"
              f" (env that passed the full test suite)\n"
              f"# Regenerate: python3.12 scripts/gen_lockfile.py --path <env-dir>\n")
    out.write_text(header + "\n".join(pins) + "\n", encoding="utf-8")
    print(f"wrote {len(pins)} pins -> {out}")

if __name__ == "__main__":
    main()

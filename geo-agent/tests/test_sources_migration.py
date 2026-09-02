# tests/test_sources_migration.py
"""回归锁(2026-09-02 审核缺口 A6): data/sources 顶层 12-hex 目录 → w3/ 幂等迁移。
以子进程跑真脚本(scripts/migrate_sources_to_week.py,stdlib-only):
两遍收敛(顶层 hex 清零、并入 w3),第三遍清单+内容逐字节不变。"""
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sources_to_week.py"
HEX_A, HEX_B, HEX_C = "0123456789ab", "fedcba987654", "123abc456def"
HEX12 = re.compile(r"^[0-9a-f]{12}$")


def _mk_sources(tmp: Path) -> None:
    """3 个顶层 12-hex 目录(各含 meta.json+text.md)+ 1 个已存在的 w3/<hexA>
    (含现行 note.md,验证并入分支不覆盖 w3 现行文件)。"""
    for h in (HEX_A, HEX_B, HEX_C):
        d = tmp / h
        d.mkdir()
        (d / "meta.json").write_text(
            json.dumps({"url": f"https://example.com/{h}"}), encoding="utf-8")
        (d / "text.md").write_text(f"# text {h}\n", encoding="utf-8")
    merged = tmp / "w3" / HEX_A
    merged.mkdir(parents=True)
    (merged / "note.md").write_text("w3 现行留存\n", encoding="utf-8")


def _run(tmp: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), str(tmp)],
                          capture_output=True, text=True, timeout=60)


def _snapshot(tmp: Path) -> dict:
    return {
        "paths": sorted(p.relative_to(tmp).as_posix() for p in tmp.rglob("*")),
        "contents": {p.relative_to(tmp).as_posix(): p.read_bytes()
                     for p in tmp.rglob("*") if p.is_file()},
    }


def test_migration_moves_hex_dirs_into_w3_and_merges(tmp_path):
    _mk_sources(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    for h in (HEX_A, HEX_B, HEX_C):                     # 迁移清单打印可见
        assert h in r.stdout
    assert sorted(p.name for p in tmp_path.iterdir()) == ["w3"]      # 顶层 hex 清零
    a = tmp_path / "w3" / HEX_A
    assert sorted(p.name for p in a.iterdir()) == ["meta.json", "note.md", "text.md"]
    assert (a / "meta.json").read_text(encoding="utf-8") == \
        json.dumps({"url": f"https://example.com/{HEX_A}"})          # 并入不覆盖 w3 现行
    assert (a / "note.md").read_text(encoding="utf-8") == "w3 现行留存\n"
    assert (tmp_path / "w3" / HEX_B / "text.md").read_text(encoding="utf-8") == \
        f"# text {HEX_B}\n"
    assert (tmp_path / "w3" / HEX_C / "meta.json").exists()


def test_migration_is_idempotent(tmp_path):
    _mk_sources(tmp_path)
    assert _run(tmp_path).returncode == 0
    r2 = _run(tmp_path)
    assert r2.returncode == 0
    top_hex = [p.name for p in tmp_path.iterdir()
               if p.is_dir() and HEX12.match(p.name)]
    assert top_hex == [], "第二遍后顶层 12-hex 目录必须清零"
    snap = _snapshot(tmp_path)
    r3 = _run(tmp_path)
    assert r3.returncode == 0
    assert "migrated" not in r3.stdout, "幂等重跑必须零动作"
    assert _snapshot(tmp_path) == snap, "第三遍后目录清单与文件内容必须逐字节不变"

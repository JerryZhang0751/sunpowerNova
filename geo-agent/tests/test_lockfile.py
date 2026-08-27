import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _norm(name: str) -> str:
    return name.lower().replace("_", "-").strip()

def _parse_req(req: str) -> str:
    for sep in (">=", "==", "~=", ">", "<", "!="):
        if sep in req:
            return _norm(req.split(sep)[0])
    return _norm(req)

def test_lockfile_covers_all_pyproject_direct_deps():
    proj = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wanted = [_parse_req(d) for d in proj["project"]["dependencies"]]
    wanted += [_parse_req(d) for d in proj["project"]["optional-dependencies"]["dev"]]
    locked = set()
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"lock 行必须精确锁版本: {line!r}"
        locked.add(_norm(line.split("==")[0]))
    missing = [w for w in wanted if w not in locked]
    assert not missing, f"pyproject 依赖未入 lock —— 重跑 scripts/gen_lockfile.py: {missing}"

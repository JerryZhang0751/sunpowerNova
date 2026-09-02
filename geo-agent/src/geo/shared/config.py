from __future__ import annotations
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = Path(__file__).resolve().parents[3]   # geo-agent/

# 2026-09-02 backlog §3: 模型名单一事实源(此前 12 处硬编码散落 collect/research/generate/fetch)。
# api_code = 各 API 请求体里的 model 值; display = 报告展示名。
MODELS: dict[str, dict] = {
    "qwen":   {"api_code": "qwen3.7-plus",               "display": "Qwen"},
    "doubao": {"api_code": "doubao-seed-2-1-pro-260628", "display": "Doubao"},
    "zhipu":  {"api_code": "glm-5.2",                    "display": "Zhipu"},
    "kimi":   {"api_code": "kimi-k3",                    "display": "Kimi"},
}

class RunSpec(BaseModel):
    week: int = 1
    mode: str = "audit"
    scope: str = "core"
    runs: int = 1
    rule_version: str = "geo-seo-v2"
    augment_citation_prompt: bool = False
    providers: list[str] = Field(default_factory=lambda: ["qwen", "doubao", "zhipu"])

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO / ".env", extra="ignore")
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://ws-sbm7h4bsls91dmh7.cn-beijing.maas.aliyuncs.com/api/v1"
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    bigmodel_api_key: str = ""
    bigmodel_base_url: str = "https://open.bigmodel.cn/api/anthropic"
    moonshot_api_key: str = ""
    moonshot_base_url: str = "https://api.moonshot.cn/v1"
    gsc_key_file: str = ""
    run_path: Path = REPO / "run.yaml"
    targets_path: Path = REPO / "targets.yaml"

    # mtime 键控缓存(2026-09-02 backlog §3): 改写文件后自动失效重读。
    # review fix(2026-09-02): 键升 (st_mtime_ns, st_size) 消同刻度重写窗口
    # (运行时写入方存在: keeper.iterate / do_rollback / graph --next-week)。
    # 契约: 返回对象为进程内共享实例，调用方不得原地修改。
    _run_cache: tuple[tuple[int, int], RunSpec] | None = PrivateAttr(default=None)
    _targets_cache: tuple[tuple[int, int], dict] | None = PrivateAttr(default=None)

    @property
    def run(self) -> RunSpec:
        st = self.run_path.stat()
        key = (st.st_mtime_ns, st.st_size)
        if self._run_cache and self._run_cache[0] == key:
            return self._run_cache[1]
        spec = RunSpec(**yaml.safe_load(self.run_path.read_text(encoding="utf-8")))
        self._run_cache = (key, spec)
        return spec

    @property
    def targets(self) -> dict:
        st = self.targets_path.stat()
        key = (st.st_mtime_ns, st.st_size)
        if self._targets_cache and self._targets_cache[0] == key:
            return self._targets_cache[1]
        t = yaml.safe_load(self.targets_path.read_text(encoding="utf-8"))
        self._targets_cache = (key, t)
        return t

    @property
    def proxy(self):
        return self.targets.get("site", {}).get("proxy")

settings = Settings()

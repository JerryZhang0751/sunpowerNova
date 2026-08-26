from __future__ import annotations
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = Path(__file__).resolve().parents[3]   # geo-agent/

class RunSpec(BaseModel):
    week: int = 1
    mode: str = "audit"
    scope: str = "core"
    runs: int = 1
    rule_version: str = "geo-seo-v2"
    cost_budget_yuan: float = 100.0
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

    @property
    def run(self) -> RunSpec:
        return RunSpec(**yaml.safe_load(self.run_path.read_text(encoding="utf-8")))

    @property
    def targets(self) -> dict:
        return yaml.safe_load(self.targets_path.read_text(encoding="utf-8"))

    @property
    def proxy(self):
        return self.targets.get("site", {}).get("proxy")

settings = Settings()

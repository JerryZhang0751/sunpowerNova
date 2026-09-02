# src/geo/shared/kimi_client.py
"""Kimi K3 客户端单一实现(2026-09-02 §4:三份 _kimi_chat 合一,超时/重试参数化)。
各层语义保留: research synthesize 120s / web_search 180s(retries 由调用方定) /
generate 300s+max_retries=0 / brand 120s / meta_llm 120s。
模型名以 MODELS 注册表为准(api_code 见 geo.shared.config),请求强制 temperature=1。"""
from __future__ import annotations
from geo.shared.config import settings, MODELS

def make_kimi_client(*, timeout: float, max_retries: int = 2):
    from openai import OpenAI
    return OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url,
                  timeout=timeout, max_retries=max_retries)

def kimi_chat(messages: list[dict], *, timeout: float = 120.0, max_retries: int = 2,
              tools: list | None = None) -> str:
    c = make_kimi_client(timeout=timeout, max_retries=max_retries)
    kwargs = dict(model=MODELS["kimi"]["api_code"], messages=messages, temperature=1)
    if tools:
        kwargs["tools"] = tools
    else:
        kwargs["response_format"] = {"type": "json_object"}
    r = c.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""

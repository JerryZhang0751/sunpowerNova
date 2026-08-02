#!/usr/bin/env python3
"""
M0 冒烟测试 —— 验证采集层 3 模型（Qwen/豆包/智谱）原生联网搜索 + 分析层 Kimi 连通性。

验证目标（PRD §13 M0；DeepSeek 已砍）：
  1. 4 个 model id 真实有效（Qwen qwen3.7-plus / 豆包 doubao-seed-2-1-pro / 智谱 glm-5.2 / Kimi kimi-k3）
  2. 原生联网搜索触发 + 返回真实 URL（各家机制不同，见下）：
     - Qwen  : 阿里云百炼 DashScope 原生 MultiModalConversation（qwen3.7-plus 为多模态模型，
               必须用 multimodal-generation 端点 + 流式），enable_search=True +
               search_options={search_strategy:agent, enable_source:True}
               → output.search_info.search_results 返回真实 URL（enable_source 仅 DashScope 协议支持；
                 OpenAI 兼容/Generation 文本端点拿不到 URL，且 Generation 对该模型会 400 url error）
     - 豆包  : Ark 【Responses API】POST /api/v3/responses，内置工具 tools=[{type:web_search}]
               （chat/completions 只认 function tools，传 web_search 会报 MissingParameter: tools.function）
     - 智谱  : BigModel Claude/Anthropic 兼容端点 /api/anthropic/v1/messages，
               tools=[{type:web_search_20250305, name:web_search}]（Anthropic 服务端工具，智谱映射到 web_search_prime）
  3. 抓取 L2 search_results 字段路径（喂 Plan 1 l2_parser）
  4. Kimi 仅连通性（分析层，不搜索）

用法：
  cd geo-agent
  pip install dashscope openai requests python-dotenv     # 若未装
  python m0_smoke.py

输出：控制台逐模型报告 + m0_report.json（字段路径 + 原始响应摘录，供 l2_parser 参考）
"""
import os
import re
import json
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("缺少依赖：pip install python-dotenv")
    sys.exit(2)

load_dotenv(Path(__file__).parent / ".env")

import requests
from openai import OpenAI, APIStatusError

# 用 prompts.csv 的 C01（品类搜索，必触发联网；GEO 相关；要求带 URL 以便核验真联网）
PROMPT = ("What is the best home solar panel and battery storage system in 2026? "
          "Name specific brands/products and cite recent sources with URLs.")

DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "")
# 阿里云百炼专属工作区 DashScope 原生端点（/api/v1；非 compatible-mode）
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://ws-sbm7h4bsls91dmh7.cn-beijing.maas.aliyuncs.com/api/v1").rstrip("/")
ARK_KEY = os.getenv("ARK_API_KEY", "")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
BIGMODEL_KEY = os.getenv("BIGMODEL_API_KEY", "")
BIGMODEL_BASE_URL = os.getenv("BIGMODEL_BASE_URL", "https://open.bigmodel.cn/api/anthropic").rstrip("/")
MOONSHOT_KEY = os.getenv("MOONSHOT_API_KEY", "")

report = {}


def _snippet(text, n=240):
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def _harvest_urls(obj, found):
    """递归收集响应里所有 http(s) URL —— 用于核验是否真联网（命中外部 URL=检索发生）。"""
    if isinstance(obj, str):
        for m in re.findall(r"https?://[^\s\"'<>)\]]+", obj):
            found.add(m.split("?")[0].rstrip(".,"))
    elif isinstance(obj, dict):
        for v in obj.values():
            _harvest_urls(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _harvest_urls(v, found)


def _mm_text(content):
    """从多模态 message.content（str / list / 嵌套 [{'text':...}] / [['text']]）抽取所有文本片段。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(item, list):
                parts.append(_mm_text(item))
        return "".join(parts)
    return ""


def probe_qwen(label, model):
    """Qwen via 阿里云百炼 DashScope 原生 MultiModalConversation + enable_search + enable_source。
    qwen3.7-plus 为多模态模型：必须用 MultiModalConversation（multimodal-generation 端点）+ 流式；
    search_strategy=agent；enable_source=True 才在 output.search_info.search_results 返回真实 URL。"""
    import dashscope
    from dashscope import MultiModalConversation
    t0 = time.time()
    dashscope.base_http_api_url = DASHSCOPE_BASE_URL  # 专属工作区原生 /api/v1
    row = {"channel": "DashScope MultiModal (enable_source)", "model": model, "base_url": DASHSCOPE_BASE_URL}
    try:
        if not DASHSCOPE_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY 为空")
        stream = MultiModalConversation.call(
            api_key=DASHSCOPE_KEY,
            model=model,
            messages=[{"role": "user", "content": [{"text": PROMPT}]}],
            enable_search=True,
            search_options={"search_strategy": "agent", "enable_source": True},
            stream=True,
            incremental_output=True,
        )
        search_results = []
        answer_parts = []
        usage = {}
        for r in stream:
            out = getattr(r, "output", None)
            odict = out if isinstance(out, dict) else {}
            si = odict.get("search_info") or {}
            sr = si.get("search_results") or []
            if sr and not search_results:
                search_results = sr
            ch = (odict.get("choices") or [{}])[0]
            msg = ch.get("message", {}) if isinstance(ch, dict) else {}
            answer_parts.append(_mm_text(msg.get("content")))
            u = getattr(r, "usage", None)
            if isinstance(u, dict) and u:
                usage = u
        row["elapsed_s"] = round(time.time() - t0, 1)
        row["http_status"] = 200
        answer = "".join(answer_parts)
        urls = [w.get("url") for w in search_results if isinstance(w, dict) and w.get("url")]
        row["search_count"] = len(search_results)
        row["search_urls"] = urls[:8]
        row["search_field_paths"] = ["output.search_info.search_results"] if search_results else []
        row["answer_snippet"] = _snippet(answer)
        row["usage"] = usage
        row["search_triggered"] = bool(urls)
        row["status"] = "OK"
    except Exception as e:
        row["elapsed_s"] = round(time.time() - t0, 1)
        row["status"] = f"FAIL: {type(e).__name__}: {str(e)[:300]}"
    report[label] = row


def probe_ark_responses(label, model):
    """豆包 via Ark Responses API (POST /api/v3/responses) + 内置 web_search 工具。
    doc: tools=[{type:web_search}] 启用联网；body 用 input；响应 output[] 含
         type=message(答案 content[].text) 与 type=web_search_call(检索动作/结果)。"""
    t0 = time.time()
    url = ARK_BASE_URL + "/responses"
    row = {"channel": "Ark Responses API", "model": model, "base_url": url}
    body = {
        "model": model,
        "input": [{"role": "user", "content": PROMPT}],
        "tools": [{"type": "web_search"}],
        "stream": False,
    }
    try:
        if not ARK_KEY:
            raise RuntimeError("ARK_API_KEY 为空")
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
            json=body, timeout=300,  # 联网搜索多轮(reasoning→search→...→message)较慢，实测≈100s
        )
        row["elapsed_s"] = round(time.time() - t0, 1)
        row["http_status"] = r.status_code
        try:
            d = r.json()
        except Exception:
            d = {"_raw": r.text[:600]}

        if r.status_code != 200:
            row["status"] = f"FAIL HTTP {r.status_code}: {json.dumps(d, ensure_ascii=False)[:500]}"
            report[label] = row
            return

        out = d.get("output") or []
        otypes = [o.get("type") for o in out if isinstance(o, dict)]
        answer = ""
        search_paths = []
        for o in out:
            if not isinstance(o, dict):
                continue
            t = o.get("type")
            if t == "message":
                for c in (o.get("content") or []):
                    if isinstance(c, dict):
                        answer += c.get("text", "") or c.get("output_text", "") or ""
            if t and "search" in str(t).lower():
                search_paths.append(f"output[].type={t}")
        top_search = [k for k in d.keys() if "search" in k.lower()]
        search_paths += [f"top.{k}" for k in top_search]
        urls = set()
        _harvest_urls(out, urls)
        row["output_types"] = otypes
        row["top_keys"] = list(d.keys())
        row["answer_snippet"] = _snippet(answer)
        row["search_urls"] = sorted(urls)[:8]
        row["search_field_paths"] = search_paths
        row["search_triggered"] = bool(search_paths) or bool(urls)
        row["status"] = "OK"
        row["_raw_excerpt"] = json.dumps(d, ensure_ascii=False)[:800]
    except Exception as e:
        row["status"] = f"FAIL: {type(e).__name__}: {e}"
    report[label] = row


def probe_zhipu_anthropic(label, model):
    """智谱 via BigModel Claude/Anthropic 兼容端点 (POST /api/anthropic/v1/messages) + web_search 服务端工具。
    model glm-5.2；header x-api-key + anthropic-version；tools=[{type:web_search_20250305, name:web_search, max_uses:5}]；
    响应 content[] 含 type=text(答案)/server_tool_use(检索)/tool_result(结果)。"""
    t0 = time.time()
    url = BIGMODEL_BASE_URL + "/v1/messages"
    row = {"channel": "智谱 Anthropic 兼容", "model": model, "base_url": url}
    body = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": PROMPT}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
    }
    try:
        if not BIGMODEL_KEY:
            raise RuntimeError("BIGMODEL_API_KEY 为空")
        r = requests.post(
            url,
            headers={"x-api-key": BIGMODEL_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json=body, timeout=180,
        )
        row["elapsed_s"] = round(time.time() - t0, 1)
        row["http_status"] = r.status_code
        try:
            d = r.json()
        except Exception:
            d = {"_raw": r.text[:600]}
        if r.status_code != 200:
            row["status"] = f"FAIL HTTP {r.status_code}: {json.dumps(d, ensure_ascii=False)[:500]}"
            report[label] = row
            return
        content = d.get("content") or []
        ctypes = [c.get("type") for c in content if isinstance(c, dict)]
        answer = ""
        search_paths = []
        tool_result_errors = []
        for c in content:
            if not isinstance(c, dict):
                continue
            t = c.get("type")
            if t == "text":
                answer += c.get("text", "") or ""
            if t == "server_tool_use":
                search_paths.append(f"content[].server_tool_use[{c.get('name')}]")
            if t == "tool_result":
                search_paths.append("content[].tool_result")
                tc = c.get("content")
                if isinstance(tc, str) and ("error" in tc.lower() or "1301" in tc or "MCP error" in tc):
                    tool_result_errors.append(tc[:140])
        urls = set()
        _harvest_urls(content, urls)
        row["content_types"] = ctypes
        row["stop_reason"] = d.get("stop_reason")
        row["answer_snippet"] = _snippet(answer)
        row["search_urls"] = sorted(urls)[:8]
        row["search_field_paths"] = search_paths
        row["search_triggered"] = bool(search_paths) or bool(urls)
        if tool_result_errors:
            row["tool_result_errors"] = tool_result_errors
        row["status"] = "OK"
        row["_raw_excerpt"] = json.dumps(d, ensure_ascii=False)[:800]
    except Exception as e:
        row["status"] = f"FAIL: {type(e).__name__}: {e}"
    report[label] = row


def probe_openai_compat(label, model, base_url, api_key):
    """Kimi(分析层) via OpenAI 兼容 chat/completions —— 仅连通性。"""
    t0 = time.time()
    row = {"channel": "OpenAI 兼容", "model": model, "base_url": base_url}
    try:
        if not api_key:
            raise RuntimeError("API key 为空")
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)  # Kimi 偶发较慢，实测≈50s
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": PROMPT}],
        )
        row["elapsed_s"] = round(time.time() - t0, 1)
        d = resp.model_dump()
        choices = d.get("choices") or []
        answer = choices[0].get("message", {}).get("content", "") if choices else ""
        row["answer_snippet"] = _snippet(answer)
        row["search_triggered"] = "n/a(分析层)"
        row["status"] = "OK"
    except APIStatusError as e:
        body = ""
        try:
            body = e.response.text[:400]
        except Exception:
            body = str(e)[:400]
        row["status"] = f"FAIL HTTP {e.status_code}: {body}"
    except Exception as e:
        row["status"] = f"FAIL: {type(e).__name__}: {e}"
    report[label] = row


def main():
    print(f"\n=== M0 冒烟测试 ===\nPrompt: {PROMPT}\n")

    # Qwen（DashScope 原生 MultiModalConversation + enable_source）
    probe_qwen("Qwen", "qwen3.7-plus")

    # 豆包（Ark Responses API + 内置 web_search）
    probe_ark_responses("豆包", "doubao-seed-2-1-pro-260628")

    # 智谱（BigModel Anthropic 兼容 + web_search 服务端工具）
    probe_zhipu_anthropic("智谱", "glm-5.2")

    # Kimi（分析层，仅连通性）
    probe_openai_compat("Kimi(分析层)", "kimi-k3", "https://api.moonshot.cn/v1", MOONSHOT_KEY)

    # 打印报告
    print("\n=== M0 结果 ===")
    for label, r in report.items():
        ok = r["status"] == "OK"
        icon = "✅" if ok else "❌"
        print(f"\n{icon} {label}  [{r.get('channel')}]  model={r.get('model')}")
        print(f"   状态: {r['status']}  耗时: {r.get('elapsed_s', '?')}s")
        if r.get("base_url"):
            print(f"   base_url: {r['base_url']}")
        if ok:
            st = r.get("search_triggered")
            if st is True:
                srch = "✅ 触发"
            elif st == "n/a(分析层)":
                srch = "—（分析层，无需）"
            else:
                srch = "❌ 未触发/未找到字段"
            print(f"   联网搜索: {srch}")
            if r.get("search_count") is not None:
                print(f"   搜索来源数: {r['search_count']}")
            if r.get("search_field_paths"):
                print(f"   搜索字段路径: {r['search_field_paths']}  ← 喂 l2_parser")
            if r.get("search_urls"):
                print(f"   命中外部URL: {r['search_urls']}")
            if r.get("output_types"):
                print(f"   output types: {r['output_types']}")
            if r.get("content_types"):
                print(f"   content types: {r['content_types']}")
            if r.get("usage"):
                u = r["usage"]
                pt = u.get("input_tokens") or u.get("prompt_tokens")
                print(f"   usage: prompt_tokens={pt}")
            if r.get("tool_result_errors"):
                print(f"   ⚠️ 检索结果错误: {r['tool_result_errors']}")
            print(f"   答案片段: {r.get('answer_snippet', '')}")
            if r.get("_raw_excerpt"):
                print(f"   原始响应(截断): {r['_raw_excerpt']}")

    ok_count = sum(1 for r in report.values() if r["status"] == "OK")
    search_ok = sum(1 for r in report.values() if r.get("search_triggered") is True)
    print(f"\n=== 汇总: 连通 {ok_count}/{len(report)} | 联网搜索 {search_ok}/3(采集层) ===")

    out = Path(__file__).parent / "m0_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"详细报告: {out}")

    return 0 if ok_count == len(report) else 1


if __name__ == "__main__":
    sys.exit(main())

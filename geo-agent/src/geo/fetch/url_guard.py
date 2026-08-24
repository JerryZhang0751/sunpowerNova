# src/geo/fetch/url_guard.py
"""SSRF 防线(2026-08-24 审查#3): 模型返回的 URL 不得触达内网。

被抓取的 URL 来自 LLM 输出(不可信输入): 直接抓取+跟随重定向会把请求打进
回环/私网/云元数据端点,抓到的正文还会发往外部 Kimi 服务(内网数据外发)。
本模块在发起请求前验证:
- 协议白名单 http/https;
- 主机为 IP 字面量或 DNS 解析结果必须是公网地址(拒绝回环/私有/链路本地/
  保留/组播/未指定/CGNAT 100.64/10 及 IPv4-mapped 内网)。
已知残余: 验证时解析与实际连接各解析一次 DNS,理论存在 rebinding 窗口;
对"防模型注入内网抓取"的威胁模型足够,收窄到 transport 级 pin 留待有真实
需求时再做。
"""
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse

__all__ = ["UnsafeURLError", "assert_safe_url", "MAX_REDIRECTS"]

MAX_REDIRECTS = 5

_ALLOWED_SCHEMES = {"http", "https"}
_CGNAT = ipaddress.ip_network("100.64.0.0/10")   # 共享地址空间(运营商级 NAT/内网)


class UnsafeURLError(ValueError):
    """URL 指向非白名单协议/内网/云元数据,或解析失败——拒绝抓取。"""


def _is_forbidden(ip: ipaddress._BaseAddress) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _is_forbidden(mapped)
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified):
        return True
    return ip.version == 4 and ip in _CGNAT


def _resolve_ips(host: str) -> list[ipaddress._BaseAddress]:
    """解析主机名的全部地址;解析失败视为不安全(拒绝而非放行)。"""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise UnsafeURLError(f"DNS 解析失败: {host!r} ({e})") from e
    ips = []
    for info in infos:
        try:
            ips.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not ips:
        raise UnsafeURLError(f"DNS 无可用地址: {host!r}")
    return ips


def assert_safe_url(url: str, *, resolve: bool = True) -> None:
    """断言 URL 可安全外抓,不安全抛 UnsafeURLError。

    resolve=False 只做协议/主机/IP 字面量检查(离线可测);生产路径必须
    默认 resolve=True。
    """
    u = urlparse(url)
    if u.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"非白名单协议: {u.scheme!r} ({url!r})")
    host = u.hostname
    if not host:
        raise UnsafeURLError(f"URL 缺少主机: {url!r}")
    try:
        ips: list = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve:
            return
        ips = _resolve_ips(host)
    for ip in ips:
        if _is_forbidden(ip):
            raise UnsafeURLError(f"内网/保留地址被拒: {host} -> {ip} ({url!r})")

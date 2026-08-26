# src/geo/fetch/url_guard.py
"""SSRF 防线(2026-08-24 审查#3): 模型返回的 URL 不得触达内网。

被抓取的 URL 来自 LLM 输出(不可信输入): 直接抓取+跟随重定向会把请求打进
回环/私网/云元数据端点,抓到的正文还会发往外部 Kimi 服务(内网数据外发)。
本模块在发起请求前验证:
- 协议白名单 http/https;
- 主机为 IP 字面量或 DNS 解析结果必须是公网地址(拒绝回环/私有/链路本地/
  保留/组播/未指定/CGNAT 100.64/10 及 IPv4-mapped 内网)。

2026-08-25 二次审查#3: 校验解析与实际连接各做一次 DNS 存在 rebinding 窗口
(校验时公网、连接时内网)。收口 = resolve_safe_ips 把已验证的公网地址交还
fetch 端,fetch 以该 IP 为连接目标(URL 主机改写,Host 头/SNI 保留原主机),
校验与连接共用同一次解析结果;代理路径下发给代理的 CONNECT 目标也是 IP,
代理侧不再自行解析域名。
"""
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse

__all__ = ["UnsafeURLError", "assert_safe_url", "resolve_safe_ips", "MAX_REDIRECTS"]

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


def resolve_safe_ips(url: str) -> list[ipaddress._BaseAddress]:
    """校验 URL 并返回其主机的全部已验公网地址(供 fetch 端 pin 连接)。

    判定与 assert_safe_url(resolve=True) 完全一致,但把解析结果交还调用方,
    消除"校验一次 DNS、连接再解析一次"的 rebinding 窗口。全部地址都必须是
    公网地址,任一不安全即抛 UnsafeURLError。
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
        ips = _resolve_ips(host)
    for ip in ips:
        if _is_forbidden(ip):
            raise UnsafeURLError(f"内网/保留地址被拒: {host} -> {ip} ({url!r})")
    return ips


def assert_safe_url(url: str, *, resolve: bool = True) -> None:
    """断言 URL 可安全外抓,不安全抛 UnsafeURLError。

    resolve=False 只做协议/主机/IP 字面量检查(离线可测);生产路径必须
    默认 resolve=True,或直接用 resolve_safe_ips 拿 pin 目标。
    """
    if not resolve:
        u = urlparse(url)
        if u.scheme.lower() not in _ALLOWED_SCHEMES:
            raise UnsafeURLError(f"非白名单协议: {u.scheme!r} ({url!r})")
        host = u.hostname
        if not host:
            raise UnsafeURLError(f"URL 缺少主机: {url!r}")
        try:
            ips: list = [ipaddress.ip_address(host)]
        except ValueError:
            return                                # 域名留给 resolve=True 判定
        for ip in ips:
            if _is_forbidden(ip):
                raise UnsafeURLError(f"内网/保留地址被拒: {host} -> {ip} ({url!r})")
        return
    resolve_safe_ips(url)

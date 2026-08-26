# tests/test_url_guard.py
"""SSRF 防线测试(2026-08-24 审查#3): 模型返回的 URL 不得触达内网/云元数据,
重定向每一跳都必须重新验证;拦截必须抛出且不落盘缓存。"""
import ipaddress
import pytest
from unittest.mock import patch
from geo.fetch.url_guard import assert_safe_url, UnsafeURLError, MAX_REDIRECTS


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",            # 非 http(s) 协议
    "ftp://example.com/a",
    "gopher://example.com",
    "http://127.0.0.1/admin",        # 回环
    "https://10.0.0.5/",             # RFC1918
    "http://192.168.1.1/router",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/",   # 云元数据
    "http://100.64.1.1/",            # CGNAT 共享段
    "http://0.0.0.0/",
    "http://[::1]/",                 # IPv6 回环
    "http://[fe80::1]/",             # 链路本地
    "http://[fc00::1]/",             # ULA 私有
    "http://[::ffff:127.0.0.1]/",    # IPv4-mapped 回环
    "http:///no-host",               # 无主机
    "://no-scheme",
])
def test_rejects_unsafe_urls_without_dns(url):
    """协议/主机/IP 字面量层面即可判死的,不允许依赖 DNS(离线可测)。"""
    with pytest.raises(UnsafeURLError):
        assert_safe_url(url, resolve=False)


def test_accepts_public_ip_literal_without_dns():
    assert_safe_url("https://93.184.216.34/", resolve=False) is None


def test_rejects_localhost_via_resolution():
    """localhost 非字面量,必须走解析;解析到回环 → 拒绝。"""
    with patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("127.0.0.1")]):
        with pytest.raises(UnsafeURLError):
            assert_safe_url("http://localhost/admin")


def test_rejects_domain_resolving_to_private():
    """外看公网域名、DNS 指向私网(经典 SSRF)→ 拒绝。"""
    with patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34"),
                             ipaddress.ip_address("10.1.2.3")]):
        with pytest.raises(UnsafeURLError):
            assert_safe_url("https://rebind.example.com/a")


def test_accepts_domain_resolving_to_public():
    with patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34")]):
        assert_safe_url("https://example.com/") is None


def test_dns_failure_is_rejected():
    import socket
    with patch("geo.fetch.url_guard.socket.getaddrinfo", side_effect=socket.gaierror("nx")):
        with pytest.raises(UnsafeURLError):
            assert_safe_url("https://nonexistent.invalid/")


def test_redirect_cap_constant():
    assert 1 <= MAX_REDIRECTS <= 10


# ---- Fix(2026-08-25 二次审查#3): 校验与连接共用一次 DNS,关闭 rebinding 窗口 ----

from geo.fetch.url_guard import resolve_safe_ips

def test_resolve_safe_ips_returns_validated_public_ips():
    """域名解析: 返回全部已验公网地址,供 fetch 端 pin 连接。"""
    with patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34")]):
        ips = resolve_safe_ips("https://rebind.example.com/a")
    assert [str(i) for i in ips] == ["93.184.216.34"]

def test_resolve_safe_ips_ip_literal_needs_no_dns():
    ips = resolve_safe_ips("https://93.184.216.34/", )
    assert str(ips[0]) == "93.184.216.34"

def test_resolve_safe_ips_rejects_mixed_private():
    with patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34"),
                             ipaddress.ip_address("10.1.2.3")]):
        with pytest.raises(UnsafeURLError):
            resolve_safe_ips("https://rebind.example.com/a")

def test_resolve_safe_ips_checks_scheme_and_host():
    with pytest.raises(UnsafeURLError):
        resolve_safe_ips("file:///etc/passwd")
    with pytest.raises(UnsafeURLError):
        resolve_safe_ips("http:///no-host")

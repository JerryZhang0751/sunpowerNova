# tests/test_kimi_client.py
# T4(2026-09-02 backlog): shared/kimi_client 合一单测——离线(monkeypatch make_kimi_client,不触网)。
# 契约: 无 tools → 自动带 response_format=json_object;有 tools → 不带 response_format;
# kimi-k3 强制 temperature=1(=0 报 400)。

def _fake_kimi(monkeypatch):
    import geo.shared.kimi_client as K
    created = {}

    class _Msg:
        content = "{\"ok\":1}"

    class _Choice:
        message = _Msg()

    class FakeResp:
        choices = [_Choice()]

    def fake_create(**kwargs):
        created.update(kwargs)
        return FakeResp()

    class FakeCompletions:
        create = staticmethod(fake_create)

    class FakeClient:
        chat = type("C", (), {"completions": FakeCompletions})()

    monkeypatch.setattr(K, "make_kimi_client", lambda **kw: FakeClient())
    return K, created


def test_kimi_chat_no_tools_sets_json_format(monkeypatch):
    K, created = _fake_kimi(monkeypatch)
    assert K.kimi_chat([{"role": "user", "content": "x"}]) == "{\"ok\":1}"
    assert created["response_format"] == {"type": "json_object"}
    assert "tools" not in created and created["temperature"] == 1


def test_kimi_chat_with_tools_no_json_format(monkeypatch):
    K, created = _fake_kimi(monkeypatch)
    tools = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    assert K.kimi_chat([{"role": "user", "content": "x"}], tools=tools) == "{\"ok\":1}"
    assert created["tools"] == tools
    assert "response_format" not in created
    assert created["temperature"] == 1

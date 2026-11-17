"""core/web_api.py：面板接口的读写、字段白名单与只读门。"""
from __future__ import annotations

import pytest

from astrbot_plugin_dynamics_world.world.core import web_api as web_api_module
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry, new_uid
from astrbot_plugin_dynamics_world.world.core.web_api import WorldBookWebAPI

from conftest import run


@pytest.fixture
def api(make_plugin):
    plugin = make_plugin()
    return WorldBookWebAPI(plugin), plugin


def _stub_body(monkeypatch, payload):
    async def fake_body():
        return payload

    monkeypatch.setattr(web_api_module, "_body", fake_body)


class FakeRequest:
    """Mimics the request surface AstrBot exposes to plugin handlers.

    AstrBot's PluginRequest carries query values on "query"; the proxy raises
    AttributeError for anything it does not define, so unknown attributes must
    stay unknown here too.
    """

    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)

    def __getattr__(self, name):  # only reached when normal lookup fails
        raise AttributeError(name)


def _stub_request(monkeypatch, **attrs):
    monkeypatch.setattr(web_api_module, "request", FakeRequest(**attrs))


def _data(response):
    """Unwrap the JSON envelope regardless of which response shim is active."""
    if isinstance(response, tuple):
        response = response[0]
    if isinstance(response, dict):
        return response
    body = getattr(response, "body", None)
    if body is not None:
        import json

        return json.loads(body)
    return response


def test_register_publishes_every_route(make_plugin):
    plugin = make_plugin()
    calls = []

    class RecordingContext:
        def register_web_api(self, route, handler, methods, desc):
            calls.append((route, tuple(methods), desc))

    plugin.context = RecordingContext()
    plugin.web.register()

    published = {route for route, _methods, _desc in calls}
    assert published == {
        "/astrbot_plugin_dynamics_world/overview",
        "/astrbot_plugin_dynamics_world/book",
        "/astrbot_plugin_dynamics_world/entry",
        "/astrbot_plugin_dynamics_world/card",
        "/astrbot_plugin_dynamics_world/session",
        "/astrbot_plugin_dynamics_world/preview",
        "/astrbot_plugin_dynamics_world/import",
    }
    assert plugin.web.registered is True


def test_initialize_registers_web_api_and_honours_seed_switches(make_plugin):
    plugin = make_plugin(
        {"seeding": {"seed_worldbook": False, "seed_card": False, "sync_persona_on_init": False}}
    )
    calls = []

    class RecordingContext:
        plugin_data_dir = plugin.context.plugin_data_dir

        def register_web_api(self, route, handler, methods, desc):
            calls.append(route)

    plugin.context = RecordingContext()
    run(plugin.initialize())

    assert "/astrbot_plugin_dynamics_world/overview" in calls
    assert plugin.store.list_books() == []
    assert plugin.store.list_cards() == []


def test_overview_reports_capabilities_and_config(api):
    handler, plugin = api
    book = WorldBook(id=new_uid(), name="测试书")
    book.entries.append(WorldEntry(uid="e1", keys=["战斗"], content="正文", scenarios=["战斗"]))
    plugin.store.upsert_book(book)

    payload = _data(run(handler.overview()))["data"]
    assert payload["capabilities"]["write"] is True
    assert [b["name"] for b in payload["books"]] == ["测试书"]
    assert payload["books"][0]["entry_count"] == 1
    assert payload["scenarios"] == ["战斗"]
    assert "inject_style" in payload["config"]


def test_read_only_mode_blocks_writes(api, monkeypatch):
    handler, plugin = api
    plugin.config["web_panel"] = {"enabled": True, "allow_write": False}
    _stub_body(monkeypatch, {"action": "create", "name": "新书"})

    response = _data(run(handler.book_post()))
    assert response["status"] == "error"
    assert plugin.store.find_book_by_name("新书") is None


def test_disabled_panel_blocks_reads(api):
    handler, plugin = api
    plugin.config["web_panel"] = {"enabled": False}

    response = _data(run(handler.overview()))
    assert response["status"] == "error"


def test_unknown_fields_are_rejected(api, monkeypatch):
    handler, plugin = api
    _stub_body(monkeypatch, {"action": "create", "name": "新书", "sneaky": 1})

    response = _data(run(handler.book_post()))
    assert response["status"] == "error"
    assert "sneaky" in response["message"]
    assert plugin.store.find_book_by_name("新书") is None


def test_book_create_update_and_delete(api, monkeypatch):
    handler, plugin = api

    _stub_body(monkeypatch, {"action": "create", "name": "新书", "description": "说明"})
    created = _data(run(handler.book_post()))["data"]["book"]
    assert created["name"] == "新书"

    _stub_body(
        monkeypatch,
        {"action": "update", "book_id": created["id"], "name": "改名后", "enabled": False},
    )
    updated = _data(run(handler.book_post()))["data"]["book"]
    assert updated["name"] == "改名后"
    assert updated["enabled"] is False

    _stub_body(monkeypatch, {"action": "delete", "book_id": created["id"]})
    _data(run(handler.book_post()))
    assert plugin.store.get_book(created["id"]) is None


def test_duplicate_book_name_is_rejected(api, monkeypatch):
    handler, plugin = api
    plugin.store.upsert_book(WorldBook(id=new_uid(), name="重名书"))

    _stub_body(monkeypatch, {"action": "create", "name": "重名书"})
    response = _data(run(handler.book_post()))
    assert response["status"] == "error"


def test_entry_create_update_delete_and_move(api, monkeypatch):
    handler, plugin = api
    book = WorldBook(id=new_uid(), name="书")
    plugin.store.upsert_book(book)

    _stub_body(
        monkeypatch,
        {
            "action": "create",
            "book_id": book.id,
            "name": "第一条",
            "keys": "战斗, boss",
            "content": "正文",
            "scenarios": ["战斗"],
            "priority": 300,
        },
    )
    first = _data(run(handler.entry_post()))["data"]["entry"]
    assert first["keys"] == ["战斗", "boss"]
    assert first["priority"] == 300

    _stub_body(
        monkeypatch,
        {"action": "create", "book_id": book.id, "name": "第二条", "content": "正文二"},
    )
    second = _data(run(handler.entry_post()))["data"]["entry"]

    _stub_body(
        monkeypatch,
        {"action": "move", "book_id": book.id, "entry_id": second["uid"], "direction": "up"},
    )
    _data(run(handler.entry_post()))
    assert [e.uid for e in plugin.store.get_book(book.id).entries] == [second["uid"], first["uid"]]

    _stub_body(
        monkeypatch,
        {"action": "update", "book_id": book.id, "entry_id": first["uid"], "enabled": False},
    )
    updated = _data(run(handler.entry_post()))["data"]["entry"]
    assert updated["enabled"] is False
    # 未提交的字段必须保持原值
    assert updated["content"] == "正文"

    _stub_body(monkeypatch, {"action": "delete", "book_id": book.id, "entry_id": first["uid"]})
    _data(run(handler.entry_post()))
    assert [e.uid for e in plugin.store.get_book(book.id).entries] == [second["uid"]]


def test_entry_without_body_is_rejected(api, monkeypatch):
    handler, plugin = api
    book = WorldBook(id=new_uid(), name="书")
    plugin.store.upsert_book(book)

    _stub_body(monkeypatch, {"action": "create", "book_id": book.id, "name": "空条目"})
    response = _data(run(handler.entry_post()))
    assert response["status"] == "error"
    assert plugin.store.get_book(book.id).entries == []


def test_unknown_book_is_a_404(api, monkeypatch):
    handler, _plugin = api
    _stub_body(monkeypatch, {"action": "update", "book_id": "nope", "name": "x"})
    response = _data(run(handler.book_post()))
    assert response["status"] == "error"
    assert "未找到" in response["message"]


def test_set_global_active_validates_ids(api, monkeypatch):
    handler, plugin = api
    book = WorldBook(id=new_uid(), name="书")
    plugin.store.upsert_book(book)

    _stub_body(monkeypatch, {"action": "set_global_active", "book_ids": [book.id]})
    payload = _data(run(handler.book_post()))["data"]
    assert payload["active_book_ids"] == [book.id]

    _stub_body(monkeypatch, {"action": "set_global_active", "book_ids": ["ghost"]})
    response = _data(run(handler.book_post()))
    assert response["status"] == "error"


def test_session_actions(api, monkeypatch):
    handler, plugin = api
    plugin.store.update_session("umo:1", enabled=True)

    _stub_body(monkeypatch, {"action": "disable", "session_id": "umo:1"})
    row = _data(run(handler.session_post()))["data"]["session"]
    assert row["enabled"] is False

    _stub_body(monkeypatch, {"action": "set_scenario", "session_id": "umo:1", "scenario": "战斗"})
    row = _data(run(handler.session_post()))["data"]["session"]
    assert row["scenario"] == "战斗"

    _stub_body(monkeypatch, {"action": "clear_scenario", "session_id": "umo:1"})
    row = _data(run(handler.session_post()))["data"]["session"]
    assert row["scenario"] == ""

    _stub_body(monkeypatch, {"action": "forget", "session_id": "umo:1"})
    _data(run(handler.session_post()))
    assert plugin.store.get_session("umo:1").scenario == ""


def test_session_requires_an_id(api, monkeypatch):
    handler, _plugin = api
    _stub_body(monkeypatch, {"action": "disable"})
    response = _data(run(handler.session_post()))
    assert response["status"] == "error"


# The panel sends every id as a query parameter, so these cover the contract
# that broke once already: reading only query_params/args made every lookup
# answer "not found" even though the id was present.


@pytest.mark.parametrize("shape", ["query", "query_params", "args"])
def test_query_reads_every_supported_request_shape(monkeypatch, shape):
    _stub_request(monkeypatch, **{shape: {"book_id": "  b1  "}})
    assert web_api_module._query("book_id") == "b1"


def test_query_returns_default_for_unknown_attribute_shape(monkeypatch):
    # The real proxy raises AttributeError for attributes it does not define.
    _stub_request(monkeypatch)
    assert web_api_module._query("book_id", "fallback") == "fallback"


def test_query_prefers_the_astrbot_shape_when_several_exist(monkeypatch):
    _stub_request(monkeypatch, query={"book_id": "from-query"}, args={"book_id": "from-args"})
    assert web_api_module._query("book_id") == "from-query"


def test_book_get_resolves_the_requested_book(api, monkeypatch):
    handler, plugin = api
    wanted = WorldBook(id=new_uid(), name="目标书")
    other = WorldBook(id=new_uid(), name="另一本")
    plugin.store.upsert_book(wanted)
    plugin.store.upsert_book(other)

    _stub_request(monkeypatch, query={"book_id": wanted.id})
    payload = _data(run(handler.book_get()))["data"]
    assert payload["book"]["id"] == wanted.id
    assert payload["book"]["name"] == "目标书"


def test_book_get_without_a_resolvable_id_is_a_404(api, monkeypatch):
    handler, plugin = api
    plugin.store.upsert_book(WorldBook(id=new_uid(), name="书"))

    _stub_request(monkeypatch, query={})
    response = _data(run(handler.book_get()))
    assert response["status"] == "error"
    assert "未找到" in response["message"]


def test_card_get_resolves_the_requested_card(api, monkeypatch):
    handler, plugin = api
    card = CharacterCard(id=new_uid(), name="目标角色", personality="冷静")
    plugin.store.upsert_card(card)

    _stub_request(monkeypatch, query={"card_id": card.id})
    payload = _data(run(handler.card_get()))["data"]
    assert payload["card"]["name"] == "目标角色"
    assert payload["card"]["personality"] == "冷静"


def test_preview_renders_the_real_injection_block(api, monkeypatch):
    handler, plugin = api
    book = WorldBook(id=new_uid(), name="书")
    book.entries.append(WorldEntry(uid="e1", name="战斗", keys=["战斗"], content="战斗设定"))
    plugin.store.upsert_book(book)

    _stub_request(monkeypatch, query={"book_id": book.id, "keys": "战斗"})
    payload = _data(run(handler.preview()))["data"]
    assert [m["uid"] for m in payload["matched"]] == ["e1"]
    assert "战斗设定" in payload["text"]

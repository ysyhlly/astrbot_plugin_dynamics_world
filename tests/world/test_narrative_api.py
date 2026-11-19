"""Authoritative character reads for the narrative coordinator."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from astrbot.core.provider.entities import ProviderRequest
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.models import SESSION_CARD_NONE, WorldBook, WorldEntry

from conftest import FakeEvent, run


UMO = "qq-main:GroupMessage:100"


def _scope(umo=UMO, persona_id="wb_anan", instance_id="wb_anan"):
    return {
        "platform": "qq-main", "umo": umo,
        "persona_id": persona_id, "instance_id": instance_id,
    }


def _card(plugin, card_id="anan", persona_id="wb_anan", name="安安"):
    card = CharacterCard(
        id=card_id, name=name, persona_id=persona_id,
        system_prompt="严格以第一人称角色扮演，保持安安的懒散性格。",
        group_addendum="\n".join(["群聊规则，不能救场。"] * 200),
    )
    plugin.store.upsert_card(card)
    plugin.store.set_default_card(card.id)
    return card


def _book(plugin):
    book = WorldBook(id="world", name="世界")
    book.entries = [
        WorldEntry(uid="constant", content="共同背景", constant=True),
        WorldEntry(
            uid="game", name="游戏", content="游戏条目", keys=["游戏"],
            scenarios=["游戏时"], behavior="不愿展开无关话题",
        ),
        WorldEntry(
            uid="sleep", content="睡眠条目", constant=True, scenarios=["睡眠"],
        ),
        WorldEntry(uid="metadata", content="合成元数据不可触发", keys=["persona_id"]),
    ]
    plugin.store.upsert_book(book)
    plugin.store.set_global_active_books([book.id])
    return book


def test_default_role_is_versioned_and_group_rules_are_complete(make_plugin):
    plugin = make_plugin()
    card = _card(plugin)
    _book(plugin)
    result = run(plugin.get_character_context(_scope(), FakeEvent(UMO, "游戏怎么样")))

    assert result["schema_version"] == 1
    assert result["available"] and not result["disabled"]
    assert result["persona_id"] == "wb_anan"
    assert result["scope"] == _scope()
    assert result["group_rules"] == card.group_addendum
    assert "对外表达采用角色视角" in result["core_prompt"]
    assert "严格以第一人称角色扮演" not in result["core_prompt"]
    assert len(result["fingerprint"]) == 64
    assert {item["source_id"] for item in result["world_items"]} == {
        "worldbook:book:world:entry:constant", "worldbook:book:world:entry:game",
    }
    assert all(item["fact_kind"] == "world_setting" for item in result["world_items"])
    assert all(item["scope"] == _scope() for item in result["world_items"])
    assert "不愿展开无关话题" in result["world_prompt"]


def test_explicit_card_wins_and_stale_binding_does_not_fallback(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    other = _card(plugin, "other", "wb_other", "另一个角色")
    plugin.store.set_default_card("anan")
    plugin.store.update_session(UMO, card_id=other.id)
    result = run(plugin.get_character_context(_scope()))
    assert result["persona_id"] == "wb_other"
    assert result["instance_id"] == "wb_other"
    plugin.store.update_session(UMO, card_id="removed-card")
    missing = run(plugin.get_character_context(_scope()))
    assert not missing["available"] and not missing["disabled"]
    assert missing["reason"] == "no_character"
    assert missing["core_prompt"] == ""


def test_explicit_none_does_not_fallback(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    plugin.store.update_session(UMO, card_id=SESSION_CARD_NONE)
    result = run(plugin.get_character_context(_scope()))
    assert result["disabled"] and not result["available"]
    assert result["persona_id"] == ""
    assert result["world_items"] == []


def test_live_global_and_session_disable_are_honored(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    assert run(plugin.get_character_context(_scope()))["available"]
    plugin.config = {"enabled": False}
    assert run(plugin.get_character_context(_scope()))["disabled"]
    plugin.config = {"enabled": True}
    plugin.store.update_session(UMO, enabled=False)
    assert run(plugin.get_character_context(_scope()))["disabled"]
    plugin.store.update_session(UMO, enabled=True, inject_card_prompt=False)
    assert run(plugin.get_character_context(_scope()))["disabled"]


def test_scoped_manual_scenario_without_an_event_and_no_state_writes(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    _book(plugin)
    plugin.store.set_scenario(UMO, "睡眠")
    before = deepcopy(plugin.store._store.to_dict())
    path = Path(plugin.store.data_file)
    before_disk = path.read_bytes()
    result = run(plugin.get_character_context(_scope()))
    assert result["scenario"] == "睡眠"
    assert "睡眠条目" in result["world_prompt"]
    assert "游戏条目" not in result["world_prompt"]
    assert plugin.store._store.to_dict() == before
    assert path.read_bytes() == before_disk
    assert run(plugin.get_character_context(_scope())) == result


def test_unknown_session_read_does_not_create_it(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    _book(plugin)
    before = deepcopy(plugin.store._store.to_dict())
    result = run(plugin.get_character_context(_scope(), "游戏"))
    assert result["scenario"] == "游戏时"
    assert UMO not in plugin.store._store.sessions
    assert plugin.store._store.to_dict() == before
    result["world_items"][0]["text"] = "caller mutation"
    assert "caller mutation" not in run(plugin.get_character_context(_scope(), "游戏"))["world_prompt"]


def test_raw_envelope_text_is_used_without_scanning_metadata(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    _book(plugin)
    result = run(plugin.get_character_context(_scope(), {
        "scope": _scope(), "body": {"text": "游戏"},
        "prompt": "睡眠", "persona_id": "metadata should not be scanned",
    }))
    assert "游戏条目" in result["world_prompt"]
    assert "合成元数据不可触发" not in result["world_prompt"]
    assert "睡眠条目" not in result["world_prompt"]


def test_foreign_event_scope_is_rejected(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    result = run(plugin.get_character_context(
        _scope(), FakeEvent("qq-main:GroupMessage:other", "游戏")
    ))
    assert not result["available"]
    assert result["reason"] == "scope_mismatch"


def test_private_chat_excludes_group_rules_and_preserves_custom_core(make_plugin):
    plugin = make_plugin()
    card = _card(plugin)
    card.system_prompt = "用户自己的角色定义，不应被改写。"
    plugin.store.upsert_card(card)
    result = run(plugin.get_character_context(_scope("qq-main:FriendMessage:100")))
    assert result["group_rules"] == ""
    assert result["core_prompt"] == card.build_system_prompt()
    assert plugin.store.get_card(card.id).system_prompt == card.system_prompt


def test_hash_covers_world_behavior_and_group_rules(make_plugin):
    plugin = make_plugin()
    card = _card(plugin)
    book = _book(plugin)
    first = run(plugin.get_character_context(_scope(), "游戏"))["fingerprint"]
    book.entries[1].behavior = "可以暂时中断游戏"
    plugin.store.upsert_book(book)
    second = run(plugin.get_character_context(_scope(), "游戏"))["fingerprint"]
    assert second != first
    card.group_addendum += "\n不要自动承诺。"
    plugin.store.upsert_card(card)
    assert run(plugin.get_character_context(_scope(), "游戏"))["fingerprint"] != second


def test_unsynced_card_has_stable_identity_and_instance_is_scoped(make_plugin):
    plugin = make_plugin()
    _card(plugin, persona_id="")
    first = run(plugin.get_character_context(_scope()))
    assert first["persona_id"] == "wb_anan"
    assert run(plugin.get_character_context(_scope()))["fingerprint"] == first["fingerprint"]
    result = run(plugin.get_character_context(_scope(instance_id="anan-alt")))
    assert result["scope"]["instance_id"] == "anan-alt"


def test_managed_hook_does_not_duplicate_or_record_injection(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    _book(plugin)
    event = FakeEvent(UMO, "游戏")
    event.get_extra = lambda key: {"turn_id": "test"} if key == "_narrative_managed_v1" else None
    req = ProviderRequest(system_prompt="Already composed by Chat Dynamics")
    before = deepcopy(plugin.store._store.to_dict())
    run(plugin.on_llm_request(event, req))
    run(plugin.on_llm_request(event, req))
    assert req.system_prompt == "Already composed by Chat Dynamics"
    assert req.extra_user_content_parts == []
    assert plugin.store._store.to_dict() == before


def test_unmanaged_hook_remains_enabled(make_plugin):
    plugin = make_plugin()
    _card(plugin)
    _book(plugin)
    event = FakeEvent(UMO, "游戏")
    req = ProviderRequest(system_prompt="platform")
    run(plugin.on_llm_request(event, req))
    assert req.system_prompt == "platform"
    extra = "\n".join(part.text for part in req.extra_user_content_parts)
    assert "游戏条目" in extra
    assert "群聊规则" in extra


def test_global_tick_reads_only_matching_persona_and_its_linked_world(make_plugin):
    plugin = make_plugin()
    card = _card(plugin)
    own_world = _book(plugin)
    card.linked_book_id = own_world.id
    plugin.store.upsert_card(card)
    private_book = WorldBook(id="private", name="另一群的资料", entries=[
        WorldEntry(uid="secret", constant=True, content="另一群的私有内容"),
    ])
    plugin.store.upsert_book(private_book)
    plugin.store.set_global_active_books([private_book.id])
    plugin.store.update_session(UMO, scenario="睡眠", book_ids=[private_book.id])
    before = deepcopy(plugin.store._store.to_dict())
    scope = {"umo": "", "platform": "", "persona_id": "wb_anan", "instance_id": "wb_anan"}
    result = run(plugin.get_character_context(scope))
    assert result["available"] and result["persona_id"] == "wb_anan"
    assert result["group_rules"] == ""
    assert result["scenario"] == ""
    assert "共同背景" in result["world_prompt"]
    assert "另一群的私有内容" not in result["world_prompt"]
    assert "睡眠条目" not in result["world_prompt"]
    assert plugin.store._store.to_dict() == before
    assert "" not in plugin.store._store.sessions
    assert not run(plugin.get_character_context({**scope, "persona_id": "missing"}))["available"]
    assert not run(plugin.get_character_context(scope, "另一群的聊天"))["available"]

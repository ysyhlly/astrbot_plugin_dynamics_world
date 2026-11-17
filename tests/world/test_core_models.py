"""core/models.py：酒馆 map uid、selective、会话字段兼容。"""
from __future__ import annotations

from astrbot_plugin_dynamics_world.world.core.models import (
    SESSION_CARD_NONE,
    SessionState,
    WorldBook,
    WorldEntry,
    WorldStore,
)


def test_st_map_entry_uid_uses_map_key():
    """回归：旧写法 entry.uid == new_uid() 恒为 False，map 的 key 永远用不上。"""
    book = WorldBook.from_dict(
        {"entries": {"1001": {"comment": "A", "content": "x"}, "1002": {"comment": "B", "content": "y"}}}
    )
    assert [e.uid for e in book.entries] == ["1001", "1002"]


def test_st_map_entry_keeps_explicit_uid():
    book = WorldBook.from_dict({"entries": {"1001": {"uid": "keep-me", "content": "x"}}})
    assert book.entries[0].uid == "keep-me"


def test_st_map_entry_keeps_explicit_id():
    book = WorldBook.from_dict({"entries": {"1001": {"id": "keep-id", "content": "x"}}})
    assert book.entries[0].uid == "keep-id"


def test_selective_not_forced_by_secondary_keys():
    """酒馆语义：selective=false 时 keysecondary 不参与判定。"""
    entry = WorldEntry.from_dict({"key": ["a"], "keysecondary": ["b"], "content": "x"})
    assert entry.selective is False
    entry2 = WorldEntry.from_dict({"key": ["a"], "keysecondary": ["b"], "selective": True})
    assert entry2.selective is True


def test_disable_field_maps_to_enabled():
    assert WorldEntry.from_dict({"content": "x", "disable": True}).enabled is False
    assert WorldEntry.from_dict({"content": "x", "disable": False}).enabled is True


def test_session_state_new_fields_roundtrip():
    state = SessionState.from_dict({"scenario": "战斗", "scenario_auto": "海边", "last_active": 123})
    assert state.scenario == "战斗"
    assert state.scenario_auto == "海边"
    assert state.last_active == 123
    data = state.to_dict()
    assert data["scenario_auto"] == "海边"
    assert data["last_active"] == 123


def test_old_session_json_without_new_fields_still_loads():
    state = SessionState.from_dict({"scenario": "咖啡馆", "card_id": SESSION_CARD_NONE})
    assert state.scenario_auto == ""
    assert state.last_active == 0
    assert state.card_id == SESSION_CARD_NONE
    assert state.inject_card_prompt is True


def test_world_store_roundtrip():
    store = WorldStore.from_dict(
        {
            "books": {"b1": {"id": "b1", "name": "书", "entries": [{"uid": "e1", "content": "c"}]}},
            "sessions": {"s1": {"scenario": "海边"}},
            "active_book_ids": ["b1"],
            "cards": {"c1": {"id": "c1", "name": "卡"}},
            "default_card_id": "c1",
        }
    )
    assert store.books["b1"].entries[0].uid == "e1"
    assert store.sessions["s1"].scenario == "海边"
    assert store.active_book_ids == ["b1"]
    assert store.default_card_id == "c1"
    again = WorldStore.from_dict(store.to_dict())
    assert again.books["b1"].name == "书"
    assert again.sessions["s1"].scenario == "海边"


def test_book_list_scenarios():
    book = WorldBook(entries=[WorldEntry(scenarios=["b", "a"]), WorldEntry(scenarios=["a"])])
    assert book.list_scenarios() == ["a", "b"]

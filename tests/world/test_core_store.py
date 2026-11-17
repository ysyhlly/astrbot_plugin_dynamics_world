"""core/store.py：热路径写盘去重、防抖、预览上限、会话剪枝。"""
from __future__ import annotations

import json
import os
import pytest

from astrbot_plugin_dynamics_world.world.core.models import SessionState, WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.world.core.store import MAX_SESSIONS, PREVIEW_MAX, WorldBookStore


def _store(tmp_path) -> tuple[WorldBookStore, str]:
    path = os.path.join(str(tmp_path), "store.json")
    return WorldBookStore(path), path


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_first_record_match_writes(tmp_path):
    store, path = _store(tmp_path)
    assert store.record_match("s1", ["a"], "预览") is True
    assert os.path.exists(path)
    assert _read(path)["sessions"]["s1"]["last_matched"] == ["a"]


def test_record_match_skips_unchanged_content(tmp_path):
    """每轮请求都会调用，内容没变就不该产生任何写盘。"""
    store, path = _store(tmp_path)
    store.record_match("s1", ["a", "b"], "预览", scenario_auto="战斗")
    before = open(path, "rb").read()

    assert store.record_match("s1", ["a", "b"], "预览", scenario_auto="战斗") is False
    assert store._dirty is False
    assert open(path, "rb").read() == before


def test_record_match_debounces_burst_writes(tmp_path):
    store, path = _store(tmp_path)
    store.save()  # 基准写盘，建立 _last_save
    before = open(path, "rb").read()

    assert store.record_match("s2", ["x"], "预览2") is True  # 内存已更新
    assert store._dirty is True
    assert open(path, "rb").read() == before  # 防抖：暂不落盘

    store.save()  # 强制落盘
    assert "s2" in _read(path)["sessions"]


def test_pending_write_flushed_by_later_call(tmp_path):
    """防抖推迟的写入，必须在下一次调用（防抖窗口过后）补上，不能永久悬空。"""
    store, path = _store(tmp_path)
    store.save()
    assert store.record_match("s1", ["a"], "预览") is True
    assert store._dirty is True  # 被防抖推迟

    store._last_save = 0.0  # 模拟防抖窗口已过
    assert store.record_match("s1", ["a"], "预览") is False  # 内容没变
    assert store._dirty is False  # 但待写内容已经落盘
    assert "s1" in _read(path)["sessions"]


def test_preview_is_capped(tmp_path):
    store, path = _store(tmp_path)
    store.record_match("s1", [], "x" * 5000)
    assert len(_read(path)["sessions"]["s1"]["last_inject_preview"]) == PREVIEW_MAX


def test_legacy_preview_migrated_on_load(tmp_path):
    path = os.path.join(str(tmp_path), "store.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sessions": {"s1": {"last_inject_preview": "y" * 2000}}}, f, ensure_ascii=False)

    store = WorldBookStore(path)
    assert len(store.get_session("s1").last_inject_preview) == PREVIEW_MAX
    # 加载时顺手把文件压小
    assert len(_read(path)["sessions"]["s1"]["last_inject_preview"]) == PREVIEW_MAX


def test_prune_only_removes_idle_sessions(tmp_path):
    store, path = _store(tmp_path)
    for i in range(MAX_SESSIONS + 10):
        store._store.sessions[f"idle{i}"] = SessionState(last_active=i)
    # 有用户意图的会话（锁定场景）即使最旧也不能删
    store._store.sessions["keep"] = SessionState(scenario="战斗", last_active=0)
    store.save()

    data = _read(path)
    assert len(data["sessions"]) == MAX_SESSIONS
    assert "keep" in data["sessions"]
    assert "idle0" not in data["sessions"]
    assert f"idle{MAX_SESSIONS + 9}" in data["sessions"]


def test_no_tmp_file_left_behind(tmp_path):
    store, path = _store(tmp_path)
    store.upsert_book(WorldBook(id="b1", name="书", entries=[WorldEntry(uid="e1", content="c")]))
    assert not os.path.exists(path + ".tmp")
    assert _read(path)["books"]["b1"]["entries"][0]["uid"] == "e1"


def test_corrupt_store_fails_closed_and_preserves_original(tmp_path):
    path = os.path.join(str(tmp_path), "store.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ not json")
    with pytest.raises(OSError, match="worldbook_load_failed"):
        WorldBookStore(path)
    with open(path, "r", encoding="utf-8") as f:
        assert f.read() == "{ not json"


def test_session_card_resolution_and_none(tmp_path):
    from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
    from astrbot_plugin_dynamics_world.world.core.models import SESSION_CARD_NONE

    store, _ = _store(tmp_path)
    card = CharacterCard(id="card1", name="卡")
    store.upsert_card(card)
    store.set_default_card("card1")

    assert store.resolve_session_card("new-session").id == "card1"
    store.update_session("bound", card_id="card1")
    assert store.resolve_session_card("bound").id == "card1"
    store.update_session("off", card_id=SESSION_CARD_NONE)
    assert store.resolve_session_card("off") is None

"""core/importer.py：酒馆格式与简易文本格式导入。"""
from __future__ import annotations

from astrbot_plugin_dynamics_world.world.core.character import (
    character_book_to_worldbook,
    import_character_card,
)
from astrbot_plugin_dynamics_world.world.core.importer import import_worldbook


def test_entries_as_object_map():
    book = import_worldbook({"name": "书", "entries": {"5": {"key": ["a"], "content": "x"}}})
    assert book.name == "书"
    assert book.entries[0].uid == "5"
    assert book.entries[0].keys == ["a"]


def test_entries_as_list_with_st_field_aliases():
    book = import_worldbook(
        {
            "entries": [
                {"key": "a", "keysecondary": "b", "order": 42, "comment": "名字", "content": "x"}
            ]
        }
    )
    entry = book.entries[0]
    assert entry.keys == ["a"]
    assert entry.secondary_keys == ["b"]
    assert entry.priority == 42
    assert entry.name == "名字"


def test_disable_and_extensions_flags():
    book = import_worldbook(
        {
            "entries": [
                {
                    "key": ["a"],
                    "content": "x",
                    "disable": True,
                    "extensions": {"match_whole_words": True, "case_sensitive": True},
                }
            ]
        }
    )
    entry = book.entries[0]
    assert entry.enabled is False
    assert entry.match_whole_word is True
    assert entry.case_sensitive is True


def test_json_fence_and_raw_array():
    book = import_worldbook('```json\n[{"key": ["a"], "content": "x"}]\n```')
    assert book.entries[0].keys == ["a"]


def test_character_book_inside_card():
    book = import_worldbook(
        {
            "name": "角色卡",
            "character_book": {"name": "内嵌书", "entries": [{"content": "内", "key": ["k"]}]},
        }
    )
    assert book.name == "内嵌书"
    assert len(book.entries) == 1


def test_text_block_with_secondary_and_constant():
    text = """# 战斗
keys: 战斗, 开打
secondary: boss
scenario: 战斗
behavior: 语气果断
priority: 150
---
正文内容

===

# 常驻设定
constant: true
---
每轮都注入
"""
    book = import_worldbook(text, default_name="文本书")
    assert len(book.entries) == 2

    battle = book.entries[0]
    assert battle.name == "战斗"
    assert battle.keys == ["战斗", "开打"]
    assert battle.secondary_keys == ["boss"]
    assert battle.selective is True
    assert battle.scenarios == ["战斗"]
    assert battle.behavior == "语气果断"
    assert battle.priority == 150
    assert battle.content == "正文内容"

    always = book.entries[1]
    assert always.constant is True
    assert always.content == "每轮都注入"


def test_text_block_rejects_empty():
    import pytest

    with pytest.raises(ValueError):
        import_worldbook("   ")


def test_import_v2_character_card_and_worldbook():
    raw = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "测试角色",
            "description": "描述",
            "first_mes": "你好",
            "character_book": {"name": "书", "entries": [{"content": "内", "key": ["k"]}]},
        },
    }
    card = import_character_card(raw)
    assert card.name == "测试角色"
    assert card.source == "tavern_v2"

    book = character_book_to_worldbook(card)
    assert book is not None
    assert book.name == "测试角色·角色书"
    assert len(book.entries) == 1


def test_import_v1_flat_character_card():
    card = import_character_card({"name": "V1", "description": "d", "personality": "p"})
    assert card.source == "tavern_v1"
    assert card.personality == "p"

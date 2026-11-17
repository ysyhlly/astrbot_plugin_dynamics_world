"""匹配器：注入文案模板化后的渲染行为。"""
from __future__ import annotations

from astrbot_plugin_dynamics_world.world.core.matcher import build_injection_text, match_entries
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.world.core.settings import Settings


def _book_with_entry(**kwargs):
    entry = WorldEntry(uid="e1", keys=["战斗"], content="正文", **kwargs)
    return WorldBook(id="b1", name="测试书", entries=[entry])


def test_default_style_matches_legacy_output():
    book = _book_with_entry(behavior="语气果断", scenarios=["战斗"])
    result = match_entries([book], "战斗", max_entries=5)
    text = build_injection_text(result, active_scenario="战斗")
    assert "【世界书 / World Info】" in text
    assert "当前场景：战斗" in text
    assert "### 条目 1: 战斗" in text
    assert "- 适用场景: 战斗" in text
    assert "- 行为变化: 语气果断" in text


def test_custom_style_changes_the_rendered_block():
    style = Settings(
        {
            "inject_style": {
                "header": "[LORE]",
                "preamble": "",
                "scenario_header": "场景={scenario}",
                "entry_title_format": "- {book} / {title}",
                "scenario_line_format": "场景：{scenarios}",
                "behavior_line_format": "行为：{behavior}",
                "footer_with_scenario": "收尾:{scenario}",
                "footer_without_scenario": "收尾:无",
            }
        }
    )
    book = _book_with_entry(behavior="冷静", scenarios=["战斗"])
    result = match_entries([book], "战斗", max_entries=5)
    text = build_injection_text(result, active_scenario="战斗", style=style)
    assert text.startswith("[LORE]")
    assert "场景=战斗" in text
    assert "- 测试书 / 战斗" in text
    assert "行为：冷静" in text
    assert text.endswith("收尾:战斗")
    assert "【世界书 / World Info】" not in text


def test_blanked_lines_are_omitted():
    style = Settings(
        {
            "inject_style": {
                "preamble": "",
                "scenario_header": "",
                "scenario_line_format": "",
                "footer_with_scenario": "",
                "footer_without_scenario": "",
            }
        }
    )
    book = _book_with_entry(behavior="冷静", scenarios=["战斗"])
    result = match_entries([book], "战斗", max_entries=5)
    text = build_injection_text(result, active_scenario="战斗", style=style)
    assert "以下设定在本轮对话中生效" not in text
    assert "适用场景" not in text
    assert "角色行为要求" not in text
    assert "正文" in text


def test_dedupe_can_be_disabled():
    shared = "完全相同的正文"
    # 名字刻意用 ASCII 以保证排序稳定：中文按码位排会得到反直觉的顺序
    entry_a = WorldEntry(uid="a", name="A-条目", keys=["甲"], content=shared)
    entry_b = WorldEntry(uid="b", name="B-条目", keys=["乙"], content=shared)
    book = WorldBook(id="b1", name="t", entries=[entry_a, entry_b])

    deduped = match_entries([book], "甲 乙", max_entries=5)
    assert [m.entry.uid for m in deduped.matched] == ["a"]

    kept = match_entries([book], "甲 乙", max_entries=5, dedupe_same_content=False)
    assert [m.entry.uid for m in kept.matched] == ["a", "b"]


def test_no_match_renders_nothing_even_with_style():
    style = Settings({"inject_style": {"header": "[LORE]"}})
    book = _book_with_entry()
    result = match_entries([book], "无关内容", max_entries=5)
    assert build_injection_text(result, style=style) == ""

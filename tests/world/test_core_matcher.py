"""core/matcher.py：自动场景截断、常驻保留、selective 语义。"""
from __future__ import annotations

from astrbot_plugin_dynamics_world.world.core.matcher import build_injection_text, match_entries
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry


def _uid(matched):
    return [m.entry.uid for m in matched]


def test_constants_survive_auto_scenario_truncation():
    """回归：开启自动场景后，常驻条目曾被 [:max_entries] 全部截掉。"""
    book = WorldBook(id="b1", name="t")
    for i in range(3):
        book.entries.append(
            WorldEntry(uid=f"c{i}", name=f"常驻{i}", content=f"C{i}", constant=True, priority=50)
        )
    for i in range(3):
        book.entries.append(
            WorldEntry(
                uid=f"s{i}",
                name=f"场景常驻{i}",
                content=f"S{i}",
                constant=True,
                scenarios=["战斗"],
                priority=200,
            )
        )
    for i in range(6):
        book.entries.append(
            WorldEntry(
                uid=f"k{i}",
                name=f"kw{i}",
                keys=["战斗"],
                content=f"K{i}",
                scenarios=["战斗"],
                priority=300 - i,
            )
        )

    result = match_entries([book], "开始战斗吧", active_scenario="", max_entries=5)
    kept = _uid(result.matched)

    assert result.auto_scenario == "战斗"
    for uid in ("c0", "c1", "c2", "s0", "s1", "s2"):
        assert uid in kept, f"常驻条目 {uid} 被截断了: {kept}"
    assert len([u for u in kept if u.startswith("k")]) == 5


def test_max_entries_only_limits_keyword_entries():
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="c1", content="常驻", constant=True))
    for i in range(20):
        book.entries.append(WorldEntry(uid=f"k{i}", keys=["关键词"], content=f"K{i}", priority=100 - i))

    result = match_entries([book], "关键词", active_scenario="", max_entries=3)
    assert len(result.matched) == 4  # 1 常驻 + 3 关键词
    assert _uid(result.matched)[0] == "c1"


def test_constants_sorted_before_keywords_by_priority():
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="low", content="低优先常驻", constant=True, priority=1))
    book.entries.append(WorldEntry(uid="high", content="高优先常驻", constant=True, priority=999))
    book.entries.append(WorldEntry(uid="kw", keys=["x"], content="关键词", priority=500))

    result = match_entries([book], "x", active_scenario="", max_entries=5)
    assert _uid(result.matched) == ["high", "low", "kw"]


def test_content_dedupe():
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="a", keys=["x"], content="同一段内容"))
    book.entries.append(WorldEntry(uid="b", keys=["x"], content="同一段内容"))

    result = match_entries([book], "x", active_scenario="", max_entries=10)
    assert _uid(result.matched) == ["a"]


def test_disabled_book_and_entry_are_skipped():
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="on", keys=["x"], content="ok"))
    book.entries.append(WorldEntry(uid="off", keys=["x"], content="no", enabled=False))

    assert _uid(match_entries([book], "x", max_entries=10).matched) == ["on"]

    book.enabled = False
    assert match_entries([book], "x", max_entries=10).matched == []


def test_scenario_bound_constant_needs_active_scenario():
    book = WorldBook(id="b1", name="t")
    book.entries.append(
        WorldEntry(uid="s1", content="战斗中", constant=True, scenarios=["战斗"])
    )
    assert match_entries([book], "随便聊聊", active_scenario="", max_entries=5).matched == []
    got = match_entries([book], "随便聊聊", active_scenario="战斗", max_entries=5)
    assert _uid(got.matched) == ["s1"]


def test_locked_scenario_filters_other_scenarios():
    """手动锁定场景时，其它场景的条目不再注入（/世界书 场景 清除 可解锁）。"""
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="x1", keys=["咖啡"], content="cafe", scenarios=["咖啡馆"]))
    book.entries.append(WorldEntry(uid="x2", keys=["海边"], content="sea", scenarios=["海边"]))

    free = match_entries([book], "海边 咖啡", active_scenario="", max_entries=10)
    assert set(_uid(free.matched)) == {"x1", "x2"}

    locked = match_entries([book], "海边 咖啡", active_scenario="咖啡馆", max_entries=10)
    assert _uid(locked.matched) == ["x1"]


def test_auto_scenario_disabled_by_flag():
    book = WorldBook(id="b1", name="t")
    book.entries.append(WorldEntry(uid="k", keys=["战斗"], content="K", scenarios=["战斗"]))
    result = match_entries([book], "战斗", active_scenario="", max_entries=5, allow_auto_scenario=False)
    assert result.auto_scenario == ""


def test_whole_word_and_case_sensitive():
    book = WorldBook(id="b1", name="t")
    book.entries.append(
        WorldEntry(uid="w", keys=["cat"], content="x", match_whole_word=True)
    )
    assert match_entries([book], "concatenate", max_entries=5).matched == []
    assert _uid(match_entries([book], "a cat here", max_entries=5).matched) == ["w"]


def test_selective_requires_secondary():
    entry = WorldEntry(uid="e", keys=["战斗"], secondary_keys=["boss"], selective=True, content="x")
    book = WorldBook(id="b1", name="t", entries=[entry])
    assert match_entries([book], "战斗开始", max_entries=5).matched == []
    assert _uid(match_entries([book], "战斗遇到boss", max_entries=5).matched) == ["e"]


def test_secondary_only_entry_is_not_constant_like():
    entry = WorldEntry(uid="e", secondary_keys=["boss"], content="x")
    book = WorldBook(id="b1", name="t", entries=[entry])
    assert match_entries([book], "无关内容", max_entries=5).matched == []
    assert _uid(match_entries([book], "遇到 boss", max_entries=5).matched) == ["e"]


def test_build_injection_text_renders_scenario_and_behavior():
    book = WorldBook(id="b1", name="t")
    book.entries.append(
        WorldEntry(uid="k", keys=["战斗"], content="正文", behavior="语气果断", scenarios=["战斗"])
    )
    result = match_entries([book], "战斗", max_entries=5)
    text = build_injection_text(result, active_scenario=result.auto_scenario)
    assert "当前场景：战斗" in text
    assert "行为变化: 语气果断" in text
    assert "正文" in text
    assert build_injection_text(match_entries([book], "无事发生", max_entries=5)) == ""

"""core/settings.py：面板配置的读取、兜底与占位符渲染。"""
from __future__ import annotations

import pytest

from astrbot_plugin_dynamics_world.world.core.settings import (
    DEFAULT_BEHAVIOR_LINE_FORMAT,
    DEFAULT_FOOTER_WITHOUT_SCENARIO,
    DEFAULT_INJECT_HEADER,
    Settings,
    render_template,
)


def test_defaults_apply_when_config_is_empty():
    cfg = Settings({})
    assert cfg.enabled is True
    assert cfg.inject_mode == "both"
    assert cfg.max_entries == 10
    assert cfg.scan_history_turns == 4
    assert cfg.inject_header == DEFAULT_INJECT_HEADER
    assert cfg.behavior_line_format == DEFAULT_BEHAVIOR_LINE_FORMAT
    assert cfg.footer_without_scenario == DEFAULT_FOOTER_WITHOUT_SCENARIO
    assert cfg.web_panel_enabled is True
    assert cfg.web_panel_allow_write is True


def test_flat_overrides_win():
    cfg = Settings({"enabled": False, "max_entries": 3, "inject_mode": "extra"})
    assert cfg.enabled is False
    assert cfg.max_entries == 3
    assert cfg.inject_mode == "extra"


def test_nested_overrides_and_missing_leaf_fall_back():
    cfg = Settings({"inject_style": {"header": "自定义标题"}})
    assert cfg.inject_header == "自定义标题"
    # 同一分组里未覆盖的键仍然回落到默认值
    assert cfg.entry_title_format == "### 条目 {index}: {title}"
    # 完全缺失的分组同样回落
    assert cfg.web_panel_page_title == "世界书"


def test_blank_template_is_preserved_so_lines_can_be_disabled():
    cfg = Settings({"inject_style": {"scenario_header": ""}})
    assert cfg.scenario_header == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", True),
        ("OFF", False),
        (1, True),
        (0, False),
        ("nonsense", True),
    ],
)
def test_bool_parsing_tolerates_panel_strings(raw, expected):
    assert Settings({"enabled": raw}).enabled is expected


def test_invalid_choice_falls_back():
    assert Settings({"inject_mode": "sideways"}).inject_mode == "both"


def test_int_floor_applies():
    assert Settings({"max_entries": 0}).max_entries == 1
    assert Settings({"scan_history_turns": -5}).scan_history_turns == 0


def test_scan_roles_filters_unknown_entries():
    assert Settings({"matching": {"scan_roles": "user, bogus"}}).scan_roles == ["user"]
    assert Settings({"matching": {"scan_roles": "nope"}}).scan_roles == [
        "user",
        "assistant",
        "system",
    ]


def test_seed_names_never_go_blank():
    cfg = Settings({"seeding": {"seed_worldbook_name": "   ", "default_card_name": ""}})
    assert cfg.seed_worldbook_name == "魔法少女的魔女审判 世界书"
    assert cfg.default_card_name == "夏目安安"


def test_render_template_substitutes_and_keeps_unknown_placeholders():
    assert render_template("你好 {name}!", name="安安") == "你好 安安!"
    assert render_template("{missing} 保持原样") == "{missing} 保持原样"
    assert render_template("") == ""


def test_panel_snapshot_exposes_every_group():
    snapshot = Settings({}).panel_snapshot()
    for key in ("inject_style", "matching", "commands", "seeding", "web_panel"):
        assert key in snapshot
    assert snapshot["inject_style"]["header"] == DEFAULT_INJECT_HEADER

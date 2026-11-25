"""Typed access to the plugin's panel-editable configuration.

Every tunable that used to be a literal inside the plugin now flows through
:class:`Settings`, so the dashboard config page and the runtime read exactly the
same values. Reads are defensive: a missing key, a wrong type or a malformed
nested node always falls back to the documented default instead of raising.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------- templates

DEFAULT_INJECT_HEADER = "【世界书 / World Info】"
DEFAULT_INJECT_PREAMBLE = (
    "以下设定在本轮对话中生效。请根据场景与设定调整角色语气、行为与决策，不要生硬复述条目原文。"
)
DEFAULT_SCENARIO_HEADER = "当前场景：{scenario}"
DEFAULT_ENTRY_TITLE_FORMAT = "### 条目 {index}: {title}"
DEFAULT_SCENARIO_LINE_FORMAT = "- 适用场景: {scenarios}"
DEFAULT_BEHAVIOR_LINE_FORMAT = "- 行为变化: {behavior}"
DEFAULT_FOOTER_WITH_SCENARIO = (
    "角色行为要求：在「{scenario}」场景下，优先遵循该场景绑定条目中的行为变化指引，"
    "保持人设一致，同时让语气、节奏、动作与决策明显受场景影响。"
)
DEFAULT_FOOTER_WITHOUT_SCENARIO = (
    "角色行为要求：结合命中的世界书条目调整细节表现；未命中的设定不要强行展开。"
)
DEFAULT_CARD_LABEL = "【角色卡：{name}】"
DEFAULT_CARD_LABEL_GROUP = "【角色卡：{name}（群聊）】"
DEFAULT_PERSONA_OVERRIDE_NOTICE = "【人设覆盖】上文若有「{name}」的其它设定，以本角色卡为准。"

DEFAULT_SEED_WORLDBOOK_NAME = "魔法少女的魔女审判 世界书"
DEFAULT_SEED_CARD_NAME = "夏目安安"
DEFAULT_SCAN_ROLES = ("user", "assistant", "system")
VALID_SCAN_ROLES = frozenset({"user", "assistant", "system"})

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(template: str, **values: Any) -> str:
    """Substitute brace-style placeholders and leave unknown ones intact.

    Args:
        template: Template text. An empty template yields an empty string.
        **values: Replacement values keyed by placeholder name.

    Returns:
        The rendered text. Placeholders without a matching value are preserved
        verbatim, so a typo in the panel degrades to visible text instead of an
        exception or a silently dropped line.
    """
    if not template:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        value = values[key]
        return "" if value is None else str(value)

    return _PLACEHOLDER_RE.sub(_replace, template)


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off", ""}:
            return False
    return default


def _as_int(value: Any, default: int, minimum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and result < minimum:
        return minimum
    return result


def _as_str(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default


def _as_str_list(value: Any, default: tuple[str, ...]) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(part).strip() for part in value]
    else:
        return list(default)
    cleaned = [item for item in items if item]
    return cleaned or list(default)


class Settings:
    """Read-only view over the plugin config with per-key defaults."""

    def __init__(self, raw: Any = None) -> None:
        self.raw = raw if raw is not None else {}

    # ------------------------------------------------------------ plumbing

    def _node(self, path: str) -> Any:
        """Walk a dotted path through the config mapping."""
        current: Any = self.raw
        for part in path.split("."):
            if not isinstance(current, dict) and not hasattr(current, "get"):
                return None
            try:
                current = current.get(part)
            except Exception:
                return None
            if current is None:
                return None
        return current

    def value(self, path: str, default: Any = None) -> Any:
        """Return the raw value at a dotted key path.

        Args:
            path: Dotted key path, e.g. inject_style.header.
            default: Value returned when the path is absent.

        Returns:
            The stored value, or default.
        """
        found = self._node(path)
        return default if found is None else found

    def string(self, path: str, default: str) -> str:
        return _as_str(self.value(path), default)

    def boolean(self, path: str, default: bool) -> bool:
        return _as_bool(self.value(path), default)

    def integer(self, path: str, default: int, minimum: int | None = None) -> int:
        return _as_int(self.value(path), default, minimum)

    def choice(self, path: str, default: str, allowed: set[str]) -> str:
        candidate = str(self.value(path) or "").strip().lower()
        return candidate if candidate in allowed else default

    # ------------------------------------------------------- top-level keys

    @property
    def enabled(self) -> bool:
        return self.boolean("enabled", True)

    @property
    def inject_mode(self) -> str:
        return self.choice("inject_mode", "extra", {"extra", "system", "both"})

    @property
    def max_entries(self) -> int:
        return self.integer("max_entries", 10, 1)

    @property
    def max_constant_entries(self) -> int:
        return self.integer("max_constant_entries", 20, 0)

    @property
    def max_inject_chars(self) -> int:
        return self.integer("max_inject_chars", 6000, 0)

    @property
    def scan_history_turns(self) -> int:
        return self.integer("scan_history_turns", 4, 0)

    @property
    def auto_scenario(self) -> bool:
        return self.boolean("auto_scenario", True)

    @property
    def default_card_anan(self) -> bool:
        return self.boolean("default_card_anan", True)

    @property
    def show_debug_in_status(self) -> bool:
        return self.boolean("show_debug_in_status", True)

    @property
    def admin_only_writes(self) -> bool:
        return self.boolean("admin_only_writes", True)

    # ---------------------------------------------------------- inject style

    @property
    def inject_header(self) -> str:
        return self.string("inject_style.header", DEFAULT_INJECT_HEADER)

    @property
    def inject_preamble(self) -> str:
        return self.string("inject_style.preamble", DEFAULT_INJECT_PREAMBLE)

    @property
    def scenario_header(self) -> str:
        return self.string("inject_style.scenario_header", DEFAULT_SCENARIO_HEADER)

    @property
    def entry_title_format(self) -> str:
        return self.string("inject_style.entry_title_format", DEFAULT_ENTRY_TITLE_FORMAT)

    @property
    def scenario_line_format(self) -> str:
        return self.string("inject_style.scenario_line_format", DEFAULT_SCENARIO_LINE_FORMAT)

    @property
    def behavior_line_format(self) -> str:
        return self.string("inject_style.behavior_line_format", DEFAULT_BEHAVIOR_LINE_FORMAT)

    @property
    def entry_separator(self) -> str:
        return self.string("inject_style.entry_separator", "")

    @property
    def footer_with_scenario(self) -> str:
        return self.string("inject_style.footer_with_scenario", DEFAULT_FOOTER_WITH_SCENARIO)

    @property
    def footer_without_scenario(self) -> str:
        return self.string(
            "inject_style.footer_without_scenario", DEFAULT_FOOTER_WITHOUT_SCENARIO
        )

    @property
    def card_label(self) -> str:
        return self.string("inject_style.card_label", DEFAULT_CARD_LABEL)

    @property
    def card_label_group(self) -> str:
        return self.string("inject_style.card_label_group", DEFAULT_CARD_LABEL_GROUP)

    @property
    def persona_override_notice(self) -> str:
        return self.string(
            "inject_style.persona_override_notice", DEFAULT_PERSONA_OVERRIDE_NOTICE
        )

    # -------------------------------------------------------------- matching

    @property
    def dedupe_same_content(self) -> bool:
        return self.boolean("matching.dedupe_same_content", True)

    @property
    def scan_roles(self) -> list[str]:
        roles = _as_str_list(self.value("matching.scan_roles"), DEFAULT_SCAN_ROLES)
        filtered = [role.lower() for role in roles if role.lower() in VALID_SCAN_ROLES]
        return filtered or list(DEFAULT_SCAN_ROLES)

    @property
    def persona_skip_min_chars(self) -> int:
        return self.integer("matching.persona_skip_min_chars", 80, 0)

    @property
    def scan_include_prompt(self) -> bool:
        return self.boolean("matching.scan_include_prompt", True)

    # -------------------------------------------------------------- commands

    @property
    def help_text(self) -> str:
        return self.string("commands.help_text", "")

    @property
    def card_help_text(self) -> str:
        return self.string("commands.card_help_text", "")

    @property
    def expose_panel_hint(self) -> bool:
        return self.boolean("commands.expose_panel_hint", True)

    # -------------------------------------------------------------- seeding

    @property
    def seed_worldbook(self) -> bool:
        return self.boolean("seeding.seed_worldbook", True)

    @property
    def seed_worldbook_name(self) -> str:
        name = self.string("seeding.seed_worldbook_name", DEFAULT_SEED_WORLDBOOK_NAME).strip()
        return name or DEFAULT_SEED_WORLDBOOK_NAME

    @property
    def seed_worldbook_legacy_keywords(self) -> list[str]:
        return _as_str_list(
            self.value("seeding.seed_worldbook_legacy_keywords"), ("魔女审判", "魔裁")
        )

    @property
    def seed_card(self) -> bool:
        return self.boolean("seeding.seed_card", True)

    @property
    def default_card_name(self) -> str:
        name = self.string("seeding.default_card_name", DEFAULT_SEED_CARD_NAME).strip()
        return name or DEFAULT_SEED_CARD_NAME

    @property
    def sync_persona_on_init(self) -> bool:
        return self.boolean("seeding.sync_persona_on_init", True)

    # ------------------------------------------------------------- web panel

    @property
    def web_panel_enabled(self) -> bool:
        return self.boolean("web_panel.enabled", True)

    @property
    def web_panel_allow_write(self) -> bool:
        return self.boolean("web_panel.allow_write", True)

    @property
    def web_panel_page_title(self) -> str:
        title = self.string("web_panel.page_title", "世界书").strip()
        return title or "世界书"

    # ------------------------------------------------------------ for UI/API

    def panel_snapshot(self) -> dict[str, Any]:
        """A flat, panel-friendly dump of every runtime-effective value."""
        return {
            "enabled": self.enabled,
            "inject_mode": self.inject_mode,
            "max_entries": self.max_entries,
            "scan_history_turns": self.scan_history_turns,
            "auto_scenario": self.auto_scenario,
            "default_card_anan": self.default_card_anan,
            "show_debug_in_status": self.show_debug_in_status,
            "admin_only_writes": self.admin_only_writes,
            "inject_style": {
                "header": self.inject_header,
                "preamble": self.inject_preamble,
                "scenario_header": self.scenario_header,
                "entry_title_format": self.entry_title_format,
                "scenario_line_format": self.scenario_line_format,
                "behavior_line_format": self.behavior_line_format,
                "entry_separator": self.entry_separator,
                "footer_with_scenario": self.footer_with_scenario,
                "footer_without_scenario": self.footer_without_scenario,
                "card_label": self.card_label,
                "card_label_group": self.card_label_group,
                "persona_override_notice": self.persona_override_notice,
            },
            "matching": {
                "dedupe_same_content": self.dedupe_same_content,
                "scan_roles": self.scan_roles,
                "persona_skip_min_chars": self.persona_skip_min_chars,
                "scan_include_prompt": self.scan_include_prompt,
            },
            "commands": {
                "help_text": self.help_text,
                "card_help_text": self.card_help_text,
                "expose_panel_hint": self.expose_panel_hint,
            },
            "seeding": {
                "seed_worldbook": self.seed_worldbook,
                "seed_worldbook_name": self.seed_worldbook_name,
                "seed_worldbook_legacy_keywords": self.seed_worldbook_legacy_keywords,
                "seed_card": self.seed_card,
                "default_card_name": self.default_card_name,
                "sync_persona_on_init": self.sync_persona_on_init,
            },
            "web_panel": {
                "enabled": self.web_panel_enabled,
                "allow_write": self.web_panel_allow_write,
                "page_title": self.web_panel_page_title,
            },
        }


__all__ = [
    "Settings",
    "render_template",
]

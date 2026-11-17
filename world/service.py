# ruff: noqa: E402
# Refresh owned dependencies before importing them during a scoped hot reload.
from __future__ import annotations


import hashlib
import json
from astrbot.api import logger
import os
import re
from typing import Any

from astrbot.api.event import AstrMessageEvent

try:
    from astrbot.api import AstrBotConfig
except Exception:  # pragma: no cover
    AstrBotConfig = dict  # type: ignore

try:
    from astrbot.core.provider.entities import ProviderRequest
except Exception:  # pragma: no cover
    ProviderRequest = Any  # type: ignore

try:
    from astrbot.core.star.filter.command import GreedyStr
except Exception:  # pragma: no cover
    GreedyStr = str  # type: ignore

from .core.character import (
    CharacterCard,
    character_book_to_worldbook,
    import_character_card,
    is_group_session,
    slug_persona_id,
)
from .core.importer import import_worldbook
from .core.matcher import build_injection_text, match_entries
from .core.models import SESSION_CARD_NONE, WorldBook, WorldEntry, new_uid
from .core.settings import Settings, render_template
from .core.store import WorldBookStore
from .core.web_api import WorldBookWebAPI


PLUGIN_NAME = "astrbot_plugin_dynamics_world"
PLUGIN_VERSION = "v1.5.0"
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILENAME = "worldbook_store.json"

PANEL_HINT = "\n\n🖥️ 可视化编辑：管理面板 → 插件 → 世界书（条目/角色卡/场景/会话）"

DEFAULT_HELP_TEXT = """群间世界 · Dynamics World
/群间世界 列表 | 新建 | 导入 | 详情
/群间世界 加条 | 加常驻 | 删条
/群间世界 场景 [设置|清除] | 绑定 | 解绑
/群间世界 角色卡 列表 | 导入 | 应用 | 卸下 | 设默认
/群间日常 [完整|重新生成|推进|暂停|恢复]
角色、世界书、场景与生活记录也可在管理面板中编辑。"""
DEFAULT_CARD_HELP_TEXT = """角色卡管理
/群间世界 角色卡 列表 | 详情 <名称>
/群间世界 角色卡 导入 <名称> <JSON>
/群间世界 角色卡 应用 <名称> | 卸下
/群间世界 角色卡 设默认 <名称>
/群间世界 角色卡 群聊 [设置 <文本>|清除|预览]
新安装从空世界开始；应用角色时可同步到 AstrBot 人格。"""


# 会改动全局数据的子命令：默认只有管理员可用（admin_only_writes 配置可放开）
ADMIN_ACTIONS = {
    "新建",
    "启用",
    "禁用",
    "删除",
    "导入",
    "导入示例",
    "加条",
    "添加条目",
    "add",
    "加常驻",
    "常驻",
    "删条",
    "删除条目",
}
# 角色卡里会改动全局数据的子命令
ADMIN_CARD_ACTIONS = {"导入", "导入安安", "设默认", "删除"}
ADMIN_DENIED_TEXT = (
    "⛔ 该操作会改动全局世界书/角色卡，仅管理员可用。\n"
    "查看类命令（列表/详情/状态/场景/开/关/绑定）不受限制；\n"
    "如需放开写操作：插件配置 admin_only_writes 设为 false。"
)


def _prompt_already_in(haystack: str, needle: str, *, min_chars: int = 80) -> bool:
    """needle 是否已基本原样地出现在 haystack 中。

    用于判断角色卡提示词是否已经被 AstrBot 人格（persona）注入到 system prompt。
    比对失败一律返回 False（照旧注入），因此不会因平台拼装方式变化而丢提示词。
    """
    needle = str(needle or "").strip()
    if len(needle) < min_chars:
        return False
    hay = re.sub(r"\s+", "", str(haystack or ""))
    if not hay:
        return False
    return re.sub(r"\s+", "", needle) in hay


def _safe_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled", "开启", "启用", "是"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled", "关闭", "停用", "否"}:
        return False
    return default


def _safe_int(value: Any, default: int, minimum: int | None = None) -> int:
    try:
        result = int(value)
    except Exception:
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


class WorldService:
    def __init__(self, context, config, data_dir):
        self.context = context
        self.config = config
        self.settings = Settings(config)
        self.store = WorldBookStore(str(data_dir / "worldbook_store.json"))
        self.web = WorldBookWebAPI(self)

    async def initialize(self):
        # A new world starts empty; importing a character is always deliberate.
        self._register_web_apis()

    def _register_web_apis(self) -> None:
        """Expose the dashboard page endpoints on the host Web server."""
        try:
            self.web.register()
            logger.info(
                "%s web panel routes published under /%s/* (panel=%s, write=%s)",
                PLUGIN_NAME,
                PLUGIN_NAME,
                self.settings.web_panel_enabled,
                self.settings.web_panel_allow_write,
            )
        except Exception as e:
            logger.warning("%s web api registration failed: %s", PLUGIN_NAME, e)

    def _ensure_mocai_seeded(self) -> None:
        """确保魔裁世界书已装入（空库或数据目录迁移后自动补种）。

        世界书名与旧名关键词都来自面板配置 seeding 组，改配置即可换成本地
        自己的世界书样本，不必改代码。
        """
        if not self.settings.seed_worldbook:
            return
        mocai_path = os.path.join(
            PLUGIN_DIR, "..", "presets", "manosaba", "worldbook.json"
        )
        if not os.path.exists(mocai_path):
            return
        target_name = self.settings.seed_worldbook_name
        legacy = self.settings.seed_worldbook_legacy_keywords
        existing = self.store.find_book_by_name(target_name)
        if existing is None:
            for b in self.store.list_books():
                if any(kw and kw in b.name for kw in legacy):
                    existing = b
                    break
        if existing is not None and existing.entries:
            return
        try:
            with open(mocai_path, "r", encoding="utf-8") as f:
                book = import_worldbook(f.read(), default_name=target_name)
            if existing is not None:
                book.id = existing.id
            book.enabled = True
            self.store.upsert_book(book)
            self.store.set_global_active_books([book.id])
            logger.info(
                "%s seeded mocai worldbook id=%s entries=%d",
                PLUGIN_NAME,
                book.id,
                len(book.entries),
            )
        except Exception as e:
            logger.warning("%s seed mocai failed: %s", PLUGIN_NAME, e)

    def _ensure_anan_card_seeded(self) -> None:
        """确保内置角色卡已装入，并按配置设为全局默认。"""
        if not self.settings.seed_card:
            return
        card_name = self.settings.default_card_name
        path = os.path.join(PLUGIN_DIR, "..", "presets", "manosaba", "character.json")
        if not os.path.exists(path):
            return
        try:
            existing = self.store.find_card_by_name(card_name)
            if existing is None or not (existing.description or existing.system_prompt):
                with open(path, "r", encoding="utf-8") as f:
                    card = import_character_card(f.read(), default_name=card_name)
                if existing is not None:
                    card.id = existing.id
                    card.persona_id = existing.persona_id
                book = self.store.find_book_by_name(self.settings.seed_worldbook_name)
                if book:
                    card.linked_book_id = book.id
                self.store.upsert_card(card)
                existing = card
                logger.info(
                    "%s seeded character card %s id=%s", PLUGIN_NAME, card_name, card.id
                )
            # 按配置把内置卡设为默认（可被用户改默认覆盖）
            if existing is not None and self.settings.default_card_anan:
                self.store.set_default_card(existing.id)
                # 修正关联世界书
                if not existing.linked_book_id:
                    book = self.store.find_book_by_name(
                        self.settings.seed_worldbook_name
                    )
                    if book:
                        existing.linked_book_id = book.id
                        self.store.upsert_card(existing)
                logger.info(
                    "%s default card set to %s id=%s",
                    PLUGIN_NAME,
                    card_name,
                    existing.id,
                )
        except Exception as e:
            logger.warning("%s seed anan card failed: %s", PLUGIN_NAME, e)

    async def terminate(self):
        try:
            self.store.save()
        except Exception as e:
            logger.warning("worldbook terminate save failed: %s", e)

    # ---------- config helpers ----------

    def _cfg(self, key: str, default: Any = None) -> Any:
        """Dotted read against the plugin config, tolerant of any container type."""
        return self.settings.value(key, default)

    def _refresh_settings(self) -> None:
        """Re-bind the settings view after the host swaps the config object."""
        self.settings = Settings(self.config)

    @property
    def inject_enabled_global(self) -> bool:
        return self.settings.enabled

    @property
    def max_entries(self) -> int:
        return self.settings.max_entries

    @property
    def scan_history_turns(self) -> int:
        return self.settings.scan_history_turns

    @property
    def inject_mode(self) -> str:
        # 角色卡默认 both，保证 system + extra 都能生效
        return self.settings.inject_mode

    @property
    def auto_scenario(self) -> bool:
        return self.settings.auto_scenario

    @property
    def show_debug_in_status(self) -> bool:
        return self.settings.show_debug_in_status

    @property
    def admin_only_writes(self) -> bool:
        """改动全局数据的命令是否需要管理员权限（默认是）。"""
        return self.settings.admin_only_writes

    # ---------- panel-editable help text ----------

    def help_text(self) -> str:
        """HELP_TEXT with the panel override and the panel entry hint applied."""
        return self._render_help(self.settings.help_text, DEFAULT_HELP_TEXT)

    def card_help_text(self) -> str:
        """CARD_HELP with the panel override and the panel entry hint applied."""
        return self._render_help(self.settings.card_help_text, DEFAULT_CARD_HELP_TEXT)

    def _render_help(self, override: str, fallback: str) -> str:
        body = override.strip() if override and override.strip() else fallback
        body = render_template(body, plugin_version=PLUGIN_VERSION)
        if self.settings.expose_panel_hint and PANEL_HINT.strip() not in body:
            body = body.rstrip() + PANEL_HINT
        return body

    def _session_id(self, event: AstrMessageEvent) -> str:
        return str(
            getattr(event, "unified_msg_origin", None)
            or event.get_session_id()
            or "default"
        )

    def _is_group_event(self, event: AstrMessageEvent) -> bool:
        """群聊判定：优先 UMO，其次消息对象上的 group_id。"""
        if is_group_session(self._session_id(event)):
            return True
        obj = getattr(event, "message_obj", None)
        return bool(getattr(obj, "group_id", None)) if obj is not None else False

    def _message_text(self, event: AstrMessageEvent) -> str:
        for getter in (
            lambda: getattr(event, "message_str", None),
            lambda: (
                event.get_message_str() if hasattr(event, "get_message_str") else None
            ),
            lambda: getattr(event, "message_str", ""),
        ):
            try:
                val = getter()
            except Exception:
                val = None
            if val:
                return str(val).strip()
        return ""

    def _extract_tail(
        self, event: AstrMessageEvent, text: Any, names: list[str]
    ) -> str:
        """取指令之后的整段参数。

        兼容两种情况：
        1) GreedyStr 正常注入整段 → 直接用；
        2) 某些 AstrBot 版本只把第一个词喂进来（导致「角色卡 导入安安」被截成「角色卡」）
           → 再按整句消息解析一遍，取更长的那份。
        """
        injected = str(text or "").strip()
        fallback = self._tail_from_message(event, names)
        if len(fallback) > len(injected):
            return fallback
        return injected or fallback

    def _tail_from_message(self, event: AstrMessageEvent, names: list[str]) -> str:
        """从整句消息里剥离 @bot 前缀与指令名，返回其后的参数（最长指令名优先）。"""
        msg = self._message_text(event)
        if not msg:
            return ""
        msg = re.sub(r"^@\S+\s*", "", msg).strip()
        msg = re.sub(r"^[/／!！]+", "", msg).strip()
        for name in sorted(names, key=len, reverse=True):
            if msg == name:
                return ""
            if msg.startswith(name):
                return msg[len(name) :].strip()
        return msg

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """写操作权限判断；admin_only_writes=false 时不限制。"""
        if not self.admin_only_writes:
            return True
        checker = getattr(event, "is_admin", None)
        if callable(checker):
            try:
                if checker():
                    return True
            except Exception:
                logger.debug("worldbook: event.is_admin() failed", exc_info=True)
        role = str(getattr(event, "role", "") or "").strip().lower()
        return role in {"admin", "administrator", "owner", "master", "管理员", "群主"}

    def _resolve_book(self, name_or_id: str) -> WorldBook | None:
        text = str(name_or_id or "").strip()
        if not text:
            return None
        book = self.store.get_book(text)
        if book:
            return book
        return self.store.find_book_by_name(text)

    # ---------- commands ----------

    async def cmd_apply_anan(self, event: AstrMessageEvent):
        """快捷：应用夏目安安角色卡"""
        result = await self._cmd_card_apply(event, self.settings.default_card_name)
        yield event.plain_result(result)
        try:
            event.stop_event()
        except Exception:
            pass

    async def cmd_import_anan(self, event: AstrMessageEvent):
        """快捷：重新导入内置夏目安安角色卡（含群聊适配层）"""
        if not self._is_admin(event):
            yield event.plain_result(ADMIN_DENIED_TEXT)
            return
        result = self._cmd_card_import_anan()
        yield event.plain_result(result)
        try:
            event.stop_event()
        except Exception:
            pass

    async def cmd_worldbook(self, event: AstrMessageEvent, text: GreedyStr = ""):
        """世界书：导入设定并按场景/关键词注入提示词"""
        raw = self._extract_tail(
            event,
            text,
            ["群间世界", "dworld", "世界书", "worldbook", "wb", "lorebook"],
        )
        # 兼容：/群间世界应用安安 无空格
        if not raw and "应用安安" in self._message_text(event):
            raw = "应用安安"
        if not raw:
            yield event.plain_result(self.help_text())
            return

        parts = raw.split(None, 1)
        action = parts[0].strip().lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # normalize common aliases
        action_map = {
            "help": "帮助",
            "list": "列表",
            "ls": "列表",
            "new": "新建",
            "create": "新建",
            "enable": "启用",
            "disable": "禁用",
            "del": "删除",
            "delete": "删除",
            "rm": "删除",
            "import": "导入",
            "detail": "详情",
            "info": "详情",
            "status": "状态",
            "on": "开",
            "off": "关",
            "scenario": "场景",
            "bind": "绑定",
            "unbind": "解绑",
            "应用安安": "应用安安",
            "安安": "应用安安",
            "card": "角色卡",
        }
        action = action_map.get(action, action)

        if action in ADMIN_ACTIONS and not self._is_admin(event):
            yield event.plain_result(ADMIN_DENIED_TEXT)
            return

        # 兼容整段：角色卡应用夏目安安（无空格）
        if action.startswith("角色卡") and action != "角色卡":
            arg = (action[3:] + (" " + arg if arg else "")).strip()
            action = "角色卡"
        if action in {"应用安安", "安安"}:
            yield event.plain_result(
                await self._cmd_card_apply(event, self.settings.default_card_name)
            )
            return

        if action in {"帮助", "?", "？"}:
            yield event.plain_result(self.help_text())
            return

        if action == "列表":
            yield event.plain_result(self._cmd_list())
            return

        if action == "新建":
            yield event.plain_result(self._cmd_create(arg))
            return

        if action == "启用":
            yield event.plain_result(self._cmd_set_enabled(arg, True))
            return

        if action == "禁用":
            yield event.plain_result(self._cmd_set_enabled(arg, False))
            return

        if action == "删除":
            yield event.plain_result(self._cmd_delete(arg))
            return

        if action == "详情":
            yield event.plain_result(self._cmd_detail(arg))
            return

        if action == "导入示例":
            yield event.plain_result(self._cmd_import_sample())
            return

        if action == "导入":
            yield event.plain_result(self._cmd_import(arg))
            return

        if action in {"加条", "添加条目", "add"}:
            yield event.plain_result(self._cmd_add_entry(arg, constant=False))
            return

        if action in {"加常驻", "常驻"}:
            yield event.plain_result(self._cmd_add_entry(arg, constant=True))
            return

        if action in {"删条", "删除条目"}:
            yield event.plain_result(self._cmd_del_entry(arg))
            return

        if action == "场景":
            yield event.plain_result(self._cmd_scenario(event, arg))
            return

        if action == "场景列表":
            yield event.plain_result(self._cmd_scenario_list(arg))
            return

        if action == "开":
            self.store.update_session(self._session_id(event), enabled=True)
            yield event.plain_result("✅ 本会话已开启世界书注入")
            return

        if action == "关":
            self.store.update_session(self._session_id(event), enabled=False)
            yield event.plain_result("⏸️ 本会话已关闭世界书注入")
            return

        if action == "状态":
            yield event.plain_result(self._cmd_status(event))
            return

        if action == "绑定":
            yield event.plain_result(self._cmd_bind(event, arg))
            return

        if action == "解绑":
            self.store.update_session(self._session_id(event), book_ids=[])
            yield event.plain_result("✅ 已解除本会话书籍绑定，将使用全部已启用世界书")
            return

        if action in {"角色卡", "卡片", "card", "persona", "人物卡"}:
            result = await self._cmd_card(event, arg)
            yield event.plain_result(result)
            return

        yield event.plain_result(f"未知子命令：{action}\n发送 /群间世界 查看帮助")

    def _cmd_list(self) -> str:
        books = self.store.list_books()
        if not books:
            return (
                "暂无世界书。可用：\n/群间世界 导入示例\n/群间世界 导入 <名称> <JSON>"
            )
        lines = ["📚 世界书列表："]
        for b in books:
            flag = "🟢" if b.enabled else "⚪"
            lines.append(
                f"{flag} {b.name}  id={b.id}  条目={len(b.entries)}  "
                f"场景={','.join(b.list_scenarios()) or '无'}"
            )
        return "\n".join(lines)

    def _cmd_create(self, name: str) -> str:
        name = str(name or "").strip() or f"世界书-{new_uid()[:6]}"
        if self.store.find_book_by_name(name):
            return f"已存在同名世界书：{name}"
        book = WorldBook(id=new_uid(), name=name, entries=[])
        self.store.upsert_book(book)
        return f"✅ 已新建世界书「{book.name}」(id={book.id})"

    def _cmd_set_enabled(self, name: str, enabled: bool) -> str:
        book = self._resolve_book(name)
        if not book:
            return f"未找到世界书：{name}"
        self.store.set_book_enabled(book.id, enabled)
        return f"{'✅ 已启用' if enabled else '⏸️ 已禁用'}世界书「{book.name}」"

    def _cmd_delete(self, name: str) -> str:
        book = self._resolve_book(name)
        if not book:
            return f"未找到世界书：{name}"
        self.store.delete_book(book.id)
        return f"🗑️ 已删除世界书「{book.name}」"

    def _cmd_detail(self, name: str) -> str:
        book = self._resolve_book(name)
        if not book:
            return f"未找到世界书：{name or '（请填写名称）'}"
        lines = [
            f"📖 {book.name} ({book.id})",
            f"启用: {'是' if book.enabled else '否'} | 自动场景: {'是' if book.auto_scenario else '否'}",
            f"描述: {book.description or '无'}",
            f"场景标签: {', '.join(book.list_scenarios()) or '无'}",
            f"条目 ({len(book.entries)})：",
        ]
        for e in sorted(book.entries, key=lambda x: (-x.priority, x.display_name())):
            flag = "📌" if e.constant else "🔑"
            if not e.enabled:
                flag = "⛔"
            keys = ",".join(e.keys[:5]) if e.keys else "-"
            sc = ",".join(e.scenarios) if e.scenarios else "-"
            lines.append(
                f"  {flag} [{e.uid}] {e.display_name()} | keys={keys} | 场景={sc} | P={e.priority}"
            )
            if e.behavior:
                lines.append(f"     行为: {e.behavior[:80]}")
        return "\n".join(lines)

    def _cmd_import_sample(self) -> str:
        """导入通用海边小镇示例；作品预设由安装引导明确选择。"""
        candidates = [
            (
                os.path.join(PLUGIN_DIR, "samples", "sample_worldbook.json"),
                "示例：海边小镇",
            ),
        ]
        sample_path = ""
        default_name = ""
        for path, name in candidates:
            if os.path.exists(path):
                sample_path, default_name = path, name
                break
        if not sample_path:
            return "示例文件不存在"
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                raw = f.read()
            book = import_worldbook(raw, default_name=default_name)
            existing = self.store.find_book_by_name(book.name)
            if existing:
                book.id = existing.id
            else:
                for b in self.store.list_books():
                    if "魔女审判" in b.name or "魔裁" in b.name:
                        book.id = b.id
                        break
            book.enabled = True
            self.store.upsert_book(book)
            self.store.set_global_active_books([book.id])
            tips = (
                "试试聊到：艾玛 / 希罗 / 魔女裁判 / 牢屋敷 / 狱长"
                if "魔女" in book.name or "魔裁" in book.name
                else "试试聊到：咖啡馆 / 海边 / 暴风雨 / 集市"
            )
            return (
                f"✅ 已导入世界书「{book.name}」共 {len(book.entries)} 条\n"
                f"场景: {', '.join(book.list_scenarios()) or '无'}\n"
                f"{tips}"
            )
        except Exception as e:
            logger.exception("import sample failed")
            return f"导入示例失败：{e}"

    def _cmd_import(self, arg: str) -> str:
        arg = str(arg or "").strip()
        if not arg:
            return "用法：/群间世界 导入 <名称> <JSON或文本>\n或：/群间世界 导入示例"
        # name + payload: first token name if payload looks like json/text block
        name = ""
        payload = arg
        # if starts with { or [ or # treat whole as payload
        if arg[0] not in "{[#" and "\n" not in arg[:80]:
            parts = arg.split(None, 1)
            if len(parts) == 2:
                name, payload = parts[0], parts[1]
            else:
                return "请提供导入内容。格式：/群间世界 导入 <名称> <内容>"
        try:
            book = import_worldbook(payload, default_name=name or "导入的世界书")
            if name:
                book.name = name
            existing = self.store.find_book_by_name(book.name)
            if existing:
                book.id = existing.id
                # merge? replace entries for simplicity when same name re-import
            self.store.upsert_book(book)
            return (
                f"✅ 已导入世界书「{book.name}」(id={book.id})\n"
                f"条目 {len(book.entries)} 个，场景: {', '.join(book.list_scenarios()) or '无'}"
            )
        except Exception as e:
            logger.exception("import worldbook failed")
            return f"导入失败：{e}"

    def _cmd_add_entry(self, arg: str, *, constant: bool) -> str:
        """加条: 书名 | 名称 | 关键词 | 场景 | 行为 | 内容
        加常驻: 书名 | 名称 | 内容
        """
        parts = [p.strip() for p in re.split(r"\s*\|\s*", str(arg or "").strip())]
        if constant:
            if len(parts) < 3:
                return "用法：/群间世界 加常驻 书名 | 名称 | 内容"
            book_name, name, content = parts[0], parts[1], parts[2]
            keys, scenarios, behavior = [], [], ""
            if len(parts) > 3:
                content = " | ".join(parts[2:])
        else:
            if len(parts) < 6:
                return (
                    "用法：/群间世界 加条 书名 | 名称 | 关键词 | 场景 | 行为 | 内容\n"
                    "关键词/场景可用逗号分隔；不需要可写 -"
                )
            book_name, name, keys_s, sc_s, behavior = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                parts[4],
            )
            content = " | ".join(parts[5:]) if len(parts) > 5 else ""
            keys = (
                []
                if keys_s in {"-", "无", ""}
                else [x.strip() for x in re.split(r"[,，/]+", keys_s) if x.strip()]
            )
            scenarios = (
                []
                if sc_s in {"-", "无", ""}
                else [x.strip() for x in re.split(r"[,，/]+", sc_s) if x.strip()]
            )

        book = self._resolve_book(book_name)
        if not book:
            return f"未找到世界书：{book_name}"
        entry = WorldEntry(
            uid=new_uid(),
            name=name,
            keys=keys,
            scenarios=scenarios,
            behavior=behavior if behavior not in {"-", "无"} else "",
            content=content,
            constant=constant,
        )
        self.store.add_entry(book.id, entry)
        return f"✅ 已向「{book.name}」添加条目 [{entry.uid}] {entry.display_name()}"

    def _cmd_del_entry(self, arg: str) -> str:
        parts = str(arg or "").split()
        if len(parts) < 2:
            return "用法：/群间世界 删条 <书名> <条目ID>"
        book = self._resolve_book(parts[0])
        if not book:
            return f"未找到世界书：{parts[0]}"
        uid = parts[1]
        if self.store.remove_entry(book.id, uid):
            return f"🗑️ 已删除条目 {uid}"
        return f"未找到条目 {uid}"

    def _cmd_scenario(self, event: AstrMessageEvent, arg: str) -> str:
        sid = self._session_id(event)
        state = self.store.get_session(sid)
        arg = str(arg or "").strip()
        if not arg:
            return (
                f"当前会话场景：{state.scenario or '（未设置，将尝试关键词自动识别）'}"
            )

        parts = arg.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in {"设置", "set", "切换", "to"}:
            if not rest:
                return "用法：/群间世界 场景 设置 <场景名>"
            self.store.set_scenario(sid, rest)
            return (
                f"🎬 场景已锁定为「{rest}」——只注入该场景相关条目；"
                "发送 /群间世界 场景 清除 可恢复自动识别"
            )
        if sub in {"清除", "clear", "reset", "无"}:
            self.store.clear_scenario(sid)
            return "🎬 已清除场景，恢复关键词自动匹配"
        # bare name = set
        self.store.set_scenario(sid, arg)
        return f"🎬 场景已设置为「{arg}」"

    def _cmd_scenario_list(self, name: str) -> str:
        if not name:
            books = self.store.list_books()
            all_sc: set[str] = set()
            for b in books:
                all_sc.update(b.list_scenarios())
            return "全部场景标签：" + ("、".join(sorted(all_sc)) if all_sc else "无")
        book = self._resolve_book(name)
        if not book:
            return f"未找到世界书：{name}"
        sc = book.list_scenarios()
        return f"「{book.name}」场景：{('、'.join(sc) if sc else '无')}"

    def _cmd_bind(self, event: AstrMessageEvent, arg: str) -> str:
        names = [x for x in str(arg or "").split() if x.strip()]
        if not names:
            return "用法：/群间世界 绑定 <书名1> [书名2...]"
        ids: list[str] = []
        labels: list[str] = []
        for n in names:
            book = self._resolve_book(n)
            if not book:
                return f"未找到世界书：{n}"
            ids.append(book.id)
            labels.append(book.name)
        self.store.update_session(self._session_id(event), book_ids=ids)
        return f"✅ 本会话已绑定：{', '.join(labels)}"

    # ---------- character cards ----------

    def _resolve_card(self, name_or_id: str) -> CharacterCard | None:
        text = str(name_or_id or "").strip()
        if not text:
            return None
        card = self.store.get_card(text)
        if card:
            return card
        return self.store.find_card_by_name(text)

    async def _cmd_card(self, event: AstrMessageEvent, arg: str) -> str:
        raw = str(arg or "").strip()
        # 兼容无空格：应用夏目安安 / 应用安安
        if not raw:
            return self.card_help_text()
        compact = re.sub(r"\s+", "", raw)
        if compact in {"应用安安", "应用夏目安安", "安安"}:
            return await self._cmd_card_apply(event, "夏目安安")
        if compact.startswith("应用") and "安安" in compact:
            return await self._cmd_card_apply(event, "夏目安安")

        parts = raw.split(None, 1)
        sub = parts[0].strip().lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        # 无空格：应用夏目安安
        if sub.startswith("应用") and len(sub) > 2 and not rest:
            rest = sub[2:]
            sub = "应用"
        sub_map = {
            "list": "列表",
            "ls": "列表",
            "import": "导入",
            "detail": "详情",
            "info": "详情",
            "group": "群聊",
            "groupchat": "群聊",
            "群聊规则": "群聊",
            "use": "应用",
            "wear": "应用",
            "remove": "卸下",
            "clear": "卸下",
            "delete": "删除",
            "del": "删除",
            "export": "导出",
            "default": "设默认",
            "setdefault": "设默认",
            "anan": "导入安安",
        }
        sub = sub_map.get(sub, sub)

        if sub in ADMIN_CARD_ACTIONS and not self._is_admin(event):
            return ADMIN_DENIED_TEXT

        if sub in {"帮助", "help", "?", "？"}:
            return self.card_help_text()
        if sub == "列表":
            return self._cmd_card_list()
        if sub == "导入安安":
            return self._cmd_card_import_anan()
        if sub == "导入":
            return self._cmd_card_import(rest)
        if sub == "详情":
            return self._cmd_card_detail(rest)
        if sub == "群聊":
            return self._cmd_card_group(event, rest)
        if sub == "应用":
            name = rest or "夏目安安"
            if name in {"安安", "默认"}:
                name = "夏目安安"
            return await self._cmd_card_apply(event, name)
        if sub == "设默认":
            return self._cmd_card_set_default(rest or "夏目安安")
        if sub == "卸下":
            return await self._cmd_card_unequip(event)
        if sub == "删除":
            return self._cmd_card_delete(rest)
        if sub == "导出":
            return self._cmd_card_export(rest)
        # 兜底：整段当角色名应用
        if self._resolve_card(raw):
            return await self._cmd_card_apply(event, raw)
        return f"未知角色卡子命令：{sub}\n{self.card_help_text()}"

    def _cmd_card_group(self, event: AstrMessageEvent, arg: str) -> str:
        """群聊适配层：查看 / 设置 / 清除 / 预览。只在群聊会话注入。"""
        sid = self._session_id(event)
        card = self.store.resolve_session_card(sid) or self.store.get_card(
            self.store.get_default_card_id()
        )
        if not card:
            return "未找到角色卡。先发送：/群间世界 角色卡 导入安安"
        arg = str(arg or "").strip()
        body = (card.group_addendum or "").strip()
        if not arg:
            state = (
                "是群聊，适配层生效"
                if self._is_group_event(event)
                else "不是群聊，适配层不注入"
            )
            preview = body if len(body) <= 300 else body[:300] + "…"
            return "\n".join(
                [
                    f"🃏 {card.name} · 群聊适配层",
                    f"本会话判定：{state}",
                    f"长度：{len(body)} 字",
                    "—— 内容预览 ——",
                    preview or "（空：群聊中不额外注入任何规则）",
                    "用法：/群间世界 角色卡 群聊 [设置 <文本> | 清除 | 预览]",
                ]
            )
        parts = arg.split(None, 1)
        sub = parts[0].strip().lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in {"预览", "preview", "show"}:
            block = card.build_system_prompt(include_group_addendum=True)
            idx = block.find("【群聊适配层")
            return block[idx:] if idx >= 0 else "（适配层为空）"
        if sub in {"清除", "清空", "clear", "reset", "删除"}:
            card.group_addendum = ""
            self.store.upsert_card(card)
            return f"🧹 已清除「{card.name}」的群聊适配层（群聊只注入基础卡）"
        if sub in {"设置", "set", "写入"}:
            if not rest:
                return "用法：/群间世界 角色卡 群聊 设置 <文本>"
            card.group_addendum = rest
            self.store.upsert_card(card)
            return (
                f"✅ 已设置「{card.name}」的群聊适配层（{len(rest)} 字）\n"
                "仅群聊会话注入；单聊沿用基础卡，不受影响。"
            )
        card.group_addendum = arg
        self.store.upsert_card(card)
        return f"✅ 已设置「{card.name}」的群聊适配层（{len(arg)} 字）"

    def _cmd_card_list(self) -> str:
        cards = self.store.list_cards()
        if not cards:
            return "暂无角色卡。发送：/群间世界 角色卡 导入安安"
        default_id = self.store.get_default_card_id()
        lines = ["🃏 角色卡列表："]
        for c in cards:
            flag = "⭐默认 " if c.id == default_id else ""
            tags = ",".join(c.tags[:4]) if c.tags else "-"
            lines.append(
                f"• {flag}{c.name}  id={c.id}  persona={c.persona_id or '未同步'}  tags={tags}"
            )
        lines.append("快捷应用：/应用安安")
        return "\n".join(lines)

    def _cmd_card_import_anan(self) -> str:
        card_name = self.settings.default_card_name
        path = os.path.join(PLUGIN_DIR, "..", "presets", "manosaba", "character.json")
        if not os.path.exists(path):
            return "内置角色卡文件不存在"
        try:
            with open(path, "r", encoding="utf-8") as f:
                card = import_character_card(f.read(), default_name=card_name)
            existing = self.store.find_card_by_name(card_name)
            if existing:
                card.id = existing.id
                card.persona_id = existing.persona_id
                card.group_addendum = card.group_addendum or existing.group_addendum
            book = self.store.find_book_by_name(self.settings.seed_worldbook_name)
            if book:
                card.linked_book_id = book.id
            self.store.upsert_card(card)
            self.store.set_default_card(card.id)
            return (
                f"✅ 已导入角色卡「{card.name}」(id={card.id})，并设为默认\n"
                f"立即扮演：/群间世界 角色卡 应用 {card.name}"
            )
        except Exception as e:
            logger.exception("import anan card failed")
            return f"导入失败：{e}"

    def _cmd_card_set_default(self, name: str) -> str:
        card = self._resolve_card(name)
        if not card:
            return f"未找到角色卡：{name}"
        self.store.set_default_card(card.id)
        return f"✅ 已将全局默认角色卡设为「{card.name}」（新会话自动生效）"

    def _cmd_card_import(self, arg: str) -> str:
        arg = str(arg or "").strip()
        if not arg:
            return "用法：/群间世界 角色卡 导入 <名称> <JSON>\n或：/群间世界 角色卡 导入安安"
        name = ""
        payload = arg
        if arg[0] not in "{[":
            parts = arg.split(None, 1)
            if len(parts) == 2:
                name, payload = parts[0], parts[1]
            else:
                return "请提供角色卡 JSON 内容"
        try:
            card = import_character_card(payload, default_name=name or "导入角色")
            if name:
                card.name = name
            existing = self.store.find_card_by_name(card.name)
            if existing:
                card.id = existing.id
                card.persona_id = existing.persona_id
                card.group_addendum = card.group_addendum or existing.group_addendum
            # 内嵌 character_book → 世界书
            wb = character_book_to_worldbook(card)
            if wb is not None:
                old = self.store.find_book_by_name(wb.name)
                if old:
                    wb.id = old.id
                self.store.upsert_book(wb)
                card.linked_book_id = wb.id
            self.store.upsert_card(card)
            extra = f"\n已同步角色书「{wb.name}」" if wb is not None else ""
            return f"✅ 已导入角色卡「{card.name}」(id={card.id}){extra}"
        except Exception as e:
            logger.exception("import card failed")
            return f"导入失败：{e}"

    def _cmd_card_detail(self, name: str) -> str:
        card = self._resolve_card(name)
        if not card:
            return f"未找到角色卡：{name or '（请填写名称）'}"
        prompt = card.build_system_prompt()
        preview = prompt if len(prompt) <= 900 else prompt[:900] + "…"
        lines = [
            f"🃏 {card.name} ({card.id})",
            f"tags: {', '.join(card.tags) or '无'}",
            f"persona_id: {card.persona_id or '未同步'}",
            f"linked_book: {card.linked_book_id or '无'}",
            f"group_addendum: {'有 ' + str(len(card.group_addendum)) + ' 字' if card.group_addendum else '无'}",
            f"first_mes: {(card.first_mes[:120] + '…') if len(card.first_mes) > 120 else (card.first_mes or '无')}",
            "—— 系统提示预览 ——",
            preview,
        ]
        return "\n".join(lines)

    def _cmd_card_delete(self, name: str) -> str:
        card = self._resolve_card(name)
        if not card:
            return f"未找到角色卡：{name}"
        self.store.delete_card(card.id)
        return f"🗑️ 已删除角色卡「{card.name}」"

    def _cmd_card_export(self, name: str) -> str:
        card = self._resolve_card(name)
        if not card:
            return f"未找到角色卡：{name}"
        import json as _json

        payload = _json.dumps(card.to_tavern_v2(), ensure_ascii=False, indent=2)
        # 聊天里不宜过长
        if len(payload) > 3500:
            return (
                f"「{card.name}」酒馆 V2 JSON 过长（{len(payload)} 字），"
                f"完整文件见 samples/characters/ 或插件数据目录。\n"
                f"开头预览：\n{payload[:1500]}…"
            )
        return f"「{card.name}」酒馆 V2：\n{payload}"

    async def _cmd_card_apply(self, event: AstrMessageEvent, name: str) -> str:
        # 自动补种，避免“未找到”
        if name in {"夏目安安", "安安", ""}:
            if not self.store.find_card_by_name("夏目安安"):
                self._ensure_anan_card_seeded()
            name = "夏目安安"
        card = self._resolve_card(name)
        if not card:
            return (
                f"未找到角色卡：{name or '（请填写名称）'}\n"
                "请先：/群间世界 角色卡 导入安安"
            )
        sid = self._session_id(event)
        logger.info("worldbook apply card=%s session=%s", card.name, sid)

        # 关联世界书自动绑定
        book_ids = list(self.store.get_session(sid).book_ids)
        mocai = self.store.find_book_by_name("魔法少女的魔女审判 世界书")
        if card.linked_book_id:
            if card.linked_book_id not in book_ids:
                book_ids = [card.linked_book_id] + [
                    x for x in book_ids if x != card.linked_book_id
                ]
        elif mocai:
            book_ids = [mocai.id] + [x for x in book_ids if x != mocai.id]
            card.linked_book_id = mocai.id
            self.store.upsert_card(card)

        # 始终启用插件侧注入（人格同步不可靠时也能扮演）
        self.store.update_session(
            sid,
            card_id=card.id,
            book_ids=book_ids,
            enabled=True,
            inject_card_prompt=True,
        )
        # 同步设为全局默认，避免其它会话掉回空；非管理员只影响自己的会话
        if self._is_admin(event):
            self.store.set_default_card(card.id)

        persona_msg = await self._sync_persona(card)
        persona_bind_msg = await self._bind_session_persona(
            event, card.persona_id or slug_persona_id(card.name)
        )

        first = (
            (card.first_mes[:200] + "…")
            if len(card.first_mes) > 200
            else card.first_mes
        )
        lines = [
            f"✅ 已应用角色卡「{card.name}」",
            f"会话：{sid}",
            f"注入：开启（mode={self.inject_mode}）",
            persona_msg,
            persona_bind_msg,
        ]
        if book_ids:
            names = []
            for bid in book_ids:
                b = self.store.get_book(bid)
                names.append(b.name if b else bid)
            lines.append("世界书绑定：" + "、".join(names))
        if first:
            lines.append("—— 开场参考 ——\n" + first)
        lines.append("可用 /群间世界 状态 确认；卸下：/群间世界 角色卡 卸下")
        return "\n".join(lines)

    async def _cmd_card_unequip(self, event: AstrMessageEvent) -> str:
        sid = self._session_id(event)
        # 明确关闭，避免回落到全局默认安安
        self.store.update_session(
            sid, card_id=SESSION_CARD_NONE, inject_card_prompt=False
        )
        return (
            "✅ 已卸下本会话角色卡（不再使用默认安安）。\n"
            "世界书注入仍保留。重新启用：/应用安安"
        )

    async def _sync_persona(self, card: CharacterCard) -> str:
        """创建/更新 AstrBot 人格。"""
        pm = getattr(self.context, "persona_manager", None)
        if pm is None:
            return "⚠️ 当前环境无 persona_manager，将仅用插件侧注入角色提示词"
        persona_id = card.persona_id or slug_persona_id(card.name)
        prompt = card.build_system_prompt()
        begin = card.build_begin_dialogs()
        try:
            try:
                await pm.get_persona(persona_id)
                exists = True
            except Exception:
                exists = False
            if exists:
                await pm.update_persona(
                    persona_id=persona_id,
                    system_prompt=prompt,
                    begin_dialogs=begin or None,
                )
                card.persona_id = persona_id
                self.store.upsert_card(card)
                return f"人格已更新：{persona_id}"
            await pm.create_persona(
                persona_id=persona_id,
                system_prompt=prompt,
                begin_dialogs=begin or None,
            )
            card.persona_id = persona_id
            self.store.upsert_card(card)
            return f"人格已创建：{persona_id}"
        except Exception as e:
            logger.warning("sync persona failed: %s", e, exc_info=True)
            return f"⚠️ 同步人格失败（仍会插件注入）：{e}"

    async def _bind_session_persona(
        self, event: AstrMessageEvent, persona_id: str
    ) -> str:
        if not persona_id:
            return "未绑定会话人格（将依赖插件注入）"
        umo = self._session_id(event)
        try:
            from astrbot.api import sp

            cfg = (
                await sp.get_async(
                    scope="umo", scope_id=umo, key="session_service_config", default={}
                )
                or {}
            )
            if not isinstance(cfg, dict):
                cfg = {}
            cfg["persona_id"] = persona_id
            await sp.put_async(
                scope="umo", scope_id=umo, key="session_service_config", value=cfg
            )
            return f"会话人格已切换：{persona_id}"
        except Exception as e:
            # fallback: conversation branch
            try:
                conv_mgr = self.context.conversation_manager
                cid = await conv_mgr.get_curr_conversation_id(umo)
                if cid:
                    await conv_mgr.update_conversation(
                        umo, conversation_id=cid, persona_id=persona_id
                    )
                    return f"对话分支人格已切换：{persona_id}"
            except Exception as e2:
                logger.warning("bind persona failed: %s / %s", e, e2)
            return f"⚠️ 会话人格绑定失败（仍会插件注入）：{e}"

    def _cmd_status(self, event: AstrMessageEvent) -> str:
        sid = self._session_id(event)
        state = self.store.get_session(sid)
        books = self.store.get_active_books_for_session(sid)
        card = self.store.resolve_session_card(sid)
        default_id = self.store.get_default_card_id()
        default_card = self.store.get_card(default_id) if default_id else None
        if state.card_id == SESSION_CARD_NONE:
            card_label = "（本会话已关闭）"
        elif state.card_id:
            card_label = card.name if card else f"（丢失 id={state.card_id}）"
        else:
            card_label = f"{card.name}（全局默认）" if card else "（无）"
        lines = [
            "📊 世界书会话状态",
            f"全局开关: {'开' if self.inject_enabled_global else '关'}",
            f"本会话: {'开' if state.enabled else '关'}",
            f"当前场景: {state.scenario or '（未锁定，按关键词自动识别）'}",
            f"自动识别场景: {state.scenario_auto or '无'}",
            f"角色卡: {card_label}",
            f"角色注入: {'开' if (state.inject_card_prompt and state.card_id != SESSION_CARD_NONE) else '关'}",
            f"群聊适配层: {'开' if (card and card.group_addendum and is_group_session(sid)) else '关'}",
            f"全局默认卡: {default_card.name if default_card else '（无）'}",
            f"生效书籍: {', '.join(b.name for b in books) or '无'}",
            f"注入方式: {self.inject_mode} | 最多条目: {self.max_entries}",
        ]
        if state.book_ids:
            lines.append(f"会话绑定: {', '.join(state.book_ids)}")
        if self.show_debug_in_status:
            lines.append(f"最近命中: {', '.join(state.last_matched) or '无'}")
            if state.last_inject_preview:
                preview = state.last_inject_preview
                if len(preview) > 600:
                    preview = preview[:600] + "…"
                lines.append("最近注入预览:\n" + preview)
        return "\n".join(lines)

    # ---------- LLM inject ----------

    async def get_character_context(
        self, scope: dict[str, Any], event: Any = None
    ) -> dict[str, Any]:
        """Read the authoritative, scoped character material for one turn.

        Args:
            scope: Platform, full UMO, persona ID, and instance ID supplied by
                the coordinator. Effective character IDs are returned separately.
            event: Original message event, event envelope, or plain query text.
                Assembled provider prompts and arbitrary JSON are never scanned.

        Returns:
            Versioned plain data with detached source items and a content hash.
            Disabled bindings are explicit and must not trigger persona fallback.
        """
        self._refresh_settings()
        incoming = scope if isinstance(scope, dict) else {}
        sid = str(incoming.get("umo") or "").strip()
        result: dict[str, Any] = {
            "schema_version": 1,
            "available": False,
            "disabled": False,
            "scope": {
                "platform": str(incoming.get("platform") or sid.split(":", 1)[0]),
                "umo": sid,
                "persona_id": "",
                "instance_id": "",
            },
            "persona_id": "",
            "instance_id": "",
            "card_id": "",
            "name": "",
            "fingerprint": "",
            "core_prompt": "",
            "group_rules": "",
            "world_items": [],
            "world_prompt": "",
            "scenario": "",
            "source_ids": [],
        }
        raw_text, event_sid = self._character_event_text(event)
        if event_sid and event_sid != sid:
            result["reason"] = "scope_mismatch"
            return result
        if sid:
            state, card, books = self.store.snapshot_context_inputs(sid)
        else:
            # Background life ticks may read the persona's own setting only.
            # Never accept raw chat events or session-specific world selections.
            if event is not None:
                result["reason"] = "global_event_not_allowed"
                return result
            if not str(incoming.get("persona_id") or "").strip():
                result["reason"] = "missing_scope"
                return result
            state, card, books = self.store.snapshot_global_character_inputs(
                str(incoming["persona_id"])
            )
        if (
            not self.settings.enabled
            or not state.enabled
            or not state.inject_card_prompt
            or state.card_id == SESSION_CARD_NONE
        ):
            result["disabled"] = True
            result["reason"] = "character_disabled"
            return result
        if card is None:
            result["reason"] = "no_character"
            return result

        # Cards without a host persona have a deterministic identity until sync.
        persona_id = card.persona_id or f"wb_{card.id}"
        instance_id = persona_id
        if str(incoming.get("persona_id") or "") == persona_id:
            instance_id = str(incoming.get("instance_id") or persona_id)
        resolved_scope = {
            **result["scope"],
            "persona_id": persona_id,
            "instance_id": instance_id,
        }
        core_prompt = card.build_system_prompt(include_world_hint=True)
        # Change the task perspective in returned material, never the stored card.
        core_prompt = core_prompt.replace(
            "严格以第一人称角色扮演", "对外表达采用角色视角"
        )
        group_rules = card.group_addendum.strip() if is_group_session(sid) else ""
        matches = match_entries(
            books,
            raw_text,
            active_scenario=state.scenario.strip(),
            max_entries=self.settings.max_entries,
            allow_auto_scenario=self.settings.auto_scenario,
            dedupe_same_content=self.settings.dedupe_same_content,
        )
        scenario = state.scenario.strip() or matches.auto_scenario
        source_ids = [f"worldbook:card:{card.id}"]
        if group_rules:
            source_ids.append(f"worldbook:card:{card.id}:group")
        world_items = []
        for matched in matches.matched:
            entry = matched.entry
            source_id = f"worldbook:book:{matched.book.id}:entry:{entry.uid}"
            lines = [entry.display_name()]
            if entry.scenarios:
                lines.append(f"适用场景：{', '.join(entry.scenarios)}")
            if entry.behavior:
                lines.append(f"行为指引：{entry.behavior}")
            if entry.content:
                lines.append(entry.content)
            world_items.append(
                {
                    "text": "\n".join(lines),
                    "source_id": source_id,
                    "occurred_at": matched.book.updated_at,
                    "scope": dict(resolved_scope),
                    "fact_kind": "world_setting",
                    "confidence": "established_setting",
                    "unknown": False,
                }
            )
            source_ids.append(source_id)
        result.update(
            {
                "available": True,
                "scope": resolved_scope,
                "persona_id": persona_id,
                "instance_id": instance_id,
                "card_id": card.id,
                "name": card.name,
                "core_prompt": core_prompt,
                "group_rules": group_rules,
                "world_items": world_items,
                "world_prompt": build_injection_text(
                    matches, active_scenario=scenario, style=self.settings
                ),
                "scenario": scenario,
                "source_ids": source_ids,
            }
        )
        material = {
            key: result[key]
            for key in (
                "persona_id",
                "instance_id",
                "card_id",
                "core_prompt",
                "group_rules",
                "world_items",
                "world_prompt",
                "scenario",
                "source_ids",
            )
        }
        result["fingerprint"] = hashlib.sha256(
            json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return result

    def _character_event_text(self, event: Any) -> tuple[str, str]:
        """Extract original message text and provenance without serializing it."""
        if event is None:
            return "", ""
        if isinstance(event, str):
            return event, ""
        if isinstance(event, dict):
            event_scope = event.get("scope")
            sid = (
                str(event_scope.get("umo") or "")
                if isinstance(event_scope, dict)
                else str(event.get("umo") or event.get("unified_msg_origin") or "")
            )
            for key in ("raw_text", "message_str", "text", "body"):
                if isinstance(event.get(key), str):
                    return event[key], sid
            # Envelopes may place text in a structured body; do not scan metadata.
            body = event.get("body")
            if isinstance(body, dict) and isinstance(body.get("text"), str):
                return body["text"], sid
            return "", sid
        sid = str(getattr(event, "unified_msg_origin", "") or "")
        return self._message_text(event), sid

    def _collect_scan_text(self, event: AstrMessageEvent, req: Any) -> str:
        """Build the text that keyword matching runs against.

        Returns:
            Current message, optionally the assembled prompt, and the tail of
            recent history limited to the roles enabled in the panel.
        """
        chunks: list[str] = []
        msg = str(getattr(event, "message_str", "") or "").strip()
        if msg:
            chunks.append(msg)
        if self.settings.scan_include_prompt:
            prompt = str(getattr(req, "prompt", None) or "").strip()
            if prompt and prompt != msg:
                chunks.append(prompt)

        # optional recent history from req.contexts
        turns = self.scan_history_turns
        roles = set(self.settings.scan_roles)
        if turns > 0:
            contexts = getattr(req, "contexts", None) or []
            if isinstance(contexts, list):
                # take last N user/assistant text snippets
                texts: list[str] = []
                for item in contexts:
                    if not isinstance(item, dict):
                        continue
                    role = item.get("role")
                    if role not in roles:
                        continue
                    content = item.get("content")
                    if isinstance(content, str):
                        t = content.strip()
                    elif isinstance(content, list):
                        parts = []
                        for p in content:
                            if isinstance(p, dict) and p.get("type") == "text":
                                parts.append(str(p.get("text") or ""))
                            elif isinstance(p, str):
                                parts.append(p)
                        t = " ".join(parts).strip()
                    else:
                        t = ""
                    if t:
                        texts.append(t)
                if texts:
                    chunks.extend(texts[-turns * 2 :])

        # active scenario name also helps matching scenario-bound constant? not needed
        return "\n".join(chunks)

    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        try:
            get_extra = getattr(event, "get_extra", None)
            if callable(get_extra) and get_extra("_narrative_managed_v1"):
                return
            blocking_context = (
                get_extra("_autonomous_blocking_context_v1", None)
                if callable(get_extra)
                else None
            )
            if (
                isinstance(blocking_context, dict)
                and blocking_context.get("schema_version") == 1
                and blocking_context.get("projection_restricted") is True
            ):
                # The core persona is already supplied by AstrBot's active persona;
                # this plugin hook adds optional session/world material.
                return
            if not self.inject_enabled_global:
                return
            sid = self._session_id(event)
            state = self.store.get_session(sid)
            if not state.enabled:
                return

            manual_scenario = state.scenario.strip()
            current_system = str(getattr(req, "system_prompt", "") or "")
            mode = self.inject_mode
            cfg_style = self.settings
            card_block = ""
            card_name = ""
            in_group = self._is_group_event(event)

            # 1) 角色卡：会话绑定 或 全局默认（卸下用 __none__ 关闭）
            card = self.store.resolve_session_card(sid)
            if card and state.card_id != SESSION_CARD_NONE and state.inject_card_prompt:
                card_name = card.name
                card_prompt = card.build_system_prompt(
                    include_world_hint=True, include_group_addendum=in_group
                )
                label = render_template(
                    cfg_style.card_label_group if in_group else cfg_style.card_label,
                    name=card.name,
                )
                # _sync_persona 写进 AstrBot 人格的是不含群聊适配层的那份；
                # 它已经在 system prompt 里时就不再重复注入整份角色卡
                persona_prompt = card.build_system_prompt(include_world_hint=True)
                if _prompt_already_in(
                    current_system,
                    persona_prompt,
                    min_chars=cfg_style.persona_skip_min_chars,
                ):
                    if in_group and card.group_addendum:
                        card_block = f"{label}\n{card.group_addendum.strip()}"
                    else:
                        logger.debug(
                            "worldbook: card prompt already injected by persona, skip card=%s",
                            card.name,
                        )
                elif card_prompt:
                    card_block = f"{label}\n{card_prompt}"
                    # 宿主人格库写失败时，旧笔谈卡可能仍在 system prompt 里；
                    # 明确覆盖，避免两套同名角色人设同时生效。
                    notice = render_template(
                        cfg_style.persona_override_notice, name=card.name
                    )
                    if notice and card.name and card.name in current_system:
                        card_block = f"{notice}\n{card_block}"
                if in_group and card.group_addendum:
                    card_name = f"{card.name}(群聊)"

            # 2) 世界书关键词/场景匹配：始终用「手动锁定的场景」匹配。
            #    自动识别的场景只影响本轮渲染与展示，不再写回 state.scenario
            #    （旧实现会把首次自动识别的场景永久锁死，导致其它场景条目再也进不来）
            wb_block = ""
            matched_uids: list[str] = []
            auto_scenario = ""
            books = self.store.get_active_books_for_session(sid)
            if books:
                scan_text = self._collect_scan_text(event, req)
                if manual_scenario:
                    scan_text = f"{scan_text}\n{manual_scenario}"
                if card_name:
                    scan_text = f"{scan_text}\n{card_name}"

                result = match_entries(
                    books,
                    scan_text,
                    active_scenario=manual_scenario,
                    max_entries=self.max_entries,
                    allow_auto_scenario=self.auto_scenario,
                    dedupe_same_content=cfg_style.dedupe_same_content,
                )
                if self.auto_scenario:
                    auto_scenario = result.auto_scenario
                if result.matched:
                    wb_block = build_injection_text(
                        result,
                        active_scenario=manual_scenario or auto_scenario,
                        style=cfg_style,
                    )
                    matched_uids = [m.entry.uid for m in result.matched]

            if wb_block or matched_uids or auto_scenario != state.scenario_auto:
                # 内容没有变化时 store.record_match 不会写盘
                self.store.record_match(
                    sid,
                    matched_uids,
                    wb_block or card_block,
                    scenario_auto=auto_scenario,
                )

            if not card_block and not wb_block:
                return

            system_add = "\n\n".join(
                part
                for part in (
                    card_block if mode in {"system", "both"} else "",
                    wb_block if mode in {"system", "both"} else "",
                )
                if part
            )
            if system_add and system_add not in current_system:
                req.system_prompt = current_system + f"\n\n{system_add}\n"

            if mode in {"extra", "both"}:
                # both 模式下角色卡已经在 system_prompt 里了，extra 只补世界书，避免重复
                extra_text = (
                    wb_block
                    if mode == "both"
                    else "\n\n".join(p for p in (card_block, wb_block) if p)
                )
                if extra_text:
                    self._append_extra_part(req, extra_text)

            logger.debug(
                "worldbook injected card=%s entries=%d scenario=%s session=%s",
                card_name or "-",
                len(matched_uids),
                manual_scenario or auto_scenario or "-",
                sid,
            )
        except Exception as e:
            logger.error("worldbook on_llm_request failed: %s", e, exc_info=True)

    def _append_extra_part(self, req: Any, text: str) -> None:
        """Prefer extra_user_content_parts; fallback to system_prompt."""
        try:
            from astrbot.core.agent.message import TextPart

            part = TextPart(text=f"\n{text}\n")
            if hasattr(part, "mark_as_temp"):
                try:
                    part.mark_as_temp()
                except Exception:
                    pass
            parts = getattr(req, "extra_user_content_parts", None)
            if parts is None:
                req.extra_user_content_parts = []
                parts = req.extra_user_content_parts
            parts.append(part)
            return
        except Exception:
            pass

        # fallback
        current = str(getattr(req, "system_prompt", "") or "")
        if text not in current:
            req.system_prompt = current + f"\n\n{text}\n"

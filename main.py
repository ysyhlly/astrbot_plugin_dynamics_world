"""One AstrBot plugin owns character, world and narrative life services."""
# ruff: noqa: E402
from __future__ import annotations

from .reload_bootstrap import ensure_current

ensure_current(
    __package__,
    __name__,
    __file__,
    version="v0.23.0",
    checks=[
        ("life.core.narrative", "NarrativeEngine", "_world_map_v1"),
        ("life.core.narrative", "NarrativeEngine", "_horizons_sync_v1"),
    ],
)

import asyncio
import copy
import json
import re
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.filter.command import GreedyStr
from astrbot.core.star.star_tools import StarTools

from .defaults import defaults
from .life.service import LifeService
from .map_service import MapService
from .migration import activate_generation, active_directory, prepare_import
from .onboarding import Onboarding
from .postcard_renderer import (
    PostcardRenderer,
    match_outfit_texture,
    parse_shot_override,
)
from .texture_resources import TextureResources
from .web_api import WorldAPI
from .world.service import WorldService


def merge_config(base, incoming):
    result = copy.deepcopy(base)
    for key, value in incoming.items():
        result[key] = merge_config(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


_MAILBOX_PREFIX_KINDS = {
    "明信片": "postcard",
    "信": "postcard",
    "卡片": "postcard",
    "postcard": "postcard",
    "鲜花": "flower",
    "花束": "flower",
    "花": "flower",
    "flower": "flower",
    "点心": "snack",
    "零食": "snack",
    "茶点": "snack",
    "甜点": "snack",
    "snack": "snack",
    "礼物": "gift",
    "纪念品": "gift",
    "小物": "gift",
    "赠礼": "gift",
    "gift": "gift",
    "书评": "book_review",
    "读后感": "book_review",
    "夹页": "book_review",
    "book_review": "book_review",
    "review": "book_review",
}

_MAILBOX_GIFT_KEYWORDS = (
    "礼物",
    "挂件",
    "书签",
    "手链",
    "项链",
    "徽章",
    "音乐盒",
    "玩偶",
    "摆件",
    "纪念",
    "发卡",
    "钥匙扣",
    "围巾",
    "钢笔",
    "小物",
    "相框",
    "胸针",
    "礼盒",
    "风铃",
)
_MAILBOX_FLOWER_KEYWORDS = (
    "花",
    "玫瑰",
    "洋甘菊",
    "薰衣草",
    "百合",
    "郁金香",
    "满天星",
    "雏菊",
    "向日葵",
    "康乃馨",
    "樱花",
)
_MAILBOX_SNACK_KEYWORDS = (
    "糕",
    "茶",
    "饼",
    "糖",
    "点心",
    "果",
    "蛋糕",
    "奶茶",
    "咖啡",
    "布丁",
    "曲奇",
    "巧克力",
    "派",
    "面包",
    "可丽饼",
    "甜甜圈",
)


def parse_mailbox_delivery(text: str) -> tuple[str, str]:
    """Parse `/投递` text into `(kind, clean_message)` with explicit first-word and keyword support."""
    content = str(text or "").strip()
    if not content:
        return "postcard", ""
    # Explicit leading category token separated by whitespace or punctuation (e.g. `礼物：...` / `鲜花 ...`).
    match = re.match(r"^([^\s:：\-—]+)(?:[\s:：\-—]+(.*))?$", content, flags=re.S)
    if match:
        head = match.group(1).strip()
        rest = (match.group(2) or "").strip()
        explicit_kind = _MAILBOX_PREFIX_KINDS.get(head.lower()) or _MAILBOX_PREFIX_KINDS.get(head)
        if explicit_kind:
            if rest:
                return explicit_kind, rest
            default_note = {
                "postcard": "寄来一张明信片",
                "flower": "送来一小束鲜花",
                "snack": "送来一份手作点心",
                "gift": "送来一件纪念小礼物",
                "book_review": "留下一枚夹页书评书签",
            }[explicit_kind]
            return explicit_kind, default_note
    if any(k in content for k in _MAILBOX_GIFT_KEYWORDS):
        return "gift", content
    if any(k in content for k in _MAILBOX_FLOWER_KEYWORDS):
        return "flower", content
    if any(k in content for k in _MAILBOX_SNACK_KEYWORDS):
        return "snack", content
    return "postcard", content


def parse_mailbox_delivery_with_title(text: str) -> tuple[str, str, str]:
    """Parse `/投递` text into `(kind, title, message)`, supporting `/投递 书评 <书名> <感悟>`."""
    kind, clean_msg = parse_mailbox_delivery(text)
    if kind != "book_review":
        return kind, "", clean_msg
    raw = str(clean_msg or "").strip()
    # Match 《书名》 感悟 or <书名> <感悟>
    m_book = re.match(r"^[《「\"]([^》」\"]+)[》」\"][\s:：\-—]*(.*)$", raw, flags=re.S)
    if m_book:
        title = m_book.group(1).strip()[:40]
        review = m_book.group(2).strip() or f"读完了《{title}》，留下书签纪念"
        return kind, title, review
    parts = raw.split(None, 1)
    if len(parts) == 2:
        return kind, parts[0].strip()[:40], parts[1].strip()
    return kind, raw[:40] or "小屋藏书", raw or "留下了一枚书评夹页书签"


class Main(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.context, self.host_config = context, config
        self.config = merge_config(defaults(), dict(config))
        self.data_root = Path(StarTools.get_data_dir())
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._terminating, self._ready, self._migrating = False, False, False
        self._migration_lock = asyncio.Lock()
        self.web = WorldAPI(self)
        self.maps = MapService(self)
        self.onboarding = Onboarding(self)
        self.textures = TextureResources(self.data_root)
        self.postcards = PostcardRenderer(self.data_root)
        self._event_bus_subs: list[tuple[Any, str]] = []

    async def initialize(self):
        from importlib import reload

        from . import series_panels
        reload(series_panels).register_series_panels(self,"astrbot_plugin_dynamics_world")
        await self._open_services()
        self.web.register()
        self._subscribe_series_event_bus()
        self._ready = True

    def _subscribe_series_event_bus(self) -> None:
        """Zero-coupling subscription to Chat Dynamics Dynamics Event Bus (`milestone_achieved`)."""
        self._unsubscribe_series_event_bus()
        try:
            _, chat = self.onboarding.companion("astrbot_plugin_chat_dynamics")
        except Exception:
            chat = None
        sub = getattr(chat, "subscribe_dynamics_event", None) if chat is not None else None
        if callable(sub):
            try:
                token = sub(
                    "milestone_achieved",
                    self._on_milestone_achieved_event,
                    owner="astrbot_plugin_dynamics_world",
                )
                if token:
                    self._event_bus_subs.append((chat, str(token)))
            except Exception:
                pass

    def _unsubscribe_series_event_bus(self) -> None:
        subs = list(getattr(self, "_event_bus_subs", []) or [])
        self._event_bus_subs = []
        for chat, token in subs:
            unsub = getattr(chat, "unsubscribe_dynamics_event", None)
            if callable(unsub):
                try:
                    unsub(token)
                except Exception:
                    pass

    def _on_milestone_achieved_event(self, payload: dict | None) -> dict | None:
        if not isinstance(payload, dict):
            return None
        title = str(payload.get("title") or "").strip()
        if not title:
            return None
        try:
            return self.register_external_keepsake(
                persona_id=str(payload.get("persona_id") or ""),
                umo=str(payload.get("umo") or ""),
                title=title,
                summary=str(payload.get("summary") or payload.get("description") or title),
                sender_name=str(payload.get("sender_name") or payload.get("actor_name") or ""),
                source_plugin=str(payload.get("source_plugin") or payload.get("plugin_id") or ""),
                deep_link=str(payload.get("deep_link") or ""),
                image_path=str(payload.get("image_path") or ""),
                kind=str(payload.get("kind") or "memory_postcard"),
            )
        except Exception:
            return None

    def register_external_keepsake(
        self,
        *,
        persona_id: str = "",
        umo: str = "",
        title: str,
        summary: str,
        sender_name: str = "",
        source_plugin: str = "",
        deep_link: str = "",
        image_path: str = "",
        kind: str = "memory_postcard",
    ) -> dict:
        """Public cross-plugin contract: register an external milestone keepsake into the 3D cabin."""
        engine = getattr(getattr(self, "life", None), "narrative", None)
        if engine is None or getattr(engine, "keepsakes", None) is None:
            raise RuntimeError("群间世界纪念格服务尚未就绪")
        pid = str(persona_id or "").strip() or self._effective_persona_id()
        if not pid and hasattr(self, "world") and getattr(self.world, "store", None) is not None:
            default_card = self.world.store.get_default_card()
            if default_card and getattr(default_card, "persona_id", ""):
                pid = str(default_card.persona_id)
        if not pid:
            pid = "default"
        scope = {
            "persona_id": pid,
            "character_id": pid,
            "umo": str(umo or ""),
        }
        receipt = engine.keepsakes.register_external_keepsake(
            scope,
            title=title,
            summary=summary,
            sender_name=sender_name,
            source_plugin=source_plugin,
            deep_link=deep_link,
            image_path=image_path,
            kind=kind,
        )
        postcards = getattr(self, "postcards", None)
        if postcards is not None and hasattr(postcards, "invalidate_cache"):
            postcards.invalidate_cache()
        web = getattr(self, "web", None)
        if web is not None and getattr(web, "bus", None) is not None:
            try:
                web.bus.notify()
            except Exception:
                pass
        return receipt

    def _resolve_identity_avatar(self, db, identity_key: str) -> dict:
        from .avatar_models import AvatarLibrary
        lib = AvatarLibrary(self.data_root / "avatar-models")
        doc = self.life.narrative.spatial.document(db, identity_key) if getattr(self.life.narrative, "spatial", None) else None
        preferred = (doc or {}).get("map_type", "virtual")
        for mode in (preferred, "virtual" if preferred != "virtual" else "real"):
            try:
                sel = lib.catalog(f"{identity_key}|{mode}")["selection"]
                if sel.get("model_id") and sel["model_id"] != "builtin":
                    return sel
            except Exception:
                continue
        return {"model_id": "builtin", "texture_index": 0}

    async def _open_services(self):
        self.data_dir = active_directory(self.data_root)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.world = WorldService(self.context, self.config, self.data_dir)
        self.world.owner = self
        self.life = LifeService(self.context, self.config, self.data_dir, self.world, self.runtime_allowed)
        await self.world.initialize()
        await self.life.initialize()
        self.life.narrative.on_db_write = self.web.bus.notify
        if getattr(self.life.narrative, "world_spaces", None) is not None:
            self.life.narrative.world_spaces.avatar_resolver = self._resolve_identity_avatar
        self.life.narrative.visuals.profiles.migrate_legacy_style()
        self.life.narrative.visuals.media_status=lambda:self.onboarding.compatibility()["visual_media"]

    def conflicts(self):
        getter = getattr(self.context, "get_all_stars", None)
        if not callable(getter):
            return []
        entries = getter()
        pairs = entries.items() if isinstance(entries, dict) else [("", x) for x in (entries or [])]
        conflicts = []
        for key, item in pairs:
            value = item.get if isinstance(item, dict) else lambda k, default=None: getattr(item, k, default)
            if value("activated", True) is False:
                continue
            names = [key, value("name"), value("root_dir_name"), value("module_path")]
            for legacy in ("astrbot_plugin_worldbook", "astrbot_plugin_dynamic_life_state"):
                if any(isinstance(n, str) and legacy in n.split(".") for n in names):
                    conflicts.append(legacy)
        return sorted(set(conflicts))

    def runtime_allowed(self):
        return bool(self._ready and not self._terminating and not self._migrating
                    and self.config.get("runtime_enabled") is True and not self.conflicts())

    def get_dynamics_capabilities(self):
        return {
            "schema_version": 1,
            "version": "v0.23.0",
            "world_integration_version": 2,
            "provider_id": "astrbot_plugin_dynamics_world",
            "display_name": "群间世界",
            "enabled": self.config.get("runtime_enabled") is True,
            "ready": self.runtime_allowed(),
            "capabilities": {
                "character": 1,
                "life": 1,
                "world_spaces": 2,
                "ecology": 2,
                "mailbox_visitors": 2,
                "keepsakes": 2,
                "postcard": 3,
                "world_stream": 1,
                "horizons_sync": 1,
                "horizons_sync_revision": 2,
                "causal_life": 1,
                "background_residents": 2,
                "resident_private_perspective": 1,
                "actor_observation": 1,
            },
        }

    def get_world_integration_capabilities(self):
        return self.get_dynamics_capabilities()

    def get_reference_assets_directory(self) -> str:
        """Public read-only accessor for the active World visual-assets directory."""
        life = getattr(self, "life", None)
        narrative = getattr(life, "narrative", None)
        visuals = getattr(narrative, "visuals", None)
        profiles = getattr(visuals, "profiles", None)
        asset_root = getattr(profiles, "asset_root", None)
        if asset_root is not None:
            return str(Path(asset_root).resolve())
        base = getattr(self, "data_dir", None) or active_directory(self.data_root)
        return str((Path(base) / "visual-assets").resolve())

    def authorize_visual_reference_access(self) -> dict:
        """Grant Visual Media read access limited to World's active visual-assets directory."""
        _, media = self.onboarding.companion("astrbot_plugin_visual_media")
        if media is None or not callable(getattr(media, "grant_world_reference_access", None)):
            raise ValueError("请安装支持世界参考图授权接口的视觉工坊")
        return media.grant_world_reference_access(self.get_reference_assets_directory())

    def _effective_persona_id(self) -> str:
        explicit = str(self.config.get("persona_id") or "").strip()
        if explicit:
            return explicit
        from . import series_panels

        shared = series_panels.get_series_shared_config(self.context)
        if isinstance(shared, dict):
            return str(shared.get("persona_id") or "").strip()
        return ""

    def _persist_config_patch(self, patch: dict[str, Any]) -> None:
        save = getattr(self.host_config, "save_config", None)
        if callable(save):
            self.onboarding.save_config(patch)
            return
        if isinstance(self.host_config, dict):
            self.host_config.update(patch)
        self.config.update(patch)

    def get_dynamics_summary(self, umo: str = "") -> dict:
        """Public, non-secret status summary for series companions."""
        world = getattr(self, "world", None)
        store = getattr(world, "store", None)
        cards = len(store.list_cards()) if store is not None and callable(getattr(store, "list_cards", None)) else 0
        sessions = list(self.config.get("narrative_sessions") or [])
        return {
            "schema_version": 1,
            "enabled": self.config.get("runtime_enabled") is True,
            "ready": self.runtime_allowed(),
            "persona_id": self._effective_persona_id(),
            "card_count": cards,
            "active_sessions": len(sessions),
            "scope_bound": bool(umo and umo in sessions) if sessions else bool(self.config.get("narrative_all_groups")),
            "visual_assets_dir": self.get_reference_assets_directory(),
        }

    def get_series_summary(self) -> dict:
        """Public synchronous summary hook for series_presence v2 badges and live pulse."""
        from .series_hooks import build_series_summary

        return build_series_summary(self)

    def get_series_health(self) -> dict:
        """Public synchronous read-only health diagnostics hook for series_panels."""
        from .series_hooks import build_series_health

        return build_series_health(self)

    def get_series_scope_status(self, umo: str) -> dict:
        """Public synchronous read-only status for a group/session scope in series_matrix."""
        from .series_hooks import build_series_scope_status

        return build_series_scope_status(self, umo)

    async def set_series_scope_enabled(
        self,
        umo: str,
        enabled: bool,
        expected_version: str | int | None = None,
    ) -> dict[str, Any]:
        """Optimistically toggle a UMO's participation in Dynamics World."""
        clean_umo = str(umo or "").strip()
        if not clean_umo or len(clean_umo) > 300:
            raise ValueError("invalid umo")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")

        async with self._migration_lock:
            before = self.get_series_scope_status(clean_umo)
            current_version = str(before.get("version") or self.onboarding.revision())
            if expected_version is not None and str(expected_version).strip() != current_version:
                return {
                    "ok": False,
                    "conflict": True,
                    "reason": "version_conflict",
                    "umo": clean_umo,
                    "enabled": bool(before.get("enabled", False)),
                    "version": current_version,
                    "summary": "配置版本已变化，请刷新后重试",
                }

            sessions = [
                str(s).strip()
                for s in (self.config.get("narrative_sessions") or [])
                if str(s).strip()
            ]
            all_groups = bool(self.config.get("narrative_all_groups"))
            store = getattr(getattr(self, "world", None), "store", None)
            if enabled:
                if clean_umo not in sessions:
                    sessions.append(clean_umo)
                if store is not None:
                    raw_sessions = getattr(getattr(store, "_store", None), "sessions", None)
                    sess = raw_sessions.get(clean_umo) if isinstance(raw_sessions, dict) else None
                    if sess is not None and (
                        not getattr(sess, "enabled", True)
                        or not getattr(sess, "inject_card_prompt", True)
                        or getattr(sess, "card_id", "") == "__none__"
                    ):
                        patch_kwargs: dict[str, Any] = {
                            "enabled": True,
                            "inject_card_prompt": True,
                        }
                        if getattr(sess, "card_id", "") == "__none__":
                            patch_kwargs["card_id"] = ""
                        store.update_session(clean_umo, **patch_kwargs)
                self._persist_config_patch({"narrative_sessions": sessions})
            else:
                sessions = [s for s in sessions if s != clean_umo]
                self._persist_config_patch({"narrative_sessions": sessions})
                if all_groups and store is not None:
                    store.update_session(clean_umo, enabled=False)

            narrative = getattr(getattr(self, "life", None), "narrative", None)
            if narrative is not None and hasattr(narrative, "invalidate_snapshot_cache"):
                narrative.invalidate_snapshot_cache()
            from . import series_panels

            series_panels.invalidate_presence_cache(
                "astrbot_plugin_dynamics_world", context=self.context
            )
            self.web.bus.notify()
            after = self.get_series_scope_status(clean_umo)
            return {
                "ok": True,
                "umo": clean_umo,
                "enabled": bool(after.get("enabled", enabled)),
                "version": str(after.get("version") or self.onboarding.revision()),
                "reason": "",
                "summary": str(after.get("summary") or ("已接入持续生活" if enabled else "未绑定持续生活")),
            }

    async def activate_series_runtime(self) -> dict[str, Any]:
        """Activate runtime_enabled for Setup Wizard step 4 when no legacy conflicts block it."""
        async with self._migration_lock:
            conflicts = self.conflicts()
            if conflicts:
                return {
                    "ok": False,
                    "runtime_enabled": self.config.get("runtime_enabled") is True,
                    "ready": self.runtime_allowed(),
                    "reason": "legacy_conflict",
                    "conflicts": conflicts,
                    "message": f"存在旧插件冲突：{'、'.join(conflicts)}",
                }
            if self.config.get("runtime_enabled") is True:
                return {
                    "ok": True,
                    "runtime_enabled": True,
                    "ready": self.runtime_allowed(),
                    "already_enabled": True,
                    "reason": "",
                }
            self._persist_config_patch({"runtime_enabled": True})
            narrative = getattr(getattr(self, "life", None), "narrative", None)
            if narrative is not None and hasattr(narrative, "invalidate_snapshot_cache"):
                narrative.invalidate_snapshot_cache()
            from . import series_panels

            series_panels.invalidate_presence_cache(
                "astrbot_plugin_dynamics_world", context=self.context
            )
            self.web.bus.notify()
            return {
                "ok": True,
                "runtime_enabled": True,
                "ready": self.runtime_allowed(),
                "already_enabled": False,
                "reason": "",
            }

    def series_search_items(
        self, query: str, scope: str = "", limit: int = 8
    ) -> list[dict]:
        """Public synchronous read-only search hook for federated Ctrl+K search."""
        from .series_hooks import search_world_items

        return search_world_items(self, query, scope=scope, limit=limit)

    def get_journal_events(
        self,
        persona: str = "",
        scope: str = "",
        date: str = "today",
        limit: int = 20,
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> list[dict]:
        """Public synchronous read-only hook returning World's own living journal events."""
        from .series_hooks import collect_world_journal_events

        return collect_world_journal_events(
            self,
            persona=persona,
            scope=scope,
            date=date,
            limit=limit,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    def _require_runtime(self):
        if not self.runtime_allowed():
            raise RuntimeError("群间世界尚未接入，或旧世界书/动态生活仍在启用")

    async def terminate(self):
        self._unsubscribe_series_event_bus()
        panel=getattr(self,"_series_panels",None)
        if panel:
            panel.close()
        self._terminating, self._ready = True, False
        await self.web.bus.close()
        await self.postcards.close()
        await self.onboarding.close()
        await self.textures.close()
        await self.maps.close()
        if hasattr(self, "life"):
            await self.life.terminate()
        if hasattr(self, "world"):
            await self.world.terminate()

    async def get_character_context(self, scope, event=None):
        self._require_runtime()
        return await self.world.get_character_context(scope, event)

    def peek_context_revision(self, scope):
        self._require_runtime()
        return self.life.peek_context_revision(scope)

    @filter.on_llm_request(priority=4)
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        if not self.runtime_allowed():
            return
        get_extra = getattr(event, "get_extra", None)
        if callable(get_extra) and (get_extra("_narrative_managed_v1", None) or get_extra("_narrative_internal_v1", False)):
            return
        await self.world.on_llm_request(event, req)
        if self.runtime_allowed():
            await self.life.on_llm_request(event, req)

    @filter.command("群间世界", alias=["dworld"])
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def world_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not text.strip():
            yield event.plain_result("群间世界 · Dynamics World\n在管理面板编辑角色、世界书、场景、日常和故事约定。\n/群间世界 列表\n/群间世界 角色卡 列表\n/群间日常\n接入状态：" + ("已接入" if self.runtime_allowed() else "编辑模式（未接入或旧插件冲突）"))
            return
        # Applying a card may synchronize a host persona; only allow after takeover.
        if not self.runtime_allowed():
            yield event.plain_result("当前为编辑模式，请在群间世界管理页编辑；启用接入后可使用聊天管理命令。")
            return
        async for result in self.world.cmd_worldbook(event, text):
            yield result

    @filter.command("群间日常")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def life_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed():
            yield event.plain_result("群间世界尚未接入。可在管理页查看日常和迁移记录。")
            return
        action = text.strip()
        actions = {"完整": self.life.dls_full, "重新生成": self.life.dls_regen,
                   "推进": self.life.dls_tick, "暂停": self.life.dls_pause, "恢复": self.life.dls_resume}
        if action and action not in actions:
            yield event.plain_result("/群间日常 [完整|重新生成|推进|暂停|恢复]；暂停与恢复作用于该角色的全部生活范围。")
            return
        async for result in actions.get(action, self.life.dls_show)(event):
            yield result

    @filter.llm_tool(name="get_dynamics_world_state")
    async def world_state_tool(self, event: AstrMessageEvent, focus: str = "activity"):
        """仅在对方询问角色现在的活动、位置、眼前场景、天气、项目进展、院门信箱、花园、纪念格或居民近况时调用。普通聊天和单独的戳一戳跳过。

        Args:
            focus (string): activity 当前活动（默认），location 所在位置，scene 当前场景，weather 当前天气，project 记录的项目进展，mailbox 院门信箱与最近拆阅记录，garden 花园作物/储物篮与访客状态，keepsakes 小屋纪念格与书架陈列，residents 近期居民互动与串门情况。选与提问对应的一项。
        """
        self._require_runtime()
        allowed_focuses = (
            "activity",
            "location",
            "scene",
            "weather",
            "project",
            "mailbox",
            "garden",
            "keepsakes",
            "residents",
        )
        if focus not in allowed_focuses:
            return "可查询 activity、location、scene、weather、project、mailbox、garden、keepsakes 或 residents。"
        scope = await self.life._scope_for_event(event)
        if scope is None:
            return "当前会话没有绑定角色。"
        return await self.life.read_current_world_state(scope, focus)

    async def build_cabin_postcard_snapshot(self, scope: dict, character: dict | None = None) -> dict:
        engine = self.life.narrative
        if character is None:
            character = await self.world.get_character_context(scope)

        def _collect_db_snapshot():
            from . import cabin_life
            from .world_stream import _life_cues

            with engine._db() as db:
                db.execute("BEGIN IMMEDIATE")
                now_ts = engine.clock()
                life_snap = engine._snapshot(db, scope, now_ts) if engine._allowed(scope) else {}
                if life_snap.get("spatial") is None:
                    engine.spatial.settle(db, scope, now_ts)
                actor_snap = life_snap.get("spatial") or engine.spatial.snapshot(db, scope, now_ts)
                env_snap = engine.environment.snapshot(db, scope, now_ts, actor_snap)
                engine.scenes.settle(db, scope, now_ts)
                scene_snap = engine.scenes.snapshot(db, scope, now_ts, admin=True)
                sc_key, _, raw_scene = engine.scenes.load(db, scope)
                if engine.ecology is not None:
                    engine.ecology.settle(db, scope, env_snap, raw_scene, now_ts)
                if engine.mailbox is not None:
                    engine.mailbox.settle(db, scope, raw_scene, actor_snap, now_ts)
                if engine.world_spaces is not None:
                    engine.world_spaces.settle(db, scope, now_ts, actor_snap, (character or {}).get("name", ""))
                eco_snap = engine.ecology.snapshot(db, scope, now_ts, life_state=life_snap, scene_state=raw_scene, env=env_snap, actor=actor_snap)
                ks_snap = engine.keepsakes.snapshot(db, scope, raw_scene, now_ts)
                mb_snap = engine.mailbox.snapshot(db, scope, now_ts, character, read_only=True)
                ws_snap = engine.world_spaces.snapshot(db, scope, now_ts) if engine.world_spaces is not None else {}
                c_style = str(cabin_life.preference(db, sc_key).get("style") or "cottage")
                cues_snap = _life_cues(db, scope, now_ts, self.life)
                from .spatial import identity as _scope_ident
                raw_map = engine.spatial.document(db, _scope_ident(scope)) if engine.spatial is not None else None
                map_snap = (
                    {
                        "map_type": raw_map.get("map_type", "virtual"),
                        "width": raw_map.get("width", 1200),
                        "height": raw_map.get("height", 800),
                        "image": raw_map.get("image", ""),
                        "places": raw_map.get("places", []),
                    }
                    if isinstance(raw_map, dict)
                    else None
                )
                return (
                    now_ts,
                    life_snap,
                    actor_snap,
                    env_snap,
                    scene_snap,
                    sc_key,
                    eco_snap,
                    ks_snap,
                    mb_snap,
                    ws_snap,
                    c_style,
                    cues_snap,
                    map_snap,
                )

        (
            now,
            life,
            actor,
            env,
            scene,
            scene_key,
            eco,
            keepsakes,
            mailbox,
            world_space,
            cabin_style,
            cues,
            map_doc,
        ) = await asyncio.to_thread(_collect_db_snapshot)

        avatar_selection = {"model_id": "builtin", "texture_index": 0, "home_room_id": "", "garden_room_id": ""}
        avatar_model = None
        avatar_tex = 0
        guest_avatar_model = None
        guest_tex = 0
        try:
            from .avatar_models import AvatarLibrary
            lib = AvatarLibrary(self.data_root / "avatar-models")
            cat = await asyncio.to_thread(lib.catalog, scene_key)
            avatar_selection = dict(cat.get("selection") or avatar_selection)
            mid = str(avatar_selection.get("model_id") or "builtin")
            avatar_model = await asyncio.to_thread(lib.model, mid)
            tex_names = [str(t.get("name") or "") for t in (avatar_model.get("textures") or []) if isinstance(t, dict)]
            avatar_tex = match_outfit_texture(tex_names, cues.get("outfit_now", ""), int(avatar_selection.get("texture_index") or 0))
            guest = world_space.get("active_guest") if isinstance(world_space, dict) else None
            if isinstance(guest, dict) and guest.get("model_id") and guest.get("model_id") != "builtin":
                guest_avatar_model = await asyncio.to_thread(lib.model, str(guest["model_id"]))
                guest_tex = int(guest.get("texture_index") or 0)
        except Exception:
            pass

        return {
            "character": {"id": (character or {}).get("card_id", ""), "name": (character or {}).get("name", "角色")},
            "cabin_style": cabin_style,
            "map": map_doc,
            "actor": actor,
            "environment": env,
            "scene": scene,
            "ecology": eco,
            "keepsakes": keepsakes,
            "mailbox": mailbox,
            "world_space": world_space,
            "activity": life.get("activity", ""),
            "availability": life.get("availability", "unknown"),
            "activity_code": cues.get("activity_code", "unknown"),
            "plan_now": cues.get("plan_now", ""),
            "outfit_now": cues.get("outfit_now", ""),
            "plan_today": cues.get("plan_today", []),
            "horizons_desk": cues.get("horizons_desk", []),
            "avatar_selection": avatar_selection,
            "avatar_model": avatar_model,
            "avatar_texture_index": avatar_tex,
            "guest_avatar_model": guest_avatar_model,
            "guest_texture_index": guest_tex,
            "server_time": now,
        }

    def _sender_identity(self, event: AstrMessageEvent) -> tuple[str, str]:
        uid = str(getattr(event, "get_sender_id", lambda: "")() or "member")
        uname = str(getattr(event, "get_sender_name", lambda: "")() or uid)[:32]
        return uid, uname

    @filter.llm_tool(name="deliver_cabin_mailbox")
    async def deliver_cabin_mailbox_tool(
        self, event: AstrMessageEvent, message: str, kind: str = "postcard", title: str = ""
    ):
        """当群友在对话中向角色赠送小礼物、鲜花、点心或寄明信片时，投入角色小屋的院门信箱。

        Args:
            message(string): 群友附带的心意或留言（不超过120字）。
            kind(string): 投递类别，可选 postcard(明信片) / snack(点心) / flower(鲜花) / gift(纪念小物)。
            title(string): 物品或卡片简短名称（可选）。
        """
        self._require_runtime()
        if not self.config.get("group_cabin_commands_enabled", True):
            return "当前会话未开放院门信箱投递。"
        scope = await self.life._scope_for_event(event)
        if scope is None:
            return "当前会话没有绑定角色。"
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            receipt = await self.life.narrative.mailbox.deliver_parcel_async(
                scope,
                sender_id=uid,
                sender_name=uname,
                kind=kind,
                title=title,
                message=message,
                cooldown_seconds=cooldown,
                character_context=character,
            )
            return f"已将 {uname} 的{receipt['kind_label']}「{receipt['title']}」投入小屋院门信箱，等角色空闲经过院门时会拆阅。"
        except ValueError as exc:
            return str(exc)

    @filter.llm_tool(name="visit_cabin_garden")
    async def visit_cabin_garden_tool(self, event: AstrMessageEvent, note: str = ""):
        """当群友表示想来角色的小花园坐坐、串门或看看风景时，在花园登记临时探访足迹（严格限室外花园区域）。

        Args:
            note(string): 探访时的简短动作或招呼语（可选，不超过80字）。
        """
        self._require_runtime()
        if not self.config.get("group_cabin_commands_enabled", True):
            return "当前会话未开放花园探访。"
        scope = await self.life._scope_for_event(event)
        if scope is None:
            return "当前会话没有绑定角色。"
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            res = await self.life.narrative.mailbox.enter_garden_async(
                scope,
                user_id=uid,
                display_name=uname,
                note=note or "来到院外花园散步看风景",
                cooldown_seconds=cooldown,
                character_context=character,
            )
            if res.get("mode") == "critter":
                form_zh = {"dove": "小信鸽", "squirrel": "林间小松鼠", "kitten": "小奶猫"}.get(res.get("form"), "小动物")
                return f"已按世界观规则将 {uname} 的探访化为一只{form_zh}停驻在院墙花园边。"
            return f"{uname} 已来到小屋外的花园（{res['spot']}）驻足小憩。"
        except ValueError as exc:
            return str(exc)

    @filter.llm_tool(name="capture_cabin_postcard")
    async def capture_cabin_postcard_tool(self, event: AstrMessageEvent, caption: str = "", shot_mode: str = "auto"):
        """仅在群友想看小屋或花园的画面、要一张图片或明信片时调用。会生成并发送小屋实况拍立得明信片。

        对方只询问角色此刻在做什么、在哪或眼前有什么时，使用 get_dynamics_world_state 的相应查询。

        Args:
            caption(string): 可选的一句话当下心境手写附言（不超过40字）。
            shot_mode(string): 可选运镜模式，auto(智能情景运镜) / room(室内近景) / garden(花园全景) / gate(院门信箱)。
        """
        self._require_runtime()
        if not self.config.get("group_cabin_commands_enabled", True):
            return "当前会话未启用小屋实况明信片。"
        scope = await self.life._scope_for_event(event)
        if scope is None:
            return "当前会话没有绑定角色。"
        now = self.life.narrative.clock()
        cd_secs = int(self.config.get("cabin_postcard_cooldown_seconds", 180) or 180)
        cd_key = f"postcard:{scope.get('umo','')}"
        wait = self.postcards.check_cooldown(cd_key, now, cd_secs)
        if wait > 0:
            return f"小屋实况明信片刚刚拍过一张，请 {wait} 秒后再拍，可先用文字描述当下日常。"
        character = await self.world.get_character_context(scope, event)
        snap = await self.build_cabin_postcard_snapshot(scope, character)
        rendered = await self.postcards.render(
            snap,
            plugin_dir=Path(__file__).parent,
            caption=caption,
            prefer_3d=True,
            shot_mode=shot_mode or "auto",
        )
        self.postcards.mark_used(cd_key, now)
        await event.send(event.image_result(rendered["path"]))
        return "小屋实况拍立得明信片已发送至当前会话。"

    async def render_keepsake_postcard(
        self,
        scope: dict,
        *,
        slot: str = "",
        caption: str = "",
        character: dict | None = None,
    ) -> dict:
        """Render an auto-focused keepsake-slot Polaroid closeup for mailbox/keepsake closure."""
        char = character if isinstance(character, dict) else await self.world.get_character_context(scope, None)
        snap = await self.build_cabin_postcard_snapshot(scope, char)
        return await self.postcards.render(
            snap,
            plugin_dir=Path(__file__).parent,
            caption=str(caption or "")[:48],
            prefer_3d=True,
            shot_mode="keepsake",
            focus_slot=str(slot or ""),
        )

    async def build_daily_world_journal(
        self,
        scope: dict,
        *,
        character: dict | None = None,
        now: float | None = None,
    ) -> dict:
        """Build today's World Journal graphic card PNG & summary (for /世界手账 and Chat Dynamics rhythm)."""
        from .world_journal_card import collect_world_journal_data, save_world_journal_card

        char = character if isinstance(character, dict) else await self.world.get_character_context(scope, None)
        engine = self.life.narrative
        journal_data = await asyncio.to_thread(
            collect_world_journal_data,
            engine,
            scope,
            character=char,
            now=now,
        )
        return await asyncio.to_thread(save_world_journal_card, self.data_root, journal_data)

    @filter.command("世界手账", alias=["今日手账", "world_journal"])
    async def world_journal_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话暂未启用每日世界手账。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        now = self.life.narrative.clock()
        cd_secs = int(self.config.get("cabin_postcard_cooldown_seconds", 180) or 180)
        cd_key = f"journal:{scope.get('umo', '')}"
        wait = self.postcards.check_cooldown(cd_key, now, cd_secs)
        if wait > 0:
            yield event.plain_result(f"📓 世界手账绘制冷却中，请 {wait} 秒后再试。")
            return
        character = await self.world.get_character_context(scope, event)
        try:
            res = await self.build_daily_world_journal(scope, character=character, now=now)
            self.postcards.mark_used(cd_key, now)
            yield event.image_result(res["path"])
        except Exception:
            try:
                from .world_journal_card import collect_world_journal_data, format_world_journal_text

                fallback_data = await asyncio.to_thread(
                    collect_world_journal_data,
                    self.life.narrative,
                    scope,
                    character=character,
                    now=now,
                )
                yield event.plain_result(format_world_journal_text(fallback_data))
            except Exception as exc:
                yield event.plain_result(f"📓 世界手账生成失败：{exc}")

    @filter.command("小屋实况", alias=["cabin"])
    async def cabin_postcard_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("群间世界小屋实况暂未启用。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        now = self.life.narrative.clock()
        cd_secs = int(self.config.get("cabin_postcard_cooldown_seconds", 180) or 180)
        cd_key = f"postcard:{scope.get('umo','')}"
        wait = self.postcards.check_cooldown(cd_key, now, cd_secs)
        if wait > 0:
            yield event.plain_result(f"📷 小屋实况相机冷却中，请 {wait} 秒后再试。")
            return
        shot_mode, clean_caption = parse_shot_override(text)
        character = await self.world.get_character_context(scope, event)
        snap = await self.build_cabin_postcard_snapshot(scope, character)
        rendered = await self.postcards.render(
            snap,
            plugin_dir=Path(__file__).parent,
            caption=clean_caption[:42],
            prefer_3d=True,
            shot_mode=shot_mode,
        )
        self.postcards.mark_used(cd_key, now)
        yield event.image_result(rendered["path"])

    @filter.command("小屋", alias=["小屋帮助", "cabin_help"])
    async def cabin_help_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话暂未启用群间小屋互动。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        character = await self.world.get_character_context(scope, event)
        engine = self.life.narrative

        def _read_cabin_overview():
            with engine._db(notify=False) as db:
                db.execute("PRAGMA query_only = ON")
                now = engine.clock()
                actor = engine.spatial.snapshot(db, scope, now) if engine.spatial is not None else {}
                env = engine.environment.snapshot(db, scope, now, actor) if engine.environment is not None else {}
                scene = engine.scenes.snapshot(db, scope, now) if engine.scenes is not None else {}
                mb = engine.mailbox.snapshot(db, scope, now, character, read_only=True) if engine.mailbox is not None else {}
                return actor, env, scene, mb

        actor, env, scene, mb = await asyncio.to_thread(_read_cabin_overview)
        char_name = str((character or {}).get("name") or "小屋主人")
        journey = actor.get("journey") if isinstance(actor, dict) else None
        if isinstance(journey, dict) and journey.get("destination_name"):
            loc_text = f"前往 {journey['destination_name']} 途中"
        else:
            place_name = str(scene.get("place_name") or actor.get("place_name") or "住所小屋")
            room_name = str(scene.get("room_name") or "")
            loc_text = f"{place_name} · {room_name}" if room_name else place_name
        if env.get("available") and not env.get("stale") and isinstance(env.get("current"), dict):
            cur = env["current"]
            temp = cur.get("temperature")
            day_str = "白天" if cur.get("is_day") else "夜间"
            wx_text = f"{cur.get('label', '晴')} {temp}℃（{day_str}）" if temp is not None else f"{cur.get('label', '晴')}（{day_str}）"
        else:
            wx_text = "暂无天气实况"
        policy_label = str(mb.get("policy_label") or "默认")
        unopened = int(mb.get("unopened_count") or 0)
        visitor_count = len(mb.get("visitors") or [])
        lines = [
            f"🏡 {char_name}的小屋实况导航",
            f"📍 当前位置：{loc_text}",
            f"🌤️ 当前天气：{wx_text}",
            f"🚪 访客策略：{policy_label}（信箱未拆 {unopened} 封 · 花园访客 {visitor_count} 位）",
            "",
            "✨ 群友可用指令：",
            "• /小屋实况 [全景|近景|院门|纪念格|旅途] [附言] — 拍摄实况拍立得（外出时自动切换旅途风景明信片）",
            "• /世界手账（或 /今日手账）— 生成今日世界手账图文日报",
            "• /浇水 [留言] — 参与花园共种浇水（盛放或节气时触发节气茶会拍立得）",
            "• /书架 [书名] — 浏览角色已定稿公开书单与群友夹页书签",
            "• /投递 [明信片|鲜花|点心|礼物|书评] <附言/书名 感悟> — 往院门信箱寄送心意或夹页书评",
            "• /探访 [留言|浇水] — 来小屋花园驻足片刻（受访客策略约束）",
            "• /小屋 或 /小屋帮助 — 查看小屋状态与指令说明",
        ]
        yield event.plain_result("\n".join(lines))

    @filter.command("投递")
    async def cabin_deliver_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话未开放院门信箱投递。")
            return
        content = text.strip()
        if not content:
            yield event.plain_result("用法：/投递 [明信片|鲜花|点心|礼物|书评] <附言或书名 感悟>")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        kind, parsed_title, clean_message = parse_mailbox_delivery_with_title(content)
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            res = await self.life.narrative.mailbox.deliver_parcel_async(
                scope,
                sender_id=uid,
                sender_name=uname,
                kind=kind,
                title=parsed_title,
                message=clean_message,
                cooldown_seconds=cooldown,
                character_context=character,
            )
            if kind == "book_review":
                yield event.plain_result(
                    f"🔖 已投递《{res['title']}》的夹页书评书签（主人拆阅后将夹在 3D 书架对应书册下）"
                )
            else:
                yield event.plain_result(f"📮 已投入院门信箱（{res['kind_label']}）：{res['title']}（主人空闲回屋时会亲自拆阅）")
        except ValueError as exc:
            yield event.plain_result(f"📮 {exc}")

    async def _run_coop_garden_water(self, event: AstrMessageEvent, scope: dict, note: str = "") -> tuple[str, str | None]:
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        engine = self.life.narrative
        env_snap = None
        try:
            def _read_env():
                with engine._db(notify=False) as db:
                    db.execute("PRAGMA query_only = ON")
                    now_ts = engine.clock()
                    act = engine.spatial.snapshot(db, scope, now_ts) if engine.spatial is not None else {}
                    return engine.environment.snapshot(db, scope, now_ts, act) if engine.environment is not None else {}

            env_snap = await asyncio.to_thread(_read_env)
        except Exception:
            env_snap = None
        res = await engine.ecology.coop_water_async(
            scope,
            user_id=uid,
            display_name=uname,
            note=note,
            cooldown_seconds=cooldown,
            daily_limit=3,
            env=env_snap,
        )
        if hasattr(self, "postcards") and hasattr(self.postcards, "invalidate_cache"):
            self.postcards.invalidate_cache()
        text_msg = (
            f"💧 {uname} 为小院花圃与菜畦浇了水！"
            f"当前进度：花圃 {res['flower_progress']}% · 菜畦 {res['veg_progress']}%"
            f"（今日共 {res['total_today']} 次共种照料）"
        )
        tea_party = res.get("tea_party") or {}
        if tea_party.get("triggered"):
            names = "、".join(tea_party.get("participants") or [uname])
            text_msg += (
                f"\n🍵 【{tea_party['solar_term']}节气茶会触发！】"
                f"庭院桌已摆上「{tea_party['treat_name']}」，感谢共种伙伴：{names}！"
            )
            try:
                snap = await self.build_cabin_postcard_snapshot(scope, character)
                rendered = await self.postcards.render(
                    snap,
                    plugin_dir=Path(__file__).parent,
                    caption=str(tea_party.get("caption") or "")[:48],
                    prefer_3d=True,
                    shot_mode="garden",
                    bypass_cache=True,
                )
                return text_msg, rendered["path"]
            except Exception:
                return text_msg, None
        return text_msg, None

    @filter.command("浇水", alias=["water", "花园浇水"])
    async def cabin_water_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话暂未开放花园共种浇水。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        try:
            msg_text, img_path = await self._run_coop_garden_water(event, scope, text.strip())
            yield event.plain_result(msg_text)
            if img_path:
                yield event.image_result(img_path)
        except ValueError as exc:
            yield event.plain_result(f"💧 {exc}")

    @filter.command("书架", alias=["bookshelf", "小屋书架"])
    async def cabin_bookshelf_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话暂未开放小屋书架阅览。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        query = str(text or "").strip()
        character = await self.world.get_character_context(scope, event)
        char_name = str((character or {}).get("name") or "小屋主人")
        engine = self.life.narrative

        def _read_bookshelf():
            from .keepsakes import bookshelf_volumes

            with engine._db(notify=False) as db:
                db.execute("PRAGMA query_only = ON")
                _, _, raw_scene = engine.scenes.load(db, scope) if engine.scenes is not None else ("", 0, {})
                vols = bookshelf_volumes(raw_scene, public_only=True)
                bms = engine.keepsakes.list_book_bookmarks(db, scope, limit=48) if engine.keepsakes is not None else []
                for v in vols:
                    vid = str(v.get("id") or "")
                    vt = str(v.get("title") or "").strip().lower()
                    v["bookmarks"] = [
                        b for b in bms
                        if (vid and b["book_id"] == vid)
                        or (vt and b["book_title"].strip().lower() and (b["book_title"].strip().lower() in vt or vt in b["book_title"].strip().lower()))
                    ][:6]
                return vols

        volumes = await asyncio.to_thread(_read_bookshelf)
        if not volumes:
            yield event.plain_result(f"📚 {char_name}的公开书架目前还没有已定稿的书册，等新作品完结后就会上架这里。")
            return
        if not query:
            lines = [f"📚 {char_name}的小屋公开书架（共 {len(volumes)} 册）："]
            for idx, vol in enumerate(volumes[:10], 1):
                bm_cnt = len(vol.get("bookmarks") or [])
                bm_bit = f" · {bm_cnt} 枚群友书签" if bm_cnt else ""
                lines.append(f"{idx}. 《{vol['title']}》（{len(vol.get('excerpts') or [])} 节{bm_bit}）")
            lines.append("")
            lines.append("💡 发送 /书架 <书名> 阅读节选；发送 /投递 书评 <书名> <感悟> 可夹入专属书签。")
            yield event.plain_result("\n".join(lines))
            return
        q_low = query.lower()
        chosen = next((v for v in volumes if v["title"].lower() == q_low), None) or next(
            (v for v in volumes if q_low in v["title"].lower()), None
        )
        if chosen is None:
            titles = "、".join(f"《{v['title']}》" for v in volumes[:6])
            yield event.plain_result(f"📚 公开书架上未找到「{query}」，当前已上架：{titles}")
            return
        excerpt = str(chosen.get("content") or "").strip()
        if len(excerpt) > 360:
            excerpt = excerpt[:358] + "…"
        lines = [
            f"📖 《{chosen['title']}》 — {char_name} 著",
            excerpt or "（本书已归档至小屋书架）",
        ]
        bms = chosen.get("bookmarks") or []
        if bms:
            lines.append("")
            lines.append("🔖 群友夹页书签：")
            for b in bms[:4]:
                lines.append(f"• {b['sender_name']}：{b['review']}")
        else:
            lines.append("\n🔖 还没有夹页书签，欢迎发送 /投递 书评 " + chosen["title"] + " <你的感悟>")
        yield event.plain_result("\n".join(lines))

    @filter.command("探访")
    async def cabin_visit_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话未开放花园探访。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        raw_note = text.strip()
        if raw_note == "浇水" or raw_note.startswith("浇水 "):
            water_note = raw_note[2:].strip()
            try:
                msg_text, img_path = await self._run_coop_garden_water(event, scope, water_note)
                yield event.plain_result(msg_text)
                if img_path:
                    yield event.image_result(img_path)
            except ValueError as exc:
                yield event.plain_result(f"💧 {exc}")
            return
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            res = await self.life.narrative.mailbox.enter_garden_async(
                scope,
                user_id=uid,
                display_name=uname,
                note=text.strip() or "在花园木椅边静静看看风景",
                cooldown_seconds=cooldown,
                character_context=character,
            )
            if res.get("mode") == "critter":
                form_zh = {"dove": "白色小信鸽", "squirrel": "林间小松鼠", "kitten": "三花小奶猫"}.get(res.get("form"), "林间小动物")
                yield event.plain_result(f"🕊️ 你的探访心意化作一只{form_zh}，正停在小院花径边陪伴。")
            else:
                yield event.plain_result(f"🌿 {uname} 已来到小屋外的花园驻足小憩（停留约 25 分钟）。")
        except ValueError as exc:
            yield event.plain_result(f"🌿 {exc}")

    async def import_legacy(self, fingerprint):
        async with self._migration_lock:
            if self.maps.task and not self.maps.task.done():
                raise ValueError("地图生成中，请等待完成后迁移")
            if self.config.get("runtime_enabled") is True:
                raise ValueError("请先关闭群间世界的聊天接入，再迁移")
            if self.conflicts():
                raise ValueError("请先停用旧世界书和动态生活，再正式导入；预览可在旧插件运行时进行")
            self._migrating = True
            pointer = self.data_root / "active.json"
            previous_pointer = pointer.read_bytes() if pointer.exists() else None
            stopped = False
            try:
                await self.web.bus.drain_projections()
                target, result = await asyncio.to_thread(prepare_import, self.data_root.parent,
                    self.data_root, fingerprint, self.data_root.parent.parent / "config")
                if result.get("already_imported"):
                    return result
                # Build and check the imported engine before moving the pointer.
                from .life.core.narrative import NarrativeEngine
                probe = NarrativeEngine(target / "narrative.sqlite3", self.config, self.life._narrative_model)
                await probe.close()
                self._ready = False
                stopped = True
                await self.life.terminate()
                await self.world.terminate()
                activate_generation(self.data_root, target)
                await self._open_services()
                self._ready = True
                return result
            except Exception:
                if stopped:
                    await self.life.terminate()
                    if previous_pointer is None:
                        pointer.unlink(missing_ok=True)
                    else:
                        temporary = self.data_root / "restore-pointer.tmp"
                        temporary.write_bytes(previous_pointer)
                        temporary.replace(pointer)
                    await self._open_services()
                    self._ready = True
                raise
            finally:
                self._migrating = False

    async def apply_imported_settings(self):
        async with self._migration_lock:
            if self.maps.task and not self.maps.task.done():
                raise ValueError("地图生成中，请等待完成后应用配置")
            if self.config.get("runtime_enabled") is True:
                raise ValueError("请先关闭聊天接入")
            source = self.data_dir / "migration-settings.json"
            if not source.exists():
                raise ValueError("没有已导入的配置")
            incoming = json.loads(source.read_text("utf-8"))
            incoming["runtime_enabled"] = False
            next_config = merge_config(self.config, incoming)
            save = getattr(self.host_config, "save_config", None)
            if not callable(save):
                raise ValueError("宿主配置保存接口不可用")
            previous = copy.deepcopy(dict(self.host_config))
            previous_config = self.config
            self._migrating = True
            try:
                await self.web.bus.drain_projections()
                try:
                    self.host_config.update(next_config)
                    save()
                except Exception:
                    self.host_config.clear()
                    self.host_config.update(previous)
                    raise
                self._ready = False
                try:
                    await self.life.terminate()
                    await self.world.terminate()
                    self.config = next_config
                    await self._open_services()
                    self._ready = True
                except Exception:
                    await self.life.terminate()
                    self.host_config.clear()
                    self.host_config.update(previous)
                    save()
                    self.config = previous_config
                    await self._open_services()
                    self._ready = True
                    raise
            finally:
                self._migrating = False
            return {"applied": sorted(incoming), "runtime_enabled": False}

    async def get_snapshot(self, scope):
        self._require_runtime()
        return await self.life.get_snapshot(scope)

    async def ingest_events(self, events):
        self._require_runtime()
        return await self.life.ingest_events(events)

    async def advance(self, events, expected_revision=None):
        self._require_runtime()
        return await self.life.advance(events, expected_revision)

    async def list_due_intents(self, now=None):
        self._require_runtime()
        return await self.life.list_due_intents(now)

    async def observe_member_activity(self, umo, uid, message_id, occurred_at):
        self._require_runtime()
        return await self.life.observe_member_activity(umo, uid, message_id, occurred_at)

    async def update_intent(self, intent_id, status, receipt=None):
        self._require_runtime()
        return await self.life.update_intent(intent_id, status, receipt)

    async def get_intent(self, intent_id):
        self._require_runtime()
        return await self.life.get_intent(intent_id)

    async def cancel_intent(self, intent_id):
        self._require_runtime()
        return await self.life.cancel_intent(intent_id)

    async def get_narrative_admin(self, scope):
        self._require_runtime()
        return await self.life.get_narrative_admin(scope)

    async def correct_state(self, scope, patch):
        self._require_runtime()
        return await self.life.correct_state(scope, patch)

    async def set_outreach_paused(self, paused, scope=None):
        self._require_runtime()
        return await self.life.set_outreach_paused(paused, scope)

    async def set_paused(self, paused, scope=None, *, proactive_only=False):
        self._require_runtime()
        return await self.life.set_paused(paused, scope, proactive_only=proactive_only)

    def record_horizon_reading(self, scope: dict, payload: dict) -> dict:
        self._require_runtime()
        return self.life.record_horizon_reading(scope, payload, owner=self)

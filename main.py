"""One AstrBot plugin owns character, world and narrative life services."""
# ruff: noqa: E402
from __future__ import annotations

from .reload_bootstrap import ensure_current

ensure_current(
    __package__,
    __name__,
    __file__,
    version="v0.23.0-rc.9",
    checks=[
        ("life.core.narrative", "NarrativeEngine", "_world_map_v1"),
        ("life.core.narrative", "NarrativeEngine", "_horizons_sync_v1"),
    ],
)

import asyncio
import copy
import json
from pathlib import Path

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

    async def initialize(self):
        from importlib import reload

        from . import series_panels
        reload(series_panels).register_series_panels(self,"astrbot_plugin_dynamics_world")
        await self._open_services()
        self.web.register()
        self._ready = True

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
            "version": "v0.23.0-rc.9",
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
            "persona_id": str(self.config.get("persona_id") or ""),
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
        """仅在对方询问角色现在的活动、位置、眼前场景、天气或项目进展时调用。普通聊天和单独的戳一戳跳过。

        Args:
            focus (string): activity 当前活动（默认），location 所在位置，scene 当前场景，weather 当前天气，project 记录的项目进展。选与提问对应的一项。
        """
        self._require_runtime()
        if focus not in ("activity", "location", "scene", "weather", "project"):
            return "可查询 activity、location、scene、weather 或 project。"
        scope = await self.life._scope_for_event(event)
        if scope is None:
            return "当前会话没有绑定角色。"
        return await self.life.read_current_world_state(scope, focus)

    async def build_cabin_postcard_snapshot(self, scope: dict, character: dict | None = None) -> dict:
        engine = self.life.narrative
        if character is None:
            character = await self.world.get_character_context(scope)
        with engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            now = engine.clock()
            life = engine._snapshot(db, scope, now) if engine._allowed(scope) else {}
            if life.get("spatial") is None:
                engine.spatial.settle(db, scope, now)
            actor = life.get("spatial") or engine.spatial.snapshot(db, scope, now)
            env = engine.environment.snapshot(db, scope, now, actor)
            engine.scenes.settle(db, scope, now)
            scene = engine.scenes.snapshot(db, scope, now, admin=True)
            scene_key, _, raw_scene = engine.scenes.load(db, scope)
            if engine.ecology is not None:
                engine.ecology.settle(db, scope, env, raw_scene, now)
            if engine.mailbox is not None:
                engine.mailbox.settle(db, scope, raw_scene, actor, now)
            if engine.world_spaces is not None:
                engine.world_spaces.settle(db, scope, now, actor, (character or {}).get("name", ""))
            eco = engine.ecology.snapshot(db, scope, now, life_state=life, scene_state=raw_scene, env=env, actor=actor)
            keepsakes = engine.keepsakes.snapshot(db, scope, raw_scene, now)
            mailbox = engine.mailbox.snapshot(db, scope, now, character)
            world_space = engine.world_spaces.snapshot(db, scope, now) if engine.world_spaces is not None else {}
            from .web_api import _life_cues
            cues = _life_cues(db, scope, now, self.life)

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
            receipt = self.life.narrative.mailbox.deliver_parcel(
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
            res = self.life.narrative.mailbox.enter_garden(
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

    @filter.command("投递")
    async def cabin_deliver_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话未开放院门信箱投递。")
            return
        content = text.strip()
        if not content:
            yield event.plain_result("用法：/投递 <想寄给角色的明信片/鲜花/点心附言>")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        kind = "flower" if any(k in content for k in ("花", "玫瑰", "洋甘菊", "薰衣草")) else "snack" if any(k in content for k in ("糕", "茶", "饼", "糖", "点心", "果")) else "postcard"
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            res = self.life.narrative.mailbox.deliver_parcel(
                scope, sender_id=uid, sender_name=uname, kind=kind, message=content, cooldown_seconds=cooldown, character_context=character
            )
            yield event.plain_result(f"📮 已投入院门信箱：{res['title']}（主人空闲回屋时会亲自拆阅）")
        except ValueError as exc:
            yield event.plain_result(f"📮 {exc}")

    @filter.command("探访")
    async def cabin_visit_command(self, event: AstrMessageEvent, text: GreedyStr = ""):
        if not self.runtime_allowed() or not self.config.get("group_cabin_commands_enabled", True):
            yield event.plain_result("当前会话未开放花园探访。")
            return
        scope = await self.life._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话尚未绑定角色。")
            return
        character = await self.world.get_character_context(scope, event)
        uid, uname = self._sender_identity(event)
        cooldown = int(self.config.get("cabin_mailbox_cooldown_seconds", 300) or 300)
        try:
            res = self.life.narrative.mailbox.enter_garden(
                scope, user_id=uid, display_name=uname, note=text.strip() or "在花园木椅边静静看看风景", cooldown_seconds=cooldown, character_context=character
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

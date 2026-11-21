"""Dashboard-only unified APIs; host plugin-page authentication is retained."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from .causal_api import CausalAPIMixin
from .migration import preview
from .world.core.web_api import _body, _err, _ok, _query
from .world_stream import (
    WorldEventBus,
    _sample_pixel_frame,
    assemble_world_payload,
    open_sse_stream,
    parse_known_revisions,
)


class WorldAPI(CausalAPIMixin):
    def __init__(self, plugin):
        self.plugin = plugin
        self.bus = WorldEventBus()

    def register(self):
        from .series_workspace import register_panel_api

        routes = [
            ("world", self.overview, ["GET"]),
            ("cabin_style", self.cabin_style_get, ["GET"]),
            ("cabin_style", self.cabin_style_post, ["POST"]),
            ("stream", self.stream_get, ["GET"]),
            ("life", self.life_get, ["GET"]),
            ("life", self.life_post, ["POST"]),
            ("migration", self.migration_get, ["GET"]),
            ("migration", self.migration_post, ["POST"]),
            ("persona", self.persona_post, ["POST"]),
            ("map", self.map_get, ["GET"]),
            ("map", self.map_post, ["POST"]),
            ("weather", self.weather_post, ["POST"]),
        ]
        routes.append(("scene", self.scene_post, ["POST"]))
        routes.append(("visual", self.visual_post, ["POST"]))
        routes.append(("visual", self.visual_get, ["GET"]))
        routes.append(("visual_asset", self.visual_asset_get, ["GET"]))
        routes.append(("visual_asset", self.visual_asset_post, ["POST"]))
        routes.append(("setup", self.setup_get, ["GET"]))
        routes.append(("setup", self.setup_post, ["POST"]))
        routes.append(("projects", self.projects_get, ["GET"]))
        routes.append(("projects", self.projects_post, ["POST"]))
        routes.append(("activity", self.activity_get, ["GET"]))
        routes.append(("journal_feed", self.journal_feed_get, ["GET"]))
        routes.extend(
            [
                ("avatar", self.avatar_get, ["GET"]),
                ("avatar", self.avatar_post, ["POST"]),
                ("avatar_model", self.avatar_model_get, ["GET"]),
                ("avatar_upload", self.avatar_upload_post, ["POST"]),
            ]
        )
        routes.extend(
            [
                ("causal", self.causal_get, ["GET"]),
                ("causal", self.causal_post, ["POST"]),
            ]
        )
        for endpoint, handler, methods in routes:
            register_panel_api(self.plugin, self.plugin.context.register_web_api,
                "/astrbot_plugin_dynamics_world/" + endpoint,
                handler,
                methods,
                "群间世界管理",
            )

    async def cabin_style_get(self):
        from . import cabin_life
        guard = self.guard("cabin_style")
        if guard is not None:
            return guard
        try:
            umo = _query("umo")
            scope = (await self.scope(umo))[0] if umo else None
            engine = self.plugin.life.narrative
            with engine._db() as db:
                key = engine.scenes.key(db, scope) if scope else cabin_life.PREVIEW
                result = cabin_life.view(db, engine.scenes, scope, key)
            result["can_write"] = self.plugin.world.web.settings.web_panel_allow_write
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def cabin_style_post(self):
        from . import cabin_life
        async with self.plugin._migration_lock:
            guard = self.guard("cabin_style", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) != {"umo","style","expected_revision"} or not isinstance(body["umo"], str):
                return _err("小屋外观字段无效")
            try:
                scope = (await self.scope(body["umo"]))[0] if body["umo"] else None
                engine = self.plugin.life.narrative
                binding = {}
                if scope:
                    with engine._db() as db:
                        key = engine.scenes.key(db, scope)
                    catalog = await asyncio.to_thread(self.avatar_library().catalog, key)
                    binding = catalog["selection"]
                with engine._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if scope:
                        engine._ensure(db, scope, engine.clock())
                    result = cabin_life.select(db,engine.scenes,scope,body["style"],body["expected_revision"],binding,engine.clock())
                self.bus.notify()
                result["can_write"] = True
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409 if "已改变" in str(exc) else 400)

    def guard(self, endpoint, write=False):
        if self.plugin._migrating:
            return _err("正在迁移，请稍后重试", 409)
        if self.plugin._terminating:
            return _err("插件正在停止", 503)
        return self.plugin.world.web._guard(endpoint, write=write)

    def _find_companion_owner(self, target_id: str):
        getter = getattr(self.plugin.context, "get_all_stars", None)
        if not callable(getter):
            return None, False
        raw = getter()
        entries = (
            list(raw.items())
            if isinstance(raw, dict)
            else [("", x) for x in (raw or [])]
        )
        for key, item in entries:
            val = (
                item.get
                if isinstance(item, dict)
                else lambda k, default=None: getattr(item, k, default)
            )
            names = [key, val("name"), val("root_dir_name"), val("module_path")]
            if any(
                isinstance(n, str) and (n == target_id or target_id in n.split("."))
                for n in names
            ):
                activated = val("activated", False) is True
                owner = next(
                    (
                        val(k)
                        for k in ("star_cls", "star", "plugin")
                        if val(k) is not None and not isinstance(val(k), type)
                    ),
                    None,
                )
                return owner, activated
        return None, False

    @staticmethod
    def _public_companion_summary(owner, umo: str = "") -> dict:
        getter = getattr(owner, "get_dynamics_summary", None)
        if callable(getter):
            try:
                data = getter(umo) if umo else getter()
                if isinstance(data, dict):
                    return data
            except TypeError:
                try:
                    data = getter()
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
            except Exception:
                pass
        caps_fn = getattr(owner, "get_dynamics_capabilities", None)
        if callable(caps_fn):
            try:
                caps = caps_fn()
                if isinstance(caps, dict) and isinstance(caps.get("summary"), dict):
                    return caps["summary"]
            except Exception:
                pass
        return {}

    def _companion_summary(
        self,
        umo: str = "",
        db=None,
        scope: dict | None = None,
        *,
        pending_outreach: int | None = None,
    ) -> dict:
        umo = str(umo or "").strip()
        summary = {
            "memory": {
                "installed": False,
                "ready": False,
                "conflicts": 0,
                "entry_count": 0,
                "bookmark_glow": False,
                "summary": "未接入",
            },
            "learning": {
                "installed": False,
                "ready": False,
                "pending": 0,
                "applied": 0,
                "recent_terms": [],
                "scope_active": False,
                "summary": "未接入",
            },
            "visual": {
                "installed": False,
                "ready": False,
                "characters": 0,
                "running": 0,
                "recent": 0,
                "frame_pixel_grid": None,
                "frame_label": "",
                "glow": False,
                "summary": "未接入",
            },
            "horizons": {
                "installed": False,
                "ready": False,
                "sources": 0,
                "books_reading": 0,
                "active_interests": 0,
                "pending_questions": 0,
                "pending_reviews": 0,
                "recent_title": "",
                "glow": False,
                "summary": "未接入",
            },
            "chat": {
                "installed": False,
                "ready": False,
                "mode": "",
                "shadow": False,
                "active_sessions": 0,
                "session_tracked": False,
                "pending_outreach": 0,
                "glow": False,
                "summary": "未接入",
            },
        }
        # 1. Dynamics Memory
        try:
            mem_owner, mem_act = self._find_companion_owner(
                "astrbot_plugin_dynamics_memory"
            )
            if mem_owner is not None or mem_act:
                caps = (
                    mem_owner.get_dynamics_capabilities()
                    if callable(getattr(mem_owner, "get_dynamics_capabilities", None))
                    else {}
                )
                ready = bool(caps.get("ready"))
                conflicts = len(caps.get("conflicts") or [])
                entry_count = int(
                    caps.get("memory_count") or caps.get("total_entries") or 0
                )
                summary["memory"].update(
                    installed=True,
                    ready=ready,
                    conflicts=conflicts,
                    entry_count=entry_count,
                    bookmark_glow=bool(ready and (conflicts > 0 or entry_count > 0)),
                    summary=(
                        "记忆检索与原文证据库就绪"
                        + (f" · {conflicts} 项冲突待核对" if conflicts else "")
                    )
                    if ready
                    else ("已加载，等待初始化或迁移完成" if mem_act else "已停用"),
                )
        except Exception:
            pass
        # 2. Dynamics Learning (public capabilities/summary only)
        try:
            lrn_owner, lrn_act = self._find_companion_owner(
                "astrbot_plugin_dynamics_learning"
            )
            if lrn_owner is not None or lrn_act:
                caps = (
                    lrn_owner.get_dynamics_capabilities()
                    if callable(getattr(lrn_owner, "get_dynamics_capabilities", None))
                    else {}
                )
                ready = bool(caps.get("ready"))
                lrn_sum = self._public_companion_summary(lrn_owner, umo)
                pending = int(lrn_sum.get("pending", 0) or 0)
                applied = int(lrn_sum.get("applied", 0) or 0)
                recent_terms = [
                    str(t)[:24] for t in (lrn_sum.get("recent_terms") or [])[:3] if t
                ]
                scope_active = (
                    bool(lrn_sum.get("scope_active"))
                    if "scope_active" in lrn_sum
                    else False
                )
                summary_text = str(lrn_sum.get("summary") or "")
                if not summary_text:
                    summary_text = (
                        (
                            f"待审提案 {pending} 条 · 已生效 {applied} 条"
                            if (pending or applied)
                            else "学习服务已就绪"
                        )
                        if ready
                        else ("等待启用接管" if lrn_act else "已停用")
                    )
                summary["learning"].update(
                    installed=True,
                    ready=ready,
                    pending=pending,
                    applied=applied,
                    recent_terms=recent_terms,
                    scope_active=scope_active,
                    summary=summary_text,
                )
        except Exception:
            pass
        # 3. Visual Media (+ local visual_assets fallback for north-wall pixel frame)
        frame_grid = None
        frame_label = ""
        try:
            vis_owner, vis_act = self._find_companion_owner(
                "astrbot_plugin_visual_media"
            )
            if vis_owner is not None or vis_act:
                caps = (
                    vis_owner.get_dynamics_capabilities()
                    if callable(getattr(vis_owner, "get_dynamics_capabilities", None))
                    else {}
                )
                ready = bool(caps.get("ready"))
                vis_sum = self._public_companion_summary(vis_owner, umo)
                chars = int(vis_sum.get("characters", 0) or 0)
                running = int(vis_sum.get("running", 0) or 0)
                recent = int(vis_sum.get("recent", 0) or 0)
                candidate_path = vis_sum.get("latest_output_path")
                if candidate_path:
                    frame_grid = _sample_pixel_frame(Path(str(candidate_path)))
                    if frame_grid:
                        frame_label = str(
                            vis_sum.get("latest_prompt") or "视觉工坊近期成片"
                        )[:36]
                summary["visual"].update(
                    installed=True,
                    ready=ready,
                    characters=chars,
                    running=running,
                    recent=recent,
                    glow=running > 0,
                    summary=str(vis_sum.get("summary") or "")
                    or (
                        f"角色档案 {chars} 个 · 近期成片 {recent} 组"
                        + (f" · 生成中 {running}" if running else "")
                        if ready
                        else ("视觉服务待就绪" if vis_act else "已停用")
                    ),
                )
        except Exception:
            pass
        if frame_grid is None:
            try:
                asset_root = self.plugin.life.narrative.visuals.profiles.asset_root
                idx_file = asset_root / "index.json"
                if idx_file.is_file():
                    rows = json.loads(idx_file.read_text("utf-8"))
                    if isinstance(rows, dict) and rows:
                        last_meta = list(rows.values())[-1]
                        frame_grid = _sample_pixel_frame(
                            asset_root / str(last_meta.get("file", ""))
                        )
                        frame_label = str(last_meta.get("label") or "墙面装裱参考画")[
                            :36
                        ]
            except Exception:
                pass
        if frame_grid is not None:
            summary["visual"]["frame_pixel_grid"] = frame_grid
            summary["visual"]["frame_label"] = frame_label
        # 4. Chat Dynamics (+ pending outreach pulse)
        if pending_outreach is None:
            pending_outreach = 0
            if db is not None and scope is not None:
                try:
                    from .life.core.narrative import _identity

                    pending_outreach = int(
                        db.execute(
                            "SELECT COUNT(*) FROM intents WHERE identity=? AND status='pending' AND expires>?",
                            (_identity(scope), self.plugin.life.narrative.clock()),
                        ).fetchone()[0]
                    )
                except Exception:
                    pending_outreach = 0
        try:
            cd_owner, cd_act = self._find_companion_owner(
                "astrbot_plugin_chat_dynamics"
            )
            if cd_owner is not None or cd_act:
                cd_sum = self._public_companion_summary(cd_owner, umo)
                shared_cfg = {}
                shared_fn = getattr(cd_owner, "get_series_shared_config", None)
                if callable(shared_fn):
                    try:
                        raw_shared = shared_fn()
                        if isinstance(raw_shared, dict):
                            shared_cfg = raw_shared
                    except Exception:
                        shared_cfg = {}
                caps = (
                    cd_owner.get_dynamics_capabilities()
                    if callable(getattr(cd_owner, "get_dynamics_capabilities", None))
                    else {}
                )
                mode = str(
                    cd_sum.get("mode")
                    or shared_cfg.get("pipeline_mode")
                    or caps.get("mode")
                    or "filter"
                )
                shadow = bool(
                    cd_sum.get("shadow", shared_cfg.get("shadow_mode", False))
                )
                active_n = int(cd_sum.get("active_sessions", 0) or 0)
                tracked = bool(cd_sum.get("session_tracked", False))
                ready = bool(cd_act and cd_owner is not None)
                mode_zh = "独占接管" if mode == "exclusive" else "过滤协同"
                summary["chat"].update(
                    installed=True,
                    ready=ready,
                    mode=mode,
                    shadow=shadow,
                    active_sessions=active_n,
                    session_tracked=tracked,
                    pending_outreach=pending_outreach,
                    glow=bool(pending_outreach > 0 or (ready and tracked)),
                    summary=str(cd_sum.get("summary") or "")
                    or (
                        f"{mode_zh}{'（影子观察）' if shadow else ''} · 活跃群会话 {active_n} 个"
                        + (" · 当前群已追踪" if tracked else "")
                        + (f" · 待联系 {pending_outreach}" if pending_outreach else "")
                        if ready
                        else "主控未激活"
                    ),
                )
            else:
                summary["chat"].update(
                    pending_outreach=pending_outreach, glow=pending_outreach > 0
                )
        except Exception:
            pass
        # 5. Dynamics Horizons
        try:
            hz_owner, hz_act = self._find_companion_owner(
                "astrbot_plugin_dynamics_horizons"
            )
            if hz_owner is not None or hz_act:
                caps_fn = getattr(
                    hz_owner, "get_dynamics_capabilities", None
                ) or getattr(hz_owner, "horizons_capabilities", None)
                caps = caps_fn() if callable(caps_fn) else {}
                ready = bool(caps.get("ready"))
                hz_sum = (
                    caps.get("summary")
                    if isinstance(caps.get("summary"), dict)
                    else self._public_companion_summary(hz_owner, umo)
                )
                sources = int(hz_sum.get("sources", 0) or 0)
                books_reading = int(hz_sum.get("books_reading", 0) or 0)
                active_interests = int(hz_sum.get("active_interests", 0) or 0)
                pending_questions = int(hz_sum.get("pending_questions", 0) or 0)
                pending_reviews = int(hz_sum.get("pending_reviews", 0) or 0)
                recent_title = str(hz_sum.get("recent_title", "") or "")[:60]
                glow = bool(
                    ready
                    and (
                        hz_sum.get("glow")
                        or pending_reviews > 0
                        or active_interests > 0
                        or books_reading > 0
                    )
                )
                summary["horizons"].update(
                    installed=True,
                    ready=ready,
                    sources=sources,
                    books_reading=books_reading,
                    active_interests=active_interests,
                    pending_questions=pending_questions,
                    pending_reviews=pending_reviews,
                    recent_title=recent_title,
                    glow=glow,
                    summary=(
                        f"活跃兴趣 {active_interests} 项 · 在读书籍 {books_reading} 册"
                        + (f" · 待审 {pending_reviews}" if pending_reviews else "")
                    )
                    if ready
                    else ("见闻服务待就绪" if hz_act else "已停用"),
                )
        except Exception:
            pass
        return summary

    async def overview(self):
        guard = self.guard("world")
        if guard is not None:
            return guard
        p = self.plugin
        return _ok(
            {
                "runtime_enabled": p.config.get("runtime_enabled") is True,
                "ready": p.runtime_allowed(),
                "conflicts": p.conflicts(),
                "mode": p.config.get("mode"),
                "persona_id": p.config.get("persona_id"),
                "settings_import_available": (
                    p.data_dir / "migration-settings.json"
                ).exists(),
                "sessions": sorted(
                    set(p.world.store._store.sessions)
                    | set(p.config.get("narrative_sessions", []))
                ),
                "compatibility": p.onboarding.compatibility(),
                "companions": self._companion_summary(_query("umo")),
                "capabilities": p.get_dynamics_capabilities(),
            }
        )

    async def setup_get(self):
        guard = self.guard("setup")
        if guard is not None:
            return guard
        return _ok(await self.plugin.onboarding.status(_query("umo")))

    def avatar_library(self):
        from .avatar_models import AvatarLibrary

        return AvatarLibrary(self.plugin.data_root / "avatar-models")

    async def avatar_get(self):
        guard = self.guard("avatar")
        if guard is not None:
            return guard
        try:
            scope, _ = await self.scope(_query("umo"))
            engine = self.plugin.life.narrative
            with engine._db() as db:
                key, _, state = engine.scenes.load(db, scope)
            data = await asyncio.to_thread(self.avatar_library().catalog, key)
            data.update(
                can_write=self.plugin.world.web.settings.web_panel_allow_write,
                rooms=list((state or {}).get("rooms", {}).values()),
                scene_available=bool(state),
            )
            return _ok(data)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def avatar_model_get(self):
        guard = self.guard("avatar_model")
        if guard is not None:
            return guard
        try:
            await self.scope(_query("umo"))
            return _ok(
                await asyncio.to_thread(self.avatar_library().model, _query("model_id"))
            )
        except (ValueError, TypeError) as exc:
            return _err(str(exc), 404)

    async def avatar_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("avatar", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) - {
                "umo",
                "model_id",
                "texture_index",
                "home_room_id",
                "garden_room_id",
                "expected_revision",
            }:
                return _err("未知角色模型字段")
            try:
                scope, _ = await self.scope(body.get("umo", ""))
                engine = self.plugin.life.narrative
                with engine._db() as db:
                    key, _, state = engine.scenes.load(db, scope)
                rooms = (state or {}).get("rooms", {})
                prior = self.avatar_library().catalog(key)["selection"]
                home = body.get("home_room_id", prior["home_room_id"])
                garden = body.get("garden_room_id", prior["garden_room_id"])
                if any(
                    not isinstance(v, str) or v and v not in rooms
                    for v in [home, garden]
                ):
                    raise ValueError("显示区域必须绑定当前世界已有房间")
                if home and home == garden:
                    raise ValueError("室内和花园不能绑定同一个房间")
                res = await asyncio.to_thread(
                    self.avatar_library().select,
                    key,
                    {k: v for k, v in body.items() if k != "umo"},
                )
                if "home_room_id" in body or "garden_room_id" in body:
                    from . import cabin_life
                    with engine._db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        cabin_life.update_binding(db, key, res)
                self.bus.notify()
                return _ok(res)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def avatar_upload_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("avatar_upload", True)
            if guard is not None:
                return guard
            body = await _body(12 * 1024 * 1024)
            if "__invalid__" in body:
                return _err(body["__invalid__"])
            if set(body) - {"umo", "filename", "name", "file_base64"}:
                return _err("未知模型上传字段")
            try:
                import base64
                import binascii

                await self.scope(body.get("umo", ""))
                encoded = body.get("file_base64")
                if (
                    not isinstance(encoded, str)
                    or not 0 < len(encoded) <= ((8 * 1024 * 1024 + 2) // 3) * 4
                ):
                    raise ValueError("模型包最大 8 MiB")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError("模型文件编码无效") from None
                return _ok(
                    await asyncio.to_thread(
                        self.avatar_library().import_package,
                        body.get("filename", ""),
                        raw,
                        body.get("name", ""),
                    )
                )
            except (ValueError, TypeError) as exc:
                return _err(str(exc))

    async def projects_get(self):
        guard = self.guard("projects")
        if guard is not None:
            return guard
        try:
            from .creative_projects import detail, public

            scope, _ = await self.scope(_query("umo"))
            engine = self.plugin.life.narrative
            with engine._db() as db:
                db.execute("BEGIN IMMEDIATE")
                engine.spatial.settle(db, scope, engine.clock())
                engine.scenes.settle(db, scope, engine.clock())
                _, revision, state = engine.scenes.load(db, scope)
                pid = _query("project_id")
                if not state:
                    if pid:
                        raise ValueError("项目不存在或不属于当前世界")
                    return _ok(
                        {
                            "available": False,
                            "projects": [],
                            "scene_revision": 0,
                            "action": None,
                            "can_write": self.plugin.world.web.settings.web_panel_allow_write,
                        }
                    )
                if pid:
                    return _ok({"project": detail(state, pid)})
                action = state.get("flow")
                return _ok(
                    {
                        "available": True,
                        "projects": public(state, admin=True),
                        "scene_revision": revision,
                        "action": {
                            k: action.get(k)
                            for k in ("id", "label", "index", "step_ends_at", "origin")
                        }
                        if action
                        else None,
                        "can_write": self.plugin.world.web.settings.web_panel_allow_write,
                        "paused": state.get("paused_at") is not None,
                        "server_time": engine.clock(),
                    }
                )
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def activity_get(self):
        guard = self.guard("activity")
        if guard is not None:
            return guard
        try:
            from .activity_feed import page

            scope, _ = await self.scope(_query("umo"))
            engine = self.plugin.life.narrative
            with engine._db() as db:
                db.execute("BEGIN IMMEDIATE")
                engine.spatial.settle(db, scope, engine.clock())
                engine.scenes.settle(db, scope, engine.clock())
                result = page(
                    engine,
                    db,
                    scope,
                    before=_query("before"),
                    limit=int(_query("limit") or 30),
                    category=_query("category") or "all",
                )
                scene = engine.scenes.snapshot(db, scope, engine.clock())
                action = scene.get("action")
                result["current"] = {
                    "place": scene.get("place_name"),
                    "room": scene.get("room_name"),
                    "phase": scene.get("phase"),
                    "destination": scene.get("destination"),
                    "paused": scene.get("paused", False),
                    "action": {
                        k: action.get(k)
                        for k in ("label", "progress", "step_ends_at", "origin")
                    }
                    if action
                    else None,
                }
                result["server_time"] = engine.clock()
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def journal_feed_get(self):
        guard = self.guard("journal_feed")
        if guard is not None:
            return guard
        try:
            from .series_hooks import aggregate_journal_feed

            umo = _query("scope") or _query("umo")
            persona = _query("persona")
            date = _query("date") or "today"
            raw_limit = _query("limit")
            try:
                limit = int(raw_limit) if raw_limit else 30
            except (TypeError, ValueError):
                limit = 30
            result = await aggregate_journal_feed(
                self.plugin,
                persona=persona,
                scope=umo,
                date=date,
                limit=limit,
            )
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def projects_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("projects", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) - {"umo", "project_id", "action", "expected_revision"}:
                return _err("未知项目字段")
            try:
                scope, _ = await self.scope(body.get("umo", ""))
                engine = self.plugin.life.narrative
                now = engine.clock()
                if body.get("action") not in {"pause", "resume"}:
                    raise ValueError("只支持暂停或继续项目")
                with engine._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    engine.scenes.settle(db, scope, now)
                    key, rev, state = engine.scenes.load(db, scope)
                    if (
                        not state
                        or type(body.get("expected_revision")) is not int
                        or body["expected_revision"] != rev
                    ):
                        raise ValueError("场景已变化，请刷新后重试")
                    project = state.get("projects", {}).get(body.get("project_id"))
                    if not project:
                        raise ValueError("项目不存在或不属于当前世界")
                    expected = "active" if body["action"] == "pause" else "paused"
                    if project["status"] != expected:
                        raise ValueError("项目状态已变化，请刷新")
                    if (
                        body["action"] == "resume"
                        and sum(
                            p["status"] == "active"
                            for p in state.get("projects", {}).values()
                        )
                        >= 4
                    ):
                        raise ValueError("请先完成或暂停其他进行中项目")
                    flow = state.get("flow")
                    cancelled = False
                    if body["action"] == "pause" and flow:
                        remaining = flow["steps"][flow["index"] :]
                        related = {
                            s.get("project_id")
                            for s in remaining
                            if s.get("project_id")
                        }
                        if remaining[0].get("project_id") == project[
                            "id"
                        ] or related == {project["id"]}:
                            engine.scenes.finish_flow(
                                db,
                                scope,
                                key,
                                state,
                                now,
                                "cancelled",
                                "管理员暂停创作项目；已保存版本保留",
                            )
                            cancelled = True
                    project.update(
                        status="paused" if body["action"] == "pause" else "active",
                        paused_by="admin" if body["action"] == "pause" else None,
                        updated_at=now,
                        revision=project["revision"] + 1,
                    )
                    from .creative_projects import summary

                    engine.scenes.audit(
                        db,
                        key,
                        "project.paused"
                        if body["action"] == "pause"
                        else "project.resumed",
                        now,
                        {"origin": "admin", "project": summary(project)},
                    )
                    engine.scenes.save(db, key, rev, state)
                return _ok({"saved": True, "cancelled_remaining_flow": cancelled})
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def setup_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("setup", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) - {
                "action",
                "preset",
                "name",
                "prompt",
                "card_id",
                "provider_id",
                "umo",
                "enabled",
                "config_revision",
                "place_name",
                "place_id",
                "room_id",
                "scene_revision",
                "furniture",
                "lighting",
                "curtains",
                "texture",
            }:
                return _err("未知安装引导字段")
            try:
                return _ok(await self.plugin.onboarding.apply(body))
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def scope(self, umo):
        if (
            not isinstance(umo, str)
            or len(umo) > 300
            or not umo
            or len(umo.split(":")) < 3
        ):
            raise ValueError("请选择完整的会话标识")
        result = await self.plugin.world.get_character_context(
            {
                "platform": umo.split(":", 1)[0],
                "umo": umo,
                "persona_id": "",
                "instance_id": "",
            }
        )
        if result.get("disabled") or not result.get("persona_id"):
            raise ValueError("该会话尚未绑定有效角色")
        return result["scope"], result

    async def life_get(self):
        guard = self.guard("life")
        if guard is not None:
            return guard
        try:
            scope, character = await self.scope(_query("umo"))
            data = await self.plugin.life.get_narrative_admin(scope)
            data["character"] = {
                k: character.get(k) for k in ("name", "persona_id", "scenario")
            }
            data["scope"] = scope
            if self.plugin.config.get("mode") == "legacy":
                state, target_date = self.plugin.life._select_current_state(
                    self.plugin.life._now()
                )
                raw_state = self.plugin.life.data_mgr.get_by_date(str(target_date))
                legacy_failed = bool(raw_state and raw_state.status == "failed")
                data["legacy"] = {
                    "date": str(target_date),
                    "text": self.plugin.life._format_full_state(state)
                    if state
                    else ("当天作息生成失败" if legacy_failed else "当天尚未生成作息"),
                }
                data["plan_status"] = {
                    "today": str(target_date),
                    "plan_date": str(target_date) if state else "",
                    "is_today": bool(state),
                    "status": "generating"
                    if self.plugin.life.generator.is_generating
                    else (
                        "ready"
                        if state
                        else ("failed" if legacy_failed else "missing")
                    ),
                    "last_attempt_at": None,
                    "last_attempt_status": "failed" if legacy_failed else "",
                    "last_error": "legacy_generation_failed" if legacy_failed else "",
                    "generating": bool(self.plugin.life.generator.is_generating),
                }
            return _ok(data)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def life_post(self):
        guard = self.guard("life", True)
        if guard is not None:
            return guard
        body = await _body()
        if set(body) - {"action", "umo", "patch", "intent_id", "extra"}:
            return _err("请求包含未知字段")
        try:
            scope, _ = await self.scope(body.get("umo", ""))
            action, life = body.get("action"), self.plugin.life
            if action in {"pause", "resume", "pause_outreach", "resume_outreach"}:
                result = await life.set_paused(
                    action.startswith("pause"),
                    scope,
                    proactive_only=action.endswith("outreach"),
                )
            elif action == "correct":
                result = await life.correct_state(scope, body.get("patch", {}))
            elif action == "regenerate_plan":
                extra = str(body.get("extra") or "").strip()[:200]
                result = await life.regenerate_plan(scope, extra=extra)
                self.bus.notify()
                if result.get("status") != "regenerated":
                    code = 409 if result.get("status") in {"paused", "generating", "stale"} else 502
                    return _err(
                        str(result.get("message") or "日程重新生成失败，请稍后重试。"),
                        code,
                    )
            elif action == "cancel_intent":
                intent = await life.get_intent(body.get("intent_id", ""))
                actual_scope = (intent.get("item") or {}).get("scope", {})
                if not intent.get("available") or any(
                    actual_scope.get(k) != scope.get(k)
                    for k in ("platform", "umo", "persona_id", "instance_id")
                ):
                    return _err("联系动机不属于所选会话", 403)
                result = await life.cancel_intent(body["intent_id"])
            else:
                return _err("未知操作")
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def migration_get(self):
        guard = self.guard("migration")
        if guard is not None:
            return guard
        try:
            p = self.plugin
            result = await asyncio.to_thread(
                preview,
                p.data_root.parent,
                p.data_root,
                p.data_root.parent.parent / "config",
            )
            return _ok(result)
        except Exception as exc:
            return _err("无法预览迁移：" + str(exc))

    async def migration_post(self):
        guard = self.guard("migration", True)
        if guard is not None:
            return guard
        body = await _body()
        if set(body) - {"action", "fingerprint"}:
            return _err("请求包含未知字段")
        try:
            if body.get("action") == "import":
                result = await self.plugin.import_legacy(body.get("fingerprint", ""))
            elif body.get("action") == "apply_settings":
                result = await self.plugin.apply_imported_settings()
            else:
                return _err("未知操作")
            return _ok(result)
        except Exception as exc:
            return _err("迁移未完成：" + str(exc), 409)

    async def persona_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("persona", True)
            if guard is not None:
                return guard
            if self.plugin.conflicts():
                return _err("请先停用旧世界书和动态生活，再同步人格", 409)
            body = await _body()
            if set(body) != {"card_id"}:
                return _err("请选择要同步的角色卡")
            card = self.plugin.world.store.get_card(body["card_id"])
            if card is None:
                return _err("角色卡不存在", 404)
            message = await self.plugin.world._sync_persona(card)
            if message.startswith("⚠️"):
                return _err(message, 409)
            return _ok({"persona_id": card.persona_id, "message": message})

    async def stream_get(self):
        guard = self.guard("stream")
        if guard is not None:
            return guard
        try:
            return await open_sse_stream(
                self, _query("umo") or "", _query("known_revisions") or ""
            )
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def map_get(self):
        guard = self.guard("map")
        if guard is not None:
            return guard
        try:
            known_map = _query("revision")
            known_map_rev = int(known_map) if known_map else None
            known_revs = parse_known_revisions(_query("known_revisions"))
            _, payload = await assemble_world_payload(
                self,
                _query("umo") or "",
                known_map_rev=known_map_rev,
                world_id_hash=str(_query("world_id") or ""),
                known_revisions=known_revs,
            )
            return _ok(payload)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def map_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("map", True)
            if guard is not None:
                return guard
            body = await _body()
            allowed = {
                "action",
                "umo",
                "seed",
                "places",
                "seconds_per_unit",
                "expected_revision",
                "map_revision",
                "position_revision",
                "target_id",
                "not_before",
                "name",
                "place_id",
                "x",
                "y",
                "mode",
                "latitude",
                "longitude",
                "timezone",
                "walking_kmh",
            }
            if set(body) - allowed:
                return _err("未知地图字段")
            try:
                scope, _ = await self.scope(body.get("umo", ""))
                action = body.get("action")
                if action == "generate":
                    result = await self.plugin.maps.start(scope, body)
                elif action in {"switch_mode", "configure_real"}:
                    from .geography import configure_real, switch_mode

                    if self.plugin.maps.task and not self.plugin.maps.task.done():
                        raise ValueError("请等待地图生成完成后切换模式")
                    spatial = self.plugin.life.narrative.spatial
                    result = (
                        switch_mode(
                            spatial,
                            scope,
                            body.get("mode"),
                            body.get("expected_revision"),
                        )
                        if action == "switch_mode"
                        else configure_real(spatial, scope, body)
                    )
                elif action == "save_place":
                    result = self.plugin.life.narrative.spatial.save_place(scope, body)
                elif action in {"locate", "plan", "depart", "cancel"}:
                    if any(
                        type(body.get(k)) is not int
                        for k in ("map_revision", "position_revision")
                    ):
                        raise ValueError("缺少地图与位置版本，请刷新")
                    result = self.plugin.life.narrative.spatial.admin_action(
                        scope,
                        {
                            "kind": action,
                            "target_id": body.get("target_id"),
                            "map_revision": body["map_revision"],
                            "position_revision": body["position_revision"],
                            **(
                                {"not_before": body["not_before"]}
                                if "not_before" in body
                                else {}
                            ),
                        },
                    )
                else:
                    raise ValueError("未知地图操作")
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def weather_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("weather", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) - {
                "action",
                "umo",
                "query",
                "settings",
                "expected_revision",
                "credentials",
                "credentials_revision",
            }:
                return _err("未知天气字段")
            try:
                scope, _ = await self.scope(body.get("umo", ""))
                service = self.plugin.life.narrative.environment
                if body.get("action") == "search":
                    return _ok(await service.search(body.get("query")))
                if body.get("action") == "credentials":
                    return _ok(service.credentials.save(body))
                if body.get("action") == "configure":
                    result = service.configure(scope, body)
                elif body.get("action") == "refresh":
                    result = {"scheduled": True}
                else:
                    raise ValueError("未知天气操作")
                service.schedule(scope)
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)
            except Exception:
                return _err("地点或天气服务暂时不可用，请稍后重试", 503)

    async def scene_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("scene", True)
            if guard is not None:
                return guard
            body = await _body()
            allowed = {
                "action",
                "umo",
                "expected_revision",
                "place_id",
                "room_id",
                "item_id",
                "name",
                "kind",
                "sheltered",
                "open",
                "opens",
                "closes",
                "accessible",
                "water",
                "steps",
                "preset",
                "target_id",
                "title",
                "text",
                "mode",
                "position",
                "enabled",
                "furniture",
                "lighting",
                "curtains",
                "map_mode",
                "sender_name",
                "message",
                "visitor_mode",
                "slot",
                "world_id",
                "label",
                "guest_name",
                "guest_model_id",
                "guest_texture",
                "spot",
                "caption",
                "prefer_3d",
                "shot_mode",
            }
            if set(body) - allowed:
                return _err("未知场景字段")
            try:
                scope, character = await self.scope(body.get("umo", ""))
                engine = self.plugin.life.narrative
                service = engine.scenes
                act = body.get("action")
                if act == "bootstrap":
                    result = service.bootstrap(scope, body)
                elif act == "retire_item":
                    result = service.retire_item(scope, body)
                elif act in {"place", "room", "item", "room_design"}:
                    result = service.configure(scope, body)
                elif act in {"start", "preset", "cancel", "interrupt", "resume"}:
                    result = service.administer(scope, body)
                elif act == "admin_arrange":
                    result = service.admin_arrange(scope, body)
                elif act == "mailbox_deliver":
                    result = engine.mailbox.deliver_parcel(
                        scope,
                        sender_id="web_admin",
                        sender_name=str(body.get("sender_name") or "面板投递"),
                        kind=str(body.get("kind") or "postcard"),
                        title=str(body.get("title") or ""),
                        message=str(body.get("message") or ""),
                        character_context=character,
                        bypass_cooldown=True,
                    )
                elif act == "mailbox_open":
                    with engine._db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        opened = engine.mailbox.open_pending_parcels(
                            db, scope, engine.clock(), max_open=5
                        )
                    result = {"opened": opened, "count": len(opened)}
                elif act == "visitor_policy":
                    result = engine.mailbox.set_policy(
                        scope, str(body.get("visitor_mode") or "")
                    )
                elif act == "visitor_enter":
                    result = engine.mailbox.enter_garden(
                        scope,
                        user_id="web_visitor_"
                        + hashlib.sha256(
                            str(body.get("sender_name") or "旅人").encode()
                        ).hexdigest()[:8],
                        display_name=str(body.get("sender_name") or "旅人"),
                        note=str(body.get("message") or ""),
                        character_context=character,
                        bypass_cooldown=True,
                    )
                elif act == "keepsake_swap":
                    result = engine.keepsakes.swap_from_archive(
                        scope,
                        str(body.get("item_id") or ""),
                        str(body.get("slot") or ""),
                    )
                elif act == "world_space_bind":
                    result = engine.world_spaces.bind(
                        scope,
                        str(body.get("world_id") or ""),
                        str(body.get("label") or ""),
                        character.get("name", ""),
                    )
                elif act == "peer_visit":
                    result = engine.world_spaces.invite_guest(
                        scope,
                        guest_name=str(body.get("guest_name") or ""),
                        guest_model_id=str(body.get("guest_model_id") or "builtin"),
                        guest_texture=int(body.get("guest_texture") or 0),
                        spot=str(body.get("spot") or "garden_bench"),
                        activity=str(body.get("text") or ""),
                    )
                elif act == "postcard_render":
                    snap = await self.plugin.build_cabin_postcard_snapshot(
                        scope, character
                    )
                    result = await self.plugin.postcards.render(
                        snap,
                        plugin_dir=Path(__file__).parent,
                        caption=str(body.get("caption") or ""),
                        prefer_3d=bool(body.get("prefer_3d", True)),
                        shot_mode=str(body.get("shot_mode") or "auto"),
                    )
                else:
                    raise ValueError("未知场景操作")
                if (
                    act != "postcard_render"
                    and getattr(self.plugin.life.narrative, "on_db_write", None) is None
                ):
                    self.bus.notify()
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def visual_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("visual", True)
            if guard is not None:
                return guard
            body = await _body()
            if set(body) - {
                "umo",
                "action",
                "expected_revision",
                "target_id",
                "asset_ids",
                "asset_id",
                "layout",
                "appearance",
                "home_room_id",
                "placement",
                "kind",
                "preset",
            }:
                return _err("未知视觉设定字段")
            try:
                scope, _ = await self.scope(body.get("umo", ""))
                return _ok(
                    self.plugin.life.narrative.visuals.profiles.configure(scope, body)
                )
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)

    async def visual_get(self):
        guard = self.guard("visual")
        if guard is not None:
            return guard
        try:
            scope, _ = await self.scope(_query("umo"))
            engine = self.plugin.life.narrative
            with engine._db() as db:
                data = engine.visuals.profiles.admin(db, scope)
            data["can_write"] = self.plugin.world.web.settings.web_panel_allow_write
            return _ok(data)
        except (ValueError, TypeError) as exc:
            return _err(str(exc))

    async def visual_asset_get(self):
        guard = self.guard("visual_asset")
        if guard is not None:
            return guard
        try:
            await self.scope(_query("umo"))
            from .visual_assets import VisualAssetLibrary

            library = VisualAssetLibrary(self.plugin.life.narrative.visuals.profiles)
            return _ok(await asyncio.to_thread(library.preview, _query("asset_id")))
        except (ValueError, TypeError) as exc:
            return _err(str(exc), 404)

    async def visual_asset_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("visual_asset", True)
            if guard is not None:
                return guard
            body = await _body(12 * 1024 * 1024)
            if "__invalid__" in body:
                return _err(body["__invalid__"])
            if set(body) - {"umo", "role", "label", "source_url", "image_base64"}:
                return _err("未知素材字段")
            try:
                await self.scope(body.get("umo", ""))
                from .visual_assets import VisualAssetLibrary

                library = VisualAssetLibrary(
                    self.plugin.life.narrative.visuals.profiles
                )
                return _ok(await asyncio.to_thread(library.upload, body))
            except (ValueError, TypeError) as exc:
                return _err(str(exc))

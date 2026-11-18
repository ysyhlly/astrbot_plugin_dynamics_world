"""Panel-driven first installation and explicit companion contract checks."""

import asyncio
import base64
import copy
import hashlib
import io
import json
import os
import signal
import sys
from pathlib import Path

from .spatial import identity, place_id
from .style_presets import catalog, preset
from .world.core.character import CharacterCard
from .world.core.models import WorldBook, WorldEntry

FEATURES = (
    "character",
    "life",
    "environment",
    "scene",
    "visual_sharing",
    "room_design",
    "creative_projects",
)


class Onboarding:
    def __init__(self, plugin):
        self.plugin = plugin
        self.install_task = None
        self.install_process = None
        self.install_status = {"state": "idle", "message": ""}

    def companion(self, name):
        getter = getattr(self.plugin.context, "get_registered_star", None)
        try:
            star = getter(name) if callable(getter) else None
        except Exception:
            star = None
        return star, getattr(star, "star_cls", None) if star is not None and getattr(
            star, "activated", False
        ) else None

    def providers(self):
        getter = getattr(self.plugin.context, "get_all_providers", None)
        result = []
        try:
            providers = getter() if callable(getter) else []
        except Exception:
            providers = []
        for p in providers:
            cfg = getattr(p, "provider_config", {})
            if cfg.get("id") and callable(getattr(p, "text_chat", None)):
                result.append(
                    {"id": cfg["id"], "name": str(cfg.get("model") or cfg["id"])[:100]}
                )
        return result

    def revision(self):
        cfg = self.plugin.config
        values = {
            k: cfg.get(k)
            for k in (
                "persona_id",
                "narrative_provider_id",
                "narrative_sessions",
                "narrative_all_groups",
                "narrative_private_chat_enabled",
                "runtime_enabled",
                "visual_style_default",
            )
        }
        return hashlib.sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:24]

    def compatibility(self):
        _, cd = self.companion("astrbot_plugin_chat_dynamics")
        features = {}
        if cd is not None:
            try:
                value = cd.get_world_integration_capabilities()
                if (
                    isinstance(value, dict)
                    and type(value.get("schema_version")) is int
                    and value["schema_version"] == 1
                    and isinstance(value.get("features"), dict)
                ):
                    features = value["features"]
            except Exception:
                pass
        missing = [k for k in FEATURES if features.get(k) != 1]
        chat = {
            "state": "ready"
            if cd is not None and not missing
            else "missing"
            if cd is None
            else "update_required",
            "missing_features": missing,
        }
        _, media = self.companion("astrbot_plugin_visual_media")
        visual = {
            "state": "missing",
            "reference_access": False,
            "grant_supported": False,
            "tools": {},
        }
        if media is not None:
            visual["state"] = "unavailable"
            try:
                status = media.get_service(api_version=1).get_status()
                visual["state"] = "ready" if status.get("ready") else "unconfigured"
                visual["grant_supported"] = callable(
                    getattr(media, "grant_world_reference_access", None)
                )
                getter = getattr(self.plugin.context, "get_llm_tool_manager", None)
                manager = getter() if callable(getter) else None
                for name in (
                    "gemini_image_generation",
                    "generate_character_image",
                    "list_visual_characters",
                ):
                    tool = manager.get_func(name) if manager else None
                    visual["tools"][name] = tool is not None and getattr(
                        tool, "active", True
                    )
                if not all(visual["tools"].values()):
                    visual["state"] = "tools_unavailable"
                access = media.get_world_reference_access(
                    self.plugin.get_reference_assets_directory()
                )
                visual["reference_access"] = access.get("allowed") is True
            except AttributeError:
                visual["state"] = "update_required"
            except Exception:
                visual["state"] = "unavailable"
        return {
            "chat_dynamics": chat,
            "visual_media": visual,
            "legacy_conflicts": self.plugin.conflicts(),
        }

    async def browser_status(self):
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                available = Path(p.chromium.executable_path).is_file()
            return {"installed": available, "module_available": True}
        except Exception:
            return {"installed": False, "module_available": False}

    async def status(self, umo=""):
        p = self.plugin
        cfg = p.config
        if not umo:
            umo = next(iter(cfg.get("narrative_sessions", [])), "")
        if not umo and cfg.get("persona_id"):
            owner = identity(
                {"persona_id": cfg["persona_id"], "instance_id": cfg["persona_id"]}
            )
            with p.life.narrative._db() as db:
                row = db.execute(
                    "SELECT umo FROM scopes WHERE identity=? AND umo!='' ORDER BY CASE WHEN umo LIKE '%:GroupMessage:%' THEN 0 ELSE 1 END,umo LIMIT 1",
                    (owner,),
                ).fetchone()
                if row:
                    umo = row[0]
        cards = [
            {"id": c.id, "name": c.name, "persona_id": c.persona_id}
            for c in p.world.store.list_cards()
        ]
        result = {
            "config_revision": self.revision(),
            "selected_umo": umo,
            "can_write": p.world.web.settings.web_panel_allow_write,
            "presets": catalog(starters=True),
            "providers": self.providers(),
            "cards": cards,
            "config": {
                k: cfg.get(k)
                for k in (
                    "persona_id",
                    "narrative_provider_id",
                    "narrative_sessions",
                    "runtime_enabled",
                    "visual_style_default",
                )
            },
            "compatibility": self.compatibility(),
            "browser": await self.browser_status(),
            "browser_install": dict(self.install_status),
            "textures": p.textures.status(),
            "world": {"has_map": False, "has_rooms": False, "has_furniture": False},
        }
        if umo:
            try:
                scope, _ = await p.web.scope(umo)
                engine = p.life.narrative
                with engine._db() as db:
                    doc = engine.spatial.document(db, identity(scope))
                    _, rev, state = engine.scenes.load(db, scope)
                    result["world"] = {
                        "has_map": bool(doc),
                        "has_rooms": bool(state),
                        "has_furniture": bool((state or {}).get("room_designs")),
                        "scene_revision": rev,
                        "places": [
                            {k: x[k] for k in ("id", "name")}
                            for x in (doc or {}).get("places", [])
                        ],
                        "rooms": list((state or {}).get("rooms", {}).values()),
                        "designed_rooms": list((state or {}).get("room_designs", {})),
                        "scope_bound": True,
                    }
                    result["world"]["position"] = engine.spatial.snapshot(
                        db, scope, engine.clock()
                    ).get("phase", "unknown")
                    result["visual"] = engine.visuals.profiles.admin(db, scope)
            except (ValueError, TypeError):
                result["world"]["scope_bound"] = False
        return result

    def save_config(self, patch):
        p = self.plugin
        previous = copy.deepcopy(dict(p.host_config))
        next_config = copy.deepcopy(p.config)
        next_config.update(patch)
        save = getattr(p.host_config, "save_config", None)
        if not callable(save):
            raise ValueError("宿主配置保存接口不可用")
        try:
            p.host_config.update(next_config)
            save()
        except Exception:
            p.host_config.clear()
            p.host_config.update(previous)
            raise
        # These fields are read dynamically by the existing services. Keep the
        # shared object, pending actions and databases intact.
        p.config.update(next_config)

    async def apply(self, body):
        p = self.plugin
        action = body.get("action")

        def text(key, default=""):
            value = body.get(key, default)
            if not isinstance(value, str):
                raise ValueError("文本字段格式不正确")
            return value.strip()

        if action == "create_character":
            chosen = preset(body.get("preset", "generic"))
            name = text("name")
            prompt = text("prompt")
            if not 1 <= len(name) <= 60 or not 1 <= len(prompt) <= 6000:
                raise ValueError("请填写角色名称和设定")
            if p.world.store.find_card_by_name(name):
                raise ValueError("同名角色已存在，请选择已有角色，避免覆盖")
            card = CharacterCard(
                name=name, system_prompt=prompt, source="world_onboarding"
            )
            card.persona_id = "wb_world_" + card.id
            if chosen["entries"]:
                book = p.world.store.find_book_by_name("预设：" + chosen["name"])
                if book is None:
                    book = WorldBook(name="预设：" + chosen["name"])
                    book.entries = [WorldEntry(**row) for row in chosen["entries"]]
                    p.world.store.upsert_book(book)
                card.linked_book_id = book.id
            p.world.store.upsert_card(card)
            if not p.world.store.get_default_card_id():
                p.world.store.set_default_card(card.id)
            return {"created": True, "card_id": card.id}
        if action in {"configure", "activate"}:
            if body.get("config_revision") != self.revision():
                raise ValueError("配置已变化，请刷新引导后再保存")
            if action == "activate":
                enabled = body.get("enabled")
                if type(enabled) is not bool:
                    raise ValueError("请选择接入状态")
                if enabled:
                    report = self.compatibility()
                    if (
                        report["legacy_conflicts"]
                        or report["chat_dynamics"]["state"] != "ready"
                    ):
                        raise ValueError("请先解决 Chat Dynamics 兼容问题和旧插件冲突")
                    if (
                        not p.config.get("persona_id")
                        or p.config.get("narrative_provider_id")
                        not in {x["id"] for x in self.providers()}
                        or not p.life.narrative._has_targets()
                    ):
                        raise ValueError("请先完成角色、有效模型和会话绑定")
                self.save_config({"runtime_enabled": enabled})
                return {"saved": True, "runtime_enabled": enabled}
            card = p.world.store.get_card(body.get("card_id", ""))
            provider = body.get("provider_id")
            umo = body.get("umo", "")
            chosen = body.get("preset", "generic")
            preset(chosen)
            if card is None or provider not in {x["id"] for x in self.providers()}:
                raise ValueError("请选择有效角色与已启用的生活模型")
            if (
                not isinstance(umo, str)
                or len(umo) > 300
                or len(umo.split(":")) < 3
                or not all(umo.split(":"))
            ):
                raise ValueError("请填写完整会话标识")
            if p.config.get("runtime_enabled") and card.persona_id != p.config.get(
                "persona_id"
            ):
                raise ValueError("切换生活角色前，请先关闭接入")
            synced = await p.world._sync_persona(card)
            if synced.startswith("⚠️"):
                raise ValueError("人格同步未成功，请检查宿主人格服务")
            sessions = list(
                dict.fromkeys([*p.config.get("narrative_sessions", []), umo])
            )
            self.save_config(
                {
                    "persona_id": card.persona_id,
                    "narrative_provider_id": provider,
                    "narrative_sessions": sessions,
                    "visual_style_default": chosen,
                }
            )
            p.world.store.update_session(umo, card_id=card.id)
            scope, _ = await p.web.scope(umo)
            profiles = p.life.narrative.visuals.profiles
            with p.life.narrative._db() as db:
                current = profiles.admin(db, scope)
            profiles.configure(
                scope,
                {
                    "action": "style",
                    "asset_ids": current["profile"]["styles"],
                    "preset": chosen,
                    "expected_revision": current["revision"],
                },
            )
            return {
                "saved": True,
                "runtime_enabled": p.config.get("runtime_enabled") is True,
            }
        if action == "grant_references":
            return p.authorize_visual_reference_access()
        if action == "install_browser":
            if not (await self.browser_status())["module_available"]:
                raise ValueError("缺少 Playwright，请修复插件依赖安装")
            if self.install_task and not self.install_task.done():
                return dict(self.install_status)
            self.install_status = {
                "state": "running",
                "message": "正在安装 Chromium，完成后会自动更新状态",
            }
            self.install_task = asyncio.create_task(self.install_browser())
            return dict(self.install_status)
        if action == "download_textures":
            return p.textures.start()
        if action == "select_texture":
            return p.textures.select(body.get("texture", ""))
        if action == "starter_world":
            scope, _ = await p.web.scope(body.get("umo", ""))
            engine = p.life.narrative
            with engine._db() as db:
                if engine.spatial.document(db, identity(scope)):
                    raise ValueError("已有地图，不能用起始场景覆盖")
            title = text("place_name", "住所")
            if not 1 <= len(title) <= 60:
                raise ValueError("地点名称需为 1–60 字")
            from PIL import Image, ImageDraw

            buffer = io.BytesIO()
            image = Image.new("RGB", (600, 400), "#e6eee8")
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle(
                (160, 80, 440, 320),
                radius=20,
                fill="#b6ccba",
                outline="#5b7a63",
                width=3,
            )
            image.save(buffer, format="PNG")
            pid = place_id(title)
            engine.spatial.install(
                scope,
                {
                    "schema_version": 1,
                    "seed": "starter",
                    "generator": "起始地点示意图",
                    "map_type": "virtual",
                    "width": 600,
                    "height": 400,
                    "seconds_per_unit": 1,
                    "places": [
                        {"id": pid, "name": title, "x": 300, "y": 200, "cell": 0}
                    ],
                    "roads": [],
                    "graph": {"points": [[300, 200]], "edges": [[]]},
                    "image": "data:image/png;base64,"
                    + base64.b64encode(buffer.getvalue()).decode(),
                },
            )
            return {"created": True, "place_id": pid}
        if action == "initialize_rooms":
            scope, _ = await p.web.scope(body.get("umo", ""))
            engine = p.life.narrative
            with engine._db() as db:
                _, rev, state = engine.scenes.load(db, scope)
            if state:
                raise ValueError("已有房间和物品，不能重复初始化")
            return engine.scenes.bootstrap(
                scope, {"expected_revision": rev, "place_id": body.get("place_id")}
            )
        if action == "initial_location":
            scope, _ = await p.web.scope(body.get("umo", ""))
            engine = p.life.narrative
            with engine._db() as db:
                position = engine.spatial.snapshot(db, scope, engine.clock())
            if position.get("phase") != "unknown":
                raise ValueError("当前位置已确认，请在地图页使用正常行程")
            return engine.spatial.admin_action(
                scope,
                {
                    "kind": "locate",
                    "target_id": body.get("place_id"),
                    "map_revision": position["map_revision"],
                    "position_revision": position["revision"],
                },
            )
        if action == "register_furniture":
            scope, _ = await p.web.scope(body.get("umo", ""))
            engine = p.life.narrative
            with engine._db() as db:
                _, rev, state = engine.scenes.load(db, scope)
            if not state or body.get("scene_revision") != rev:
                raise ValueError("场景已变化，请刷新")
            room = state["rooms"].get(body.get("room_id"))
            if not room:
                raise ValueError("请选择已有房间")
            return engine.scenes.configure(
                scope,
                {
                    "action": "room_design",
                    "expected_revision": rev,
                    "place_id": room["place_id"],
                    "room_id": room["id"],
                    "enabled": True,
                    "furniture": body.get("furniture"),
                    "lighting": body.get("lighting"),
                    "curtains": body.get("curtains"),
                },
            )
        raise ValueError("未知引导操作")

    async def install_browser(self):
        try:
            kwargs = (
                {"creationflags": 0x08000000}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            self.install_process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                **kwargs,
            )
            await asyncio.wait_for(self.install_process.wait(), 300)
            ok = (
                self.install_process.returncode == 0
                and (await self.browser_status())["installed"]
            )
            self.install_status = {
                "state": "ready" if ok else "failed",
                "message": "Chromium 已安装"
                if ok
                else "安装未完成，请检查网络或宿主环境后重试",
            }
        except (asyncio.TimeoutError, OSError):
            self.install_status = {
                "state": "failed",
                "message": "安装超时或无法启动，请检查宿主环境",
            }
        finally:
            if self.install_process and self.install_process.returncode is None:
                if os.name == "nt":
                    killer = await asyncio.create_subprocess_exec(
                        "taskkill",
                        "/PID",
                        str(self.install_process.pid),
                        "/T",
                        "/F",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        creationflags=0x08000000,
                    )
                    await killer.wait()
                else:
                    try:
                        os.killpg(self.install_process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(self.install_process.wait(), 5)
                except asyncio.TimeoutError:
                    if os.name == "nt":
                        self.install_process.kill()
                    else:
                        try:
                            os.killpg(self.install_process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    await self.install_process.wait()
            self.install_process = None

    async def close(self):
        if self.install_task and not self.install_task.done():
            self.install_task.cancel()
            try:
                await self.install_task
            except asyncio.CancelledError:
                pass

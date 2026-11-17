"""World-owned visual context. No generation, network calls, or sending here."""

import hashlib
import json

from .spatial import identity
from .visual_profiles import VisualProfiles
from .style_presets import preset, selected

RULES = [
    "想分享眼前景色、刚发生的小事，或对方问起你那边的样子时，图像确有交流价值才选择画一幅；不必等斜杠命令，也不每轮配图。普通寒暄、答题和认真倾诉优先回应内容。",
    "画自己的见闻时，以当前地点、房间、途中状态和完成回执为依据。未抵达的目的地、未来安排不能说成亲眼经历。参考城市只提供天气，不把虚构世界搬到参考城市。明确要求想象、设定或未来场景时可画构想图，不需要先到场。",
    "可以按已有世界设定补充画面，未记录的装饰仅作艺术表达，不成为新的世界事实。室内天气只作光线和室外氛围参考，不把雨画进有遮蔽的房间，也不凭空宣称看见远处地点。",
    "纯景色或室内物品图用本轮允许的 gemini_image_generation，prompt 写画面描述。有 visual_design 时 references 必须按其中 references 的顺序填写 reference；否则默认 []。不要默认使用用户头像或当前消息照片。画本人先 list_visual_characters，再用 generate_character_image；世界角色 ID 不是视觉角色 key。",
    "把图表达为角色世界的插画、回忆示意或构想，例如“画给你看看”“大概是这样的”，不冒充真实相机拍摄。不要自动把群友身份、私聊、笔记全文、路径、坐标或内部 ID 写进生图提示词。",
    "只有实际调用工具并取得成功结果才算生成；按视觉工坊的工具回执交付，未完成就不说已发出，失败可回到文字。同一幕无新变化不反复画，可按本会话生成历史复用或修改。表情包用于情绪和接梗，景色见闻使用场景图；沿用现有媒体选择规则，避免重复发送。",
    "这些素材和规则不授予主动发言或外部工具权限。世界后台不自行生图或发图；工具未开放、暂停或停止边界生效时保持原限制，不绕过它们。",
    "没有工具调用或受理回执时，不说已画好、导不出来或正在后台生成，也不承诺稍后自动补发。工具不可用可用文字描写或简短说明这次无法生成；只有实际任务被受理才说明正在画。生成图不等于世界内拍照或新见闻。",
    "visual_design 持续保存视觉设定：底图保留建筑、家具外形和美术；room_state.changed=true 时，以 layout 的布置及灯光窗帘为准，可覆盖旧底图摆位。style 图仅参考画法。prompt 带入参考图用途、当前布局和外观。实时天气、携带、开关机、水量优先；移除 remove_from_layout 的物品，不留副本。generation_ready=false 时不无参考生成。摊开的笔记页只画不可读笔迹，不复制正文。新图不回写事实。",
]


def short(value, limit=60):
    return str(value or "").strip()[:limit]


class WorldVisualContext:
    def __init__(self, engine):
        self.engine = engine
        self.profiles = VisualProfiles(engine)
        self.media_status = None

    def snapshot(self, db, scope, now, spatial, scene, environment):
        spatial = spatial or {}
        scene = scene or {}
        environment = environment or {}
        result = {
            "schema_version": 1,
            "provider_id": "astrbot_plugin_dynamics_world",
            "available": False,
            "fact_kind": "fiction",
            "captured_at": now,
            "valid_until": now + 300,
            "rules": list(RULES),
            "tools": {
                "scenery": "gemini_image_generation",
                "character_lookup": "list_visual_characters",
                "character": "generate_character_image",
                "reuse": "gemini_image_lookup",
            },
            "references_default": [],
            "context_only": True,
            "current_scene": None,
            "recent_experiences": [],
        }
        _, _, profile = self.profiles.load(db, scope)
        chosen = selected(profile, self.engine.config)
        result["style_preset"] = chosen
        result["rules"].append(preset(chosen)["visual_rule"])
        doc = (
            self.engine.spatial.document(db, identity(scope))
            if self.engine.spatial
            else None
        )
        if not doc:
            result["limitations"] = [
                "没有已建立的地图位置；只能按已有设定或对方明确要求创作构想图，不描述为见闻。"
            ]
            return result
        design = self.profiles.project(db, scope, scene, spatial)
        if design["revision"] or design.get("room_state"):
            result["visual_design"] = design
            result["references_default"] = [
                r["reference"] for r in design["references"]
            ]
        if callable(self.media_status):
            status = self.media_status()
            result["generation_available"] = status.get("state") == "ready" and (
                not result["references_default"]
                or status.get("reference_access") is True
            )
            if not result["generation_available"]:
                result["rules"].append(
                    "当前生图配套能力或世界参考图读取权限尚未就绪。本轮使用文字描述，不调用未开放的工具，不绕过固定参考图生成，也不承诺后台补发。管理员可在安装引导检查或授权。"
                )
        phase = spatial.get("phase", "unknown")
        current = {
            "phase": phase,
            "map_kind": doc.get("map_type", "virtual"),
            "basis": "program_position",
        }
        constraints = []
        if phase == "unknown":
            constraints.append("角色尚未确认位置，不知道此刻具体看见什么。")
        elif phase == "travelling":
            journey = spatial.get("journey") or {}
            current.update(
                origin=short(spatial.get("place_name")),
                destination=short(journey.get("destination_name")),
            )
            constraints.append(
                "仍在途中；不能把目的地当作已抵达或已看到，路线图没有证明沿途的具体景物。"
            )
        else:
            current["place"] = short(spatial.get("place_name"))
            if scene.get("room_id"):
                current["room"] = short(scene.get("room_name"))
            elif scene.get("available"):
                constraints.append(
                    "具体房间未确认或位于地点入口；不要自行指定室内房间。"
                )
        sheltered = scene.get("sheltered")
        if type(sheltered) is bool:
            current["sheltered"] = sheltered
        if sheltered is True:
            constraints.append(
                "当前有遮蔽；固定布局若包含窗户，只按当前天气绘制窗外光线，不能把底图的远处建筑当成已确认地标。"
                if design.get("layout")
                else "当前有遮蔽；未记录窗户、视线或邻近地标，不推断能直接看见屋外景色。"
            )
        current["visible_objects"] = []
        for item in scene.get("items", []):
            if not (item.get("visible") or item.get("carried")):
                continue
            value = {
                "name": short(item.get("name")),
                "kind": short(item.get("kind"), 24),
                "carried": bool(item.get("carried")),
            }
            if item.get("kind") == "computer":
                value["powered"] = bool(item.get("powered"))
            if item.get("kind") == "umbrella":
                value["open"] = bool(item.get("open"))
            for key in ("servings", "capacity"):
                if type(item.get(key)) in (int, float):
                    value[key] = item[key]
            if item.get("wet") is True:
                value["wet"] = True
            current["visible_objects"].append(value)
            if len(current["visible_objects"]) >= 6:
                break
        action = scene.get("action")
        if action:
            current["activity_in_progress"] = short(action.get("label"), 100)
            constraints.append(
                "当前动作仍在进行；绘制正在做的姿态可以，不能把后续步骤画成已经完成并声称真实发生。"
            )
        if (
            environment.get("available") is True
            and not environment.get("stale")
            and environment.get("status") == "ready"
        ):
            weather = environment.get("current") or {}
            current["visual_weather"] = {
                "condition": short(weather.get("label"), 24),
                "is_day": weather.get("is_day")
                if type(weather.get("is_day")) is bool
                else None,
                "basis": "fictional_simulation"
                if environment.get("fact_kind") == "fiction"
                else "configured_weather_reference",
            }
        else:
            constraints.append(
                "当前天气不可确认；不从旧值或地名编造此刻下雨、晴天、黄昏或日照。可选中性光线的示意图，或明确作为构想创作。"
            )
        places = {p["id"]: p["name"] for p in doc.get("places", [])}
        rooms = {r["id"]: r for r in scene.get("rooms", [])}
        map_row = db.execute(
            "SELECT created FROM world_maps WHERE identity=?", (identity(scope),)
        ).fetchone()
        since = max(now - 86400, map_row[0] if map_row else 0)
        # Scene receipts are namespaced by map mode. Admin changes, raw diary
        # prose, notebook contents and planned actions are never sightings.
        if self.engine.scenes and scene.get("available"):
            key = self.engine.scenes.key(db, scope)
            rows = db.execute(
                "SELECT event_id,occurred,payload FROM world_scene_events WHERE identity=? AND kind='step.completed' AND occurred>=? AND occurred<=? ORDER BY occurred DESC,rowid DESC LIMIT 20",
                (key, since, now),
            )
            seen = set()
            for row in rows:
                payload = json.loads(row["payload"])
                kind = payload.get("operation")
                target = payload.get("target_id")
                if kind not in {
                    "travel",
                    "enter",
                    "read",
                    "write_note",
                    "computer_work",
                }:
                    continue
                experience = {
                    "source_id": row["event_id"],
                    "occurred_at": row["occurred"],
                    "basis": "completed_fictional_action",
                }
                if kind == "travel":
                    if target not in places:
                        continue
                    experience.update(
                        kind="confirmed_visit",
                        place=short(places[target]),
                        description="已确认抵达这个地点；具体可见景物仍结合世界设定。",
                    )
                elif kind == "enter":
                    room = rooms.get(target)
                    if not room or room.get("place_id") not in places:
                        continue
                    experience.update(
                        kind="confirmed_room",
                        place=short(places[room["place_id"]]),
                        room=short(room["name"]),
                        description="已确认进入这个房间。",
                    )
                else:
                    if (
                        kind == "computer_work"
                        and (payload.get("result") or {}).get("last_mode") != "writing"
                    ):
                        continue
                    experience.update(
                        kind="daily_experience",
                        description={
                            "read": "完成过一段阅读，可以分享阅读氛围，不伪造已读完整本书。",
                            "write_note": "完成过一条笔记；可以表达创作氛围，不自动公开笔记正文。",
                            "computer_work": "完成过一次电脑写作；草稿是创作，不是亲眼见过的事件。",
                        }[kind],
                    )
                dedupe = (kind, experience.get("place"), experience.get("room"))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                result["recent_experiences"].append(experience)
                if len(result["recent_experiences"]) >= 3:
                    break
        result["current_scene"] = current
        result["available"] = phase == "located" or bool(result["recent_experiences"])
        result["limitations"] = constraints
        basis = [
            doc.get("world_id"),
            doc.get("revision"),
            phase,
            current.get("place"),
            current.get("room"),
            current.get("visual_weather"),
            current.get("visible_objects"),
            current.get("activity_in_progress"),
            [p["source_id"] for p in result["recent_experiences"]],
            design,
        ]
        result["scene_key"] = hashlib.sha256(
            json.dumps(basis, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()[:24]
        return result

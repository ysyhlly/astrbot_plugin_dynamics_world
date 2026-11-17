"""Human-readable, paged views of committed program receipts, never invented diary."""

import base64
import json
import math
from .spatial import identity
from .creative_projects import KINDS as PROJECTS, LABELS as PROJECT_LABELS, STAGES
from .room_design import KINDS as ROOM

SCENE_BASE = "kind IN ('step.completed','action.failed','action.cancelled','scene.initialized','project.paused','project.resumed') OR kind LIKE 'admin.%'"


def cursor(row):
    return (
        base64.urlsafe_b64encode(
            json.dumps(
                [row["occurred"], row["source"], row["seq"]], separators=(",", ":")
            ).encode()
        )
        .decode()
        .rstrip("=")
    )


def parse_cursor(value):
    if not value:
        return None
    try:
        if not isinstance(value, str) or len(value) > 256:
            raise ValueError()
        result = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if not isinstance(result, list) or len(result) != 3:
            raise ValueError()
        at, source, seq = result
        if (
            type(at) not in (int, float)
            or not math.isfinite(at)
            or not 0 <= at < 1e12
            or type(source) is not int
            or source not in {0, 1}
            or type(seq) is not int
            or seq < 1
        ):
            raise ValueError()
        return result
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("无效的动态翻页位置") from exc


def page(engine, db, scope, *, before="", limit=30, category="all"):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("每页需为 1–50 条")
    if category not in {
        "all",
        "projects",
        "room",
        "movement",
        "admin",
        "errors",
        "ecology",
        "mailbox",
        "timeline",
        "encounters",
    }:
        raise ValueError("未知动态分类")
    if category == "timeline" and getattr(engine, "keepsakes", None) is not None:
        frames = engine.keepsakes.timeline_snapshot(
            db, scope, engine.clock(), limit=limit
        )
        return {
            "events": [
                {
                    "id": "kf:" + f["id"],
                    "occurred_at": f["occurred_at"],
                    "status": "completed",
                    "title": f.get("clock_label", "")
                    + " · "
                    + (f.get("place_name") or "小屋"),
                    "description": f.get("summary", ""),
                    "source": "时间轴关键帧",
                    "scope": "过去 24h 足迹",
                }
                for f in reversed(frames)
            ],
            "next_cursor": None,
            "category": category,
            "fact_kind": "program_receipts",
        }
    if category == "mailbox" and getattr(engine, "mailbox", None) is not None:
        snap = engine.mailbox.snapshot(db, scope, engine.clock())
        return {
            "events": [
                {
                    "id": "mail:" + p["parcel_id"],
                    "occurred_at": p["opened_at"] or p["created_at"],
                    "status": p["status"],
                    "title": p["kind_label"] + " · " + p["title"],
                    "description": p["reaction"] or p["message"],
                    "source": p["sender_name"],
                    "scope": "院门信箱",
                }
                for p in snap["parcels"][:limit]
            ],
            "next_cursor": None,
            "category": category,
            "fact_kind": "program_receipts",
        }
    if category == "encounters" and getattr(engine, "world_spaces", None) is not None:
        snap = engine.world_spaces.snapshot(db, scope, engine.clock())
        return {
            "events": [
                {
                    "id": "enc:" + e["id"],
                    "occurred_at": e["occurred_at"],
                    "status": "completed",
                    "title": "同组角色互动 · " + e["place_name"],
                    "description": e["summary"],
                    "source": "共享世界组",
                    "scope": snap["label"],
                }
                for e in snap["recent_encounters"][:limit]
            ],
            "next_cursor": None,
            "category": category,
            "fact_kind": "program_receipts",
        }
    previous = parse_cursor(before)
    scene_key = engine.scenes.key(db, scope)
    owner = identity(scope)
    operation = "json_extract(payload,'$.operation')"
    if category == "projects":
        scene_filter = (
            "(kind='step.completed' AND "
            + operation
            + " LIKE 'project_%') OR kind IN ('project.paused','project.resumed')"
        )
    elif category == "room":
        scene_filter = (
            "kind='step.completed' AND "
            + operation
            + " IN ('move_furniture','place_item','set_lighting','set_curtains','display_note')"
        )
    elif category == "ecology":
        scene_filter = (
            "kind='step.completed' AND "
            + operation
            + " IN ('water_garden','harvest_garden','prepare_meal','brew_tea','open_mailbox')"
        )
    elif category == "movement":
        scene_filter = (
            "kind='step.completed' AND " + operation + " IN ('enter','leave')"
        )
    elif category == "admin":
        scene_filter = "kind LIKE 'admin.%' OR kind='scene.initialized'"
    elif category == "errors":
        scene_filter = "kind IN ('action.failed','action.cancelled','action.rejected')"
    else:
        scene_filter = (
            "(" + SCENE_BASE + ") AND COALESCE(" + operation + ",'')!='travel'"
        )
    map_filter = (
        "kind LIKE 'admin.%'"
        if category == "admin"
        else "1"
        if category in {"all", "movement"}
        else "0"
    )
    query = (
        """WITH records AS (
        SELECT event_id,kind,occurred,payload,0 source,rowid seq FROM world_scene_events WHERE identity=? AND ("""
        + scene_filter
        + """)
        UNION ALL SELECT id event_id,kind,occurred,payload,1 source,rowid seq FROM world_map_events WHERE identity=? AND ("""
        + map_filter
        + """))
        SELECT * FROM records"""
    )
    args = [scene_key, owner]
    if previous:
        at, source, seq = previous
        query += (
            " WHERE occurred<? OR (occurred=? AND (source<? OR (source=? AND seq<?)))"
        )
        args += [at, at, source, source, seq]
    query += " ORDER BY occurred DESC,source DESC,seq DESC LIMIT ?"
    args.append(limit + 1)
    records = list(db.execute(query, args))
    more = len(records) > limit
    records = records[:limit]
    _, _, scene = engine.scenes.load(db, scope)
    doc = engine.spatial.document(db, owner) or {}
    names = {p["id"]: p["name"] for p in doc.get("places", [])}
    if scene:
        names.update({k: v["name"] for k, v in scene["rooms"].items()})
        names.update({k: v["name"] for k, v in scene["items"].items()})
    rows = []
    for row in records:
        payload = json.loads(row["payload"])
        result = payload.get("result") or {}
        kind = row["kind"]
        op = payload.get("operation")
        event = {
            "id": str(row["source"]) + ":" + row["event_id"],
            "occurred_at": row["occurred"],
            "status": "completed",
            "title": "世界状态更新",
            "description": "",
            "source": "管理员"
            if payload.get("origin") == "admin" or kind.startswith("admin.")
            else "自主日常"
            if payload.get("origin") == "life_model"
            else "世界系统",
            "scope": (
                {"virtual": "虚拟世界", "real": "现实底图"}.get(
                    scene_key.rsplit("|", 1)[-1], "角色世界"
                )
                + " · 房间与物品"
            )
            if row["source"] == 0
            else "角色地图历史",
        }
        if row["source"] == 1:
            event["title"] = {
                "movement.arrived": "抵达地点",
                "admin.locate": "确认角色位置",
                "admin.depart": "开始行程",
                "life.depart": "开始行程",
                "admin.plan": "保存出行计划",
                "life.plan": "保存出行计划",
                "admin.cancel": "撤销剩余行程",
                "life.cancel": "撤销剩余行程",
                "map.generated": "生成了地图",
                "map.mode_changed": "切换地图模式",
            }.get(kind, "更新了角色地图")
            event["description"] = names.get(
                payload.get("place_id") or payload.get("target_id"), ""
            )
            if kind == "map.mode_changed":
                event["description"] = {"virtual": "虚拟世界", "real": "现实底图"}.get(
                    payload.get("mode"), ""
                )
        elif kind in {"project.paused", "project.resumed"}:
            project = payload.get("project") or {}
            event["title"] = (
                ("暂停创作项目" if kind == "project.paused" else "继续创作项目")
                + " · "
                + str(project.get("title", ""))
            )
            event["project_id"] = project.get("id")
            event["description"] = "已保存的进度与版本保留。"
        elif kind == "step.completed":
            if op in PROJECTS:
                event["title"] = (
                    PROJECT_LABELS[op] + " · " + str(result.get("project_title", ""))
                )
                event["description"] = (
                    f"初稿 {result.get('draft_parts', 0)}/{result.get('target_parts', 0)} 段 · 已修订 {result.get('revised_parts', 0)} 段 · "
                    + (
                        "已暂停"
                        if result.get("project_status") == "paused"
                        else STAGES.get(result.get("project_stage"), "")
                    )
                )
                event["project_id"] = result.get("project_id")
            elif op in ROOM:
                event["title"] = "房间布置 · " + str(result.get("name", ""))
                event["description"] = (
                    str(result.get("before", "")) + " → " + str(result.get("after", ""))
                )
            else:
                labels = {
                    "enter": "进入房间",
                    "leave": "离开房间",
                    "take": "拿取物品",
                    "put": "放下物品",
                    "read": "完成一段阅读",
                    "drink": "喝水",
                    "refill": "补满水壶",
                    "rest": "完成休息",
                    "dry": "完成晾干",
                    "write_note": "保存了一条笔记",
                    "read_notes": "翻阅已有笔记",
                    "power_on": "打开电脑",
                    "power_off": "关闭电脑",
                    "computer_work": "完成电脑活动",
                    "open_umbrella": "撑开雨伞",
                    "fold_umbrella": "收起雨伞",
                    "water_garden": "浇灌了花圃与菜畦",
                    "harvest_garden": "采收了花园蔬果与花草",
                    "prepare_meal": "下厨做好了简餐",
                    "brew_tea": "煮好了一壶花草茶",
                    "open_mailbox": "去院门信箱拆阅了来信",
                }
                event["title"] = labels.get(op, "完成一个行动步骤")
                event["description"] = str(
                    result.get("summary")
                    or result.get("name")
                    or names.get(payload.get("target_id"), "")
                )
        elif kind in {"action.failed", "action.cancelled", "action.rejected"}:
            event["status"] = {
                "action.failed": "failed",
                "action.cancelled": "cancelled",
                "action.rejected": "rejected",
            }[kind]
            event["title"] = {
                "action.failed": "行动未完成",
                "action.cancelled": "取消后续行动",
                "action.rejected": "提案未执行，状态未改变",
            }[kind]
            event["description"] = str(
                payload.get("reason") or payload.get("reason_code") or ""
            )[:220]
        else:
            event["source"] = "管理员"
            event["title"] = {
                "scene.initialized": "建立房间与物品",
                "admin.item": "维护物品设定",
                "admin.room": "维护房间设定",
                "admin.place": "维护地点状态",
                "admin.visual": "更新视觉设定",
                "admin.room_design": "更新自主布置设置",
            }.get(kind, "管理设置更新")
            event["description"] = str(payload.get("name") or "")[:100]
        rows.append(event)
    return {
        "events": rows,
        "next_cursor": cursor(records[-1]) if more and records else None,
        "category": category,
        "fact_kind": "program_receipts",
    }

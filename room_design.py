"""Completed, room-scoped furnishing actions. No image generation or new furniture."""

import copy
import hashlib

KINDS = {"move_furniture", "place_item", "set_lighting", "set_curtains", "display_note"}
LABELS = {
    "move_furniture": "移动家具",
    "place_item": "摆放物品",
    "set_lighting": "调整灯光",
    "set_curtains": "调整窗帘",
    "display_note": "展示已写纸页",
}
POSITIONS = {
    "left_wall": "左侧墙边",
    "right_wall": "右侧墙边",
    "back_wall": "后墙旁",
    "center": "房间中央",
    "near_window": "窗边",
    "bedside": "床边",
    "desk_left": "书桌左侧",
    "desk_right": "书桌右侧",
    "bookshelf": "书架上",
    "entry_rack": "门边收纳架",
}
FLOOR = {"left_wall", "right_wall", "back_wall", "center", "near_window", "bedside"}
SURFACES = {"desk_left", "desk_right", "bedside", "bookshelf", "entry_rack"}
LIGHTS = {
    "bright": "明亮室内灯光",
    "warm": "柔和暖光",
    "dim": "昏暗小灯",
    "off": "室内灯已关闭",
}
CURTAINS = {"open": "窗帘打开", "half": "窗帘半掩", "closed": "窗帘合拢"}


def positions_for(d, kind):
    kinds = {f["kind"] for f in d["furniture"]}
    positions = SURFACES if kind in {"lamp", "item"} else FLOOR
    needed = {
        "desk_left": "desk",
        "desk_right": "desk",
        "bookshelf": "bookcase",
        "bedside": "bed",
        "entry_rack": "fixture",
        "near_window": "window",
    }
    return sorted(
        p
        for p in positions
        if (p not in needed or needed[p] in kinds)
        and not (kind == "bed" and p == "bedside")
    )


def design(state, room):
    return state.get("room_designs", {}).get(room)


def configure(state, body):
    rid = body.get("room_id")
    if rid not in state["rooms"]:
        raise ValueError("房间不存在")
    if type(body.get("enabled")) is not bool:
        raise ValueError("请选择是否允许自主布置")
    old = design(state, rid)
    if old:
        if set(body) & {"furniture", "lighting", "curtains"}:
            raise ValueError("已有家具通过行动移动，不重置已有布置")
        old["enabled"] = body["enabled"]
        return
    rows = body.get("furniture", [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise ValueError("请先登记 1–12 件已有家具")
    furniture = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) - {
            "name",
            "position",
            "kind",
            "movable",
        }:
            raise ValueError("未知家具字段")
        name = row.get("name")
        kind = row.get("kind")
        pos = row.get("position")
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 40
            or type(row.get("movable")) is not bool
        ):
            raise ValueError("无效家具名称或可移动状态")
        if kind not in {
            "bed",
            "desk",
            "chair",
            "bookcase",
            "lamp",
            "window",
            "fixture",
        }:
            raise ValueError("未知家具类型")
        allowed = SURFACES if kind == "lamp" else FLOOR
        if pos not in allowed:
            raise ValueError("家具位置不适用")
        if kind in {"window", "fixture"} and row["movable"]:
            raise ValueError("窗户与建筑固定设施不能移动")
        fid = (
            "furn_"
            + hashlib.sha256(
                (rid + ":" + str(index) + ":" + name).encode()
            ).hexdigest()[:16]
        )
        furniture.append(
            {
                "id": fid,
                "name": name.strip(),
                "kind": kind,
                "position": pos,
                "movable": row["movable"],
            }
        )
    lighting = body.get("lighting")
    curtains = body.get("curtains")
    for f in furniture:
        if f["position"] not in positions_for({"furniture": furniture}, f["kind"]):
            raise ValueError("摆放位置缺少对应的支撑家具或窗户")
    if lighting is not None and (
        lighting not in LIGHTS or not any(f["kind"] == "lamp" for f in furniture)
    ):
        raise ValueError("灯光需对应已登记灯具")
    if curtains is not None and (
        curtains not in CURTAINS or not any(f["kind"] == "window" for f in furniture)
    ):
        raise ValueError("窗帘需对应已登记窗户")
    state.setdefault("room_designs", {})[rid] = {
        "enabled": body["enabled"],
        "revision": 1,
        "furniture": furniture,
        "lighting": lighting,
        "curtains": curtains,
        "history": [],
    }


def check(state, step, actor, now):
    rid = state.get("room_id")
    room = state["rooms"].get(rid)
    value = design(state, rid)
    if (
        not room
        or room["place_id"] != actor.get("place_id")
        or not room["accessible"]
        or not value
        or not value["enabled"]
    ):
        raise ValueError("需要进入允许布置的房间")
    kind = step["kind"]
    target = step.get("target_id")
    position = step.get("position")
    mode = step.get("mode")
    if kind == "move_furniture":
        fixture = next((f for f in value["furniture"] if f["id"] == target), None)
        if not fixture or not fixture["movable"]:
            raise ValueError("只能移动本房间已登记的可移动家具")
        if position not in positions_for(value, fixture["kind"]):
            raise ValueError("家具位置不适用")
        if fixture["kind"] == "desk" and any(
            i["kind"] == "computer" and i.get("powered") and i.get("room_id") == rid
            for i in state["items"].values()
        ):
            raise ValueError("先关闭桌上的电脑，再移动书桌")
        if position == fixture["position"]:
            raise ValueError("家具已经在该位置")
        return 600 if fixture["kind"] in {"bed", "desk", "bookcase"} else 120
    if kind in {"set_lighting", "set_curtains"}:
        key, choices = (
            ("lighting", LIGHTS) if kind == "set_lighting" else ("curtains", CURTAINS)
        )
        if target != rid or value.get(key) is None or mode not in choices:
            raise ValueError("房间设施或调整方式不适用")
        if value[key] == mode:
            raise ValueError("房间设施已经处于该状态")
        return 10 if kind == "set_lighting" else 20
    item = state["items"].get(target)
    if not item or (
        not item["carried"]
        and (item["room_id"] != rid or item["place_id"] != actor["place_id"])
    ):
        raise ValueError("只能布置手边或随身的物品")
    if position not in SURFACES:
        raise ValueError("请选择房间内的摆放位置")
    needed = {
        "desk_left": "desk",
        "desk_right": "desk",
        "bookshelf": "bookcase",
        "bedside": "bed",
        "entry_rack": "fixture",
    }[position]
    if not any(f["kind"] == needed for f in value["furniture"]):
        raise ValueError("房间没有对应的摆放家具")
    if item["kind"] == "computer" and (
        position not in {"desk_left", "desk_right"} or item.get("powered")
    ):
        raise ValueError("电脑仅能关机后在房间书桌上调整位置")
    if kind == "display_note":
        record = next(
            (r for r in item.get("notes", []) if r["id"] == step.get("record_id")), None
        )
        if item["kind"] != "notebook" or not record:
            raise ValueError("只能展示这本纸本已经写成的记录")
        if item.get("wet_until", 0) > now:
            raise ValueError("潮湿纸本不能展示")
        if (
            item.get("displayed_note_id") == record["id"]
            and item.get("arranged_position") == position
            and not item["carried"]
        ):
            raise ValueError("该纸页已经展示在这里")
        return 90
    if (
        item.get("arranged_position") == position
        and item.get("arranged_room_id") == rid
        and not item["carried"]
        and not item.get("displayed_note_id")
    ):
        raise ValueError("物品已经在该位置")
    return 60


def apply(state, step, actor, now, origin):
    rid = state["room_id"]
    value = design(state, rid)
    kind = step["kind"]
    target = step["target_id"]
    if kind == "move_furniture":
        obj = next(f for f in value["furniture"] if f["id"] == target)
        before = POSITIONS[obj["position"]]
        obj["position"] = step["position"]
        after = POSITIONS[obj["position"]]
        label = obj["name"]
    elif kind in {"set_lighting", "set_curtains"}:
        key, choices = (
            ("lighting", LIGHTS) if kind == "set_lighting" else ("curtains", CURTAINS)
        )
        before = choices[value[key]]
        value[key] = step["mode"]
        after = choices[value[key]]
        label = "灯光" if key == "lighting" else "窗帘"
    else:
        obj = state["items"][target]
        label = obj["name"]
        before = (
            "随身携带"
            if obj["carried"]
            else POSITIONS.get(obj.get("arranged_position"), "原摆放位置")
        )
        obj.update(
            carried=False,
            place_id=actor["place_id"],
            room_id=rid,
            arranged_position=step["position"],
            arranged_room_id=rid,
            open=kind == "display_note",
        )
        if kind == "display_note":
            obj["displayed_note_id"] = step["record_id"]
        else:
            obj.pop("displayed_note_id", None)
        after = POSITIONS[step["position"]] + (
            "，摊开展示已写纸页" if kind == "display_note" else ""
        )
    value["revision"] += 1
    change = {
        "room_id": rid,
        "operation": kind,
        "name": label,
        "before": before,
        "after": after,
        "occurred_at": now,
        "origin": origin,
        "revision": value["revision"],
    }
    value["history"] = (value["history"] + [change])[-12:]
    return change


def resolve_admin_room(state, step):
    explicit = step.get("room_id")
    if explicit and explicit in state.get("room_designs", {}):
        return explicit
    target = step.get("target_id")
    if step.get("kind") in {"set_lighting", "set_curtains"} and target in state.get(
        "room_designs", {}
    ):
        return target
    if step.get("kind") == "move_furniture":
        for rid, d in state.get("room_designs", {}).items():
            if any(f["id"] == target for f in d.get("furniture", [])):
                return rid
    cur = state.get("room_id")
    if cur and cur in state.get("room_designs", {}):
        return cur
    return next(iter(state.get("room_designs", {})), None)


def check_admin(state, step, actor, now):
    if not isinstance(step, dict) or step.get("kind") not in KINDS:
        raise ValueError("不支持的布置操作")
    rid = resolve_admin_room(state, step)
    room = state.get("rooms", {}).get(rid)
    value = design(state, rid)
    if not room or not value:
        raise ValueError("请先为该房间开启房间布置并登记家具")
    kind = step["kind"]
    target = step.get("target_id")
    position = step.get("position")
    mode = step.get("mode")
    if kind == "move_furniture":
        fixture = next((f for f in value["furniture"] if f["id"] == target), None)
        if not fixture or not fixture["movable"]:
            raise ValueError("只能移动本房间已登记的可移动家具")
        if position not in positions_for(value, fixture["kind"]):
            raise ValueError("家具位置不适用")
        if fixture["kind"] == "desk" and any(
            i["kind"] == "computer" and i.get("powered") and i.get("room_id") == rid
            for i in state["items"].values()
        ):
            raise ValueError("先关闭桌上的电脑，再移动书桌")
        if position == fixture["position"]:
            raise ValueError("家具已经在该位置")
        return rid
    if kind in {"set_lighting", "set_curtains"}:
        key, choices = (
            ("lighting", LIGHTS) if kind == "set_lighting" else ("curtains", CURTAINS)
        )
        if (target and target != rid) or value.get(key) is None or mode not in choices:
            raise ValueError("房间设施或调整方式不适用")
        if value[key] == mode:
            raise ValueError("房间设施已经处于该状态")
        return rid
    item = state["items"].get(target)
    if not item or item.get("retired"):
        raise ValueError("要摆放的物品不存在")
    if item["carried"] and actor.get("place_id") != room["place_id"]:
        raise ValueError("该物品正由角色随身携带外出，暂无法在屋内摆位")
    if not item["carried"] and item.get("place_id") != room["place_id"]:
        raise ValueError("该物品不在当前住所")
    if position not in SURFACES:
        raise ValueError("请选择房间内的摆放位置")
    needed = {
        "desk_left": "desk",
        "desk_right": "desk",
        "bookshelf": "bookcase",
        "bedside": "bed",
        "entry_rack": "fixture",
    }[position]
    if not any(f["kind"] == needed for f in value["furniture"]):
        raise ValueError("房间没有对应的摆放家具")
    if item["kind"] == "computer" and (
        position not in {"desk_left", "desk_right"} or item.get("powered")
    ):
        raise ValueError("电脑仅能关机后在房间书桌上调整位置")
    if kind == "display_note":
        record = next(
            (r for r in item.get("notes", []) if r["id"] == step.get("record_id")), None
        )
        if item["kind"] != "notebook" or not record:
            raise ValueError("只能展示这本纸本已经写成的记录")
        if item.get("wet_until", 0) > now:
            raise ValueError("潮湿纸本不能展示")
        if (
            item.get("displayed_note_id") == record["id"]
            and item.get("arranged_position") == position
            and not item["carried"]
        ):
            raise ValueError("该纸页已经展示在这里")
        return rid
    if (
        item.get("arranged_position") == position
        and item.get("arranged_room_id") == rid
        and not item["carried"]
        and not item.get("displayed_note_id")
    ):
        raise ValueError("物品已经在该位置")
    return rid


def apply_admin(state, step, actor, now):
    rid = check_admin(state, step, actor, now)
    room = state["rooms"][rid]
    saved_room = state.get("room_id")
    try:
        state["room_id"] = rid
        step_norm = dict(
            step,
            target_id=rid
            if step["kind"] in {"set_lighting", "set_curtains"}
            else step.get("target_id"),
        )
        return apply(state, step_norm, {"place_id": room["place_id"]}, now, "admin")
    finally:
        state["room_id"] = saved_room


def public(state):
    rows = []
    for rid, d in state.get("room_designs", {}).items():
        row = copy.deepcopy(d)
        row.update(room_id=rid, room_name=state["rooms"][rid]["name"])
        row["positions"] = dict(POSITIONS)
        for f in row["furniture"]:
            f["position_label"] = POSITIONS[f["position"]]
        for f in row["furniture"]:
            f["allowed_positions"] = positions_for(d, f["kind"]) if f["movable"] else []
        row["item_positions"] = positions_for(d, "item")
        row["lighting_label"] = LIGHTS.get(row.get("lighting"))
        row["curtains_label"] = CURTAINS.get(row.get("curtains"))
        rows.append(row)
    return rows


def candidates(state):
    rid = state.get("room_id")
    d = design(state, rid)
    if not d or not d["enabled"]:
        return []
    result = []
    # One legal example per action target; full allowed positions remain in room_designs.
    for f in d["furniture"]:
        choices = [p for p in positions_for(d, f["kind"]) if p != f["position"]]
        if f["movable"] and choices:
            result.append(
                {"kind": "move_furniture", "target_id": f["id"], "position": choices[0]}
            )
    for kind, key, modes in [
        ("set_lighting", "lighting", LIGHTS),
        ("set_curtains", "curtains", CURTAINS),
    ]:
        if d.get(key) is not None:
            result += [
                {"kind": kind, "target_id": rid, "mode": m}
                for m in modes
                if m != d[key]
            ]
    for i in state["items"].values():
        if i["carried"] or i["room_id"] == rid:
            result.append(
                {
                    "kind": "place_item",
                    "target_id": i["id"],
                    "position": "desk_right"
                    if i.get("arranged_position") == "desk_left"
                    else "desk_left",
                }
            )
            if i.get("notes"):
                result.append(
                    {
                        "kind": "display_note",
                        "target_id": i["id"],
                        "record_id": i["notes"][-1]["id"],
                        "position": "desk_left",
                    }
                )
    return result


def layout_text(d):
    furniture = "；".join(
        f["name"] + "在" + f["position_label"] for f in d["furniture"]
    )
    return (
        "沿用原底图的固定视角。当前已登记且持续保存的房间布置："
        + furniture
        + "。"
        + str(d.get("lighting_label") or "")
        + "；"
        + str(d.get("curtains_label") or "")
        + "。以这些当前摆位与设施状态为准；原参考底图仅保留建筑外壳、家具外形和美术风格，不覆盖已完成的布置变化。不增加未登记的新家具。"
    )

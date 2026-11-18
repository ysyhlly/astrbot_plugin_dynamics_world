"""Owned rooms, belongings and timed fictional actions in the narrative transaction."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from . import creative_projects, room_design
from .garden_ecology import ECOLOGY_DURATIONS, ECOLOGY_KINDS, ECOLOGY_LABELS
from .life.core.narrative import NarrativeValidationError
from .mailbox_visitors import MailboxVisitorService
from .spatial import encode, identity
from .study_items import (
    MODES,
    STUDY_KINDS,
    STUDY_LABELS,
    content,
)
from .study_items import (
    apply as apply_study,
)
from .study_items import (
    check as check_study,
)
from .study_items import (
    defaults as item_defaults,
)
from .study_items import (
    present as present_item,
)
from .study_items import (
    receipt as item_receipt,
)

V20_FREE_KINDS = ECOLOGY_KINDS | MailboxVisitorService.MAILBOX_KINDS

KINDS = {
    "enter",
    "leave",
    "take",
    "put",
    "read",
    "drink",
    "refill",
    "open_umbrella",
    "fold_umbrella",
    "rest",
    "dry",
    "travel",
}
LABELS = {
    "enter": "进入房间",
    "leave": "前往地点入口",
    "take": "拿取物品",
    "put": "放下物品",
    "read": "阅读",
    "drink": "喝水",
    "refill": "补水",
    "open_umbrella": "撑伞",
    "fold_umbrella": "收伞",
    "rest": "休息",
    "dry": "晾干衣物和随身物品",
    "travel": "前往地点",
}
DURATION = {
    "enter": 30,
    "leave": 20,
    "take": 10,
    "put": 10,
    "read": 600,
    "drink": 30,
    "refill": 45,
    "open_umbrella": 10,
    "fold_umbrella": 10,
    "rest": 900,
    "dry": 600,
    "open_mailbox": 90,
    **ECOLOGY_DURATIONS,
}

KINDS.update(STUDY_KINDS)
LABELS.update(STUDY_LABELS)
KINDS.update(room_design.KINDS)
LABELS.update(room_design.LABELS)
KINDS.update(creative_projects.KINDS)
LABELS.update(creative_projects.LABELS)
KINDS.update(ECOLOGY_KINDS)
LABELS.update(ECOLOGY_LABELS)
KINDS.update(MailboxVisitorService.MAILBOX_KINDS)
LABELS.update(MailboxVisitorService.MAILBOX_LABELS)


class SceneActionError(NarrativeValidationError):
    def __init__(self, message):
        codes = {
            "已经在这个房间": "scene_already_in_room",
            "已经携带该物品": "scene_already_carrying",
            "行动目标不存在": "scene_target_invalid",
            "物品不在当前位置，先前往其所在房间": "scene_item_not_here",
            "需要先拿到该物品": "scene_item_not_carried",
            "先离开当前房间，再进入另一个房间": "scene_leave_room_first",
            "没有正在执行的行动": "scene_no_active_action",
            "电脑是固定设施，不能拿取": "scene_computer_stationary",
            "需要先打开电脑": "scene_computer_power_off",
        }
        super().__init__(
            codes.get(message, "scene_action_precondition_failed"), message
        )


def name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 60:
        raise SceneActionError("名称需为 1–60 字")
    return value.strip()


class SceneService:
    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS world_scene_state(identity TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS world_scene_events(event_id TEXT PRIMARY KEY,identity TEXT NOT NULL,kind TEXT NOT NULL,occurred REAL NOT NULL,payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_scene_event_scope ON world_scene_events(identity,occurred);""")

    def key(self, db, scope, mode=None):
        doc = self.engine.spatial.document(db, identity(scope))
        return identity(scope) + "|" + (mode or (doc or {}).get("map_type", "virtual"))

    def load(self, db, scope, mode=None):
        key = self.key(db, scope, mode)
        row = db.execute(
            "SELECT revision,state FROM world_scene_state WHERE identity=?", (key,)
        ).fetchone()
        return key, (row[0] if row else 0), (json.loads(row[1]) if row else None)

    def save(self, db, key, revision, state, bump=True):
        revision += int(bump)
        db.execute(
            "INSERT INTO world_scene_state VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,state=excluded.state",
            (key, revision, encode(state)),
        )
        if bump:
            owner = key.rsplit("|", 1)[0]
            db.execute(
                "UPDATE lives SET revision=revision+1 WHERE identity=?", (owner,)
            )
        return revision

    def audit(self, db, key, kind, now, payload):
        eid = "scene:" + uuid.uuid4().hex
        db.execute(
            "INSERT INTO world_scene_events VALUES(?,?,?,?,?)",
            (eid, key, kind, now, encode(dict(payload, fact_kind="fiction"))),
        )
        if getattr(self.engine, "causal", None) is not None:
            owner = json.loads(key.rsplit("|", 1)[0])
            scope = {
                "persona_id": owner[0],
                "instance_id": owner[1],
                "umo": "",
                "platform": "",
            }
            self.engine.causal.scene_receipt(db, scope, eid, kind, now, payload)
        return eid

    def bootstrap(self, scope, body):
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, revision, state = self.load(db, scope)
            if state:
                raise SceneActionError("场景已经初始化，不会覆盖现有物品和房间")
            if body.get("expected_revision") != revision:
                raise SceneActionError("场景已变化，请刷新")
            doc = self.engine.spatial.document(db, identity(scope))
            if not doc:
                raise SceneActionError("请先生成或配置地图")
            home = next(
                (p for p in doc["places"] if p["id"] == body.get("place_id")), None
            )
            if not home:
                raise SceneActionError("请选择已有地图中的住所地点")
            prefix = hashlib.sha256((key + home["id"]).encode()).hexdigest()[:12]
            entry = "room_" + prefix + "_entry"
            room = "room_" + prefix + "_room"
            rooms = {
                entry: {
                    "id": entry,
                    "name": "玄关",
                    "place_id": home["id"],
                    "sheltered": True,
                    "accessible": True,
                    "water": False,
                },
                room: {
                    "id": room,
                    "name": "房间",
                    "place_id": home["id"],
                    "sheltered": True,
                    "accessible": True,
                    "water": True,
                },
            }
            items = {}
            for kind, label, target in [
                ("book", "随身读物", room),
                ("umbrella", "雨伞", entry),
                ("water", "水壶", room),
                ("notebook", "笔记本", room),
                ("computer", "电脑", room),
            ]:
                iid = "item_" + prefix + "_" + kind
                items[iid] = {
                    "id": iid,
                    "name": label,
                    "kind": kind,
                    "place_id": home["id"],
                    "room_id": target,
                    "carried": False,
                    "open": False,
                    "wet_until": 0,
                    **item_defaults(kind),
                }
            state = {
                "places": {
                    p["id"]: {
                        "kind": "building" if p["id"] == home["id"] else "unknown",
                        "sheltered": True if p["id"] == home["id"] else None,
                        "open": True,
                        "opens": 0,
                        "closes": 24,
                    }
                    for p in doc["places"]
                },
                "rooms": rooms,
                "items": items,
                "room_id": None,
                "room_known": False,
                "at_place": None,
                "wetness": 0,
                "flow": None,
                "last_flow": None,
                "last_environment": None,
                "completion_event": None,
                "paused_at": None,
            }
            if self.engine._paused(db, dict(scope, umo="", platform="")):
                state["paused_at"] = now
            state["at_place"] = self.engine.spatial.snapshot(db, scope, now).get(
                "place_id"
            )
            self.save(db, key, revision, state)
            self.audit(
                db,
                key,
                "scene.initialized",
                now,
                {
                    "place_id": home["id"],
                    "rooms": list(rooms),
                    "items": list(items),
                    "history_backfilled": False,
                },
            )
        return {"initialized": True, "rooms": 2, "items": len(items)}

    def opened(self, profile, now, zone):
        if not profile.get("open", True):
            return False
        hour = datetime.fromtimestamp(now, ZoneInfo(zone)).hour
        a, b = profile.get("opens", 0), profile.get("closes", 24)
        return a == b or a <= hour < b if a <= b else hour >= a or hour < b

    def exposure(self, state, actor):
        if actor.get("journey"):
            return True
        room = state["rooms"].get(state.get("room_id"))
        if room:
            return not room["sheltered"]
        if not state.get("room_known"):
            return None
        profile = state["places"].get(actor.get("place_id"), {})
        sheltered = profile.get("sheltered")
        return not sheltered if type(sheltered) is bool else None

    def conditions(self, db, scope, state, now):
        actor = self.engine.spatial.snapshot(db, scope, now)
        env = (
            dict(self.engine.environment.snapshot(db, scope, now, actor))
            if self.engine.environment
            else {}
        )
        v20 = {}
        if getattr(self.engine, "ecology", None) is not None:
            _, _, v20["eco"] = self.engine.ecology.load(db, scope)
        if getattr(self.engine, "mailbox", None) is not None:
            v20["unopened_mail"] = db.execute(
                "SELECT COUNT(*) FROM world_mailbox WHERE identity=? AND status='unopened'",
                (identity(scope),),
            ).fetchone()[0]
        if v20:
            env["_v20"] = v20
        return actor, env

    def check_step(self, state, step, actor, env, now):
        kind = step.get("kind")
        target = step.get("target_id")
        if kind not in KINDS:
            raise SceneActionError("未知行动")
        if actor.get("phase") != "located":
            raise SceneActionError("需要先确认当前位置，并等待当前行程结束")
        place = actor["place_id"]
        room_id = state.get("room_id")
        item = state["items"].get(target)
        if item and item.get("retired"):
            raise SceneActionError("物品已停用，已保存记录仅供查阅")
        if kind == "enter":
            room = state["rooms"].get(target)
            if not room or room["place_id"] != place:
                raise SceneActionError("只能进入当前地点的房间")
            if room_id == target:
                raise SceneActionError("已经在这个房间")
            if room_id:
                raise SceneActionError("先离开当前房间，再进入另一个房间")
            if not room["accessible"] or not self.opened(
                state["places"].get(place, {}),
                now,
                env.get("timezone", "Asia/Shanghai"),
            ):
                raise SceneActionError("地点或房间当前不允许进入")
        elif kind == "leave":
            if room_id is None and state.get("room_known"):
                raise SceneActionError("已经位于地点入口")
        elif kind == "travel":
            if room_id:
                raise SceneActionError("先离开房间，再出发")
            if target == place:
                raise SceneActionError("已经在目的地")
            if target not in {p["id"] for p in actor["places"]}:
                raise SceneActionError("目的地不存在")
        elif kind in creative_projects.KINDS:
            try:
                return creative_projects.check(state, step, actor, now)
            except ValueError as exc:
                raise SceneActionError(str(exc)) from None
        elif kind in room_design.KINDS:
            try:
                return room_design.check(state, step, actor, now)
            except ValueError as exc:
                raise SceneActionError(str(exc)) from None
        elif kind in STUDY_KINDS:
            try:
                return check_study(state, item, step, actor, now)
            except ValueError as exc:
                raise SceneActionError(str(exc)) from None
        elif kind in {"rest", "dry"}:
            if kind == "dry" and self.exposure(state, actor) is not False:
                raise SceneActionError("需要在已确认的遮蔽地点晾干")
        elif kind in V20_FREE_KINDS:
            home_places = {r["place_id"] for r in state["rooms"].values()}
            if place not in home_places:
                raise SceneActionError(
                    "需要先回到住所才能打理花园、使用厨房或打开院门信箱"
                )
            v20 = (env or {}).get("_v20") or {}
            eco = v20.get("eco")
            if kind in {"prepare_meal", "brew_tea"}:
                if not state["rooms"].get(room_id, {}).get("water"):
                    raise SceneActionError("需要进入带水源的室内房间才能下厨或煮茶")
                if eco is not None:
                    pantry = eco.get("pantry", {})
                    keys = (
                        ("卷心菜", "小南瓜")
                        if kind == "prepare_meal"
                        else ("洋甘菊", "薄荷叶")
                    )
                    if sum(int(pantry.get(k, 0)) for k in keys) <= 0:
                        raise SceneActionError(
                            "厨房篮中暂无对应鲜蔬或花草，可先去花园采收"
                        )
            elif kind in {"eat_meal", "drink_tea"}:
                wanted = "meal" if kind == "eat_meal" else "tea"
                if eco is None or not any(
                    x["kind"] == wanted for x in eco.get("prepared", [])
                ):
                    raise SceneActionError("没有已经完成制作的餐食或茶饮")
            elif kind == "harvest_garden" and eco is not None:
                if (
                    eco["flowerbed"]["progress"] < 0.65
                    and eco["veg_patch"]["progress"] < 0.65
                ):
                    raise SceneActionError("花圃与菜畦尚在生长中，再等一等就能采收")
            elif (
                kind == "open_mailbox"
                and v20.get("unopened_mail") is not None
                and v20["unopened_mail"] <= 0
            ):
                raise SceneActionError("院门信箱里目前没有未拆阅的信件")
        else:
            if not item:
                raise SceneActionError("物品不存在")
            if kind == "take":
                if item["kind"] == "computer":
                    raise SceneActionError("电脑是固定设施，不能拿取")
                if item["carried"]:
                    raise SceneActionError("已经携带该物品")
                if item["place_id"] != place or item["room_id"] != room_id:
                    raise SceneActionError("物品不在当前位置，先前往其所在房间")
            elif not item["carried"]:
                raise SceneActionError("需要先拿到该物品")
            if kind == "read" and (
                item["kind"] != "book"
                or item["page"] >= item["pages"]
                or item.get("wet_until", 0) > now
            ):
                raise SceneActionError("需要可阅读且尚未读完的干燥书本")
            if kind == "drink" and (item["kind"] != "water" or item["servings"] <= 0):
                raise SceneActionError("水壶没有可饮用的余量")
            if kind == "refill" and (
                item["kind"] != "water"
                or not state["rooms"].get(room_id, {}).get("water")
            ):
                raise SceneActionError("需要携带水壶并位于有水源的房间")
            if (
                kind in {"open_umbrella", "fold_umbrella"}
                and item["kind"] != "umbrella"
            ):
                raise SceneActionError("这不是雨伞")
        return DURATION.get(kind, 0)

    def life_state(self, db, scope, activity, code, now, summary=None):
        row = db.execute(
            "SELECT state,revision FROM lives WHERE identity=?", (identity(scope),)
        ).fetchone()
        if not row:
            return
        state = json.loads(row[0])
        state.update(
            activity=activity,
            activity_code=code,
            availability="available"
            if code in {"unknown", "reading", "resting"}
            else "busy",
            activity_revision=row[1] + 1,
            activity_started_at=now if code != "unknown" else None,
            valid_from=now,
            valid_until=now + 3600,
            source_ids=[],
        )
        if summary is not None:
            state["summary"] = summary
        db.execute(
            "UPDATE lives SET state=?,revision=revision+1,updated=? WHERE identity=?",
            (encode(state), now, identity(scope)),
        )

    def begin_step(self, db, scope, key, state, now):
        flow = state["flow"]
        step = flow["steps"][flow["index"]]
        actor, env = self.conditions(db, scope, state, now)
        duration = self.check_step(state, step, actor, env, now)
        if step["kind"] == "travel":
            self.engine.spatial.commit(
                db,
                scope,
                {
                    "kind": "depart",
                    "target_id": step["target_id"],
                    "map_revision": actor["map_revision"],
                    "position_revision": actor["revision"],
                },
                now,
                scene_owned=True,
            )
            actor = self.engine.spatial.snapshot(db, scope, now)
            duration = actor["journey"]["arrives_at"] - now
            flow["journey_id"] = actor["journey"]["id"]
            state["room_known"] = True
        if step["kind"] == "read":
            duration = min(
                duration,
                (
                    state["items"][step["target_id"]]["pages"]
                    - state["items"][step["target_id"]]["page"]
                )
                * 60,
            )
        flow.update(step_started_at=now, step_ends_at=now + duration)
        target = (
            state["items"].get(step.get("target_id"))
            or state["rooms"].get(step.get("target_id"))
            or {}
        )
        if step["kind"] == "move_furniture":
            target = next(
                f
                for d in state.get("room_designs", {}).values()
                for f in d["furniture"]
                if f["id"] == step["target_id"]
            )
        label = LABELS[step["kind"]] + (
            "：" + target["name"] if target.get("name") else ""
        )
        if step["kind"] in creative_projects.KINDS:
            label = creative_projects.label(state, step)
        if step["kind"] == "computer_work":
            label += "（" + MODES[step.get("mode", "writing")] + "）"
        if step.get("position"):
            label += " → " + room_design.POSITIONS[step["position"]]
        if step["kind"] == "set_lighting":
            label += " · " + room_design.LIGHTS[step["mode"]]
        if step["kind"] == "set_curtains":
            label += " · " + room_design.CURTAINS[step["mode"]]
        flow["label"] = label
        code = (
            "writing"
            if step["kind"] in creative_projects.WRITING
            or step["kind"] == "write_note"
            or step["kind"] == "computer_work"
            and step.get("mode", "writing") == "writing"
            else "gaming"
            if step["kind"] == "computer_work" and step.get("mode") == "gaming"
            else "reading"
            if step["kind"] in {"read", "read_notes"}
            else "resting"
            if step["kind"] == "rest"
            else "walking"
            if step["kind"] == "travel"
            else "chores"
        )
        flow["activity_code"] = code
        self.life_state(
            db, scope, "正在" + label, code, now, "正在执行行动流程，后续步骤尚未完成。"
        )

    def finish_flow(self, db, scope, key, state, now, status, reason=""):
        flow = state["flow"]
        flow.update(status=status, finished_at=now, reason=reason)
        state["last_flow"] = copy.deepcopy(flow)
        state["flow"] = None
        eid = self.audit(
            db,
            key,
            "action." + status,
            now,
            {
                "action_id": flow["id"],
                "origin": flow.get("origin", "legacy_unknown"),
                "reason": reason,
                "completed_steps": flow["index"],
            },
        )
        text = (
            "行动流程已完成"
            if status == "completed"
            else (
                "行动已取消；已产生的结果保留"
                if status == "cancelled"
                else "行动未完成：" + reason
            )
        )
        self.life_state(db, scope, text, "unknown", now, text)
        state["completion_event"] = {
            "event_id": "life.scene:" + flow["id"],
            "type": "life.tick",
            "scope": dict(scope, umo="", platform=""),
            "occurred_at": now,
            "received_at": now,
            "fact_kind": "fiction",
            "text": text,
            "data": {
                "trigger": "world_action_completed",
                "scene_receipt": {
                    "action_id": flow["id"],
                    "status": status,
                    "reason": reason,
                    "completed_steps": flow["index"],
                    "receipt_id": eid,
                },
            },
        }

    def settle(self, db, scope, now):
        key, revision, state = self.load(db, scope)
        if not state:
            return
        if state.get("paused_at") is not None:
            return
        actor, env = self.conditions(db, scope, state, now)
        last = state.get("last_environment")
        flow = state.get("flow")
        if (
            last
            and 0 <= now - last["at"] < 30
            and state.get("at_place") == actor.get("place_id")
            and (not flow or flow.get("step_ends_at", 0) > now)
        ):
            return
        changed = False
        if state.get("at_place") != actor.get("place_id"):
            state.update(
                at_place=actor.get("place_id"),
                room_id=None,
                room_known=bool(actor.get("place_id")),
            )
            changed = True
        previous = state.get("last_environment")
        before_wetness = state.get("wetness", 0)
        before_wet_until = tuple(
            (k, i.get("wet_until", 0)) for k, i in state.get("items", {}).items()
        )
        if previous:
            elapsed = max(0, min(now, previous["until"]) - previous["at"])
            if previous["outdoors"] is True and previous["raining"] and elapsed:
                protected = any(
                    i["kind"] == "umbrella" and i["carried"] and i["open"]
                    for i in state["items"].values()
                )
                state["wetness"] = min(
                    100, state["wetness"] + elapsed * (0.008 if protected else 0.15)
                )
                for item in state["items"].values():
                    if item["carried"] and (
                        item["kind"] == "umbrella"
                        and item["open"]
                        or item["kind"] in {"book", "notebook"}
                        and not protected
                    ):
                        item["wet_until"] = max(
                            item["wet_until"],
                            min(now, previous["until"])
                            + (1800 if item["kind"] == "umbrella" else 3600),
                        )
            elif previous["outdoors"] is False:
                state["wetness"] = max(0, state["wetness"] - elapsed / 60)
        ends = (actor.get("journey") or {}).get("arrives_at", now + 300)
        new_env = {
            "at": now,
            "until": min(now + 300, ends, env.get("expires_at", now + 300)),
            "outdoors": self.exposure(state, actor),
            "raining": bool(
                env.get("available")
                and not env.get("stale")
                and env.get("current", {}).get("effect") in {"rain", "snow"}
            ),
        }
        state["last_environment"] = new_env
        flow_settled = False
        flow = state.get("flow")
        # Complete at most the current step. Subsequent actions start now;
        # an offline interval never fabricates an entire chain of actions.
        if flow and flow.get("step_ends_at", float("inf")) <= now:
            step = flow["steps"][flow["index"]]
            kind = step["kind"]
            target = step.get("target_id")
            try:
                actor, env = self.conditions(db, scope, state, now)
                if kind == "travel":
                    if actor.get("journey") or actor.get("place_id") != target:
                        raise SceneActionError("行程尚未确认抵达或已被管理操作改变")
                else:
                    self.check_step(state, step, actor, env, now)
                item = state["items"].get(target)
                design_result = None
                if kind in creative_projects.KINDS:
                    design_result = creative_projects.apply(
                        state, step, now, flow.get("origin", "legacy_unknown")
                    )
                elif kind in room_design.KINDS:
                    design_result = room_design.apply(
                        state, step, actor, now, flow.get("origin", "legacy_unknown")
                    )
                elif (
                    kind in ECOLOGY_KINDS
                    and getattr(self.engine, "ecology", None) is not None
                ):
                    design_result = self.engine.ecology.apply_step(
                        db, scope, state, step, now
                    )
                elif (
                    kind == "open_mailbox"
                    and getattr(self.engine, "mailbox", None) is not None
                ):
                    opened_list = self.engine.mailbox.open_pending_parcels(
                        db, scope, now
                    )
                    design_result = {
                        "operation": "open_mailbox",
                        "opened": len(opened_list),
                        "name": opened_list[0]["title"] if opened_list else "来信",
                    }
                elif kind in STUDY_KINDS:
                    apply_study(item, step, now)
                elif kind == "enter":
                    state.update(room_id=target, room_known=True)
                elif kind == "leave":
                    state.update(room_id=None, room_known=True)
                elif kind == "take":
                    item.update(carried=True, place_id=None, room_id=None)
                elif kind == "put":
                    item.update(
                        carried=False,
                        place_id=actor["place_id"],
                        room_id=state.get("room_id"),
                        open=False,
                    )
                elif kind == "read":
                    item["page"] = min(item["pages"], item["page"] + 10)
                elif kind == "drink":
                    item["servings"] -= 1
                elif kind == "refill":
                    item["servings"] = item["capacity"]
                elif kind == "open_umbrella":
                    item["open"] = True
                elif kind == "fold_umbrella":
                    item["open"] = False
                elif kind == "dry":
                    state["wetness"] = max(0, state["wetness"] - 40)
                    for held in state["items"].values():
                        if held["carried"]:
                            held["wet_until"] = max(now, held["wet_until"] - 600)
                if kind in {"take", "put"}:
                    for field in (
                        "arranged_position",
                        "arranged_room_id",
                        "displayed_note_id",
                    ):
                        item.pop(field, None)
                    if item["kind"] == "notebook":
                        item["open"] = False
                receipt = {
                    "action_id": flow["id"],
                    "origin": flow.get("origin", "legacy_unknown"),
                    "step": flow["index"],
                    "operation": kind,
                    "target_id": target,
                    "result": design_result
                    if design_result is not None
                    else item_receipt(item, step)
                    if item
                    else {
                        "room_id": state.get("room_id"),
                        "wetness": round(state["wetness"], 1),
                    },
                }
                self.audit(db, key, "step.completed", now, receipt)
                flow["index"] += 1
                changed = True
                if getattr(self.engine, "keepsakes", None) is not None:
                    designs = room_design.public(state)
                    active_d = next(
                        (
                            d
                            for d in designs
                            if d.get("room_id") == state.get("room_id")
                            and d.get("furniture")
                        ),
                        next(
                            (d for d in designs if d.get("furniture")),
                            designs[0] if designs else {},
                        ),
                    )
                    cur = (env or {}).get("current") or {}
                    self.engine.keepsakes.record_keyframe(
                        db,
                        scope,
                        "step." + kind,
                        LABELS.get(kind, kind),
                        {
                            "timezone": (env or {}).get("timezone", "Asia/Shanghai"),
                            "weather": cur.get("effect", "clear"),
                            "weather_label": cur.get("label", "晴"),
                            "temperature": cur.get("temperature"),
                            "curtains": active_d.get("curtains") or "open",
                            "lighting": active_d.get("lighting") or "warm",
                            "furniture": active_d.get("furniture"),
                            "location": "room" if state.get("room_id") else "garden",
                            "place_name": actor.get("place_name") or "",
                            "pose": kind,
                        },
                        now,
                    )
                if flow["index"] == len(flow["steps"]):
                    self.finish_flow(db, scope, key, state, now, "completed")
                elif flow.get("interrupt_requested"):
                    self.finish_flow(
                        db,
                        scope,
                        key,
                        state,
                        now,
                        "interrupted",
                        "在步骤完成处中断，已完成结果保留",
                    )
                else:
                    self.begin_step(db, scope, key, state, now)
            except ValueError as exc:
                self.finish_flow(db, scope, key, state, now, "failed", str(exc))
                changed = True
            # Do not apply the previous room/exposure to the next interval.
            state["last_environment"] = None
            flow_settled = True
        after_wet_until = tuple(
            (k, i.get("wet_until", 0)) for k, i in state.get("items", {}).items()
        )
        env_stable = (
            not changed
            and not flow_settled
            and previous is not None
            and state.get("wetness", 0) == before_wetness
            and after_wet_until == before_wet_until
            and previous.get("outdoors") == new_env["outdoors"]
            and previous.get("raining") == new_env["raining"]
            and 0 <= now - float(previous.get("at") or 0)
            and now < float(previous.get("until") or 0) - 30
        )
        if not env_stable:
            self.save(db, key, revision, state, bump=changed)

    def snapshot(self, db, scope, now, admin=False):
        key, revision, state = self.load(db, scope)
        if not state:
            return {"available": False, "revision": 0}
        actor, env = self.conditions(db, scope, state, now)
        place = actor.get("place_id")
        room = state["rooms"].get(state.get("room_id"))
        items = [
            dict(
                present_item(i, admin),
                visible=i["carried"]
                or i["place_id"] == place
                and i["room_id"] == state.get("room_id"),
                wet=i["wet_until"] > now,
            )
            for i in state["items"].values()
            if not i.get("retired")
        ]
        for item in items:
            if (
                not item["carried"]
                and item.get("arranged_room_id") == item.get("room_id")
                and item.get("arranged_position") in room_design.POSITIONS
            ):
                item["placement"] = room_design.POSITIONS[item["arranged_position"]] + (
                    "，摊开展示已写纸页" if item.get("displayed_note_id") else ""
                )
        flow = copy.deepcopy(state.get("flow"))
        if flow:
            end = flow["step_ends_at"]
            start = flow["step_started_at"]
            clock = state.get("paused_at") or now
            flow["progress"] = max(0, min(1, (clock - start) / max(1, end - start)))
        receipts = [
            dict(
                json.loads(r["payload"]),
                event_id=r["event_id"],
                kind=r["kind"],
                occurred_at=r["occurred"],
            )
            for r in db.execute(
                "SELECT * FROM world_scene_events WHERE identity=? ORDER BY occurred DESC,rowid DESC LIMIT 8",
                (key,),
            )
        ]
        return {
            "available": True,
            "revision": revision,
            "fact_kind": "fiction",
            "place_id": place,
            "place_name": actor.get("place_name"),
            "phase": actor.get("phase"),
            "destination": (actor.get("journey") or {}).get("destination_name"),
            "room_id": state.get("room_id"),
            "room_name": room["name"]
            if room
            else "地点入口"
            if state.get("room_known")
            else "房间待确认",
            "sheltered": None
            if self.exposure(state, actor) is None
            else not self.exposure(state, actor),
            "wetness": round(state["wetness"], 1),
            "rooms": list(state["rooms"].values()),
            "places": {
                p["id"]: copy.deepcopy(
                    state["places"].get(
                        p["id"],
                        {
                            "kind": "unknown",
                            "sheltered": None,
                            "open": True,
                            "opens": 0,
                            "closes": 24,
                        },
                    )
                )
                for p in actor["places"]
            },
            "items": items,
            "action": flow,
            "last_action": state.get("last_flow"),
            "receipts": receipts,
            "paused": state.get("paused_at") is not None,
            "removed_items": [
                {"id": i["id"], "name": i["name"], "room_id": i.get("room_id")}
                for i in state["items"].values()
                if i.get("retired")
            ],
            **(
                {
                    "archived_items": [
                        present_item(i, True)
                        for i in state["items"].values()
                        if i.get("retired")
                    ]
                }
                if admin
                else {}
            ),
            "available_actions": self.available_actions(state, actor, env, now),
            "room_designs": room_design.public(state),
            "projects": creative_projects.public(state, admin),
            "map_revision": actor.get("map_revision", 0),
            "position_revision": actor.get("revision", 0),
        }

    def available_actions(self, state, actor, env, now):
        if state.get("paused_at") is not None:
            return []
        if state.get("flow"):
            return [{"operation": "cancel"}]
        candidates = [
            {"kind": k} for k in ("leave", "rest", "dry", *sorted(V20_FREE_KINDS))
        ]
        candidates += [
            {"kind": "enter", "target_id": r["id"]} for r in state["rooms"].values()
        ]
        candidates += [
            {"kind": "travel", "target_id": p["id"]} for p in actor.get("places", [])
        ]
        for item in state["items"].values():
            kinds = ["take", "put"]
            kinds += {
                "book": ["read"],
                "water": ["drink", "refill"],
                "umbrella": ["open_umbrella", "fold_umbrella"],
                "notebook": ["write_note", "read_notes"],
                "computer": ["power_on", "power_off", "computer_work"],
            }.get(item["kind"], [])
            candidates += [
                {"kind": k, "target_id": item["id"]}
                for k in kinds
                if k != "computer_work"
            ]
            if "computer_work" in kinds:
                candidates += [
                    {"kind": "computer_work", "target_id": item["id"], "mode": mode}
                    for mode in MODES
                ]
        candidates = (
            creative_projects.candidates(state)
            + room_design.candidates(state)
            + candidates
        )
        result = []
        for candidate in candidates:
            probe = dict(candidate)
            writing = (
                probe["kind"] in creative_projects.WRITING
                or probe["kind"] == "write_note"
                or probe["kind"] == "computer_work"
                and probe.get("mode", "writing") == "writing"
            )
            if writing:
                probe.update(text="待角色生成的记录内容", title="记录")
            try:
                self.check_step(state, probe, actor, env, now)
            except ValueError:
                continue
            result.append(dict(candidate, requires_text=True) if writing else candidate)
        return result[:64]

    def validate(self, action, request):
        if request["scope"]["umo"]:
            raise SceneActionError("聊天事件不能直接改变共享场景或物品")
        scene = request["snapshot"].get("scene") or {}
        if (
            not scene.get("available")
            or not isinstance(action, dict)
            or set(action) - {"operation", "steps"}
        ):
            raise SceneActionError("场景未就绪或未知行动字段")
        operation = action.get("operation", "start")
        resume_from = (
            (scene.get("last_action") or {}).get("id")
            if operation == "resume"
            else None
        )
        if operation not in {"start", "cancel", "interrupt", "resume"}:
            raise SceneActionError("未知行动操作")
        steps = copy.deepcopy(action.get("steps", []))
        if operation == "resume":
            previous = scene.get("last_action") or {}
            if previous.get("status") != "interrupted":
                raise SceneActionError("没有可继续的中断流程")
            steps = copy.deepcopy(previous["steps"][previous["index"] :])
            operation = "start"
        if operation == "start":
            if scene.get("action"):
                raise SceneActionError("已有正在执行的行动，先等待或明确取消")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 6:
                raise SceneActionError("行动流程需要 1–6 个步骤")
            for step in steps:
                if (
                    not isinstance(step, dict)
                    or set(step)
                    - {
                        "kind",
                        "target_id",
                        "title",
                        "text",
                        "mode",
                        "position",
                        "record_id",
                        "project_id",
                        "parts",
                        "section",
                    }
                    or step.get("kind") not in KINDS
                ):
                    raise SceneActionError("未知行动步骤")
                if "target_id" in step and (
                    not isinstance(step["target_id"], str)
                    or len(step["target_id"]) > 160
                ):
                    raise SceneActionError("无效行动目标")
                kind = step["kind"]
                target = step.get("target_id")
                if kind in creative_projects.KINDS:
                    try:
                        creative_projects.validate(step, scene)
                    except ValueError as exc:
                        raise SceneActionError(str(exc)) from None
                    continue
                if any(k in step for k in ("project_id", "parts", "section")):
                    raise SceneActionError("该动作不接受创作项目字段")
                if kind in {"leave", "rest", "dry"} | V20_FREE_KINDS and target in {
                    scene.get("room_id"),
                    scene.get("place_id"),
                }:
                    step.pop("target_id", None)
                    target = None
                if (
                    kind not in {"move_furniture", "place_item", "display_note"}
                    and "position" in step
                ):
                    raise SceneActionError("该动作不接受摆放位置")
                if (
                    kind in {"move_furniture", "place_item", "display_note"}
                    and step.get("position") not in room_design.POSITIONS
                ):
                    raise SceneActionError("无效摆放位置")
                if "record_id" in step and (
                    kind != "display_note"
                    or not isinstance(step["record_id"], str)
                    or len(step["record_id"]) > 160
                ):
                    raise SceneActionError("无效纸页记录")
                if kind in room_design.KINDS and any(
                    k in step for k in ("title", "text")
                ):
                    raise SceneActionError("布置行动不能凭空生成纸页正文")
                if kind in {"set_lighting", "set_curtains"} and step.get(
                    "mode"
                ) not in (
                    room_design.LIGHTS
                    if kind == "set_lighting"
                    else room_design.CURTAINS
                ):
                    raise SceneActionError("无效设施状态")
                if kind not in {
                    "write_note",
                    "computer_work",
                    "set_lighting",
                    "set_curtains",
                } and any(k in step for k in ("title", "text", "mode")):
                    raise SceneActionError("该动作不接受写作内容")
                if kind == "write_note" and "mode" in step:
                    raise SceneActionError("笔记本记录不需要电脑模式")
                if kind in {"write_note", "computer_work"}:
                    if "text" in step and (
                        not isinstance(step["text"], str) or len(step["text"]) > 1000
                    ):
                        raise SceneActionError("记录内容过长或格式错误")
                    if "title" in step and (
                        not isinstance(step["title"], str) or len(step["title"]) > 60
                    ):
                        raise SceneActionError("记录标题过长或格式错误")
                    if (
                        kind == "computer_work"
                        and step.get("mode", "writing") not in MODES
                    ):
                        raise SceneActionError("未知电脑任务模式")
                    if kind == "write_note" or step.get("mode", "writing") == "writing":
                        try:
                            content(step, 500 if kind == "write_note" else 1000)
                        except ValueError as exc:
                            raise SceneActionError(str(exc)) from None
                valid = (
                    {
                        f["id"]
                        for d in scene.get("room_designs", [])
                        for f in d["furniture"]
                    }
                    if kind == "move_furniture"
                    else {r["id"] for r in scene["rooms"]}
                    if kind in {"enter", "set_lighting", "set_curtains"}
                    else set(scene["places"])
                    if kind == "travel"
                    else {i["id"] for i in scene["items"]}
                    if kind not in ({"leave", "rest", "dry"} | V20_FREE_KINDS)
                    else {None, ""}
                )
                if target not in valid:
                    raise SceneActionError("行动目标不存在")
        skipped = 0
        # A model may repeat a prerequisite from the prior completed flow.
        # Skip only leading conditions already true; never create a fake receipt.
        while operation == "start" and len(steps) > 1:
            first = steps[0]
            kind = first["kind"]
            target = first.get("target_id")
            item = next((i for i in scene["items"] if i["id"] == target), {})
            satisfied = (
                kind == "enter"
                and target == scene.get("room_id")
                or kind == "take"
                and item.get("carried")
                or kind == "power_on"
                and item.get("powered")
                and item.get("place_id") == scene.get("place_id")
                and item.get("room_id") == scene.get("room_id")
                or kind == "open_umbrella"
                and item.get("carried")
                and item.get("open")
            )
            if not satisfied:
                break
            steps.pop(0)
            skipped += 1
        return {
            "resume_from": resume_from,
            "operation": operation,
            "steps": copy.deepcopy(steps),
            "satisfied_prerequisites": skipped,
            "scene_revision": scene["revision"],
            "map_revision": scene["map_revision"],
            "position_revision": scene["position_revision"],
        }

    def commit(
        self, db, scope, action, now, *, origin="life_model", source_event_ids=None
    ):
        key, revision, state = self.load(db, scope)
        actor = self.engine.spatial.snapshot(db, scope, now)
        if not state or any(
            action[k] != v
            for k, v in [
                ("scene_revision", revision),
                ("map_revision", actor.get("map_revision")),
                ("position_revision", actor.get("revision")),
            ]
        ):
            raise SceneActionError("场景、地图或位置已变化，本次行动失效")
        if (
            self.engine._paused(db, dict(scope, umo="", platform=""))
            or state.get("paused_at") is not None
        ):
            raise SceneActionError("生活已暂停")
        if action["operation"] == "interrupt":
            if not state.get("flow"):
                raise SceneActionError("没有正在执行的行动")
            state["flow"]["interrupt_requested"] = True
            self.audit(
                db,
                key,
                "action.interrupt_requested",
                now,
                {
                    "action_id": state["flow"]["id"],
                    "origin": origin,
                    "reason": "当前步骤完成后暂停剩余步骤",
                },
            )
        elif action["operation"] == "cancel":
            if not state.get("flow"):
                raise SceneActionError("没有正在执行的行动")
            self.finish_flow(
                db,
                scope,
                key,
                state,
                now,
                "cancelled",
                "后续步骤取消；已经开始的地图行程仍按程序继续",
            )
        else:
            if state.get("flow"):
                raise SceneActionError("已有行动正在执行")
            state["flow"] = {
                "id": uuid.uuid4().hex,
                "origin": origin,
                "status": "running",
                "steps": copy.deepcopy(action["steps"]),
                "index": 0,
                "started_at": now,
            }
            self.begin_step(db, scope, key, state, now)
            if (
                action.get("resume_from")
                and getattr(self.engine, "causal", None) is not None
            ):
                cr, cd = self.engine.causal.load(db, scope)
                previous = next(
                    (
                        p
                        for p in cd["agenda"]
                        if p.get("action_id") == action["resume_from"]
                        and p["status"] == "interrupted"
                    ),
                    None,
                )
                if previous:
                    self.engine.causal.attach_action(
                        db, scope, previous["id"], state["flow"]["id"], now
                    )
            state["completion_event"] = None
            self.audit(
                db,
                key,
                "action.started",
                now,
                {
                    "action_id": state["flow"]["id"],
                    "origin": origin,
                    "source_event_ids": list(source_event_ids or []),
                    "steps": [
                        {k: v for k, v in step.items() if k != "text"}
                        for step in action["steps"]
                    ],
                    "satisfied_prerequisites": action.get("satisfied_prerequisites", 0),
                    "deferred_diary_count": action.get("deferred_diary_count", 0),
                },
            )
        state["last_environment"] = None
        self.save(db, key, revision, state)

    def completion_event(self, db, scope, now):
        key, revision, state = self.load(db, scope)
        event = state.get("completion_event") if state else None
        if not event:
            return None
        row = db.execute(
            "SELECT status,next_retry FROM events WHERE event_id=?",
            (event["event_id"],),
        ).fetchone()
        if row and row[0] != "pending":
            return None
        if now - event["occurred_at"] > 3600:
            if row:
                db.execute(
                    "UPDATE events SET status='observed_only',error='scene:old_completion' WHERE event_id=? AND status='pending'",
                    (event["event_id"],),
                )
            state["completion_event"] = None
            self.save(db, key, revision, state, bump=False)
            return None
        return event if not row or row[1] <= now else None

    def record_rejection(self, scope, raw, code, events):
        if (
            scope.get("umo")
            or not isinstance(raw, dict)
            or not isinstance(raw.get("world_action"), dict)
        ):
            return
        with self.engine._db() as db:
            key, _, state = self.load(db, scope)
            if not state:
                return
            doc = self.engine.spatial.document(db, identity(scope)) or {}
            valid = (
                set(state["rooms"])
                | set(state["items"])
                | {p["id"] for p in doc.get("places", [])}
                | {
                    f["id"]
                    for d in state.get("room_designs", {}).values()
                    for f in d["furniture"]
                }
            )
            action = raw["world_action"]
            steps = action.get("steps") or []
            safe = []
            for step in steps[:6] if isinstance(steps, list) else []:
                if not isinstance(step, dict):
                    continue
                kind = step.get("kind")
                target = step.get("target_id")
                safe.append(
                    {
                        "kind": kind
                        if isinstance(kind, str) and kind in KINDS
                        else "unknown",
                        "target_id": target
                        if isinstance(target, str) and target in valid
                        else None,
                    }
                )
            self.audit(
                db,
                key,
                "action.rejected",
                self.engine.clock(),
                {
                    "origin": "life_model",
                    "reason_code": code,
                    "steps": safe,
                    "source_event_ids": [e["event_id"] for e in events],
                },
            )

    def pause(self, db, scope, paused, now, mode=None):
        key, revision, state = self.load(db, scope, mode)
        if not state:
            return
        if paused and mode is not None and state.get("completion_event"):
            event = state["completion_event"]
            db.execute(
                "UPDATE events SET status='observed_only',error='scene:mode_suspended' WHERE event_id=? AND status='pending'",
                (event["event_id"],),
            )
            state["completion_event"] = None
        if paused and state.get("paused_at") is None:
            state["paused_at"] = now
        elif not paused and state.get("paused_at") is not None:
            elapsed = max(0, now - state["paused_at"])
            if state.get("flow"):
                for field in ("started_at", "step_started_at", "step_ends_at"):
                    state["flow"][field] += elapsed
            for item in state["items"].values():
                if item["wet_until"] > state["paused_at"]:
                    item["wet_until"] += elapsed
            state["paused_at"] = None
        else:
            return
        if getattr(self.engine, "causal", None) is not None:
            self.engine.causal.pause(db, scope, paused, now)
        if getattr(self.engine, "ecology", None) is not None:
            ek, er, eco = self.engine.ecology.load(db, scope)
            if paused:
                eco["paused_at"] = now
            else:
                delta = max(0, now - eco.pop("paused_at", now))
                for plot in ("flowerbed", "veg_patch"):
                    eco[plot]["watered_at"] += delta
            eco["last_settled_at"] = now
            self.engine.ecology.save(db, ek, er, eco, now)
        state["last_environment"] = None
        self.save(db, key, revision, state)

    def guard_movement(self, db, scope, action, now, admin=False):
        key, revision, state = self.load(db, scope)
        if not state:
            return
        if admin and action["kind"] in {"locate", "cancel"}:
            if state.get("flow"):
                self.finish_flow(
                    db, scope, key, state, now, "cancelled", "管理员纠正位置"
                )
            state.update(room_id=None, room_known=False, last_environment=None)
            self.save(db, key, revision, state)
        elif state.get("flow"):
            raise SceneActionError("行动流程正在执行，不能另行移动")
        elif action["kind"] == "depart" and state.get("room_id"):
            raise SceneActionError("请先离开房间，再出发")

    def guard_map(self, db, scope, document):
        _, _, state = self.load(db, scope)
        if not state:
            return
        if state.get("flow"):
            raise SceneActionError("请先完成或取消行动流程，再编辑地图")
        retained = {p["id"] for p in document["places"]}
        used = {r["place_id"] for r in state["rooms"].values()} | {
            i["place_id"] for i in state["items"].values() if i["place_id"]
        }
        if used - retained:
            raise SceneActionError("地图变更会移除有房间或物品的地点，请保留这些地点")

    def retire_item(self, scope, body):
        """Remove an item from use without deleting its records or project references."""
        now = self.engine.clock()
        mode = body.get("map_mode")
        if mode is not None and mode not in {"virtual", "real"}:
            raise SceneActionError("未知地图类型")
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, revision, state = self.load(db, scope, mode)
            if (
                not state
                or type(body.get("expected_revision")) is not int
                or body["expected_revision"] != revision
            ):
                raise SceneActionError("场景已变化，请刷新")
            item = state["items"].get(body.get("item_id"))
            if not item:
                raise SceneActionError("物品不存在")
            if item.get("retired"):
                return {"retired": True, "already_retired": True}
            flow = state.get("flow")
            cancelled = False
            if flow:
                pending = flow["steps"][flow["index"] :]
                affected = any(
                    s.get("target_id") == item["id"]
                    or s.get("kind") == "project_finish"
                    and state.get("projects", {})
                    .get(s.get("project_id"), {})
                    .get("last_item_id")
                    == item["id"]
                    for s in pending
                )
                if affected:
                    self.finish_flow(
                        db,
                        scope,
                        key,
                        state,
                        now,
                        "cancelled",
                        "物品已停用；已完成记录保留",
                    )
                    cancelled = True
            item.update(
                retired=True,
                retired_at=now,
                retired_reason="admin",
                carried=False,
                open=False,
            )
            if item["kind"] == "computer":
                item["powered"] = False
            self.save(db, key, revision, state)
            self.audit(
                db,
                key,
                "admin.item_retired",
                now,
                {
                    "origin": "admin",
                    "target_id": item["id"],
                    "name": item["name"],
                    "records_retained": True,
                    "cancelled_related_flow": cancelled,
                },
            )
        return {
            "retired": True,
            "records_retained": True,
            "cancelled_related_flow": cancelled,
        }

    def configure(self, scope, body):
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, revision, state = self.load(db, scope)
            if (
                not state
                or type(body.get("expected_revision")) is not int
                or body["expected_revision"] != revision
            ):
                raise SceneActionError("场景已变化，请刷新")
            adding = (body.get("action") == "item" and not body.get("item_id")) or (
                body.get("action") == "room" and not body.get("room_id")
            )
            if state.get("flow") and not adding:
                raise SceneActionError("请先完成或取消行动流程，再编辑场景")
            doc = self.engine.spatial.document(db, identity(scope))
            place = body.get("place_id")
            if place not in {p["id"] for p in doc["places"]}:
                raise SceneActionError("地点不存在")
            action = body["action"]
            if action == "room_design":
                room = state["rooms"].get(body.get("room_id"))
                if not room or room["place_id"] != place:
                    raise SceneActionError("房间不属于该地点")
                room_design.configure(state, body)
            elif action == "place":
                kind = body.get("kind", "unknown")
                if kind not in {"building", "outdoor", "unknown"}:
                    raise SceneActionError("未知地点类型")
                a, b = body.get("opens", 0), body.get("closes", 24)
                if (
                    type(a) is not int
                    or type(b) is not int
                    or not 0 <= a <= 23
                    or not 0 <= b <= 24
                ):
                    raise SceneActionError("开放时间需为整点小时")
                if (
                    type(body.get("open")) is not bool
                    or body.get("sheltered") is not None
                    and type(body["sheltered"]) is not bool
                ):
                    raise SceneActionError("无效地点状态")
                state["places"][place] = {
                    "kind": kind,
                    "sheltered": body.get("sheltered"),
                    "open": body["open"],
                    "opens": a,
                    "closes": b,
                }
            elif action == "room":
                rid = body.get("room_id")
                if rid and rid not in state["rooms"]:
                    raise SceneActionError("房间不存在")
                if not rid:
                    if len(state["rooms"]) >= 32:
                        raise SceneActionError("最多配置 32 个房间")
                    rid = "room_" + uuid.uuid4().hex[:16]
                elif state["rooms"][rid]["place_id"] != place:
                    raise SceneActionError("已有房间不能跨地点移动")
                if any(
                    type(body.get(k)) is not bool
                    for k in ("sheltered", "accessible", "water")
                ):
                    raise SceneActionError("无效房间状态")
                state["rooms"][rid] = {
                    "id": rid,
                    "place_id": place,
                    "name": name(body.get("name")),
                    **{k: body[k] for k in ("sheltered", "accessible", "water")},
                }
            elif action == "item":
                iid = body.get("item_id")
                rid = body.get("room_id") or None
                if rid and (
                    rid not in state["rooms"]
                    or state["rooms"][rid]["place_id"] != place
                ):
                    raise SceneActionError("物品房间不属于该地点")
                if iid and iid not in state["items"]:
                    raise SceneActionError("物品不存在")
                if iid:
                    item = state["items"][iid]
                    if item["carried"]:
                        raise SceneActionError("请先把物品放下，再更正存放位置")
                else:
                    if len(state["items"]) >= 32:
                        raise SceneActionError("最多配置 32 件物品")
                    kind = body.get("kind")
                    if kind not in {
                        "book",
                        "umbrella",
                        "water",
                        "notebook",
                        "computer",
                    }:
                        raise SceneActionError("本版支持书、雨伞、水壶、笔记本和电脑")
                    iid = "item_" + uuid.uuid4().hex[:16]
                    item = {
                        "id": iid,
                        "kind": kind,
                        "carried": False,
                        "open": False,
                        "wet_until": 0,
                        **item_defaults(kind),
                    }
                item.update(name=name(body.get("name")), place_id=place, room_id=rid)
                state["items"][iid] = item
            else:
                raise SceneActionError("未知场景编辑操作")
            self.save(db, key, revision, state)
            self.audit(
                db,
                key,
                "admin." + action,
                now,
                {"place_id": place, "name": body.get("name")},
            )
        return {"saved": True}

    def preset(self, snapshot, preset, destination=None, data=None):
        data = data or {}
        if preset in V20_FREE_KINDS:
            steps = []
            room = snapshot["room_id"]
            if preset in {"prepare_meal", "brew_tea"}:
                current_room = next(
                    (r for r in snapshot["rooms"] if r["id"] == room), None
                )
                if not current_room or not current_room.get("water"):
                    water_room = next(
                        (
                            r
                            for r in snapshot["rooms"]
                            if r["place_id"] == snapshot["place_id"]
                            and r.get("water")
                            and r.get("accessible")
                        ),
                        None,
                    )
                    if not water_room:
                        raise SceneActionError("当前住所没有带水源的可用房间")
                    if room:
                        steps.append({"kind": "leave"})
                    steps.append({"kind": "enter", "target_id": water_room["id"]})
            steps.append({"kind": preset})
            return steps
        kind = {
            "read": "book",
            "drink": "water",
            "rain_walk": "umbrella",
            "write_note": "notebook",
            "computer_work": "computer",
        }.get(preset)
        if not kind:
            raise SceneActionError("未知预设行动")
        item = next(
            (
                i
                for i in snapshot["items"]
                if i["kind"] == kind
                and (i["carried"] or i["place_id"] == snapshot["place_id"])
            ),
            None,
        )
        if not item:
            raise SceneActionError("当前位置没有所需物品，可先前往物品所在地点")
        steps = []
        room = snapshot["room_id"]
        if not item["carried"]:
            if room != item["room_id"]:
                if room:
                    steps.append({"kind": "leave"})
                if item["room_id"]:
                    steps.append({"kind": "enter", "target_id": item["room_id"]})
                room = item["room_id"]
            if kind != "computer":
                steps.append({"kind": "take", "target_id": item["id"]})
        if preset == "rain_walk":
            if room:
                steps.append({"kind": "leave"})
            if not item["open"]:
                steps.append({"kind": "open_umbrella", "target_id": item["id"]})
            steps.append({"kind": "travel", "target_id": destination})
        elif preset in {"write_note", "computer_work"}:
            if kind == "computer" and not item.get("powered"):
                steps.append({"kind": "power_on", "target_id": item["id"]})
            step = {"kind": preset, "target_id": item["id"]}
            if kind == "computer":
                step["mode"] = data.get("mode", "writing")
            if kind == "notebook" or step["mode"] == "writing":
                step.update(
                    title=data.get("title") or "未命名记录", text=data.get("text", "")
                )
            steps.append(step)
        else:
            steps.append({"kind": preset, "target_id": item["id"]})
        return steps

    def administer(self, scope, body):
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self.engine._ensure(db, scope, now)
            self.engine.spatial.settle(db, scope, now)
            self.settle(db, scope, now)
            snapshot = self.snapshot(db, scope, now, admin=True)
            if not snapshot.get("available"):
                raise SceneActionError("请先初始化场景")
            if (
                type(body.get("expected_revision")) is not int
                or snapshot["revision"] != body["expected_revision"]
            ):
                raise SceneActionError("场景已变化，请刷新")
            steps = (
                self.preset(snapshot, body["preset"], body.get("target_id"), body)
                if body["action"] == "preset"
                else body.get("steps", [])
            )
            action = self.validate(
                {
                    "operation": body["action"]
                    if body["action"] in {"cancel", "interrupt", "resume"}
                    else "start",
                    "steps": steps,
                },
                {
                    "scope": dict(scope, umo="", platform=""),
                    "snapshot": {"scene": snapshot},
                },
            )
            self.commit(db, scope, action, now, origin="admin")
        return {"accepted": True}

    def admin_arrange(self, scope, body):
        """Instantaneous administrator room arrangement (works even when character is away, asleep or busy)."""
        now = self.engine.clock()
        raw_steps = body.get("steps")
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 4:
            raise SceneActionError("单次即时布置需包含 1–4 个步骤")
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self.engine._ensure(db, scope, now)
            self.engine.spatial.settle(db, scope, now)
            self.settle(db, scope, now)
            key, revision, state = self.load(db, scope)
            if not state:
                raise SceneActionError("请先初始化场景")
            exp = body.get("expected_revision")
            if exp is not None and (type(exp) is not int or exp != revision):
                raise SceneActionError("场景已变化，请刷新")
            actor = self.engine.spatial.snapshot(db, scope, now)
            changes = []
            for raw in raw_steps:
                if not isinstance(raw, dict):
                    raise SceneActionError("无效布置步骤")
                step = dict(raw)
                if body.get("room_id") and "room_id" not in step:
                    step["room_id"] = body["room_id"]
                try:
                    change = room_design.apply_admin(state, step, actor, now)
                except ValueError as exc:
                    raise SceneActionError(str(exc)) from None
                changes.append(change)
                self.audit(db, key, "admin.arrange", now, change)
            new_rev = self.save(db, key, revision, state)
            if getattr(self.engine, "keepsakes", None) is not None and changes:
                last_c = changes[-1]
                _, env_now = self.conditions(db, scope, state, now)
                cur_now = (env_now or {}).get("current") or {}
                designs_now = room_design.public(state)
                target_rid = last_c.get("room_id") or state.get("room_id")
                active_d = next(
                    (
                        d
                        for d in designs_now
                        if d.get("room_id") == target_rid and d.get("furniture")
                    ),
                    next(
                        (d for d in designs_now if d.get("furniture")),
                        designs_now[0] if designs_now else {},
                    ),
                )
                life_snap = (
                    self.engine._snapshot(db, scope, now)
                    if self.engine._allowed(scope)
                    else {}
                )
                pose_now = (
                    "sleep" if life_snap.get("availability") == "asleep" else "idle"
                )
                self.engine.keepsakes.record_keyframe(
                    db,
                    scope,
                    "admin_arrange",
                    f"布置了小屋：{last_c['name']} → {last_c['after']}",
                    {
                        "operation": last_c["operation"],
                        "room_id": last_c["room_id"],
                        "timezone": (env_now or {}).get("timezone", "Asia/Shanghai"),
                        "weather": cur_now.get("effect", "clear"),
                        "weather_label": cur_now.get("label", "晴"),
                        "temperature": cur_now.get("temperature"),
                        "curtains": active_d.get("curtains") or "open",
                        "lighting": active_d.get("lighting") or "warm",
                        "furniture": active_d.get("furniture"),
                        "location": "away"
                        if actor.get("phase") == "travelling"
                        else ("room" if state.get("room_id") else "garden"),
                        "place_name": actor.get("place_name") or "",
                        "pose": pose_now,
                    },
                    now,
                )
        return {"arranged": True, "changes": changes, "scene_revision": new_rev}

    @staticmethod
    def activity(snapshot, base):
        if not snapshot or not snapshot.get("available"):
            return base
        if snapshot.get("action"):
            return (
                "在"
                + str(snapshot.get("place_name") or "当前位置")
                + ("·" + snapshot["room_name"] if snapshot.get("room_id") else "")
                + "：正在"
                + snapshot["action"]["label"]
            )
        if snapshot.get("room_id") and snapshot["room_name"] not in base:
            prefix = "在" + str(snapshot.get("place_name") or "当前位置")
            return (
                prefix
                + "·"
                + snapshot["room_name"]
                + "："
                + base.removeprefix(prefix + "：")
            )
        return base

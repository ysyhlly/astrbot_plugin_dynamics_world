"""Cabin settings and receipt-backed activities in the existing narrative transaction."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .series_panels import resolve_series_timezone
from .spatial import encode, identity

ZONE = ZoneInfo("Asia/Shanghai")
PREVIEW = "dashboard:unbound"
STYLES = {"cottage", "whale_coast", "witch_court"}


@dataclass(frozen=True)
class Activity:
    style: str
    zone: str
    label: str
    seconds: int
    hour: int
    code: str
    record: str


ACTIVITIES = {
    "cabin_tide_chart": Activity(
        "whale_coast",
        "room",
        "绘制潮汐图",
        720,
        10,
        "writing",
        "在海图桌完成了本次潮汐图绘制。",
    ),
    "cabin_whale_watch": Activity(
        "whale_coast",
        "garden",
        "海堤观鲸",
        540,
        16,
        "chores",
        "在海堤使用望远镜完成了一次海面观测。",
    ),
    "cabin_testimony": Activity(
        "witch_court",
        "room",
        "核对证词",
        720,
        10,
        "reading",
        "在证词桌逐条核对了本次卷宗的证词。",
    ),
    "cabin_weigh_evidence": Activity(
        "witch_court",
        "garden",
        "复核证物重量",
        540,
        16,
        "chores",
        "在钟庭的天平站完成了一次证物称量复核。",
    ),
}
PENDING = {"planned", "deferred"}
DDL = """CREATE TABLE IF NOT EXISTS world_cabin_homes(
    world_key TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)"""


def preference(db, key):
    row = db.execute(
        "SELECT revision,payload FROM world_cabin_homes WHERE world_key=?", (key,)
    ).fetchone()
    if not row:
        return {"style": "cottage", "revision": 0}
    return dict(json.loads(row[1]), revision=row[0])


def stations(state, pref):
    rooms = (state or {}).get("rooms", {})
    home = rooms.get(pref.get("home_room_id"))
    if home is None:
        candidates = [
            r for r in rooms.values() if r.get("sheltered") and r.get("water")
        ]
        home = candidates[0] if len(candidates) == 1 else None
    if not home:
        return None
    yard = rooms.get(pref.get("garden_room_id"))
    if yard is None:
        candidates = [
            r
            for r in rooms.values()
            if r["place_id"] == home["place_id"] and not r.get("sheltered", True)
        ]
        yard = candidates[0] if len(candidates) == 1 else None
    if yard and (yard["place_id"] != home["place_id"] or yard["id"] == home["id"]):
        yard = None
    return {
        "place": home["place_id"],
        "room": home["id"],
        "garden": yard["id"] if yard else None,
    }


def update_binding(db, key, selection):
    row = db.execute(
        "SELECT payload FROM world_cabin_homes WHERE world_key=?", (key,)
    ).fetchone()
    if row:
        pref = json.loads(row[0])
        pref.update(
            home_room_id=selection.get("home_room_id", ""),
            garden_room_id=selection.get("garden_room_id", ""),
        )
        db.execute(
            "UPDATE world_cabin_homes SET payload=?,revision=revision+1 WHERE world_key=?",
            (encode(pref), key),
        )


def view(db, scenes, scope, key):
    saved = preference(db, key)
    result = {
        "style": saved["style"],
        "revision": saved["revision"],
        "activities": [
            {"kind": k, "label": a.label, "zone": a.zone, "seconds": a.seconds}
            for k, a in ACTIVITIES.items()
            if a.style == saved["style"]
        ],
        "upcoming": [],
        "bound": bool(scope),
    }
    if scope and scenes.engine.causal is not None:
        _, doc = scenes.engine.causal.load(db, scope)
        result["upcoming"] = sorted(
            (
                {
                    k: row[k]
                    for k in (
                        "id",
                        "activity",
                        "start",
                        "end",
                        "status",
                        "cabin_operation",
                    )
                }
                for row in doc["agenda"]
                if row.get("cabin_world") == key
                and row["status"] in PENDING | {"running"}
                and ACTIVITIES[row["cabin_operation"]].style == saved["style"]
            ),
            key=lambda row: row["start"],
        )
    return result


def select(db, scenes, scope, style, expected, binding, now):
    if style not in STYLES or type(expected) is not int:
        raise ValueError("小屋外观或版本无效")
    key = scenes.key(db, scope) if scope else PREVIEW
    old = preference(db, key)
    if old["revision"] != expected and old["style"] != style:
        raise ValueError("小屋外观已改变，请重新读取")
    if old["style"] != style:
        if scope:
            # Settle elapsed work under its original setting before retiring that station.
            scenes.settle(db, scope, now)
        payload = {
            "style": style,
            "scope": scope,
            "home_room_id": binding.get("home_room_id", ""),
            "garden_room_id": binding.get("garden_room_id", ""),
        }
        db.execute(
            "INSERT INTO world_cabin_homes VALUES(?,?,?) ON CONFLICT(world_key) DO UPDATE SET revision=excluded.revision,payload=excluded.payload",
            (key, old["revision"] + 1, encode(payload)),
        )
        if scope:
            _, rev, state = scenes.load(db, scope)
            flow = (state or {}).get("flow") or {}
            remaining = flow.get("steps", [])[flow.get("index", 0) :]
            if any(
                s.get("kind") in ACTIVITIES and ACTIVITIES[s["kind"]].style != style
                for s in remaining
            ):
                scenes.finish_flow(
                    db,
                    scope,
                    key,
                    state,
                    now,
                    "cancelled",
                    "小屋外观切换，余下的主题活动已取消",
                )
            if state:
                scenes.save(db, key, rev, state)
            if scenes.engine.causal is not None:
                reconcile(
                    db,
                    scenes,
                    scope,
                    key,
                    dict(payload, revision=old["revision"] + 1),
                    state,
                    now,
                )
    return view(db, scenes, scope, key)


def validate_station(kind, state, actor, config):
    spec = ACTIVITIES[kind]
    station = stations(state, config)
    if config.get("style") != spec.style or not station:
        raise ValueError("当前小屋没有这项主题活动")
    if (
        actor.get("phase") != "located"
        or actor.get("place_id") != station["place"]
        or not state.get("room_known")
    ):
        raise ValueError("需要先回到已绑定的小屋")
    if state.get("room_id") != station[spec.zone]:
        raise ValueError("需要先到达对应主题设施")
    return spec.seconds


def _resolve_zone(scenes=None):
    engine = getattr(scenes, "engine", None)
    tz_fn = getattr(engine, "_timezone", None)
    if callable(tz_fn):
        return tz_fn()
    return resolve_series_timezone(getattr(engine, "host_context", None))


def _project_daily(db, scope, agenda, now, *, tz=None):
    zone = tz or ZONE
    owner = identity(scope)
    row = db.execute("SELECT state FROM lives WHERE identity=?", (owner,)).fetchone()
    if not row:
        return
    life = json.loads(row[0])
    date = datetime.fromtimestamp(now, zone).date()
    original = life.get("plan", [])
    plan = [p for p in original if not str(p.get("id", "")).startswith("cabin:")]
    plan.extend(
        {k: a[k] for k in ("id", "start", "end", "activity", "fact_kind")}
        for a in agenda
        if a.get("cabin_operation")
        and a["status"] in PENDING | {"running", "completed"}
        and datetime.fromtimestamp(a["start"], zone).date() == date
    )
    plan.sort(key=lambda p: p["start"])
    if plan != original:
        life["plan"] = plan
        db.execute(
            "UPDATE lives SET state=?,revision=revision+1 WHERE identity=?",
            (encode(life), owner),
        )


def _free(start, duration, busy):
    for lo, hi in sorted(busy):
        if start + duration <= lo:
            break
        if start < hi:
            start = math.ceil(hi / 60) * 60
    return start


def reconcile(db, scenes, scope, key, pref, state, now):
    zone = _resolve_zone(scenes)
    causal = scenes.engine.causal
    rev, doc = causal.load(db, scope)
    agenda = doc["agenda"]
    changed = False
    for a in agenda:
        if not a.get("cabin_operation") or a["status"] not in PENDING:
            continue
        if (
            a["cabin_world"] != key
            or ACTIVITIES[a["cabin_operation"]].style != pref["style"]
            or a["end"] <= now
        ):
            appearance = (
                a["cabin_world"] != key
                or ACTIVITIES[a["cabin_operation"]].style != pref["style"]
            )
            a.update(
                status="cancelled",
                reason="小屋外观已切换" if appearance else "时段已过，未执行",
                cancelled_for="appearance" if appearance else "elapsed",
            )
            changed = True
    if (
        pref["style"] != "cottage"
        and stations(state, pref)
        and scenes.engine._allowed(scope)
        and not scenes.engine._paused(db, scope)
    ):
        today = datetime.fromtimestamp(now, zone).date()
        end_of_day = datetime.combine(
            today + timedelta(days=1), time(), zone
        ).timestamp()
        ordinary = [
            (a["start"], a["end"])
            for a in agenda
            if not a.get("cabin_operation") and a["status"] in PENDING | {"running"}
        ]
        owner = db.execute(
            "SELECT state FROM lives WHERE identity=?", (identity(scope),)
        ).fetchone()
        if owner:
            ordinary.extend(
                (r["start"], r["end"])
                for r in json.loads(owner[0]).get("plan", [])
                if not str(r.get("id", "")).startswith("cabin:")
            )
        for kind, spec in ACTIVITIES.items():
            if spec.style != pref["style"]:
                continue
            pid = (
                "cabin:"
                + hashlib.sha256(encode([key, str(today), kind]).encode()).hexdigest()[
                    :20
                ]
            )
            entry = next((a for a in agenda if a["id"] == pid), None)
            # Preserve completed, interrupted and explicitly declined history.
            resume = (
                entry
                and entry["status"] == "cancelled"
                and entry.get("cancelled_for") == "appearance"
                and not entry.get("receipts")
            )
            if entry and entry["status"] not in PENDING and not resume:
                continue
            duration = spec.seconds + 180
            if (
                entry
                and not resume
                and not any(
                    lo < entry["end"] and hi > entry["start"] for lo, hi in ordinary
                )
            ):
                continue
            busy = ordinary + [
                (a["start"], a["end"])
                for a in agenda
                if a.get("cabin_operation")
                and a["id"] != pid
                and a["status"] in PENDING | {"running"}
            ]
            desired = datetime.combine(today, time(spec.hour, 15), zone).timestamp()
            earliest = math.ceil((now + 180) / 60) * 60
            start = _free(max(desired, earliest), duration, busy)
            if start + duration > end_of_day:
                start = _free(earliest, duration, busy)
            if start + duration > end_of_day:
                if entry:
                    entry.update(
                        status="cancelled", reason="当日没有足够空档，等待下一日程"
                    )
                    changed = True
                tomorrow = today + timedelta(days=1)
                pid = (
                    "cabin:"
                    + hashlib.sha256(
                        encode([key, str(tomorrow), kind]).encode()
                    ).hexdigest()[:20]
                )
                entry = next((a for a in agenda if a["id"] == pid), None)
                resume = (
                    entry
                    and entry.get("cancelled_for") == "appearance"
                    and not entry.get("receipts")
                )
                if entry and entry["status"] not in PENDING and not resume:
                    continue
                if (
                    entry
                    and not resume
                    and not any(
                        lo < entry["end"] and hi > entry["start"] for lo, hi in ordinary
                    )
                ):
                    continue
                busy = ordinary + [
                    (a["start"], a["end"])
                    for a in agenda
                    if a.get("cabin_operation")
                    and a["id"] != pid
                    and a["status"] in PENDING | {"running"}
                ]
                start = _free(
                    datetime.combine(tomorrow, time(spec.hour, 15), zone).timestamp(),
                    duration,
                    busy,
                )
                if (
                    start + duration
                    > datetime.combine(
                        tomorrow + timedelta(days=1), time(), zone
                    ).timestamp()
                ):
                    continue
            fields = {
                "id": pid,
                "activity": spec.label,
                "start": start,
                "end": start + duration,
                "fact_kind": "plan",
                "cabin_operation": kind,
                "cabin_world": key,
                "origin": "cabin_schedule",
            }
            if entry:
                entry["history"].append(
                    {
                        "start": entry["start"],
                        "end": entry["end"],
                        "reason": "重新启用主题" if resume else "让开已有日程",
                    }
                )
                entry.update(fields)
                entry.update(status="planned", cancelled_for=None)
            else:
                agenda.append(
                    dict(
                        fields,
                        status="planned",
                        original=fields.copy(),
                        history=[],
                        receipts=[],
                    )
                )
            changed = True
    if changed:
        causal.save(db, scope, rev, doc)
    _project_daily(db, scope, agenda, now, tz=zone)
    return next(
        (
            a
            for a in agenda
            if a.get("cabin_world") == key
            and a["status"] in PENDING
            and a["start"] <= now < a["end"]
        ),
        None,
    )


def tick_homes(scenes, db, now):
    """Run from the narrative maintenance clock; closing the page does not stop a plan."""
    engine = scenes.engine
    if engine.causal is None:
        return
    for key, raw in db.execute(
        "SELECT world_key,payload FROM world_cabin_homes WHERE world_key<>?", (PREVIEW,)
    ).fetchall():
        pref = json.loads(raw)
        scope = pref.get("scope")
        if (
            not scope
            or pref["style"] == "cottage"
            or not engine._allowed(scope)
            or scenes.key(db, scope) != key
        ):
            continue
        scope = dict(scope, platform="", umo="")
        if engine._paused(db, scope):
            continue
        engine.spatial.settle(db, scope, now)
        scenes.settle(db, scope, now)
        _, revision, state = scenes.load(db, scope)
        if not state or state.get("paused_at") is not None:
            continue
        entry = reconcile(db, scenes, scope, key, pref, state, now)
        if not entry or state.get("flow"):
            continue
        life_row = db.execute(
            "SELECT state FROM lives WHERE identity=?", (identity(scope),)
        ).fetchone()
        if not life_row:
            continue
        life = json.loads(life_row[0])
        if life.get("availability") == "asleep" or (
            life.get("activity_code") not in {None, "unknown"}
            and life.get("valid_until", 0) > now
        ):
            continue
        actor, env = scenes.conditions(db, scope, state, now)
        station = stations(state, pref)
        kind = entry["cabin_operation"]
        spec = ACTIVITIES[kind]
        if (
            not station
            or actor.get("phase") != "located"
            or actor.get("place_id") != station["place"]
        ):
            continue
        target = station[spec.zone]
        steps = []
        if state.get("room_id") != target:
            if state.get("room_id"):
                steps.append({"kind": "leave"})
            if target:
                steps.append({"kind": "enter", "target_id": target})
        elif not state.get("room_known") and target is None:
            steps.extend(
                [{"kind": "enter", "target_id": station["room"]}, {"kind": "leave"}]
            )
        steps.append({"kind": kind})
        needed = spec.seconds + sum(
            30 if s["kind"] == "enter" else 20 for s in steps[:-1]
        )
        if now + needed > entry["end"]:
            continue
        # Check the complete path on a copy before starting; never move someone
        # through a closed door or take over an active real action to fill a slot.
        projected = dict(state)
        try:
            for s in steps:
                scenes.check_step(projected, s, actor, env, now)
                if s["kind"] in {"enter", "leave"}:
                    projected.update(room_id=s.get("target_id"), room_known=True)
        except ValueError:
            continue
        scenes.commit(
            db,
            scope,
            {
                "operation": "start",
                "steps": steps,
                "scene_revision": revision,
                "map_revision": actor["map_revision"],
                "position_revision": actor["revision"],
            },
            now,
            origin="cabin_schedule",
        )
        flow = scenes.load(db, scope)[2]["flow"]
        engine.causal.attach_action(db, scope, entry["id"], flow["id"], now)


def reconcile_committed_plan(engine, db, scope, now):
    """Keep a regenerated life plan and the persisted agenda consistent immediately."""
    if engine.scenes is None or engine.causal is None:
        return
    key, _, state = engine.scenes.load(db, scope)
    pref = preference(db, key)
    if state and pref["style"] != "cottage":
        reconcile(db, engine.scenes, scope, key, pref, state, now)


def record_completion(db, scope, kind, flow_id, index, event_id, now):
    owner = identity(scope)
    rev = db.execute("SELECT revision FROM lives WHERE identity=?", (owner,)).fetchone()
    db.execute(
        "INSERT OR IGNORE INTO diary(entry_id,identity,umo,occurred,text,fact_kind,source_ids,revision) VALUES(?,?,?,?,?,?,?,?)",
        (
            f"cabin:{flow_id}:{index}",
            owner,
            "",
            now,
            ACTIVITIES[kind].record,
            "fiction",
            encode([event_id]),
            rev[0] if rev else 0,
        ),
    )

"""Persistent, receipt-backed life. Reading a projection never invents actions."""

from __future__ import annotations

import copy
import hashlib
import json
import math

from .background_residents import BackgroundResidentsMixin
from .spatial import encode, identity

_CREATE_RECEIPTS = """CREATE TABLE IF NOT EXISTS world_life_receipts(
    id TEXT NOT NULL, identity TEXT NOT NULL, occurred REAL NOT NULL,
    kind TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(identity, id))"""


def finite(value, minimum=0, maximum=1e12):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError("无效数值")
    return float(value)


class CausalLifeService(BackgroundResidentsMixin):
    """One revisioned document per existing persona; original world tables stay authoritative."""

    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS world_life_documents(
                identity TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL)""")
            db.execute(_CREATE_RECEIPTS)
            keys = {
                row[1]: row[5]
                for row in db.execute("PRAGMA table_info(world_life_receipts)")
                if row[5]
            }
            if keys == {"id": 1}:
                db.execute(
                    "ALTER TABLE world_life_receipts RENAME TO world_life_receipts_legacy"
                )
                db.execute(_CREATE_RECEIPTS)
                db.execute("""INSERT INTO world_life_receipts(rowid, id, identity, occurred, kind, payload)
                    SELECT rowid, id, identity, occurred, kind, payload FROM world_life_receipts_legacy""")
                db.execute("DROP TABLE world_life_receipts_legacy")
            db.execute("""CREATE INDEX IF NOT EXISTS world_life_receipt_scope
                ON world_life_receipts(identity, occurred)""")
            db.execute("""CREATE TABLE IF NOT EXISTS world_life_requests(
                identity TEXT NOT NULL, request_id TEXT NOT NULL, digest TEXT NOT NULL,
                result TEXT NOT NULL, PRIMARY KEY(identity,request_id))""")

    def load(self, db, scope):
        row = db.execute(
            "SELECT revision,state FROM world_life_documents WHERE identity=?",
            (identity(scope),),
        ).fetchone()
        if row:
            return int(row[0]), json.loads(row[1])
        now = self.engine.clock()
        return 0, {
            "schema_version": 1,
            "created_at": now,
            "body": {
                "energy": 0.65,
                "satiety": 0.65,
                "hydration": 0.65,
                "settled_at": now,
                "basis": "migration_baseline",
                "reasons": [],
            },
            "agenda": [],
            "growth": {},
            "residents": {},
            "invitations": {},
            "paused_at": None,
            "last_settled_at": now,
        }

    def save(self, db, scope, revision, state, bump=True):
        revision += int(bump)
        db.execute(
            "INSERT INTO world_life_documents VALUES(?,?,?) ON CONFLICT(identity) "
            "DO UPDATE SET revision=excluded.revision,state=excluded.state",
            (identity(scope), revision, encode(state)),
        )
        return revision

    def receipt(self, db, scope, event_id, kind, now, payload):
        return (
            db.execute(
                """INSERT INTO world_life_receipts(id, identity, occurred, kind, payload)
                          VALUES(?,?,?,?,?) ON CONFLICT(identity, id) DO NOTHING""",
                (event_id, identity(scope), now, kind, encode(payload)),
            ).rowcount
            == 1
        )

    def advance(self, db, scope, now):
        """Integrate only a confirmed interval; no LLM and no unattended auto-harvest."""
        rev, doc = self.load(db, scope)
        before_meta = (bool(doc.get("agenda_initialized")), doc.get("paused_at"))
        before_body_state = encode(
            [
                doc["body"].get("energy"),
                doc["body"].get("satiety"),
                doc["body"].get("hydration"),
                doc["body"].get("basis"),
                doc["body"].get("reasons"),
            ]
        )
        before_residents = encode([doc["residents"], doc["invitations"], doc["agenda"]])
        row = db.execute(
            "SELECT state FROM lives WHERE identity=?", (identity(scope),)
        ).fetchone()
        life = json.loads(row[0]) if row else {}
        if not doc.get("agenda_initialized"):
            # Carry existing schedules forward as plans, never as completed history.
            for p in life.get("plan", [])[-12:]:
                if not isinstance(p, dict) or not all(
                    k in p for k in ("start", "end", "activity")
                ):
                    continue
                if str(p.get("id","")).startswith("cabin:"):
                    continue
                key = (
                    "plan_"
                    + hashlib.sha256(
                        encode([p["start"], p["end"], p["activity"]]).encode()
                    ).hexdigest()[:16]
                )
                if not any(a["id"] == key for a in doc["agenda"]):
                    doc["agenda"].append(
                        dict(
                            p,
                            id=key,
                            original=copy.deepcopy(p),
                            status="planned",
                            history=[],
                            receipts=[],
                            origin="legacy_plan",
                        )
                    )
            doc["agenda_initialized"] = True
        scene = self.engine.scenes.load(db, scope)[2] if self.engine.scenes else None
        paused = self.engine._paused(db, dict(scope, umo="", platform="")) or bool(
            scene and scene.get("paused_at") is not None
        )
        body = doc["body"]
        start = max(
            float(body["settled_at"]), float(life.get("activity_started_at") or now)
        )
        end = min(now, float(life.get("valid_until") or now))
        code = life.get("activity_code", "unknown")
        flow = (scene or {}).get("flow")
        if flow:
            start = max(float(body["settled_at"]), flow["step_started_at"])
            end = min(now, flow["step_ends_at"])
            op = flow["steps"][flow["index"]]["kind"]
            code = {"rest": "resting", "travel": "walking", "read": "reading"}.get(
                op, "chores"
            )
        integrated = False
        if paused:
            if doc["paused_at"] is None:
                doc["paused_at"] = now
        else:
            if doc["paused_at"] is not None:
                delta = max(0, now - doc["paused_at"])
                self.shift_residents(doc, delta)
                for entry in doc["agenda"]:
                    if entry["status"] in {"planned", "deferred", "interrupted"}:
                        entry["start"] += delta
                        entry["end"] += delta
                doc["paused_at"] = None
                start = now  # paused wall time is not activity
            hours = max(0, end - start) / 3600
            if code != "unknown" and hours:
                integrated = True
                rate = (
                    0.075
                    if code == "sleeping"
                    else 0.045
                    if code == "resting"
                    else -0.045
                    if code == "walking"
                    else -0.025
                )
                body["energy"] = max(0.15, min(1, body["energy"] + rate * hours))
                body["satiety"] = max(0.15, body["satiety"] - 0.035 * hours)
                body["hydration"] = max(0.15, body["hydration"] - 0.045 * hours)
                body["basis"] = "confirmed_activity_interval"
                reason = {
                    "kind": code,
                    "from": start,
                    "until": end,
                    "text": {
                        "sleeping": "已确认睡眠逐步恢复精力",
                        "resting": "已确认休息逐步恢复精力",
                        "walking": "已确认出行消耗精力",
                    }.get(code, "已确认活动消耗精力"),
                }
                reasons = body["reasons"]
                if (
                    reasons
                    and reasons[-1].get("kind") == code
                    and reasons[-1].get("until") == start
                ):
                    reasons[-1]["until"] = end
                else:
                    body["reasons"] = (reasons + [reason])[-8:]
            self.settle_residents(db, scope, doc, now)
            for entry in doc["agenda"]:
                interval = entry.get("life_interval")
                if entry["status"] != "running" or not interval:
                    continue
                same_activity = (
                    life.get("activity_code") == interval["activity_code"]
                    and life.get("activity_started_at") == interval["started_at"]
                )
                if now >= interval["until"] or not same_activity:
                    entry["status"] = (
                        "completed"
                        if same_activity and now >= interval["until"]
                        else "interrupted"
                    )
                    entry["actual_end"] = min(now, interval["until"])
                    eid = "interval:" + entry["id"] + ":" + str(interval["started_at"])
                    self.receipt(
                        db,
                        scope,
                        eid,
                        "life." + entry["status"],
                        entry["actual_end"],
                        {
                            "summary": entry["activity"],
                            "plan_id": entry["id"],
                            "origin": "confirmed_interval",
                        },
                    )
                    entry["receipts"] = (entry.get("receipts", []) + [eid])[-40:]
        after_residents = encode([doc["residents"], doc["invitations"], doc["agenda"]])
        residents_changed = before_residents != after_residents
        body_changed = before_body_state != encode(
            [
                body.get("energy"),
                body.get("satiety"),
                body.get("hydration"),
                body.get("basis"),
                body.get("reasons"),
            ]
        )
        meta_changed = (
            bool(doc.get("agenda_initialized")),
            doc.get("paused_at"),
        ) != before_meta
        if (
            rev > 0
            and not integrated
            and not body_changed
            and not meta_changed
            and not residents_changed
        ):
            return
        body["settled_at"] = max(now, body["settled_at"])
        doc["last_settled_at"] = now
        self.save(
            db,
            scope,
            rev,
            doc,
            bump=rev == 0 or residents_changed,
        )

    def scene_receipt(self, db, scope, event_id, kind, now, payload):
        if not self.receipt(db, scope, event_id, kind, now, payload):
            return
        self.advance(db, scope, now)
        rev, doc = self.load(db, scope)
        op = payload.get("operation")
        if kind == "step.completed":
            body = doc["body"]
            if op in {"eat_meal", "drink_tea", "drink"}:
                field, gain = (
                    ("satiety", 0.30) if op == "eat_meal" else ("hydration", 0.25)
                )
                body[field] = min(1, body[field] + gain)
                body["energy"] = min(
                    1, body["energy"] + (0.04 if op == "eat_meal" else 0)
                )
                body["reasons"] = (
                    body["reasons"]
                    + [
                        {
                            "event_id": event_id,
                            "text": "实际食用后补充体力"
                            if op == "eat_meal"
                            else "实际饮用后补充水分",
                        }
                    ]
                )[-8:]
            category = (
                "reading"
                if op in {"read", "read_notes"}
                else "writing"
                if op
                in {"write_note", "project_write", "project_revise", "project_finish"}
                or op == "computer_work"
                and payload.get("result", {}).get("mode") == "writing"
                else "gardening"
                if op in {"water_garden", "harvest_garden"}
                else None
            )
            if category:
                item = doc["growth"].setdefault(
                    category, {"sessions": 0, "days": [], "sources": []}
                )
                item["sessions"] += 1
                day = int(now // 86400)
                item["days"] = sorted(set(item["days"] + [day]))[-90:]
                item["sources"] = (item["sources"] + [event_id])[-20:]
        for entry in doc["agenda"]:
            if entry.get("action_id") != payload.get("action_id") or not payload.get(
                "action_id"
            ):
                continue
            entry["receipts"] = (entry.get("receipts", []) + [event_id])[-40:]
            if kind in {
                "action.completed",
                "action.cancelled",
                "action.failed",
                "action.interrupted",
            }:
                entry["status"] = {
                    "action.completed": "completed",
                    "action.cancelled": "interrupted",
                    "action.failed": "interrupted",
                    "action.interrupted": "interrupted",
                }[kind]
                entry["actual_end"] = now
                entry["reason"] = payload.get(
                    "reason",
                    "行动已完成"
                    if kind == "action.completed"
                    else "行动中断，已完成结果保留",
                )
        self.save(db, scope, rev, doc)

    def pause(self, db, scope, paused, now):
        rev, doc = self.load(db, scope)
        if paused and doc["paused_at"] is None:
            doc["paused_at"] = now
        elif not paused and doc["paused_at"] is not None:
            delta = max(0, now - doc["paused_at"])
            self.shift_residents(doc, delta)
            for a in doc["agenda"]:
                if a["status"] in {"planned", "deferred", "interrupted"}:
                    a["start"] += delta
                    a["end"] += delta
            doc["paused_at"] = None
        else:
            return
        doc["body"]["settled_at"] = now
        self.save(db, scope, rev, doc)

    def sync_plan(self, db, scope, plan, now):
        rev, doc = self.load(db, scope)
        for p in plan:
            if str(p.get("id","")).startswith("cabin:") and any(a["id"]==p["id"] for a in doc["agenda"]):
                continue
            key = (
                "plan_"
                + hashlib.sha256(
                    encode([p["start"], p["end"], p["activity"]]).encode()
                ).hexdigest()[:16]
            )
            p["id"] = key
            if not any(a["id"] == key for a in doc["agenda"]):
                doc["agenda"].append(
                    dict(
                        p,
                        original=copy.deepcopy(p),
                        status="planned",
                        history=[],
                        receipts=[],
                    )
                )
        current = {p["id"] for p in plan}
        for a in doc["agenda"]:
            if (
                a["start"] >= now
                and a["id"] not in current
                and a["status"] == "planned"
                and not a.get("cabin_operation")
            ):
                a["status"] = "cancelled"
                a["reason"] = "新日程替代，原计划保留"
        doc["agenda"] = doc["agenda"][-168:]
        self.save(db, scope, rev, doc)

    def attach_action(self, db, scope, plan_id, action_id, now):
        if not plan_id:
            return
        rev, doc = self.load(db, scope)
        entry = next((p for p in doc["agenda"] if p["id"] == plan_id), None)
        if not entry or entry["status"] not in {"planned", "deferred", "interrupted"}:
            raise ValueError("日程不可开始")
        if entry.get("cabin_operation"):
            key, _, state = self.engine.scenes.load(db,scope)
            flow=(state or {}).get("flow") or {}
            if key!=entry.get("cabin_world") or flow.get("id")!=action_id or not any(
                step.get("kind")==entry["cabin_operation"] for step in flow.get("steps",[])
            ):
                raise ValueError("主题日程需要对应的实际设施行动")
        entry.update(status="running", action_id=action_id, actual_start=now)
        self.save(db, scope, rev, doc)

    def attach_interval(self, db, scope, plan_id, life, now):
        rev, doc = self.load(db, scope)
        entry = next((p for p in doc["agenda"] if p["id"] == plan_id), None)
        if not entry or entry["status"] not in {"planned", "deferred", "interrupted"}:
            raise ValueError("日程不可开始")
        if entry.get("cabin_operation"):
            raise ValueError("主题日程须凭实际设施行动的完成回执结算")
        entry.update(
            status="running",
            actual_start=now,
            life_interval={
                "activity_code": life["activity_code"],
                "started_at": life["activity_started_at"],
                "until": min(life["valid_until"], entry["end"]),
            },
        )
        self.save(db, scope, rev, doc)

    @staticmethod
    def projected_plan(doc):
        return [
            {k: a[k] for k in ("id", "start", "end", "activity")}
            for a in doc["agenda"]
            if a["status"] in {"planned", "deferred", "running"}
        ][-12:]

    def revise_agenda(self, doc, changes, now):
        if not isinstance(changes, list) or len(changes) > 12:
            raise ValueError("日程调整最多十二项")
        for change in changes:
            entry = next(
                (a for a in doc["agenda"] if a["id"] == change.get("id")), None
            )
            if not entry or entry["status"] not in {
                "planned",
                "deferred",
                "interrupted",
            }:
                raise ValueError("只能调整未执行或已中断的日程")
            reason = str(change.get("reason", "")).strip()
            if not reason or len(reason) > 200:
                raise ValueError("请说明调整原因")
            status = change.get("status")
            if status not in {"deferred", "cancelled"}:
                raise ValueError("日程调整仅支持延期或取消")
            previous = {k: entry[k] for k in ("start", "end", "status")}
            if status == "deferred":
                start = finite(change.get("start"), now, now + 7 * 86400)
                end = finite(change.get("end"), start + 1, now + 7 * 86400)
                if any(
                    a["id"] != entry["id"]
                    and a["status"] in {"running", "planned", "deferred"}
                    and a["start"] < end
                    and a["end"] > start
                    for a in doc["agenda"]
                ):
                    raise ValueError("调整后的安排与已有日程重叠")
                entry.update(start=start, end=end)
            entry.update(status=status, reason=reason)
            entry["history"] = (
                entry["history"] + [{"at": now, "before": previous, "reason": reason}]
            )[-20:]

    def projection(self, db, scope, now, *, viewer="admin", actor_id="self"):
        rev, doc = self.load(db, scope)
        body = copy.deepcopy(doc["body"])
        body["label"] = (
            "精力充足"
            if body["energy"] >= 0.7
            else "精力平稳"
            if body["energy"] >= 0.4
            else "有些疲倦"
        )
        body["level"] = (
            "recovered"
            if body["energy"] >= 0.7
            else "normal"
            if body["energy"] >= 0.4
            else "tired"
        )
        events = [
            dict(
                json.loads(r["payload"]),
                id=r["id"],
                kind=r["kind"],
                occurred_at=r["occurred"],
            )
            for r in db.execute(
                "SELECT * FROM world_life_receipts WHERE identity=? ORDER BY occurred DESC,rowid DESC LIMIT 100",
                (identity(scope),),
            )
        ]
        if viewer not in {"admin", "actor"}:
            raise ValueError("未知观察视角")
        if viewer == "actor" and actor_id != "self":
            actor = doc["residents"].get(actor_id)
            if not actor:
                raise ValueError("居民不存在")
            return {
                "revision": rev,
                "viewer": viewer,
                "actor_id": actor_id,
                "resident": self.public_resident(actor),
                "knowledge": copy.deepcopy(actor.get("knowledge", [])),
                "server_time": now,
            }
        if viewer == "actor":
            events = [
                e
                for e in events
                if not e["kind"].startswith("admin.")
                and ("observers" not in e or "self" in e["observers"])
            ]
        residents = [
            self.public_resident(a, admin=viewer == "admin")
            for a in doc["residents"].values()
            if viewer == "admin"
            or a.get("id") in {k for e in events for k in e.get("observers", [])}
        ]
        if viewer == "actor":
            # A past conversation is not a live tracking permission for the other person.
            residents = [
                {
                    "id": a["id"],
                    "name": next(
                        (
                            e.get("speaker_name")
                            for e in events
                            if e.get("speaker") == a["id"] and e.get("speaker_name")
                        ),
                        "已接触的居民",
                    ),
                    "last_observed_at": max(
                        (
                            e["occurred_at"]
                            for e in events
                            if a["id"] in e.get("observers", [])
                        ),
                        default=0,
                    ),
                }
                for a in residents
            ]
        return {
            "revision": rev,
            "viewer": viewer,
            "actor_id": actor_id,
            "body": body,
            "agenda": copy.deepcopy(doc["agenda"]),
            "growth": copy.deepcopy(doc["growth"]),
            "residents": residents,
            "invitations": [
                copy.deepcopy(v)
                for v in doc["invitations"].values()
                if viewer == "admin" or "self" in {v["host"], v["guest"]}
            ],
            "events": events,
            "paused": doc["paused_at"] is not None,
            "last_settled_at": doc["last_settled_at"],
            "server_time": now,
            "baseline": "初始化基线，不补写历史"
            if body["basis"] == "migration_baseline"
            else "已确认活动与完成回执",
        }

    def administer(self, scope, body, *, card=None):
        rid = body.get("request_id")
        if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
            raise ValueError("缺少操作幂等标识")
        digest = hashlib.sha256(encode(body).encode()).hexdigest()
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT digest,result FROM world_life_requests WHERE identity=? AND request_id=?",
                (identity(scope), rid),
            ).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError("同一操作标识不可用于不同请求")
                return json.loads(previous[1])
            expected = body.get("expected_revision")
            current, _ = self.load(db, scope)
            if type(expected) is not int or expected != current:
                raise ValueError("生活状态已变化，请刷新后重试")
            self.advance(db, scope, now)
            rev, doc = self.load(db, scope)
            if current and rev != current:
                # Commit clock-driven changes before reporting a conflict so the next GET sees them.
                db.commit()
                raise ValueError("生活状态已变化，请刷新后重试")
            action = body.get("action")
            if action == "agenda":
                self.revise_agenda(doc, body.get("changes"), now)
                row = db.execute(
                    "SELECT state FROM lives WHERE identity=?", (identity(scope),)
                ).fetchone()
                if row:
                    life = json.loads(row[0])
                    life["plan"] = self.projected_plan(doc)
                    db.execute(
                        "UPDATE lives SET state=?,revision=revision+1 WHERE identity=?",
                        (encode(life), identity(scope)),
                    )
            elif action == "resident":
                self.configure_resident(db, scope, doc, body, card, now)
            elif action == "resident_enabled":
                a = doc["residents"].get(body.get("actor_id"))
                if not a or type(body.get("enabled")) is not bool:
                    raise ValueError("居民或启停状态无效")
                if a.get("journey") or any(
                    a["id"] in {i["host"], i["guest"]}
                    and i["status"] not in {"completed", "declined", "cancelled"}
                    for i in doc["invitations"].values()
                ):
                    raise ValueError("请先完成或取消居民当前的行程和约定")
                if a["enabled"] != body["enabled"]:
                    a["enabled"] = body["enabled"]
                    a["revision"] += 1
            elif action == "cancel_invitation":
                invitation = doc["invitations"].get(body.get("invitation_id"))
                if not invitation or invitation["status"] in {
                    "completed",
                    "declined",
                    "cancelled",
                }:
                    raise ValueError("约定不可取消")
                invitation.update(
                    status="cancelled", reason="管理员取消，已开始行程继续"
                )
            else:
                raise ValueError("未知生活管理操作")
            self.receipt(
                db,
                scope,
                "admin:" + rid,
                "admin." + action,
                now,
                {"origin": "admin", "summary": "管理操作：" + action},
            )
            result = {"revision": self.save(db, scope, rev, doc), "applied": True}
            db.execute(
                "INSERT INTO world_life_requests VALUES(?,?,?,?)",
                (identity(scope), rid, digest, encode(result)),
            )
            return result

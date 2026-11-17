"""One background model batch, individually scoped proposals, deterministic travel."""

from __future__ import annotations

import copy
import hashlib
import math
import uuid

from .spatial import identity, route


class BackgroundResidentsMixin:
    def public_resident(self, actor, admin=False):
        fields = (
            "id",
            "name",
            "card_id",
            "enabled",
            "place_id",
            "home_id",
            "activity",
            "busy_until",
            "journey",
            "revision",
            "model_id",
            "texture_index",
        )
        out = {k: copy.deepcopy(actor.get(k)) for k in fields}
        if admin:
            out["knowledge_count"] = len(actor.get("knowledge", []))
            out["last_reason"] = actor.get("last_reason", "")
            out["last_evaluated_at"] = actor.get("last_served", 0)
            out["last_evaluation_status"] = actor.get(
                "last_evaluation_status", "not_evaluated"
            )
            out["last_decision"] = actor.get("last_decision")
        return out

    def configure_resident(self, db, scope, doc, body, card, now):
        if not card or not card.get("id") or not card.get("name"):
            raise ValueError("请先选择已有角色卡")
        if card.get("persona_id") == scope.get("persona_id"):
            raise ValueError("当前主角色不能重复登记为背景居民")
        actor_id = "resident_" + hashlib.sha256(card["id"].encode()).hexdigest()[:16]
        if actor_id in doc["residents"]:
            raise ValueError("该角色已经登记，请使用启停操作")
        if len(doc["residents"]) >= 32:
            raise ValueError("背景居民名册最多三十二人")
        world = self.engine.spatial.document(db, identity(scope)) or {}
        place = body.get("place_id")
        if place not in {p["id"] for p in world.get("places", [])}:
            raise ValueError("请选择已存在的初始地点")
        doc["residents"][actor_id] = {
            "id": actor_id,
            "card_id": card["id"],
            "name": card["name"],
            "enabled": False,
            "profile": {
                k: str(card.get(k, ""))[:1500]
                for k in ("description", "personality", "scenario")
            },
            "home_id": place,
            "place_id": place,
            "journey": None,
            "busy_until": now,
            "activity": "当前设定，尚未自主行动",
            "revision": 1,
            "last_served": 0,
            "knowledge": [],
            "model_id": "builtin",
            "texture_index": 0,
        }

    def shift_residents(self, doc, delta):
        for actor in doc["residents"].values():
            actor["busy_until"] += delta
            if actor.get("journey"):
                actor["journey"]["arrives_at"] += delta
                actor["journey"]["departed_at"] += delta
        for inv in doc["invitations"].values():
            if inv["status"] not in {"completed", "declined", "cancelled"}:
                inv["when"] += delta
                if inv.get("ends_at"):
                    inv["ends_at"] += delta

    def resident_event(
        self, db, scope, doc, kind, text, observers, now, *, event_id=None, extra=None
    ):
        eid = event_id or "resident:" + uuid.uuid4().hex
        event = {
            "summary": text,
            "observers": sorted(set(observers)),
            "origin": "background_model",
            **(extra or {}),
        }
        if self.receipt(db, scope, eid, kind, now, event):
            for actor_id in observers:
                if actor_id in doc["residents"]:
                    actor = doc["residents"][actor_id]
                    actor["knowledge"] = (
                        actor["knowledge"]
                        + [
                            {
                                "id": eid,
                                "text": text,
                                "at": now,
                                **{
                                    k: v
                                    for k, v in event.items()
                                    if k
                                    in {
                                        "speaker",
                                        "speaker_name",
                                        "participants",
                                        "invitation_id",
                                    }
                                },
                            }
                        ]
                    )[-40:]
                    actor["revision"] += 1
        return eid

    def settle_residents(self, db, scope, doc, now):
        world = self.engine.spatial.document(db, identity(scope)) or {}
        valid_places = {p["id"] for p in world.get("places", [])}
        for a in doc["residents"].values():
            if a.get("routine_kind") and a["busy_until"] <= now:
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "resident.completed",
                    a["name"] + "完成了一段" + a["activity"],
                    [a["id"]],
                    a["busy_until"],
                )
                a.pop("routine_kind", None)
                a["activity"] = "当前活动待确认"
                a["revision"] += 1
            journey = a.get("journey")
            if journey and journey["arrives_at"] <= now:
                if (
                    journey["map_revision"] != world.get("revision")
                    or journey["target_id"] not in valid_places
                    or "map_world_id" in journey
                    and journey["map_world_id"] != world.get("world_id")
                ):
                    a.update(
                        journey=None,
                        activity="路线已变化，停留在最后确认地点",
                        busy_until=now,
                    )
                else:
                    a.update(
                        place_id=journey["target_id"],
                        journey=None,
                        activity="已抵达，等待下一步安排",
                        busy_until=now,
                    )
                    self.resident_event(
                        db,
                        scope,
                        doc,
                        "resident.arrived",
                        a["name"] + "抵达了目的地",
                        [a["id"]],
                        now,
                        event_id=journey["id"] + ":arrived",
                    )
                a["revision"] += 1
        for inv in doc["invitations"].values():
            if inv["status"] in {"proposed", "accepted"} and now > inv["when"] + 7200:
                inv.update(status="cancelled", reason="约定时间已过，未记录赴约")
            if inv["status"] == "accepted" and now >= inv["when"]:
                participants = [
                    self.actor_state(db, scope, doc, aid, now)
                    for aid in (inv["host"], inv["guest"])
                ]
                if all(
                    p
                    and not p.get("journey")
                    and p.get("place_id") == inv["place_id"]
                    and not p.get("asleep")
                    and p.get("busy_until", 0) <= now
                    for p in participants
                ):
                    inv.update(status="visiting", started_at=now, ends_at=now + 1800)
                    self.resident_event(
                        db,
                        scope,
                        doc,
                        "visit.arrived",
                        "双方已经抵达约定地点",
                        [inv["host"], inv["guest"]],
                        now,
                        event_id=inv["id"] + ":arrived",
                    )
            departed = False
            if inv["status"] == "visiting":
                parties = [
                    self.actor_state(db, scope, doc, aid, now)
                    for aid in (inv["host"], inv["guest"])
                ]
                departed = any(
                    not a or a.get("journey") or a.get("place_id") != inv["place_id"]
                    for a in parties
                )
            if inv["status"] == "visiting" and (now >= inv["ends_at"] or departed):
                inv.update(
                    status="completed", reason="本次相处时段结束；位置由后续行程改变"
                )
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "visit.completed",
                    "本次相处时段结束",
                    [inv["host"], inv["guest"]],
                    now,
                    event_id=inv["id"] + ":ended",
                )

    def actor_state(self, db, scope, doc, actor_id, now):
        if actor_id != "self":
            return doc["residents"].get(actor_id)
        import json

        spatial = self.engine.spatial.snapshot(db, scope, now)
        row = db.execute(
            "SELECT state FROM lives WHERE identity=?", (identity(scope),)
        ).fetchone()
        life = json.loads(row[0]) if row else {}
        scene = self.engine.scenes.load(db, scope)[2] if self.engine.scenes else {}
        flow = (scene or {}).get("flow")
        return {
            "id": "self",
            "enabled": True,
            "place_id": spatial.get("place_id"),
            "journey": spatial.get("journey"),
            "asleep": life.get("availability") == "asleep"
            and life.get("valid_until", 0) > now,
            "busy_until": flow.get("step_ends_at", now) if flow else now,
        }

    def background_request(self, db, scope, now):
        rev, doc = self.load(db, scope)
        active = [a for a in doc["residents"].values() if a["enabled"]]
        resolver = getattr(self, "card_resolver", None)
        if callable(resolver):
            active = [a for a in active if resolver(a["card_id"]) is not None]
        if not active:
            return None
        invitations = [
            i
            for i in doc["invitations"].values()
            if i["status"] not in {"completed", "declined", "cancelled"}
        ]
        due = {
            a
            for i in invitations
            if i["when"] <= now + 3600
            for a in (i["host"], i["guest"])
        }
        active.sort(
            key=lambda a: (a["id"] not in due, a.get("last_served", 0), a["id"])
        )
        selected = active[:3]  # plus the existing main actor; no extra model call
        world = self.engine.spatial.document(db, identity(scope)) or {}
        actors = [
            {
                **self.public_resident(a),
                "profile": a["profile"],
                "knowledge": copy.deepcopy(a["knowledge"]),
            }
            for a in selected
        ]
        resolver = getattr(self, "card_resolver", None)
        for a in actors:
            if callable(resolver):
                card = resolver(a["card_id"])
                if card is None:
                    a["enabled"] = False
                    a["profile"] = {}
                else:
                    a["profile"] = {
                        k: str(card.get(k, ""))[:1500]
                        for k in ("description", "personality", "scenario")
                    }
                    a["name"] = card["name"]
                a["card_fingerprint"] = hashlib.sha256(repr(card).encode()).hexdigest()
        self_events = self.projection(db, scope, now, viewer="actor")["events"]
        actors.insert(
            0,
            {
                **self.actor_state(db, scope, doc, "self", now),
                "knowledge": [
                    {"id": e["id"], "text": e.get("summary", e["kind"])}
                    for e in self_events[:20]
                ],
            },
        )
        for a in actors:
            a["available_source_ids"] = [k["id"] for k in a["knowledge"]] + [
                "observation:" + a["id"]
            ]
        selected_ids = {a["id"] for a in actors}
        return {
            "revision": rev,
            "map_revision": world.get("revision", 0),
            "map_world_id": world.get("world_id"),
            "actors": actors,
            "places": [
                {"id": p["id"], "name": p["name"]} for p in world.get("places", [])
            ],
            "invitations": [
                copy.deepcopy(i)
                for i in invitations
                if i["host"] in selected_ids and i["guest"] in selected_ids
            ],
        }

    def validate_updates(self, raw, request):
        value = raw.get("world_updates")
        if value is None:
            return None
        context = request.get("background_world")
        if request["scope"]["umo"] or not context or raw.get("no_change"):
            raise ValueError("只有全局后台推演可提出居民行动")
        if not isinstance(value, list) or len(value) > 8:
            raise ValueError("一次最多八项居民提案")
        actors = {a["id"]: a for a in context["actors"]}
        if context.get("isolated") and any(
            not isinstance(c, dict) or c.get("actor_id") != context["acting_actor_id"]
            for c in value
        ):
            raise ValueError("不得代演其他居民")
        allowed = {
            "actor_id",
            "operation",
            "target_id",
            "invitation_id",
            "response",
            "when",
            "text",
            "source_ids",
        }
        for change in value:
            if (
                not isinstance(change, dict)
                or set(change) - allowed
                or change.get("actor_id") not in actors
            ):
                raise ValueError("未知居民或提案字段")
            sources = change.get("source_ids")
            if (
                not isinstance(sources, list)
                or not sources
                or not all(
                    isinstance(s, str)
                    and s in actors[change["actor_id"]]["available_source_ids"]
                    for s in sources
                )
            ):
                raise ValueError("居民提案引用了未感知的信息")
            if change.get("operation") not in {
                "rest",
                "observe",
                "travel",
                "invite",
                "respond",
                "speak",
            }:
                raise ValueError("未知居民行动")
            if (
                not isinstance(change.get("text", ""), str)
                or len(change.get("text", "")) > 240
            ):
                raise ValueError("居民动机或言语过长")
        return {"context": copy.deepcopy(context), "updates": copy.deepcopy(value)}

    def commit_updates(self, db, scope, change, now):
        if not change:
            return
        rev, doc = self.load(db, scope)
        world = self.engine.spatial.document(db, identity(scope)) or {}
        isolated = change["context"].get("isolated", False)
        active_actor = doc["residents"].get(
            change["context"].get("acting_actor_id"), {}
        )
        stale_actor = isolated and active_actor.get("revision") != change[
            "context"
        ].get("actor_revision")
        stale_map = world.get("revision", 0) != change["context"][
            "map_revision"
        ] or world.get("world_id") != change["context"].get("map_world_id")
        if (
            stale_actor
            or (not isolated and rev != change["context"]["revision"])
            or stale_map
        ):
            raise ValueError("居民或地图已改变，本批提案作废")
        resolver = getattr(self, "card_resolver", None)
        if callable(resolver):
            for a in change["context"]["actors"]:
                if a["id"] == "self" or a.get("public_only"):
                    continue
                card = resolver(a["card_id"])
                if card is None or hashlib.sha256(
                    repr(card).encode()
                ).hexdigest() != a.get("card_fingerprint"):
                    raise ValueError("居民角色卡在推演期间已变化")
        for p in change["updates"]:
            aid, op = p["actor_id"], p["operation"]
            actor = self.actor_state(db, scope, doc, aid, now)
            if (
                not actor
                or not actor.get("enabled")
                or actor.get("asleep")
                or actor.get("journey")
                or actor.get("busy_until", 0) > now
            ):
                raise ValueError("居民正在忙碌、睡眠、途中或未启用")
            if op in {"rest", "observe", "travel"} and aid == "self":
                raise ValueError("主角色行动应通过原有 world_action 执行")
            if op in {"rest", "observe"}:
                actor.update(
                    activity="休息" if op == "rest" else "留意周围环境",
                    busy_until=now + 900,
                    routine_kind=op,
                )
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "resident.started",
                    actor["name"] + "开始" + actor["activity"],
                    [aid],
                    now,
                )
            elif op == "travel":
                places = {x["id"]: x for x in world.get("places", [])}
                start, target = (
                    places.get(actor["place_id"]),
                    places.get(p.get("target_id")),
                )
                if not start or not target or start["id"] == target["id"]:
                    raise ValueError("居民行程起终点无效")
                if world.get("map_type") == "real":
                    from .geography import real_route

                    path, duration = real_route(world, start, target)
                else:
                    path, distance = route(world, start["cell"], target["cell"])
                    if not path:
                        raise ValueError("目的地不可达")
                    duration = max(60, distance * world["seconds_per_unit"])
                if duration > 86400:
                    raise ValueError("居民行程超过一天")
                actor.update(
                    activity="前往" + target["name"],
                    busy_until=now + duration,
                    journey={
                        "id": "trip_" + uuid.uuid4().hex,
                        "target_id": target["id"],
                        "departed_at": now,
                        "arrives_at": now + duration,
                        "path": path,
                        "map_revision": world["revision"],
                        "map_world_id": world.get("world_id"),
                    },
                )
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "resident.departed",
                    actor["name"] + "出发前往" + target["name"],
                    [aid],
                    now,
                )
            elif op == "invite":
                target_id = p.get("target_id")
                peer = self.actor_state(db, scope, doc, target_id, now)
                if (
                    target_id == aid
                    or not peer
                    or not peer.get("enabled")
                    or target_id not in {a["id"] for a in change["context"]["actors"]}
                ):
                    raise ValueError("邀请对象无效")
                when = p.get("when", now + 1800)
                if (
                    type(when) not in (int, float)
                    or not math.isfinite(when)
                    or not now <= when <= now + 7 * 86400
                ):
                    raise ValueError("邀请时间无效")
                if (
                    len(
                        [
                            i
                            for i in doc["invitations"].values()
                            if i["status"] not in {"completed", "declined", "cancelled"}
                        ]
                    )
                    >= 16
                ):
                    raise ValueError("待处理约定已达上限")
                iid = "invite_" + uuid.uuid4().hex[:20]
                doc["invitations"][iid] = {
                    "id": iid,
                    "host": aid,
                    "guest": target_id,
                    "place_id": actor["place_id"],
                    "when": when,
                    "status": "proposed",
                    "reason": p.get("text", ""),
                }
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "invitation.proposed",
                    "收到一次见面邀请",
                    [aid, target_id],
                    now,
                    extra={"invitation_id": iid},
                )
            elif op == "respond":
                inv = doc["invitations"].get(p.get("invitation_id"))
                if isolated and p.get("invitation_id") not in {
                    i["id"] for i in change["context"].get("invitations", [])
                }:
                    raise ValueError("邀请未向该居民提供")
                if not inv or inv["guest"] != aid or inv["status"] != "proposed":
                    raise ValueError("邀请不属于当前接收者或已处理")
                response = p.get("response")
                if response not in {"accepted", "declined", "reschedule"}:
                    raise ValueError("未知邀请回应")
                if response == "reschedule":
                    when = p.get("when")
                    if (
                        type(when) not in (int, float)
                        or not math.isfinite(when)
                        or not now < when <= now + 7 * 86400
                    ):
                        raise ValueError("改期时间无效")
                    inv.update(
                        host=aid, guest=inv["host"], when=when, status="proposed"
                    )
                else:
                    inv["status"] = response
                inv["reason"] = p.get("text", "")
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "invitation.responded",
                    "约定回应：" + response,
                    [inv["host"], inv["guest"]],
                    now,
                    extra={"invitation_id": inv["id"]},
                )
            elif op == "speak":
                target_id = p.get("target_id")
                peer = self.actor_state(db, scope, doc, target_id, now)
                if (
                    not peer
                    or target_id == aid
                    or not peer.get("enabled")
                    or peer.get("journey")
                    or peer.get("asleep")
                    or peer.get("place_id") != actor.get("place_id")
                ):
                    raise ValueError("对方不在场或无法感知")
                # Sharing the map place is insufficient for a private house: require an accepted arrival.
                public_encounter = (
                    isolated
                    and target_id in change["context"].get("visible_peer_ids", [])
                    and target_id != "self"
                )
                if target_id == "self" and isolated:
                    scene = self.engine.scenes.load(db, scope)[2] or {}
                    if scene.get("room_id") is not None or not scene.get("room_known"):
                        raise ValueError("主角色在不可感知的房间")
                    public_encounter = target_id in change["context"].get(
                        "visible_peer_ids", []
                    )
                if not public_encounter and not any(
                    i["status"] == "visiting"
                    and {i["host"], i["guest"]} == {aid, target_id}
                    for i in doc["invitations"].values()
                ):
                    raise ValueError("尚未建立双方到场的交流时段")
                if not p.get("text", "").strip():
                    raise ValueError("言语不能为空")
                self.resident_event(
                    db,
                    scope,
                    doc,
                    "speech.perceived",
                    p["text"],
                    [aid, target_id],
                    now,
                    extra={
                        "speaker": aid,
                        "source_ids": p["source_ids"],
                        "participants": [aid, target_id],
                        **(
                            {"speaker_name": actor["name"]}
                            if actor.get("name") and actor["name"] in p["text"]
                            else {}
                        ),
                    },
                )
            if aid != "self":
                actor["last_reason"] = p.get("text", "")
                actor["revision"] += 1
        for a in change["context"]["actors"]:
            if a["id"] in doc["residents"] and not a.get("public_only"):
                doc["residents"][a["id"]]["last_served"] = now
        self.save(db, scope, rev, doc)

    def guest_projection(self, db, scope, now):
        _, doc = self.load(db, scope)
        scene = self.engine.scenes.load(db, scope)[2] if self.engine.scenes else {}
        main = self.actor_state(db, scope, doc, "self", now)
        homes = {r["place_id"] for r in (scene or {}).get("rooms", {}).values()}
        if main.get("journey") or main.get("place_id") not in homes:
            return None
        for i in doc["invitations"].values():
            if (
                i["status"] != "visiting"
                or "self" not in {i["host"], i["guest"]}
                or i["place_id"] != main["place_id"]
            ):
                continue
            aid = i["guest"] if i["host"] == "self" else i["host"]
            a = doc["residents"].get(aid)
            if a and not a.get("journey") and a["place_id"] == main["place_id"]:
                return {
                    "identity": aid,
                    "name": a["name"],
                    "model_id": a["model_id"],
                    "texture_index": a["texture_index"],
                    "spot": "garden_bench",
                    "activity": "已按约抵达，交流以见闻记录为准",
                    "started_at": i["started_at"],
                    "ends_at": i["ends_at"],
                    "origin": "background_model",
                }
        return None

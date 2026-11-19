"""One shared narrator, one private actor perspective per call, bounded fair scheduling."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from .spatial import encode, identity

OPERATIONS = ["wait", "rest", "observe", "travel", "invite", "respond", "speak"]
DEFAULT_RESIDENT_HOURLY_BUDGET = 6
RESIDENT_CARD_FIELD_LIMIT = 1800
RESIDENT_CARD_TOTAL_LIMIT = 6000
RESIDENT_CARD_FIELDS = (
    "name",
    "description",
    "personality",
    "scenario",
    "system_prompt",
    "post_history_instructions",
)
RULES = """你是群间世界的后台生活模拟器，本次只决定 acting_actor_id 这一名居民的下一步。
你不是主角色，不要继承主角色的睡眠、性格或想法。private_character 是本人的完整人设；own_knowledge 是实际收到的见闻。public_peers 只是当前可见或已联系的人，不包含他们的私有经历。匿名标签不等于姓名；不要用作品知识猜别人的身份、秘密、心理、异地行为或未来剧情。
依据本人性格、兴趣、当前时间、忙碌状态和实际信息自主选择：休息、观察、出行、邀请、回应邀请、向实际在场者说话，或合理等待。不要强制社交、制造进度、补写过去；但“主角色睡觉”不是其他居民一律不行动的理由。
只返回一个 JSON decision，不调用工具或发送真实消息。actor_id 必须等于 acting_actor_id；source_ids 必须引用 available_source_ids；reason 是本人本次选择的简短原因（私有），不要用泛泛的“无新消息”替代判断。
operation: wait 保持现状；rest 休息15分钟；observe 留意环境15分钟；travel(target_id为合法地点)走程序路线；invite(target_id为可联系居民,when为约定epoch秒)在当前地点发起邀请；respond(invitation_id,response=accepted/declined/reschedule，改期需when)；speak(target_id,text)只对当前可感知的对象说一句自然的话。
邀请与到场不同，接受不自动移动。看到人不代表认识，也不必认识后才能礼貌搭话。只能知道自己说过、听过及本人的已有背景；对方的言语是对方的说法，不自动证明其内容。
当前没有居民读写、做饭、施法的程序工具，不要把观察、意图或台词写成已完成作品、已食用、已施法或已控制别人。可以因兴趣留意环境或提出未来想法。
一次只做一个动作。不要同时宣称对方回应；reason 不会传给对方。speak 的 text 是实际言语，invite/respond 的 text 是实际邀请或回应内容，不能把内部动机混入对方已收到的信息。"""


def fingerprint(card):
    return hashlib.sha256(repr(card).encode()).hexdigest()


def _truncate_resident_card(card: dict) -> dict[str, str]:
    """Enforce per-field and total character caps on resident card context."""
    private: dict[str, str] = {}
    remaining = RESIDENT_CARD_TOTAL_LIMIT
    for key in RESIDENT_CARD_FIELDS:
        raw = str(card.get(key, "") or "")
        limit = min(RESIDENT_CARD_FIELD_LIMIT, max(0, remaining))
        value = raw[:limit]
        private[key] = value
        remaining -= len(value)
    return private


_STATIC_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "actor_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "operation": {"type": "string", "enum": list(OPERATIONS)},
        "reason": {"type": "string", "minLength": 1, "maxLength": 240},
        "source_ids": {
            "type": "array",
            "items": {"type": "string", "maxLength": 160},
            "minItems": 1,
            "maxItems": 8,
        },
        "target_id": {"type": "string", "maxLength": 160},
        "text": {"type": "string", "maxLength": 240},
        "invitation_id": {"type": "string", "maxLength": 80},
        "response": {"type": "string", "enum": ["accepted", "declined", "reschedule"]},
        "when": {"type": "number", "minimum": 0},
    },
    "required": ["actor_id", "operation", "reason", "source_ids"],
    "additionalProperties": False,
}


def decision_schema(request=None):
    """Return a static JSON schema; actor_id, source_ids and when are validated in Python."""
    return copy.deepcopy(_STATIC_DECISION_SCHEMA)


def build_prompt_parts(request) -> tuple[str, str]:
    """Split static resident rules/character from volatile per-tick context."""
    # Deliberate allowlist: no main persona, snapshot, diary, other profiles or conversations.
    resident_context = request.get("resident_context")
    system_prompt = RULES
    if isinstance(resident_context, dict) and "private_character" in resident_context:
        system_prompt = (
            RULES
            + "\nprivate_character：\n"
            + json.dumps(
                resident_context["private_character"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        volatile_context = {
            k: v for k, v in resident_context.items() if k != "private_character"
        }
    else:
        volatile_context = resident_context
    payload = {}
    for k in ("now", "local_datetime"):
        if k in request:
            payload[k] = request[k]
    if "resident_context" in request:
        payload["resident_context"] = volatile_context
    user_prompt = "当前个人视角：\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    )
    return system_prompt, user_prompt


def build_prompt(request):
    system_prompt, user_prompt = build_prompt_parts(request)
    return f"{system_prompt}\n{user_prompt}"


class ResidentRunner:
    def __init__(self, service):
        self.service = service
        self.engine = service.narrative
        self.lock = asyncio.Lock()
        with self.engine._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS world_resident_evaluations(
                call_id TEXT PRIMARY KEY, identity TEXT NOT NULL, actor_id TEXT NOT NULL,
                started REAL NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS world_resident_evaluated ON world_resident_evaluations(identity,started);
            """)

    def enabled(self):
        return (
            self.service.is_active()
            and self.engine.config.get("mode", "narrative") == "narrative"
        )

    def context(self, db, scope, actor_id, now):
        causal = self.engine.causal
        rev, doc = causal.load(db, scope)
        actor = doc["residents"].get(actor_id)
        if not actor or not actor.get("enabled"):
            raise ValueError("居民未启用")
        card = causal.card_resolver(actor["card_id"])
        if not card:
            raise ValueError("居民角色卡不存在")
        world = self.engine.spatial.document(db, identity(scope)) or {}
        known = copy.deepcopy(actor.get("knowledge", []))
        own_text = "\n".join(
            str(card.get(k, "") or "") for k in ("description", "personality")
        )

        def label(peer):
            spoken = next(
                (
                    k.get("speaker_name")
                    for k in reversed(known)
                    if k.get("speaker") == peer["id"] and k.get("speaker_name")
                ),
                None,
            )
            if spoken:
                return spoken
            # Explicit established acquaintances in this actor's own background only.
            aliases = {"樱羽艾玛": "艾玛", "二阶堂希罗": "希罗", "月代雪": "月代雪"}
            if aliases.get(peer["name"]) and aliases[peer["name"]] in own_text:
                return peer["name"]
            return "尚未获知姓名的居民"

        invitations = [
            copy.deepcopy(i)
            for i in doc["invitations"].values()
            if actor_id in {i["host"], i["guest"]}
            and i["status"] not in {"completed", "declined", "cancelled"}
        ]
        contacts = {a for i in invitations for a in (i["host"], i["guest"])}
        for k in known:
            contacts.update(k.get("participants") or [])
            if k.get("speaker"):
                contacts.add(k["speaker"])
        peers = []
        for other in doc["residents"].values():
            if not other.get("enabled") or other["id"] == actor_id:
                continue
            visible = (
                not actor.get("journey")
                and not other.get("journey")
                and actor.get("place_id") == other.get("place_id")
            )
            if visible or other["id"] in contacts:
                peers.append(
                    {
                        "id": other["id"],
                        "label": label(other),
                        "visible": visible,
                        "contactable": True,
                        "place_id": other["place_id"] if visible else None,
                    }
                )
        main = causal.actor_state(db, scope, doc, "self", now)
        scene = self.engine.scenes.load(db, scope)[2] or {}
        main_visible = (
            not main.get("asleep")
            and not main.get("journey")
            and not actor.get("journey")
            and main.get("place_id") == actor.get("place_id")
            and scene.get("room_known")
            and scene.get("room_id") is None
        )
        if main_visible or "self" in contacts:
            peers.append(
                {
                    "id": "self",
                    "label": "当前世界的主人",
                    "visible": bool(main_visible),
                    "contactable": True,
                    "place_id": main.get("place_id") if main_visible else None,
                }
            )
        places = [{"id": p["id"], "name": p["name"]} for p in world.get("places", [])]
        private = _truncate_resident_card(card)
        sources = [k["id"] for k in known] + [
            "observation:" + actor_id,
            "profile:" + actor_id,
        ]
        public = {
            "acting_actor_id": actor_id,
            "private_character": private,
            "own_state": causal.public_resident(actor),
            "own_knowledge": known,
            "available_source_ids": sources,
            "public_peers": peers,
            "invitations": invitations,
            "places": places,
            "observation_rule": "无指定房间的背景居民位于已登记地点的公共入口；其他房间内人物不可见。",
        }
        public["own_recent_decisions"] = [
            {
                "at": r["started"],
                "status": r["status"],
                **{
                    k: v
                    for k, v in json.loads(r["evidence"]).items()
                    if k in {"reason", "operation"}
                },
            }
            for r in db.execute(
                "SELECT started,status,evidence FROM world_resident_evaluations WHERE identity=? AND actor_id=? ORDER BY started DESC LIMIT 4",
                (identity(scope), actor_id),
            )
        ]
        actors = [
            {
                **causal.public_resident(actor),
                "card_fingerprint": fingerprint(card),
                "available_source_ids": sources,
            }
        ]
        actors += [
            {
                "id": p["id"],
                "enabled": True,
                "public_only": True,
                "available_source_ids": [],
            }
            for p in peers
        ]
        commit_context = {
            "isolated": True,
            "acting_actor_id": actor_id,
            "actor_revision": actor["revision"],
            "revision": rev,
            "map_revision": world.get("revision", 0),
            "map_world_id": world.get("world_id"),
            "actors": actors,
            "visible_peer_ids": [p["id"] for p in peers if p["visible"]],
            "invitations": invitations,
        }
        return public, commit_context

    async def tick(self, *, actor_id=None, request_id=None, manual=False):
        if not self.enabled():
            return {"status": "disabled"}
        if self.lock.locked() and not manual:
            return {"status": "busy"}
        async with self.lock:
            engine = self.engine
            causal = engine.causal
            scope = engine._global_scope()
            now = engine.clock()
            cid = request_id or "resident:" + uuid.uuid4().hex
            base_interval = max(60, int(engine.config.get("resident_tick_seconds", 300)))
            interval = (
                engine.effective_tick_interval(base_interval, kind="resident", now=now)
                if hasattr(engine, "effective_tick_interval")
                else float(base_interval)
            )
            if not manual and request_id is None:
                with engine._db(notify=False) as db:
                    if engine._paused(db, scope):
                        return {"status": "paused"}
                    last = db.execute(
                        "SELECT last FROM maintenance WHERE identity=? AND kind='resident_tick'",
                        (identity(scope),),
                    ).fetchone()
                    if last and now - last[0] < interval:
                        return {"status": "not_due"}
            with engine._db() as db:
                db.execute("BEGIN IMMEDIATE")
                prior = db.execute(
                    "SELECT * FROM world_resident_evaluations WHERE call_id=?", (cid,)
                ).fetchone()
                if prior:
                    if (
                        prior["identity"] != identity(scope)
                        or actor_id
                        and prior["actor_id"] != actor_id
                    ):
                        raise ValueError("请求标识属于另一居民")
                    return {
                        "status": prior["status"],
                        "actor_id": prior["actor_id"],
                        "replayed": True,
                    }
                if engine._paused(db, scope):
                    return {"status": "paused"}
                last = db.execute(
                    "SELECT last FROM maintenance WHERE identity=? AND kind='resident_tick'",
                    (identity(scope),),
                ).fetchone()
                if not manual and last and now - last[0] < interval:
                    return {"status": "not_due"}
                causal.advance(db, scope, now)
                _, doc = causal.load(db, scope)
                available = [
                    a
                    for a in doc["residents"].values()
                    if a.get("enabled")
                    and not a.get("journey")
                    and a.get("busy_until", 0) <= now
                    and causal.card_resolver(a["card_id"])
                ]
                if actor_id:
                    available = [a for a in available if a["id"] == actor_id]
                if not available:
                    return {"status": "no_ready_resident"}
                # Waiting invitations receive priority only within a bounded fairness window.
                due = {
                    i["guest"]
                    for i in doc["invitations"].values()
                    if i["status"] == "proposed"
                }
                available.sort(
                    key=lambda a: (
                        a.get("last_served", 0) > now - 1800,
                        a["id"] not in due,
                        a.get("last_served", 0),
                        a["id"],
                    )
                )
                selected = available[0]
                actor_id = selected["id"]
                hour = int(now // 3600)
                budget = "resident_global"
                maximum = max(
                    1,
                    min(
                        60,
                        int(
                            engine.config.get(
                                "resident_hourly_budget", DEFAULT_RESIDENT_HOURLY_BUDGET
                            )
                        ),
                    ),
                )
                used = db.execute(
                    "SELECT used FROM budgets WHERE identity=? AND hour=? AND kind=?",
                    (identity(scope), hour, budget),
                ).fetchone()
                if used and used[0] >= maximum:
                    return {"status": "budget_exhausted"}
                db.execute(
                    "INSERT INTO budgets VALUES(?,?,?,1) ON CONFLICT(identity,hour,kind) DO UPDATE SET used=used+1",
                    (identity(scope), hour, budget),
                )
                db.execute(
                    "INSERT INTO maintenance VALUES(?,'resident_tick',?) ON CONFLICT(identity,kind) DO UPDATE SET last=excluded.last",
                    (identity(scope), now),
                )
                if not manual and hasattr(engine, "record_background_tick"):
                    engine.record_background_tick(kind="resident", now=now)
                public, context = self.context(db, scope, actor_id, now)
                request = {
                    "scope": scope,
                    "now": now,
                    "local_datetime": datetime.fromtimestamp(
                        now, ZoneInfo("Asia/Shanghai")
                    ).isoformat(),
                    "resident_isolated": True,
                    "resident_context": public,
                    "inference_call_id": cid,
                }
                evidence = {
                    "profile_hash": context["actors"][0]["card_fingerprint"],
                    "prompt_hash": hashlib.sha256(
                        build_prompt(request).encode()
                    ).hexdigest(),
                    "source_ids": public["available_source_ids"],
                    "visible_peer_ids": context["visible_peer_ids"],
                    "other_private_profiles": 0,
                }
                db.execute(
                    "INSERT INTO world_resident_evaluations VALUES(?,?,?,?,?,?)",
                    (cid, identity(scope), actor_id, now, "pending", encode(evidence)),
                )
            status = "invalid"
            reason = ""
            operation = None
            started = time.monotonic()
            try:
                raw = await asyncio.wait_for(
                    self.service._narrative_model(request),
                    min(90, float(engine.config.get("narrative_timeout_seconds", 90))),
                )
                if not isinstance(raw, dict) or set(raw) - set(
                    decision_schema(request)["properties"]
                ):
                    raise ValueError("居民决策结构无效")
                if (
                    raw.get("actor_id") != actor_id
                    or raw.get("operation") not in OPERATIONS
                ):
                    raise ValueError("本次只允许所选居民行动")
                reason = raw.get("reason")
                if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 240:
                    raise ValueError("需要具体且有限的选择原因")
                sources = raw.get("source_ids")
                if (
                    not isinstance(sources, list)
                    or not 1 <= len(sources) <= 8
                    or not all(
                        isinstance(s, str) and s in public["available_source_ids"]
                        for s in sources
                    )
                ):
                    raise ValueError("引用了未感知来源")
                if "when" in raw:
                    when_val = raw["when"]
                    if (
                        type(when_val) not in (int, float)
                        or not math.isfinite(when_val)
                        or not now <= when_val <= now + 7 * 86400
                    ):
                        raise ValueError("预约时间超出允许范围")
                operation = raw["operation"]
                proposal = {k: v for k, v in raw.items() if k != "reason"}
                if operation in {"rest", "observe", "travel"}:
                    proposal["text"] = reason
                with engine._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not self.enabled() or engine._paused(db, scope):
                        raise ValueError("运行权限已撤销")
                    causal.advance(db, scope, engine.clock())
                    rev, doc = causal.load(db, scope)
                    actor = doc["residents"].get(actor_id)
                    if (
                        not actor
                        or not actor["enabled"]
                        or actor["revision"] != context["actor_revision"]
                    ):
                        raise ValueError("居民在推演期间已变化")
                    if (
                        fingerprint(causal.card_resolver(actor["card_id"]))
                        != context["actors"][0]["card_fingerprint"]
                    ):
                        raise ValueError("人设在推演期间已变化")
                    if operation != "wait":
                        change = causal.validate_updates(
                            {"world_updates": [proposal]},
                            {"scope": scope, "background_world": context},
                        )
                        causal.commit_updates(db, scope, change, engine.clock())
                        rev, doc = causal.load(db, scope)
                        actor = doc["residents"][actor_id]
                    actor["last_served"] = now
                    actor["last_reason"] = reason
                    actor["last_evaluation_status"] = (
                        "wait" if operation == "wait" else "advanced"
                    )
                    actor["last_decision"] = operation
                    causal.save(db, scope, rev, doc)
                    status = "no_change" if operation == "wait" else "advanced"
                    evidence.update(operation=operation, reason=reason, decision=raw)
                    db.execute(
                        "UPDATE world_resident_evaluations SET status=?,evidence=? WHERE call_id=?",
                        (status, encode(evidence), cid),
                    )
            except asyncio.CancelledError:
                status = "cancelled"
                reason = "推演取消，未提交行动"
                raise
            except Exception as exc:
                status = (
                    "timeout"
                    if isinstance(exc, TimeoutError)
                    else "policy_refusal"
                    if engine._is_policy_refusal(exc)
                    else "invalid"
                )
                reason = (
                    str(exc)[:180]
                    if isinstance(exc, ValueError)
                    else type(exc).__name__
                )
            finally:
                with engine._db() as db:
                    if status not in {"advanced", "no_change"}:
                        evidence.update(error=reason)
                        db.execute(
                            "UPDATE world_resident_evaluations SET status=?,evidence=? WHERE call_id=?",
                            (status, encode(evidence), cid),
                        )
                        rev, doc = causal.load(db, scope)
                        if actor_id in doc["residents"]:
                            doc["residents"][actor_id].update(
                                last_served=now,
                                last_evaluation_status=status,
                                last_reason="评估未提交：" + reason,
                            )
                            causal.save(db, scope, rev, doc, bump=False)
                engine._call(cid, identity(scope), "", now, started, status, "resident")
            return {
                "status": status,
                "actor_id": actor_id,
                "operation": operation,
                "reason": reason,
                "call_id": cid,
            }

"""Garden gate mailbox parcels, lore-safe visitor policies and strictly outdoor garden visitors."""
from __future__ import annotations

import hashlib
import re
import uuid

from .spatial import identity

VISITOR_MODES = ("pixel_avatar", "critter", "mailbox_only", "off")
VISITOR_MODE_LABELS = {
    "pixel_avatar": "像素访客小人（花园驻足）",
    "critter": "林间信鸽与小动物化身（防出戏）",
    "mailbox_only": "仅开放院门信箱投递",
    "off": "完全封闭（不接客不收信）",
}
GARDEN_VISITOR_SPOTS = ("bench_west", "pond_edge", "arbor_gate", "flower_path")
CRITTER_FORMS = ("dove", "squirrel", "kitten")
PARCEL_KINDS = {
    "postcard": "手写明信片",
    "snack": "手作点心",
    "flower": "小束鲜花",
    "gift": "纪念小物",
}

BLOCKED_PATTERNS = re.compile(
    r"(ignore\s+previous|system\s*prompt|作为AI|大语言模型|越狱|jailbreak|<script|javascript:|eval\()",
    re.IGNORECASE,
)


def _clean_user_text(value: str, label: str, max_len: int = 120) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip()
    if not text:
        raise ValueError(f"请填写{label}")
    if len(text) > max_len:
        raise ValueError(f"{label}最多 {max_len} 字")
    if BLOCKED_PATTERNS.search(text):
        raise ValueError(f"{label}包含违和或不受支持的指令词，请换一种自然的表达")
    return text


def infer_default_visitor_mode(character_context: dict | None, configured_default: str = "auto") -> str:
    if configured_default in VISITOR_MODES:
        return configured_default
    blob = " ".join(
        str((character_context or {}).get(k) or "")
        for k in ("name", "scenario", "card_id", "persona_id", "worldbook_summary")
    )
    if any(token in blob for token in ("魔女审判", "牢屋敷", "manosaba", "夏目安安", "封闭", "监禁")):
        return "critter"
    return "pixel_avatar"


class MailboxVisitorService:
    """Own garden gate mailbox queue and strictly garden-scoped group member visits."""

    MAILBOX_KINDS = {"open_mailbox"}
    MAILBOX_LABELS = {"open_mailbox": "去院门信箱查收来信与包裹"}

    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_visitor_policy(
                    identity TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_mailbox(
                    parcel_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    umo TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reaction TEXT NOT NULL DEFAULT '',
                    keepsake_slot TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    opened_at REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS world_mailbox_idx ON world_mailbox(identity, status, created_at DESC);
                CREATE TABLE IF NOT EXISTS world_garden_visitors(
                    visitor_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    umo TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    form TEXT NOT NULL,
                    palette_seed TEXT NOT NULL,
                    spot TEXT NOT NULL,
                    note TEXT NOT NULL,
                    arrived_at REAL NOT NULL,
                    departs_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_visitor_active ON world_garden_visitors(identity, departs_at DESC);
                """
            )

    def policy_for(self, db, scope: dict, character_context: dict | None = None) -> str:
        key = identity(scope)
        row = db.execute("SELECT mode FROM world_visitor_policy WHERE identity=?", (key,)).fetchone()
        if row and row[0] in VISITOR_MODES:
            return str(row[0])
        configured = str(self.engine.config.get("default_visitor_policy", "auto"))
        return infer_default_visitor_mode(character_context, configured)

    def set_policy(self, scope: dict, mode: str) -> dict:
        if mode not in VISITOR_MODES:
            raise ValueError("未知访客策略")
        key = identity(scope)
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO world_visitor_policy VALUES(?,?,?) "
                "ON CONFLICT(identity) DO UPDATE SET mode=excluded.mode,updated=excluded.updated",
                (key, mode, now),
            )
            if mode in {"mailbox_only", "off"}:
                db.execute("DELETE FROM world_garden_visitors WHERE identity=?", (key,))
        return {"mode": mode, "label": VISITOR_MODE_LABELS[mode]}

    def deliver_parcel(
        self,
        scope: dict,
        *,
        sender_id: str,
        sender_name: str,
        kind: str = "postcard",
        title: str = "",
        message: str,
        cooldown_seconds: int = 300,
        character_context: dict | None = None,
        bypass_cooldown: bool = False,
    ) -> dict:
        if kind not in PARCEL_KINDS:
            kind = "postcard"
        clean_sender = _clean_user_text(sender_name or sender_id or "旅人", "署名", 32)
        clean_msg = _clean_user_text(message, "投递附言", 140)
        clean_title = _clean_user_text(title or f"{clean_sender}寄来的{PARCEL_KINDS[kind]}", "标题", 40)
        uid = str(sender_id or clean_sender)[:80]
        key = identity(scope)
        now = self.engine.clock()

        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            mode = self.policy_for(db, scope, character_context)
            if mode == "off":
                raise ValueError("当前世界的院门信箱暂未开放投递")
            if not bypass_cooldown and cooldown_seconds > 0:
                recent = db.execute(
                    "SELECT created_at FROM world_mailbox WHERE identity=? AND sender_id=? ORDER BY created_at DESC LIMIT 1",
                    (key, uid),
                ).fetchone()
                if recent and now - float(recent[0]) < cooldown_seconds:
                    wait = max(1, int(cooldown_seconds - (now - float(recent[0]))))
                    raise ValueError(f"信箱刚刚收到过你的投递，请 {wait} 秒后再寄")
            unopened = db.execute(
                "SELECT COUNT(*) FROM world_mailbox WHERE identity=? AND status='unopened'",
                (key,),
            ).fetchone()[0]
            if unopened >= 16:
                raise ValueError("院门信箱已经塞得满满当当，等主人先拆阅后再投递吧")

            pid = "mail_" + uuid.uuid4().hex[:16]
            db.execute(
                "INSERT INTO world_mailbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, key, str(scope.get("umo") or ""), uid, clean_sender, kind, clean_title, clean_msg, "unopened", "", "", now, 0.0),
            )
        return {
            "parcel_id": pid,
            "kind": kind,
            "kind_label": PARCEL_KINDS[kind],
            "title": clean_title,
            "sender_name": clean_sender,
            "status": "unopened",
        }

    def enter_garden(
        self,
        scope: dict,
        *,
        user_id: str,
        display_name: str,
        note: str = "",
        cooldown_seconds: int = 300,
        character_context: dict | None = None,
        bypass_cooldown: bool = False,
    ) -> dict:
        clean_name = _clean_user_text(display_name or user_id or "访客", "访客昵称", 32)
        clean_note = _clean_user_text(note or "在院门外轻轻打了个招呼，在花园边看看风景", "探访留言", 90)
        uid = str(user_id or clean_name)[:80]
        key = identity(scope)
        now = self.engine.clock()
        ttl = 1500.0  # 25 minutes cozy stay in garden

        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM world_garden_visitors WHERE departs_at<=?", (now,))
            mode = self.policy_for(db, scope, character_context)
            if mode in {"mailbox_only", "off"}:
                raise ValueError("当前世界不开放花园探访，你可以通过院门信箱投递心意")

            existing = db.execute(
                "SELECT visitor_id,arrived_at,spot,form FROM world_garden_visitors WHERE identity=? AND user_id=? AND departs_at>?",
                (key, uid, now),
            ).fetchone()
            if existing and not bypass_cooldown and now - float(existing["arrived_at"]) < min(120, cooldown_seconds):
                return {
                    "visitor_id": existing["visitor_id"],
                    "display_name": clean_name,
                    "form": existing["form"],
                    "spot": existing["spot"],
                    "already_present": True,
                    "departs_at": now + ttl,
                }

            seed_hex = hashlib.sha256(f"{key}:{uid}:{clean_name}".encode()).hexdigest()[:16]
            if mode == "critter":
                form = CRITTER_FORMS[int(seed_hex[:2], 16) % len(CRITTER_FORMS)]
            else:
                form = "pixel_avatar"

            active_rows = db.execute(
                "SELECT visitor_id,spot FROM world_garden_visitors WHERE identity=? AND departs_at>? AND user_id<>? ORDER BY arrived_at ASC",
                (key, now, uid),
            ).fetchall()
            # Cap strictly at max 2 concurrent garden visitors!
            if len(active_rows) >= 2:
                db.execute("DELETE FROM world_garden_visitors WHERE visitor_id=?", (active_rows[0]["visitor_id"],))
                active_rows = active_rows[1:]
            taken_spots = {r["spot"] for r in active_rows}
            spot = next((s for s in GARDEN_VISITOR_SPOTS if s not in taken_spots), GARDEN_VISITOR_SPOTS[0])

            vid = existing["visitor_id"] if existing else ("vis_" + uuid.uuid4().hex[:14])
            db.execute("DELETE FROM world_garden_visitors WHERE identity=? AND user_id=?", (key, uid))
            db.execute(
                "INSERT INTO world_garden_visitors VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (vid, key, str(scope.get("umo") or ""), uid, clean_name, form, seed_hex, spot, clean_note, now, now + ttl),
            )
            if self.engine.keepsakes is not None:
                form_zh = {"dove": "白色小信鸽", "squirrel": "林间小松鼠", "kitten": "三花小奶猫"}.get(form, "访客")
                summary = (
                    f"{clean_name}化作一只{form_zh}停在院墙花径边：{clean_note}"
                    if mode == "critter"
                    else f"{clean_name}来到花园小坐片刻：{clean_note}"
                )
                self.engine.keepsakes.record_keyframe(db, scope, "garden_visit", summary, {}, now)

        return {
            "visitor_id": vid,
            "display_name": clean_name,
            "form": form,
            "mode": mode,
            "spot": spot,
            "note": clean_note,
            "departs_at": now + ttl,
        }

    def check_step(self, db, scope: dict, scene_state: dict, actor: dict) -> int:
        home_places = {r["place_id"] for r in scene_state.get("rooms", {}).values()}
        if actor.get("place_id") not in home_places:
            raise ValueError("需要先回到住所院门旁才能打开信箱")
        key = identity(scope)
        count = db.execute("SELECT COUNT(*) FROM world_mailbox WHERE identity=? AND status='unopened'", (key,)).fetchone()[0]
        if count <= 0:
            raise ValueError("院门信箱里目前没有未拆阅的信件")
        return 90

    def open_pending_parcels(self, db, scope: dict, now: float, *, max_open: int = 3) -> list[dict]:
        """Open up to max_open parcels, place gifts/flowers/snacks into keepsake slots, and return receipts."""
        key = identity(scope)
        rows = db.execute(
            "SELECT * FROM world_mailbox WHERE identity=? AND status='unopened' ORDER BY created_at ASC LIMIT ?",
            (key, max_open),
        ).fetchall()
        opened = []
        for row in rows:
            kind = row["kind"]
            slot_choice = (
                "windowsill_vase"
                if kind == "flower"
                else "table_snack"
                if kind == "snack"
                else "desk_2"
                if kind == "postcard"
                else "shelf_2"
            )
            reaction = {
                "postcard": f"认真读完了{row['sender_name']}寄来的明信片，把卡片压在书桌一角。",
                "snack": f"拆开{row['sender_name']}送来的点心尝了一口，眉眼弯弯地摆上果盘。",
                "flower": f"把{row['sender_name']}送的花束修剪花茎，插进北窗台的花瓶里。",
                "gift": f"小心收好{row['sender_name']}寄来的「{row['title']}」，摆进纪念格。",
            }.get(kind, f"拆阅了{row['sender_name']}寄来的信件。")

            placed_slot = ""
            if self.engine.keepsakes is not None:
                ks = self.engine.keepsakes.place_item(
                    db,
                    scope,
                    {
                        "id": "mail_ks_" + row["parcel_id"][-10:],
                        "title": row["title"],
                        "kind": "bouquet" if kind == "flower" else kind,
                        "sender": row["sender_name"],
                        "summary": f"来自 {row['sender_name']}：{row['message']}",
                        "preferred_slot": slot_choice,
                    },
                    now,
                )
                placed_slot = ks["slot"]

            db.execute(
                "UPDATE world_mailbox SET status='opened',reaction=?,keepsake_slot=?,opened_at=? WHERE parcel_id=?",
                (reaction, placed_slot, now, row["parcel_id"]),
            )
            item = {
                "parcel_id": row["parcel_id"],
                "sender_id": row["sender_id"],
                "sender_name": row["sender_name"],
                "umo": row["umo"],
                "kind": kind,
                "title": row["title"],
                "message": row["message"],
                "reaction": reaction,
                "keepsake_slot": placed_slot,
                "opened_at": now,
            }
            opened.append(item)
            if self.engine.keepsakes is not None:
                self.engine.keepsakes.record_keyframe(db, scope, "mailbox_opened", reaction, {}, now)
        return opened

    def settle(self, db, scope: dict, scene_state: dict | None, actor: dict | None, now: float) -> list[dict]:
        """Expire departed garden visitors; auto-open aged parcels when character is home & idle."""
        if db.execute("SELECT 1 FROM world_garden_visitors WHERE departs_at<=? LIMIT 1", (now,)).fetchone():
            db.execute("DELETE FROM world_garden_visitors WHERE departs_at<=?", (now,))
        if not scene_state or scene_state.get("paused_at") is not None or scene_state.get("flow"):
            return []
        home_places = {r["place_id"] for r in scene_state.get("rooms", {}).values()}
        if not home_places or (actor or {}).get("place_id") not in home_places or (actor or {}).get("phase") != "located":
            return []
        key = identity(scope)
        # If an unopened parcel has waited >= 180s while character is home & free, she checks the gate mailbox!
        due = db.execute(
            "SELECT 1 FROM world_mailbox WHERE identity=? AND status='unopened' AND created_at<=? LIMIT 1",
            (key, now - 180),
        ).fetchone()
        if due:
            return self.open_pending_parcels(db, scope, now, max_open=2)
        return []

    def latest_opened_at(self, db, scope: dict) -> float:
        key = identity(scope)
        row = db.execute("SELECT MAX(opened_at) FROM world_mailbox WHERE identity=? AND status='opened'", (key,)).fetchone()
        return float(row[0] or 0.0) if row else 0.0

    def snapshot(self, db, scope: dict, now: float, character_context: dict | None = None, *, read_only: bool = False) -> dict:
        key = identity(scope)
        if not read_only and db.execute("SELECT 1 FROM world_garden_visitors WHERE departs_at<=? LIMIT 1", (now,)).fetchone():
            db.execute("DELETE FROM world_garden_visitors WHERE departs_at<=?", (now,))
        mode = self.policy_for(db, scope, character_context)
        unopened_count = db.execute(
            "SELECT COUNT(*) FROM world_mailbox WHERE identity=? AND status='unopened'",
            (key,),
        ).fetchone()[0]
        parcels = [
            {
                "parcel_id": r["parcel_id"],
                "sender_name": r["sender_name"],
                "kind": r["kind"],
                "kind_label": PARCEL_KINDS.get(r["kind"], "来信"),
                "title": r["title"],
                "message": r["message"],
                "status": r["status"],
                "reaction": r["reaction"],
                "keepsake_slot": r["keepsake_slot"],
                "created_at": float(r["created_at"]),
                "opened_at": float(r["opened_at"]),
            }
            for r in db.execute(
                "SELECT * FROM world_mailbox WHERE identity=? ORDER BY created_at DESC LIMIT 16",
                (key,),
            ).fetchall()
        ]
        visitors = [
            {
                "visitor_id": r["visitor_id"],
                "display_name": r["display_name"],
                "form": r["form"],
                "palette_seed": r["palette_seed"],
                "spot": r["spot"],
                "note": r["note"],
                "arrived_at": float(r["arrived_at"]),
                "departs_at": float(r["departs_at"]),
            }
            for r in db.execute(
                "SELECT * FROM world_garden_visitors WHERE identity=? AND departs_at>? ORDER BY arrived_at DESC LIMIT 2",
                (key, now),
            ).fetchall()
        ]
        return {
            "policy": mode,
            "policy_label": VISITOR_MODE_LABELS[mode],
            "policy_options": dict(VISITOR_MODE_LABELS),
            "unopened_count": int(unopened_count),
            "parcels": parcels,
            "visitors": visitors,
        }

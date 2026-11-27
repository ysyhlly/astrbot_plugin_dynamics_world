"""Garden gate mailbox parcels, lore-safe visitor policies and strictly outdoor garden visitors."""
from __future__ import annotations

import asyncio
import hashlib
import json
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
SLOT_LABELS = {
    "shelf_1": "书架上格",
    "shelf_2": "书架纪念格",
    "desk_1": "书桌左角",
    "desk_2": "书桌右角",
    "windowsill_vase": "北窗台花瓶",
    "table_snack": "茶几果盘",
    "entry_hook": "玄关挂钩",
}


def _slot_label(slot: str) -> str:
    return SLOT_LABELS.get(str(slot or ""), str(slot or "纪念格"))


def _fallback_parcel_reaction(
    sender_name: str,
    kind: str,
    title: str,
    message: str,
    slot: str = "",
) -> str:
    snippet = re.sub(r"\s+", " ", str(message or "")).strip()[:28]
    slot_zh = _slot_label(slot) if slot else "纪念格"
    if kind == "postcard":
        if snippet:
            return f"拆开{sender_name}寄来的明信片，反复读了那句「{snippet}」，把卡片仔细压在{slot_zh}。"
        return f"认真读完了{sender_name}寄来的明信片，把卡片压在{slot_zh}。"
    if kind == "snack":
        if snippet:
            return f"尝了口{sender_name}送来的点心，记着附言里说的「{snippet}」，眉眼弯弯地摆上{slot_zh}。"
        return f"拆开{sender_name}送来的点心尝了一口，眉眼弯弯地摆上{slot_zh}。"
    if kind == "flower":
        if snippet:
            return f"把{sender_name}送的花束细心修剪插进{slot_zh}，心里念着那句「{snippet}」。"
        return f"把{sender_name}送的花束修剪花茎，插进{slot_zh}里。"
    if kind == "gift":
        if snippet:
            return f"小心收好{sender_name}寄来的「{title}」摆进{slot_zh}，记下了「{snippet}」这份心意。"
        return f"小心收好{sender_name}寄来的「{title}」，摆进{slot_zh}。"
    return f"拆阅了{sender_name}寄来的信件，妥帖收进了{slot_zh}。"


def _sanitize_reaction(raw: str) -> str:
    text = re.sub(r"[\r\n\t]+", " ", str(raw or "")).strip()
    text = re.sub(r"^[\"'「『《]+|[\"'」』》]+$", "", text).strip()
    text = re.sub(r"\s{2,}", " ", text)
    if not text or BLOCKED_PATTERNS.search(text):
        return ""
    if len(text) > 140:
        cut = text[:140]
        for sep in ("。", "！", "？", ".", "!", "?"):
            pos = cut.rfind(sep)
            if pos >= 24:
                return cut[: pos + 1]
        return cut.rstrip("，,;； ") + "…"
    return text

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
                CREATE TABLE IF NOT EXISTS world_mailbox_receipts(
                    parcel_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    umo TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    keepsake_slot TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL,
                    reply_status TEXT NOT NULL DEFAULT 'pending',
                    reply_text TEXT NOT NULL DEFAULT '',
                    opened_at REAL NOT NULL,
                    replied_at REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS world_mailbox_receipts_idx ON world_mailbox_receipts(identity, opened_at DESC);
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

    def open_pending_parcels(
        self,
        db,
        scope: dict,
        now: float,
        *,
        max_open: int = 3,
        reaction_map: dict[str, str] | None = None,
    ) -> list[dict]:
        """Open up to max_open parcels, place gifts/flowers/snacks into keepsake slots, record diary/receipts."""
        key = identity(scope)
        rows = db.execute(
            "SELECT * FROM world_mailbox WHERE identity=? AND status='unopened' ORDER BY created_at ASC LIMIT ?",
            (key, max_open),
        ).fetchall()
        has_diary_table = bool(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='diary' LIMIT 1"
            ).fetchone()
        )
        opened = []
        custom_reactions = reaction_map if isinstance(reaction_map, dict) else {}
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

            custom_text = _sanitize_reaction(custom_reactions.get(row["parcel_id"], ""))
            reaction_source = "model" if custom_text else "template"
            reaction = custom_text or _fallback_parcel_reaction(
                row["sender_name"],
                kind,
                row["title"],
                row["message"],
                placed_slot or slot_choice,
            )

            slot_zh = _slot_label(placed_slot or slot_choice)
            summary = (
                f"拆阅了{row['sender_name']}寄来的{PARCEL_KINDS.get(kind, '来信')}"
                f"「{row['title']}」（陈列于{slot_zh}）：{row['message'][:60]}"
            )
            db.execute(
                "UPDATE world_mailbox SET status='opened',reaction=?,keepsake_slot=?,opened_at=? WHERE parcel_id=?",
                (reaction, placed_slot, now, row["parcel_id"]),
            )
            db.execute(
                "INSERT INTO world_mailbox_receipts("
                "parcel_id,identity,umo,sender_id,sender_name,kind,title,message,"
                "reaction,keepsake_slot,summary,reply_status,reply_text,opened_at,replied_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(parcel_id) DO UPDATE SET "
                "reaction=excluded.reaction,keepsake_slot=excluded.keepsake_slot,"
                "summary=excluded.summary,opened_at=excluded.opened_at",
                (
                    row["parcel_id"],
                    key,
                    row["umo"],
                    row["sender_id"],
                    row["sender_name"],
                    kind,
                    row["title"],
                    row["message"],
                    reaction,
                    placed_slot,
                    summary,
                    "pending",
                    "",
                    now,
                    0.0,
                ),
            )
            if has_diary_table:
                diary_id = f"mail_diary_{row['parcel_id']}"
                diary_text = (
                    f"拆阅了{row['sender_name']}寄来的{PARCEL_KINDS.get(kind, '来信')}"
                    f"「{row['title']}」：{reaction}"
                )[:240]
                diary_umo = str(row["umo"] or scope.get("umo") or "")
                db.execute(
                    "INSERT INTO diary VALUES(?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(entry_id) DO UPDATE SET text=excluded.text,occurred=excluded.occurred",
                    (
                        diary_id,
                        key,
                        diary_umo,
                        now,
                        diary_text,
                        "fiction",
                        json.dumps([row["parcel_id"]], ensure_ascii=False),
                        0,
                    ),
                )
            item = {
                "parcel_id": row["parcel_id"],
                "sender_id": row["sender_id"],
                "sender_name": row["sender_name"],
                "umo": row["umo"],
                "kind": kind,
                "kind_label": PARCEL_KINDS.get(kind, "来信"),
                "title": row["title"],
                "message": row["message"],
                "reaction": reaction,
                "reaction_source": reaction_source,
                "summary": summary,
                "keepsake_slot": placed_slot,
                "keepsake_slot_label": slot_zh,
                "reply_status": "pending",
                "opened_at": now,
            }
            opened.append(item)
            if self.engine.keepsakes is not None:
                self.engine.keepsakes.record_keyframe(db, scope, "mailbox_opened", reaction, {}, now)
        return opened

    def pending_reply_material(
        self,
        db,
        scope: dict,
        *,
        umo: str = "",
        sender_id: str = "",
        limit: int = 3,
    ) -> list[dict]:
        """Return opened mailbox receipts awaiting a natural in-character reply."""
        key = identity(scope)
        cap = max(1, min(12, int(limit or 3)))
        clauses = ["identity=?", "reply_status='pending'"]
        params: list = [key]
        if umo:
            clauses.append("(umo=? OR umo='')")
            params.append(umo)
        if sender_id:
            clauses.append("sender_id=?")
            params.append(sender_id)
        params.append(cap)
        rows = db.execute(
            f"SELECT * FROM world_mailbox_receipts WHERE {' AND '.join(clauses)} "
            "ORDER BY opened_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        out = []
        for r in rows:
            slot = str(r["keepsake_slot"] or "")
            slot_zh = _slot_label(slot) if slot else ""
            cue_slot = f"（已陈列于{slot_zh}）" if slot_zh else ""
            out.append(
                {
                    "parcel_id": r["parcel_id"],
                    "umo": r["umo"],
                    "sender_id": r["sender_id"],
                    "sender_name": r["sender_name"],
                    "kind": r["kind"],
                    "kind_label": PARCEL_KINDS.get(r["kind"], "来信"),
                    "title": r["title"],
                    "message": r["message"],
                    "reaction": r["reaction"],
                    "keepsake_slot": slot,
                    "keepsake_slot_label": slot_zh,
                    "reply_cue": (
                        f"可以自然回应{r['sender_name']}寄来的{PARCEL_KINDS.get(r['kind'], '来信')}"
                        f"「{r['title']}」{cue_slot}：{r['reaction']}"
                    ),
                    "opened_at": float(r["opened_at"]),
                }
            )
        return out

    def mark_reply_delivered(
        self, scope: dict, parcel_id: str, reply_text: str = ""
    ) -> bool:
        """Mark a mailbox receipt as naturally replied to."""
        key = identity(scope)
        now = self.engine.clock()
        clean_reply = str(reply_text or "").strip()[:240]
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute(
                "UPDATE world_mailbox_receipts SET reply_status='replied',reply_text=?,replied_at=? "
                "WHERE identity=? AND parcel_id=?",
                (clean_reply, now, key, str(parcel_id or "")),
            )
            return cur.rowcount > 0

    async def mark_reply_delivered_async(
        self, scope: dict, parcel_id: str, reply_text: str = ""
    ) -> bool:
        return await asyncio.to_thread(
            self.mark_reply_delivered, scope, parcel_id, reply_text
        )

    async def open_pending_parcels_async(
        self,
        scope: dict,
        *,
        max_open: int = 3,
        character_context: dict | None = None,
        reaction_generator=None,
    ) -> list[dict]:
        """Async parcel opening that optionally generates 1-2 persona-faithful sentences via LLM."""
        key = identity(scope)

        def _peek_pending():
            with self.engine._db(notify=False) as db:
                db.execute("PRAGMA query_only = ON")
                rows = db.execute(
                    "SELECT * FROM world_mailbox WHERE identity=? AND status='unopened' "
                    "ORDER BY created_at ASC LIMIT ?",
                    (key, max_open),
                ).fetchall()
                return [dict(r) for r in rows]

        pending = await asyncio.to_thread(_peek_pending)
        if not pending:
            return []

        gen = reaction_generator or getattr(self.engine, "mailbox_reaction_generator", None)
        reaction_map: dict[str, str] = {}
        if callable(gen):
            for parcel in pending:
                kind = parcel.get("kind", "postcard")
                slot_choice = (
                    "windowsill_vase"
                    if kind == "flower"
                    else "table_snack"
                    if kind == "snack"
                    else "desk_2"
                    if kind == "postcard"
                    else "shelf_2"
                )
                enriched_parcel = {
                    **parcel,
                    "kind_label": PARCEL_KINDS.get(kind, "来信"),
                    "slot_hint": _slot_label(slot_choice),
                }
                try:
                    raw = await asyncio.wait_for(
                        gen(scope, enriched_parcel, character_context),
                        timeout=12.0,
                    )
                    cleaned = _sanitize_reaction(raw)
                    if cleaned:
                        reaction_map[parcel["parcel_id"]] = cleaned
                except Exception:
                    continue

        def _commit_open():
            with self.engine._db() as db:
                db.execute("BEGIN IMMEDIATE")
                return self.open_pending_parcels(
                    db,
                    scope,
                    self.engine.clock(),
                    max_open=max_open,
                    reaction_map=reaction_map,
                )

        return await asyncio.to_thread(_commit_open)

    def recent_opened_summaries(
        self, db, scope: dict, *, limit: int = 3, umo: str = ""
    ) -> list[dict]:
        """Return recent opened parcel receipts/summaries (Wave 1 awareness + Wave 2 reply base)."""
        key = identity(scope)
        cap = max(1, min(16, int(limit or 3)))
        params: tuple
        if umo:
            sql = (
                "SELECT * FROM world_mailbox_receipts "
                "WHERE identity=? AND (umo=? OR umo='') "
                "ORDER BY opened_at DESC LIMIT ?"
            )
            params = (key, umo, cap)
        else:
            sql = (
                "SELECT * FROM world_mailbox_receipts "
                "WHERE identity=? ORDER BY opened_at DESC LIMIT ?"
            )
            params = (key, cap)
        rows = db.execute(sql, params).fetchall()
        out = [
            {
                "parcel_id": r["parcel_id"],
                "umo": r["umo"],
                "sender_id": r["sender_id"],
                "sender_name": r["sender_name"],
                "kind": r["kind"],
                "kind_label": PARCEL_KINDS.get(r["kind"], "来信"),
                "title": r["title"],
                "message": r["message"],
                "reaction": r["reaction"],
                "keepsake_slot": r["keepsake_slot"],
                "summary": r["summary"],
                "reply_status": r["reply_status"],
                "reply_text": r["reply_text"],
                "opened_at": float(r["opened_at"]),
                "replied_at": float(r["replied_at"]),
            }
            for r in rows
        ]
        if len(out) >= cap:
            return out
        seen = {item["parcel_id"] for item in out}
        fallback_rows = db.execute(
            "SELECT * FROM world_mailbox WHERE identity=? AND status='opened' "
            "ORDER BY opened_at DESC LIMIT ?",
            (key, cap),
        ).fetchall()
        for r in fallback_rows:
            if r["parcel_id"] in seen:
                continue
            if umo and r["umo"] and r["umo"] != umo:
                continue
            kind = r["kind"]
            out.append(
                {
                    "parcel_id": r["parcel_id"],
                    "umo": r["umo"],
                    "sender_id": r["sender_id"],
                    "sender_name": r["sender_name"],
                    "kind": kind,
                    "kind_label": PARCEL_KINDS.get(kind, "来信"),
                    "title": r["title"],
                    "message": r["message"],
                    "reaction": r["reaction"],
                    "keepsake_slot": r["keepsake_slot"],
                    "summary": (
                        f"拆阅了{r['sender_name']}寄来的{PARCEL_KINDS.get(kind, '来信')}"
                        f"「{r['title']}」：{r['message'][:60]}"
                    ),
                    "reply_status": "pending",
                    "reply_text": "",
                    "opened_at": float(r["opened_at"]),
                    "replied_at": 0.0,
                }
            )
            if len(out) >= cap:
                break
        return out

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
        recent_opened = self.recent_opened_summaries(db, scope, limit=3)
        pending_replies = self.pending_reply_material(
            db, scope, umo=str(scope.get("umo") or ""), limit=3
        )
        return {
            "policy": mode,
            "policy_label": VISITOR_MODE_LABELS[mode],
            "policy_options": dict(VISITOR_MODE_LABELS),
            "unopened_count": int(unopened_count),
            "parcels": parcels,
            "visitors": visitors,
            "latest_opened": recent_opened[0] if recent_opened else None,
            "recent_opened": recent_opened,
            "pending_replies": pending_replies,
        }

    async def set_policy_async(self, scope: dict, mode: str) -> dict:
        return await asyncio.to_thread(self.set_policy, scope, mode)

    async def deliver_parcel_async(self, scope: dict, **kwargs) -> dict:
        return await asyncio.to_thread(self.deliver_parcel, scope, **kwargs)

    async def enter_garden_async(self, scope: dict, **kwargs) -> dict:
        return await asyncio.to_thread(self.enter_garden, scope, **kwargs)

    async def snapshot_async(
        self,
        scope: dict,
        now: float | None = None,
        character_context: dict | None = None,
        *,
        read_only: bool = True,
    ) -> dict:
        def _read():
            ts = self.engine.clock() if now is None else float(now)
            with self.engine._db(notify=False) as db:
                return self.snapshot(
                    db, scope, ts, character_context, read_only=read_only
                )

        return await asyncio.to_thread(_read)

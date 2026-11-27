"""8 fixed 3D keepsake slots, collection box archive, bookshelf volumes and 24h keyframes."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from .series_panels import resolve_series_timezone
from .spatial import encode, identity

SOURCE_PLUGIN_LABELS = {
    "astrbot_plugin_group_chronicle": "群史记",
    "astrbot_plugin_dynamics_games": "群间游戏",
    "astrbot_plugin_dynamics_memory": "群间记忆",
    "astrbot_plugin_dynamics_horizons": "群间见闻",
    "astrbot_plugin_dynamics_learning": "群间学习",
    "astrbot_plugin_visual_media": "视觉工坊",
    "astrbot_plugin_dynamics_world": "群间世界",
    "astrbot_plugin_chat_dynamics": "对话主控",
}


def _safe_deep_link(raw: str) -> str:
    text = str(raw or "").strip()[:160]
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:", "http://", "https://")):
        return ""
    return text


def _build_keepsake_thumbnail_data_url(image_path: str) -> str:
    raw = str(image_path or "").strip()
    if not raw:
        return ""
    try:
        p = Path(raw)
        if not p.is_file() or p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return ""
        if p.stat().st_size > 8 * 1024 * 1024:
            return ""
        from PIL import Image

        with Image.open(p) as im:
            im = im.convert("RGB")
            im.thumbnail((280, 220))
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=78, optimize=True)
            data = buf.getvalue()
            if len(data) > 48 * 1024:
                buf = BytesIO()
                im.thumbnail((200, 160))
                im.save(buf, format="JPEG", quality=68, optimize=True)
                data = buf.getvalue()
            return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""

KEEPSAKE_SLOTS = (
    "windowsill_vase",
    "shelf_1",
    "shelf_2",
    "shelf_3",
    "desk_1",
    "desk_2",
    "table_snack",
    "entry_hook",
)

SLOT_LABELS = {
    "windowsill_vase": "窗台花瓶",
    "shelf_1": "书架纪念格 · 左",
    "shelf_2": "书架纪念格 · 中",
    "shelf_3": "书架纪念格 · 右",
    "desk_1": "书桌摆件位 · 左",
    "desk_2": "书桌摆件位 · 右",
    "table_snack": "点心果盘位",
    "entry_hook": "玄关挂钩",
}

BOOK_SPINE_COLORS = (
    "#8e5a44",
    "#4f6f82",
    "#5c7c57",
    "#9c6f3e",
    "#73567a",
    "#8c4a52",
    "#4e6c66",
    "#967846",
)


def bookshelf_volumes(scene_state: dict | None, *, public_only: bool = False) -> list[dict]:
    """Map completed creative_projects into color-coded clickable 3D bookshelf volumes."""
    projects = (scene_state or {}).get("projects") or {}
    volumes = []
    # scene_state may come from raw dict (projects is dict) or public list (projects is list)
    iterable = projects.values() if isinstance(projects, dict) else projects
    for proj in iterable:
        if not isinstance(proj, dict) or proj.get("status") != "completed":
            continue
        if public_only:
            vis = str(proj.get("visibility") or "public").strip().lower()
            if vis in {"private", "secret", "hidden", "admin_only"} or proj.get("private") is True or proj.get("is_public") is False:
                continue
        pid = str(proj.get("id") or "")
        title = str(proj.get("title") or "未命名作品")
        digest = hashlib.sha256((pid + ":" + title).encode("utf-8")).digest()
        color = BOOK_SPINE_COLORS[digest[0] % len(BOOK_SPINE_COLORS)]
        sections = proj.get("sections") or proj.get("artifacts") or []
        if isinstance(sections, dict):
            sections = [sections[k] for k in sorted(sections, key=lambda x: int(x) if str(x).isdigit() else str(x))]
        excerpts = []
        for idx, sec in enumerate(sections[:12]):
            if isinstance(sec, dict):
                txt = str(sec.get("revised_text") or sec.get("draft_text") or sec.get("text") or sec.get("content") or "").strip()
                if txt:
                    excerpts.append({"part": idx + 1, "title": str(sec.get("title") or f"第 {idx + 1} 节"), "text": txt[:800]})
        full_content = "\n\n".join(f"【{e['title']}】\n{e['text']}" for e in excerpts)
        volumes.append(
            {
                "id": pid,
                "project_id": pid,
                "title": title,
                "kind": str(proj.get("kind") or "prose"),
                "spine_color": color,
                "completed_at": float(proj.get("completed_at") or proj.get("updated_at") or 0),
                "target_parts": int(proj.get("target_parts") or len(excerpts) or 1),
                "excerpts": excerpts,
                "content": full_content,
            }
        )
    volumes.sort(key=lambda v: (v["completed_at"], v["project_id"]))
    return volumes[:16]


class KeepsakeTimelineService:
    """Manage 8 fixed 3D display slots, collection box archive and 24h footprint keyframes."""

    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_keepsakes(
                    identity TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    slots TEXT NOT NULL,
                    archive TEXT NOT NULL,
                    updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_timeline_keyframes(
                    id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    occurred REAL NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_timeline_idx ON world_timeline_keyframes(identity, occurred DESC);
                CREATE TABLE IF NOT EXISTS world_book_bookmarks(
                    bookmark_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    umo TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    book_title TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    review TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_book_bookmarks_idx ON world_book_bookmarks(identity, created_at DESC);
                """
            )

    def load_keepsakes(self, db, scope: dict) -> tuple[str, int, dict, list]:
        key = identity(scope)
        row = db.execute("SELECT revision,slots,archive FROM world_keepsakes WHERE identity=?", (key,)).fetchone()
        if row:
            return key, int(row["revision"]), json.loads(row["slots"]), json.loads(row["archive"])
        return key, 0, {}, []

    def save_keepsakes(self, db, key: str, revision: int, slots: dict, archive: list, now: float) -> int:
        next_rev = revision + 1
        db.execute(
            "INSERT INTO world_keepsakes VALUES(?,?,?,?,?) "
            "ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,slots=excluded.slots,"
            "archive=excluded.archive,updated=excluded.updated",
            (key, next_rev, encode(slots), encode(archive[-60:]), now),
        )
        return next_rev

    def place_item(self, db, scope: dict, item: dict, now: float) -> dict:
        """Place a bouquet, gift, snack or travel souvenir into an appropriate 3D slot; overflow to archive."""
        key, rev, slots, archive = self.load_keepsakes(db, scope)
        preferred = str(item.get("preferred_slot") or "").strip()
        kind = str(item.get("kind") or "souvenir")
        if preferred not in KEEPSAKE_SLOTS:
            if kind == "bouquet":
                preferred = "windowsill_vase"
            elif kind in {"meal", "tea", "snack"}:
                preferred = "table_snack"
            elif kind == "umbrella":
                preferred = "entry_hook"
            else:
                preferred = next((s for s in ("shelf_1", "shelf_2", "shelf_3", "desk_1", "desk_2") if s not in slots), "shelf_1")

        entry = {
            "id": str(item.get("id") or ("ks_" + uuid.uuid4().hex[:12])),
            "title": str(item.get("title") or "纪念小物")[:40],
            "kind": kind,
            "sender": str(item.get("sender") or "")[:32],
            "summary": str(item.get("summary") or "")[:160],
            "color": str(item.get("color") or "#" + hashlib.sha256(str(item.get("title", "")).encode()).hexdigest()[:6]),
            "placed_at": now,
            "slot": preferred,
        }
        for extra_key in ("source_plugin", "source_label", "deep_link", "image_path", "image_data_url", "dedupe_key"):
            val = item.get(extra_key)
            if val:
                entry[extra_key] = val
        displaced = slots.get(preferred)
        if displaced and displaced.get("title") != entry["title"]:
            displaced_copy = dict(displaced, archived_at=now)
            archive = ([a for a in archive if a.get("id") != displaced_copy.get("id")] + [displaced_copy])[-60:]
        slots[preferred] = entry
        self.save_keepsakes(db, key, rev, slots, archive, now)
        return entry

    def register_external_keepsake(
        self,
        scope: dict,
        *,
        title: str,
        summary: str,
        sender_name: str = "",
        source_plugin: str = "",
        deep_link: str = "",
        image_path: str = "",
        kind: str = "memory_postcard",
        preferred_slot: str = "",
    ) -> dict:
        """Persistently register & deduplicate an external companion keepsake into 3D cabin slots."""
        clean_title = re.sub(r"[\x00-\x1f\x7f]+", " ", str(title or "")).strip()[:40]
        if not clean_title:
            raise ValueError("纪念品标题不能为空")
        clean_summary = re.sub(r"[\x00-\x1f\x7f]+", " ", str(summary or "")).strip()[:160]
        clean_sender = re.sub(r"[\x00-\x1f\x7f]+", " ", str(sender_name or "")).strip()[:32]
        clean_plugin = str(source_plugin or "").strip()[:64]
        clean_link = _safe_deep_link(deep_link)
        clean_kind = str(kind or "memory_postcard").strip()[:32] or "memory_postcard"
        source_label = SOURCE_PLUGIN_LABELS.get(clean_plugin, clean_plugin or "系列伙伴")
        thumb_url = _build_keepsake_thumbnail_data_url(image_path)
        dedupe_key = hashlib.sha256(
            f"{clean_plugin}|{clean_kind}|{clean_title}|{clean_sender}".encode()
        ).hexdigest()[:16]
        now = self.engine.clock()

        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, rev, slots, archive = self.load_keepsakes(db, scope)
            for slot_id, existing in list(slots.items()):
                if isinstance(existing, dict) and existing.get("dedupe_key") == dedupe_key:
                    updated = dict(existing)
                    updated.update(
                        summary=clean_summary or updated.get("summary", ""),
                        deep_link=clean_link or updated.get("deep_link", ""),
                        source_label=source_label,
                        placed_at=now,
                    )
                    if image_path:
                        updated["image_path"] = str(image_path)
                    if thumb_url:
                        updated["image_data_url"] = thumb_url
                    slots[slot_id] = updated
                    self.save_keepsakes(db, key, rev, slots, archive, now)
                    return {
                        "ok": True,
                        "deduplicated": True,
                        "slot": slot_id,
                        "slot_label": SLOT_LABELS.get(slot_id, slot_id),
                        "item": updated,
                    }
            # Also dedupe from archive: promote back to shelf if re-registered
            archive = [
                a for a in archive if not (isinstance(a, dict) and a.get("dedupe_key") == dedupe_key)
            ]
            chosen_slot = preferred_slot if preferred_slot in KEEPSAKE_SLOTS else ""
            if not chosen_slot:
                preferred_order = ("shelf_1", "shelf_2", "shelf_3", "desk_1", "desk_2")
                chosen_slot = next((s for s in preferred_order if s not in slots), "shelf_1")
            item_payload = {
                "id": "ext_" + dedupe_key[:12],
                "title": clean_title,
                "kind": clean_kind,
                "sender": clean_sender,
                "summary": clean_summary or f"来自{source_label}的珍贵纪念。",
                "source_plugin": clean_plugin,
                "source_label": source_label,
                "deep_link": clean_link,
                "image_path": str(image_path or ""),
                "image_data_url": thumb_url,
                "dedupe_key": dedupe_key,
                "preferred_slot": chosen_slot,
            }
            placed = self.place_item(db, scope, item_payload, now)
            self.record_keyframe(
                db,
                scope,
                "external_keepsake",
                f"在{SLOT_LABELS.get(placed['slot'], '纪念格')}摆上了来自{source_label}的「{clean_title}」",
                {},
                now,
            )
        return {
            "ok": True,
            "deduplicated": False,
            "slot": placed["slot"],
            "slot_label": SLOT_LABELS.get(placed["slot"], placed["slot"]),
            "item": placed,
        }

    def add_book_bookmark(
        self,
        db,
        scope: dict,
        *,
        book_id: str = "",
        book_title: str,
        sender_id: str,
        sender_name: str,
        review: str,
        now: float,
    ) -> dict:
        """Attach a group member's book review as an interleaved bookmark on a bookshelf volume."""
        key = identity(scope)
        bid = "bm_" + uuid.uuid4().hex[:14]
        clean_title = re.sub(r"[\x00-\x1f\x7f]+", " ", str(book_title or "")).strip()[:60]
        clean_sender = re.sub(r"[\x00-\x1f\x7f]+", " ", str(sender_name or sender_id or "读者")).strip()[:32]
        clean_review = re.sub(r"[\x00-\x1f\x7f]+", " ", str(review or "")).strip()[:160]
        db.execute(
            "INSERT INTO world_book_bookmarks VALUES(?,?,?,?,?,?,?,?,?)",
            (
                bid,
                key,
                str(scope.get("umo") or ""),
                str(book_id or ""),
                clean_title,
                str(sender_id or ""),
                clean_sender,
                clean_review,
                float(now),
            ),
        )
        return {
            "bookmark_id": bid,
            "book_id": str(book_id or ""),
            "book_title": clean_title,
            "sender_id": str(sender_id or ""),
            "sender_name": clean_sender,
            "review": clean_review,
            "created_at": float(now),
        }

    def list_book_bookmarks(self, db, scope: dict, *, book_id: str = "", limit: int = 32) -> list[dict]:
        key = identity(scope)
        cap = max(1, min(64, int(limit or 32)))
        if book_id:
            rows = db.execute(
                "SELECT * FROM world_book_bookmarks WHERE identity=? AND book_id=? ORDER BY created_at DESC LIMIT ?",
                (key, book_id, cap),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM world_book_bookmarks WHERE identity=? ORDER BY created_at DESC LIMIT ?",
                (key, cap),
            ).fetchall()
        return [
            {
                "bookmark_id": r["bookmark_id"],
                "umo": r["umo"],
                "book_id": r["book_id"],
                "book_title": r["book_title"],
                "sender_id": r["sender_id"],
                "sender_name": r["sender_name"],
                "review": r["review"],
                "created_at": float(r["created_at"]),
            }
            for r in rows
        ]

    def swap_from_archive(self, scope: dict, item_id: str, slot: str) -> dict:
        if slot not in KEEPSAKE_SLOTS:
            raise ValueError("无效的陈列槽位置")
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, rev, slots, archive = self.load_keepsakes(db, scope)
            chosen = next((a for a in archive if a.get("id") == item_id), None)
            if not chosen:
                raise ValueError("收藏匣中未找到该纪念物")
            archive = [a for a in archive if a.get("id") != item_id]
            if slot in slots:
                old = dict(slots[slot], archived_at=now)
                archive.append(old)
            chosen = dict(chosen, slot=slot, placed_at=now)
            chosen.pop("archived_at", None)
            slots[slot] = chosen
            next_rev = self.save_keepsakes(db, key, rev, slots, archive, now)
        return {"revision": next_rev, "slot": slot, "item": chosen}

    def record_keyframe(self, db, scope: dict, kind: str, summary: str, cues: dict | None, now: float) -> str | None:
        """Append a 24h keyframe snapshot, pruning >24h entries and deduplicating rapid identical polls."""
        key = identity(scope)
        cues = dict(cues or {})
        raw_furn = cues.get("furniture")
        compact_furn = (
            [
                {
                    "id": str(f.get("id") or ""),
                    "name": str(f.get("name") or ""),
                    "kind": str(f.get("kind") or ""),
                    "position": str(f.get("position") or ""),
                    "movable": bool(f.get("movable")),
                }
                for f in raw_furn
                if isinstance(f, dict) and f.get("kind") and f.get("position")
            ]
            if isinstance(raw_furn, list)
            else None
        )
        latest = db.execute(
            "SELECT occurred,kind,payload FROM world_timeline_keyframes WHERE identity=? ORDER BY occurred DESC LIMIT 1",
            (key,),
        ).fetchone()
        if latest:
            prev_payload = json.loads(latest["payload"])
            same_signature = (
                prev_payload.get("summary") == summary
                and prev_payload.get("weather") == cues.get("weather")
                and prev_payload.get("curtains") == cues.get("curtains")
                and prev_payload.get("lighting") == cues.get("lighting")
                and prev_payload.get("location") == cues.get("location")
                and prev_payload.get("pose") == cues.get("pose")
                and prev_payload.get("cabin_style","cottage") == cues.get("cabin_style","cottage")
                and (compact_furn is None or prev_payload.get("furniture") == compact_furn)
            )
            elapsed = now - float(latest["occurred"])
            if kind == "ambient":
                if same_signature and elapsed < 3600:
                    return None
                if not same_signature and elapsed < 120:
                    return None
            elif latest["kind"] == kind and same_signature and elapsed < 120:
                return None

        tz = resolve_series_timezone(
            getattr(self.engine, "host_context", None),
            explicit_tz=str(cues.get("timezone") or ""),
        )
        local = datetime.fromtimestamp(float(now), tz)
        payload = {
            "hour": round(local.hour + local.minute / 60.0, 2),
            "clock_label": local.strftime("%H:%M"),
            "weather": str(cues.get("weather") or "clear"),
            "weather_label": str(cues.get("weather_label") or "晴"),
            "temperature": cues.get("temperature"),
            "curtains": str(cues.get("curtains") or "open"),
            "lighting": str(cues.get("lighting") or "warm"),
            "location": str(cues.get("location") or "room"),
            "place_name": str(cues.get("place_name") or ""),
            "pose": str(cues.get("pose") or "idle"),
            "cabin_style":str(cues.get("cabin_style") or "cottage"),
            "cat_spot": str(cues.get("cat_spot") or "bed_nap"),
            "outfit_now": str(cues.get("outfit_now") or "")[:80],
            "summary": str(summary or "日常片刻")[:160],
        }
        if compact_furn is not None:
            payload["furniture"] = compact_furn
        kid = "kf_" + uuid.uuid4().hex[:16]
        db.execute(
            "INSERT INTO world_timeline_keyframes VALUES(?,?,?,?,?)",
            (kid, key, now, kind, encode(payload)),
        )
        # Prune keyframes older than 30h and cap at 96 entries per identity
        db.execute("DELETE FROM world_timeline_keyframes WHERE identity=? AND occurred<?", (key, now - 30 * 3600))
        overflow = db.execute(
            "SELECT id FROM world_timeline_keyframes WHERE identity=? ORDER BY occurred DESC LIMIT -1 OFFSET 96",
            (key,),
        ).fetchall()
        if overflow:
            db.executemany("DELETE FROM world_timeline_keyframes WHERE id=?", [(r[0],) for r in overflow])
        return kid

    def timeline_snapshot(self, db, scope: dict, now: float, limit: int = 72) -> list[dict]:
        key = identity(scope)
        rows = db.execute(
            "SELECT id,occurred,kind,payload FROM world_timeline_keyframes "
            "WHERE identity=? AND occurred>=? ORDER BY occurred ASC LIMIT ?",
            (key, now - 24 * 3600, max(1, min(96, int(limit)))),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "occurred_at": float(r["occurred"]),
                "kind": r["kind"],
                **json.loads(r["payload"]),
            }
            for r in rows
        ]

    def snapshot(self, db, scope: dict, scene_state: dict | None, now: float) -> dict:
        _, rev, slots, archive = self.load_keepsakes(db, scope)
        # Check wet umbrella physical trace on entry_hook
        wet_umbrella = False
        for item in (scene_state or {}).get("items", {}).values() if isinstance((scene_state or {}).get("items"), dict) else (scene_state or {}).get("items") or []:
            if isinstance(item, dict) and item.get("kind") == "umbrella" and float(item.get("wet_until", 0) or 0) > now and not item.get("carried"):
                wet_umbrella = True
                break
        effective_slots = copy.deepcopy(slots)
        if wet_umbrella and "entry_hook" not in effective_slots:
            effective_slots["entry_hook"] = {
                "id": "trace_wet_umbrella",
                "title": "滴水的雨伞",
                "kind": "umbrella",
                "sender": "",
                "summary": "刚从雨里回来挂在玄关沥水的雨伞，伞尖还在轻轻滴答。",
                "color": "#4f779e",
                "placed_at": now,
                "slot": "entry_hook",
            }
        volumes = bookshelf_volumes(scene_state)
        all_bookmarks = self.list_book_bookmarks(db, scope, limit=48)
        for vol in volumes:
            vid = str(vol.get("id") or "")
            vtitle = str(vol.get("title") or "").strip().lower()
            matched = [
                bm
                for bm in all_bookmarks
                if (vid and bm["book_id"] == vid)
                or (
                    vtitle
                    and bm["book_title"].strip().lower()
                    and (
                        bm["book_title"].strip().lower() == vtitle
                        or bm["book_title"].strip().lower() in vtitle
                        or vtitle in bm["book_title"].strip().lower()
                    )
                )
            ]
            vol["bookmarks"] = matched[:12]
        return {
            "revision": rev,
            "slot_labels": dict(SLOT_LABELS),
            "slots": effective_slots,
            "archive": copy.deepcopy(archive[-30:]),
            "archive_count": len(archive),
            "bookshelf_volumes": volumes,
            "book_bookmarks": all_bookmarks[:24],
            "wet_umbrella": wet_umbrella,
        }

"""8 fixed 3D keepsake slots, collection box archive, bookshelf volumes and 24h keyframes."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from .spatial import encode, identity

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


def bookshelf_volumes(scene_state: dict | None) -> list[dict]:
    """Map completed creative_projects into color-coded clickable 3D bookshelf volumes."""
    projects = (scene_state or {}).get("projects") or {}
    volumes = []
    # scene_state may come from raw dict (projects is dict) or public list (projects is list)
    iterable = projects.values() if isinstance(projects, dict) else projects
    for proj in iterable:
        if not isinstance(proj, dict) or proj.get("status") != "completed":
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
            "summary": str(item.get("summary") or "")[:140],
            "color": str(item.get("color") or "#" + hashlib.sha256(str(item.get("title", "")).encode()).hexdigest()[:6]),
            "placed_at": now,
            "slot": preferred,
        }
        displaced = slots.get(preferred)
        if displaced and displaced.get("title") != entry["title"]:
            displaced_copy = dict(displaced, archived_at=now)
            archive = ([a for a in archive if a.get("id") != displaced_copy.get("id")] + [displaced_copy])[-60:]
        slots[preferred] = entry
        self.save_keepsakes(db, key, rev, slots, archive, now)
        return entry

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

        tz_name = str(cues.get("timezone") or "Asia/Shanghai")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Shanghai")
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
        return {
            "revision": rev,
            "slot_labels": dict(SLOT_LABELS),
            "slots": effective_slots,
            "archive": copy.deepcopy(archive[-30:]),
            "archive_count": len(archive),
            "bookshelf_volumes": bookshelf_volumes(scene_state),
            "wet_umbrella": wet_umbrella,
        }

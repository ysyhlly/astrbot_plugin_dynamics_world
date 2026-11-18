"""Shared world groups (world_id), multi-character public encounters and cabin visits."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid

from .spatial import encode, identity

WORLD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\u4e00-\u9fff]{2,48}$")


def default_world_id(key: str) -> str:
    return "solo_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


class WorldSpaceService:
    """Optional world_id grouping: shared map & weather, private cabins, encounters & visits."""

    def __init__(self, engine):
        self.engine = engine
        self.avatar_resolver = None
        with engine._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_space_bindings(
                    identity TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    character_name TEXT NOT NULL DEFAULT '',
                    updated REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_space_by_group ON world_space_bindings(world_id);
                CREATE TABLE IF NOT EXISTS world_space_guests(
                    host_identity TEXT PRIMARY KEY,
                    guest_identity TEXT NOT NULL,
                    guest_name TEXT NOT NULL,
                    guest_model_id TEXT NOT NULL DEFAULT 'builtin',
                    guest_texture INTEGER NOT NULL DEFAULT 0,
                    spot TEXT NOT NULL DEFAULT 'garden_bench',
                    activity TEXT NOT NULL DEFAULT '',
                    started_at REAL NOT NULL,
                    ends_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_space_encounters(
                    id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    place_id TEXT NOT NULL,
                    place_name TEXT NOT NULL,
                    actors TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    occurred REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_space_encounter_time ON world_space_encounters(world_id, occurred DESC);
                """
            )

    def world_id_for(self, db, key: str) -> str:
        row = db.execute("SELECT world_id FROM world_space_bindings WHERE identity=?", (key,)).fetchone()
        return str(row[0]) if row and row[0] else default_world_id(key)

    def map_owner_key(self, db, key: str) -> str:
        """Return canonical map/weather owner key in a shared world_id, or key itself if solo."""
        row = db.execute("SELECT world_id FROM world_space_bindings WHERE identity=?", (key,)).fetchone()
        if not row or not row[0]:
            return key
        wid = str(row[0])
        # If this identity already has its own map and was first, or pick earliest bound identity with a map.
        members = [
            r[0]
            for r in db.execute(
                "SELECT identity FROM world_space_bindings WHERE world_id=? ORDER BY updated ASC, identity ASC",
                (wid,),
            ).fetchall()
        ]
        for member in members:
            has_map = db.execute("SELECT 1 FROM world_maps WHERE identity=?", (member,)).fetchone()
            if has_map:
                return member
        return key

    def bind(self, scope: dict, world_id: str, label: str = "", character_name: str = "") -> dict:
        key = identity(scope)
        now = self.engine.clock()
        clean_id = str(world_id or "").strip()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not clean_id or clean_id == "solo":
                db.execute("DELETE FROM world_space_bindings WHERE identity=?", (key,))
                return {"world_id": default_world_id(key), "shared": False}
            if not WORLD_ID_PATTERN.fullmatch(clean_id):
                raise ValueError("世界组标识需为 2–48 位中英文、数字、下划线或连字符")
            clean_label = str(label or clean_id).strip()[:60]
            clean_name = str(character_name or scope.get("persona_id") or "").strip()[:60]
            db.execute(
                "INSERT INTO world_space_bindings VALUES(?,?,?,?,?) "
                "ON CONFLICT(identity) DO UPDATE SET world_id=excluded.world_id,label=excluded.label,"
                "character_name=CASE WHEN excluded.character_name<>'' THEN excluded.character_name ELSE world_space_bindings.character_name END,"
                "updated=excluded.updated",
                (key, clean_id, clean_label, clean_name, now),
            )
            # Ensure initial position exists on shared map if another member already generated a map
            owner_key = self.map_owner_key(db, key)
            if owner_key != key and self.engine.spatial is not None:
                doc = self.engine.spatial.document(db, owner_key)
                pos = db.execute("SELECT state FROM world_positions WHERE identity=?", (key,)).fetchone()
                if doc and doc.get("places") and not pos:
                    first_place = doc["places"][0]["id"]
                    db.execute(
                        "INSERT INTO world_positions VALUES(?,?,?)",
                        (key, 1, encode({"place_id": first_place, "journey": None, "plan": None})),
                    )
        return {"world_id": clean_id, "shared": True, "label": clean_label}

    def invite_guest(
        self,
        host_scope: dict,
        *,
        guest_scope: dict | None = None,
        guest_name: str = "",
        guest_model_id: str = "builtin",
        guest_texture: int = 0,
        spot: str = "garden_bench",
        activity: str = "",
        duration_seconds: int = 1800,
    ) -> dict:
        host_key = identity(host_scope)
        guest_key = identity(guest_scope) if guest_scope else ("peer:" + hashlib.sha256(guest_name.encode()).hexdigest()[:12])
        if guest_key == host_key:
            raise ValueError("不能邀请自己做客")
        if spot not in {"garden_bench", "tea_table", "pond_side"}:
            spot = "garden_bench"
        clean_name = str(guest_name or "同伴角色").strip()[:40]
        if not clean_name:
            raise ValueError("请提供来访角色名称")
        duration = max(300, min(7200, int(duration_seconds or 1800)))
        now = self.engine.clock()
        summary = str(activity or f"{clean_name}由管理员布置为小屋访客，未记录自主赴约或交谈").strip()[:120]
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            wid = self.world_id_for(db, host_key)
            if not guest_scope:
                peer_row = db.execute(
                    "SELECT identity FROM world_space_bindings WHERE world_id=? AND identity<>? AND character_name=? LIMIT 1",
                    (wid, host_key, clean_name),
                ).fetchone()
                if peer_row and peer_row[0]:
                    guest_key = str(peer_row[0])
            resolved_model = str(guest_model_id or "builtin")
            resolved_tex = int(guest_texture or 0)
            if resolved_model == "builtin" and callable(self.avatar_resolver) and not guest_key.startswith("peer:"):
                try:
                    sel = self.avatar_resolver(db, guest_key) or {}
                    if sel.get("model_id") and sel["model_id"] != "builtin":
                        resolved_model = str(sel["model_id"])
                        resolved_tex = int(sel.get("texture_index") or 0)
                except Exception:
                    pass
            db.execute(
                "INSERT INTO world_space_guests VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(host_identity) DO UPDATE SET guest_identity=excluded.guest_identity,"
                "guest_name=excluded.guest_name,guest_model_id=excluded.guest_model_id,"
                "guest_texture=excluded.guest_texture,spot=excluded.spot,activity=excluded.activity,"
                "started_at=excluded.started_at,ends_at=excluded.ends_at",
                (host_key, guest_key, clean_name, resolved_model, resolved_tex, spot, summary, now, now + duration),
            )
            eid = "enc_" + uuid.uuid4().hex[:16]
            db.execute(
                "INSERT INTO world_space_encounters VALUES(?,?,?,?,?,?,?)",
                (eid, wid, "cabin_visit", "小屋做客", encode([host_key, guest_key]), summary, now),
            )
            if self.engine.keepsakes is not None:
                self.engine.keepsakes.record_keyframe(
                    db, host_scope, "peer_visit", summary, {"guest_name": clean_name, "spot": spot}, now
                )
        return {
            "origin": "admin",
            "guest_name": clean_name,
            "spot": spot,
            "activity": summary,
            "ends_at": now + duration,
        }

    def settle(self, db, scope: dict, now: float, actor: dict | None = None, character_name: str = "") -> dict:
        key = identity(scope)
        if db.execute("SELECT 1 FROM world_space_guests WHERE ends_at<=? LIMIT 1", (now,)).fetchone():
            db.execute("DELETE FROM world_space_guests WHERE ends_at<=?", (now,))
        row = db.execute("SELECT world_id,label,character_name FROM world_space_bindings WHERE identity=?", (key,)).fetchone()
        if row and character_name and row["character_name"] != character_name:
            db.execute("UPDATE world_space_bindings SET character_name=? WHERE identity=?", (character_name[:60], key))
        if not row:
            return self.snapshot(db, scope, now)

        wid = str(row["world_id"])
        place_id = (actor or {}).get("place_id")
        if place_id and (actor or {}).get("phase") == "located":
            # Check if this place is a private home of any character
            private_places = set()
            for s_row in db.execute("SELECT state FROM world_scene_state").fetchall():
                try:
                    st = json.loads(s_row[0])
                    for r in st.get("rooms", {}).values():
                        private_places.add(r.get("place_id"))
                except Exception:
                    continue
            if place_id not in private_places:
                peers = db.execute(
                    "SELECT identity,character_name FROM world_space_bindings WHERE world_id=? AND identity<>?",
                    (wid, key),
                ).fetchall()
                for peer in peers:
                    pos_row = db.execute("SELECT state FROM world_positions WHERE identity=?", (peer["identity"],)).fetchone()
                    if not pos_row:
                        continue
                    peer_pos = json.loads(pos_row[0])
                    if peer_pos.get("place_id") == place_id and not peer_pos.get("journey"):
                        recent = db.execute(
                            "SELECT 1 FROM world_space_encounters WHERE world_id=? AND place_id=? AND occurred>?",
                            (wid, place_id, now - 7200),
                        ).fetchone()
                        if not recent:
                            my_name = character_name or row["character_name"] or "角色"
                            peer_name = peer["character_name"] or "同伴"
                            place_name = str((actor or {}).get("place_name") or "街角")
                            summary = f"{my_name}与{peer_name}在「{place_name}」同时位于这里；尚无交谈回执。"
                            db.execute(
                                "INSERT INTO world_space_encounters VALUES(?,?,?,?,?,?,?)",
                                (
                                    "enc_" + uuid.uuid4().hex[:16],
                                    wid,
                                    place_id,
                                    place_name,
                                    encode(sorted([key, peer["identity"]])),
                                    summary,
                                    now,
                                ),
                            )
        return self.snapshot(db, scope, now)

    def snapshot(self, db, scope: dict, now: float) -> dict:
        key = identity(scope)
        row = db.execute("SELECT world_id,label,character_name FROM world_space_bindings WHERE identity=?", (key,)).fetchone()
        wid = str(row["world_id"]) if row else default_world_id(key)
        shared = bool(row)
        members = []
        if shared:
            for m in db.execute(
                "SELECT identity,character_name,updated FROM world_space_bindings WHERE world_id=? ORDER BY updated ASC",
                (wid,),
            ).fetchall():
                pos_row = db.execute("SELECT state FROM world_positions WHERE identity=?", (m["identity"],)).fetchone()
                pos = json.loads(pos_row[0]) if pos_row else {}
                members.append(
                    {
                        "name": m["character_name"] or m["identity"],
                        "is_self": m["identity"] == key,
                        "place_id": pos.get("place_id"),
                        "travelling": bool(pos.get("journey")),
                    }
                )
        guest_row = db.execute(
            "SELECT guest_identity,guest_name,guest_model_id,guest_texture,spot,activity,started_at,ends_at "
            "FROM world_space_guests WHERE host_identity=? AND ends_at>?",
            (key, now),
        ).fetchone()
        active_guest = None
        if guest_row:
            g_model = str(guest_row["guest_model_id"] or "builtin")
            g_tex = int(guest_row["guest_texture"] or 0)
            g_ident = str(guest_row["guest_identity"] or "")
            if g_model == "builtin" and callable(self.avatar_resolver) and g_ident and not g_ident.startswith("peer:"):
                try:
                    sel = self.avatar_resolver(db, g_ident) or {}
                    if sel.get("model_id") and sel["model_id"] != "builtin":
                        g_model = str(sel["model_id"])
                        g_tex = int(sel.get("texture_index") or 0)
                except Exception:
                    pass
            active_guest = {
                "identity": g_ident,
                "name": guest_row["guest_name"],
                "model_id": g_model,
                "texture_index": g_tex,
                "spot": guest_row["spot"],
                "activity": guest_row["activity"],
                "started_at": guest_row["started_at"],
                "ends_at": guest_row["ends_at"],
            }
        if active_guest is not None:
            active_guest["origin"] = "admin"
        if active_guest is None and getattr(self.engine, "causal", None) is not None:
            active_guest = self.engine.causal.guest_projection(db, scope, now)
        encounters = [
            {
                "id": r["id"],
                "place_id": r["place_id"],
                "place_name": r["place_name"],
                "summary": r["summary"],
                "occurred_at": r["occurred"],
            }
            for r in db.execute(
                "SELECT id,place_id,place_name,summary,occurred FROM world_space_encounters "
                "WHERE world_id=? ORDER BY occurred DESC LIMIT 8",
                (wid,),
            ).fetchall()
        ]
        return {
            "world_id": wid,
            "label": str(row["label"]) if row and row["label"] else ("共享世界 · " + wid if shared else "独立角色世界"),
            "shared": shared,
            "members": copy.deepcopy(members),
            "active_guest": active_guest,
            "recent_encounters": encounters,
        }

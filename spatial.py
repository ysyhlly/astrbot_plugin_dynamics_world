"""Persistent fictional geography and clock-driven journeys, owned by World.

Uses the narrative transaction so a rejected/stale model response cannot move
the avatar. No chat evidence is copied into the shared map or its audit log.
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import json
import math
import uuid


def identity(scope):
    values = [
        scope.get("persona_id"),
        scope.get("instance_id") or scope.get("persona_id"),
    ]
    if not all(isinstance(v, str) and v and len(v) <= 300 for v in values):
        raise ValueError("地图需要明确的角色与实例")
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


MAX_MAP_VERSIONS = 5


def _map_content_digest(doc: dict) -> str:
    """Stable content hash for map version deduplication (excludes revision/world_id)."""
    payload = {
        k: v
        for k, v in doc.items()
        if k not in {"revision", "world_id", "_content_sha256", "image_ref_sha256", "graph_ref_sha256"}
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compact_map_version_doc(doc: dict, old_doc: dict | None, content_sha256: str) -> dict:
    """Avoid duplicating unchanged multi-MB image/graph blobs in world_map_versions."""
    compact = dict(doc)
    compact["_content_sha256"] = content_sha256
    if isinstance(old_doc, dict):
        img = doc.get("image")
        if isinstance(img, str) and img and img == old_doc.get("image"):
            compact["image"] = ""
            compact["image_ref_sha256"] = hashlib.sha256(img.encode("utf-8")).hexdigest()
        graph = doc.get("graph")
        if graph is not None and graph == old_doc.get("graph"):
            compact.pop("graph", None)
            compact["graph_ref_sha256"] = hashlib.sha256(
                encode(graph).encode("utf-8")
            ).hexdigest()
    return compact


def place_id(name):
    return "place_" + hashlib.sha256(name.strip().encode()).hexdigest()[:16]


def route(document, start, end):
    """Route on generated land-cell adjacency, never draw a shortcut over water."""
    points, edges = document["graph"]["points"], document["graph"]["edges"]
    start, end = int(start), int(end)
    pending, costs, previous = [(0, start)], {start: 0.0}, {}
    while pending:
        cost, cell = heapq.heappop(pending)
        if cost != costs[cell]:
            continue
        if cell == end:
            chain = [cell]
            while chain[-1] != start:
                chain.append(previous[chain[-1]])
            return [points[i] for i in reversed(chain)], cost
        for target in edges[cell]:
            step = math.dist(points[cell], points[target])
            total = cost + step
            if total < costs.get(target, float("inf")):
                costs[target], previous[target] = total, cell
                heapq.heappush(pending, (total, target))
    raise ValueError("两个地点之间没有可通行的陆路")


class SpatialState:
    def __init__(self, engine):
        self.engine = engine
        self._cache = {}
        with engine._db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS world_maps(identity TEXT PRIMARY KEY,revision INTEGER NOT NULL,document TEXT NOT NULL,created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS world_map_versions(identity TEXT NOT NULL,revision INTEGER NOT NULL,document TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(identity,revision));
              CREATE INDEX IF NOT EXISTS world_map_versions_created ON world_map_versions(created);
              CREATE TABLE IF NOT EXISTS world_positions(identity TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS world_map_events(id TEXT PRIMARY KEY,identity TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,occurred REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS world_map_events_scope ON world_map_events(identity,occurred);
              CREATE INDEX IF NOT EXISTS world_map_events_occurred ON world_map_events(occurred);
              CREATE TABLE IF NOT EXISTS world_mode_saves(identity TEXT NOT NULL,mode TEXT NOT NULL,document TEXT NOT NULL,position TEXT NOT NULL,suspended REAL NOT NULL,PRIMARY KEY(identity,mode));
            """)

    def document(self, db, key):
        ws = getattr(self.engine, "world_spaces", None)
        lookup_key = ws.map_owner_key(db, key) if ws is not None else key
        row = db.execute(
            "SELECT revision FROM world_maps WHERE identity=?", (lookup_key,)
        ).fetchone()
        if not row:
            return None
        cached = self._cache.get(lookup_key)
        if cached is None or cached[0] != row["revision"]:
            cached = (
                row["revision"],
                json.loads(
                    db.execute(
                        "SELECT document FROM world_maps WHERE identity=?",
                        (lookup_key,),
                    ).fetchone()[0]
                ),
            )
            self._cache[lookup_key] = cached
        return cached[1]

    def _position(self, db, key):
        row = db.execute(
            "SELECT revision,state FROM world_positions WHERE identity=?", (key,)
        ).fetchone()
        return (
            (row["revision"], json.loads(row["state"]))
            if row
            else (0, {"place_id": None, "journey": None, "plan": None})
        )

    def _save(self, db, key, state, revision):
        db.execute(
            "INSERT INTO world_positions VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,state=excluded.state",
            (key, revision, encode(state)),
        )

    def _audit(self, db, key, kind, payload, now):
        db.execute(
            "INSERT INTO world_map_events VALUES(?,?,?,?,?)",
            (uuid.uuid4().hex, key, kind, encode(payload), now),
        )

    def record_map_version(
        self,
        db,
        map_owner: str,
        doc: dict,
        now: float,
        *,
        old_doc: dict | None = None,
        max_versions: int = MAX_MAP_VERSIONS,
    ) -> bool:
        """Archive a deduplicated, blob-compacted map version and enforce retention cap."""
        digest = _map_content_digest(doc)
        prev = db.execute(
            "SELECT revision, document FROM world_map_versions "
            "WHERE identity=? ORDER BY revision DESC LIMIT 1",
            (map_owner,),
        ).fetchone()
        if prev is not None:
            try:
                prev_doc = json.loads(prev["document"])
            except Exception:
                prev_doc = None
            if isinstance(prev_doc, dict):
                prev_digest = prev_doc.get("_content_sha256")
                if not isinstance(prev_digest, str) or not prev_digest:
                    prev_digest = _map_content_digest(prev_doc)
                if prev_digest == digest:
                    return False
        stored_doc = _compact_map_version_doc(doc, old_doc, digest)
        db.execute(
            "INSERT INTO world_map_versions VALUES(?,?,?,?)",
            (map_owner, int(doc["revision"]), encode(stored_doc), now),
        )
        keep = max(1, int(max_versions))
        db.execute(
            "DELETE FROM world_map_versions WHERE identity=? AND revision NOT IN ("
            "SELECT revision FROM world_map_versions WHERE identity=? ORDER BY revision DESC LIMIT ?)",
            (map_owner, map_owner, keep),
        )
        return True

    def install(
        self, scope, document, expected_revision=0, *, audit_kind="map.generated"
    ):
        key, now = identity(scope), self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self.document(db, key)
            if old and old.get("map_type", "virtual") != document.get(
                "map_type", "virtual"
            ):
                raise ValueError("请先通过地图模式切换，避免覆盖另一种地图")
            revision = old["revision"] if old else 0
            if type(expected_revision) is not int or revision != expected_revision:
                raise ValueError("地图已更新，请刷新后重试")
            if self.engine.scenes is not None:
                self.engine.scenes.guard_map(db, scope, document)
            position_revision, position = self._position(db, key)
            if position.get("journey"):
                raise ValueError("角色正在移动，请先取消移动再重新生成地图")
            ws = getattr(self.engine, "world_spaces", None)
            map_owner = ws.map_owner_key(db, key) if ws is not None else key
            doc = copy.deepcopy(document)
            doc["revision"] = revision + 1
            doc["world_id"] = hashlib.sha256(map_owner.encode()).hexdigest()[:24]
            db.execute(
                "INSERT INTO world_maps VALUES(?,?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,document=excluded.document,created=excluded.created",
                (map_owner, revision + 1, encode(doc), now),
            )
            self.record_map_version(db, map_owner, doc, now, old_doc=old)
            if position.get("place_id") not in {p["id"] for p in doc["places"]}:
                position["place_id"] = None
            position.update(journey=None, plan=None)
            if self.engine._paused(db, dict(scope, umo="", platform="")):
                position["paused_at"] = now
            self._save(db, key, position, position_revision + 1)
            self._audit(
                db,
                key,
                audit_kind,
                {"revision": revision + 1, "seed": doc["seed"]},
                now,
            )
            # Invalidate any in-flight life response even if it has no movement.
            db.execute("UPDATE lives SET revision=revision+1 WHERE identity=?", (key,))
        self._cache.pop(map_owner, None)
        return {"revision": revision + 1, "places": len(document["places"])}

    def settle(self, db, scope, now):
        key = identity(scope)
        revision, state = self._position(db, key)
        journey = state.get("journey")
        if (
            not journey
            or state.get("paused_at") is not None
            or journey["arrives_at"] > now
        ):
            return
        doc = self.document(db, key)
        if not doc:
            return
        target = next(p for p in doc["places"] if p["id"] == journey["destination_id"])
        state.update(place_id=target["id"], journey=None, plan=None)
        self._save(db, key, state, revision + 1)
        self._audit(
            db,
            key,
            "movement.arrived",
            {"place_id": target["id"], "journey_id": journey["id"]},
            journey["arrives_at"],
        )
        row = db.execute("SELECT state FROM lives WHERE identity=?", (key,)).fetchone()
        if row:
            life = json.loads(row["state"])
            current_revision = db.execute(
                "SELECT revision FROM lives WHERE identity=?", (key,)
            ).fetchone()[0]
            life.update(
                activity_code="unknown",
                activity="抵达" + target["name"],
                availability="available",
                valid_from=journey["arrives_at"],
                valid_until=now + 300,
                source_ids=[],
                activity_revision=current_revision + 1,
            )
            db.execute(
                "UPDATE lives SET state=?,revision=revision+1,updated=? WHERE identity=?",
                (encode(life), now, key),
            )

    def snapshot(self, db, scope, now):
        key = identity(scope)
        doc = self.document(db, key)
        if not doc:
            return {"available": False, "revision": 0, "map_revision": 0}
        revision, state = self._position(db, key)
        by_id = {p["id"]: p for p in doc["places"]}
        place = by_id.get(state.get("place_id"))
        journey = copy.deepcopy(state.get("journey"))
        coords, progress = ([place["x"], place["y"]] if place else None), 0.0
        if journey:
            effective_now = (
                state.get("paused_at") if state.get("paused_at") is not None else now
            )
            progress = max(
                0,
                min(
                    1,
                    (effective_now - journey["departed_at"])
                    / (journey["arrives_at"] - journey["departed_at"]),
                ),
            )
            path = journey["path"]
            lengths = [math.dist(a, b) for a, b in zip(path, path[1:])]
            remaining = sum(lengths) * progress
            coords = path[-1]
            for a, b, length in zip(path, path[1:], lengths):
                if remaining <= length and length > 0:
                    ratio = remaining / length
                    coords = [
                        a[0] + (b[0] - a[0]) * ratio,
                        a[1] + (b[1] - a[1]) * ratio,
                    ]
                    break
                remaining -= length
            journey["destination_name"] = by_id[journey["destination_id"]]["name"]
        return {
            "available": True,
            "revision": revision,
            "map_revision": doc["revision"],
            "map_type": doc.get("map_type", "virtual"),
            "place_id": state.get("place_id"),
            "place_name": place["name"] if place else None,
            "position": coords,
            "phase": "travelling" if journey else "located" if place else "unknown",
            "journey": journey,
            "progress": progress,
            "plan": state.get("plan"),
            "paused": state.get("paused_at") is not None,
            "fact_kind": "fiction",
            "places": [{k: p[k] for k in ("id", "name")} for p in doc["places"]],
        }

    def validate(self, movement, request):
        if request["scope"]["umo"]:
            raise ValueError("聊天事件不能直接改写全局位置")
        if not isinstance(movement, dict) or set(movement) - {
            "kind",
            "target_id",
            "not_before",
        }:
            raise ValueError("未知移动字段")
        kind, target = movement.get("kind"), movement.get("target_id")
        snapshot = request["snapshot"].get("spatial", {})
        if kind not in {"locate", "plan", "depart"} or not snapshot.get("available"):
            raise ValueError("地图未就绪或移动类型无效")
        if target not in {p["id"] for p in snapshot["places"]}:
            raise ValueError("目的地不存在")
        if kind == "locate" and snapshot["phase"] != "unknown":
            raise ValueError("已经定位的角色不能瞬移")
        if kind == "depart" and snapshot["phase"] != "located":
            raise ValueError("先确认当前位置，再出发")
        start = movement.get("not_before", request["now"])
        if (
            type(start) not in (int, float)
            or not math.isfinite(start)
            or not request["now"] <= start <= request["now"] + 86400
        ):
            raise ValueError("出发计划必须在未来一天以内")
        return {
            "kind": kind,
            "target_id": target,
            "not_before": start,
            "map_revision": snapshot["map_revision"],
            "position_revision": snapshot["revision"],
        }

    def commit(self, db, scope, action, now, *, admin=False, scene_owned=False):
        key = identity(scope)
        doc = self.document(db, key)
        revision, state = self._position(db, key)
        if (
            not doc
            or action["map_revision"] != doc["revision"]
            or action["position_revision"] != revision
        ):
            raise ValueError("地图或位置已变化，本次操作失效")
        if self.engine.scenes is not None and not scene_owned:
            self.engine.scenes.guard_movement(db, scope, action, now, admin)
        if state.get("paused_at") is not None:
            raise ValueError("全局生活已暂停，请先恢复")
        kind = action["kind"]
        was_travelling = bool(state.get("journey"))
        by_id = {p["id"]: p for p in doc["places"]}
        target = by_id.get(action.get("target_id"))
        if kind not in {"cancel"} and target is None:
            raise ValueError("目的地不存在")
        if kind == "locate":
            if not admin and state.get("place_id"):
                raise ValueError("禁止瞬移")
            state.update(place_id=target["id"], journey=None, plan=None)
        elif kind == "plan":
            start = action.get("not_before", now)
            if (
                type(start) not in (int, float)
                or not math.isfinite(start)
                or not now <= start <= now + 86400
            ):
                raise ValueError("计划时间需在未来一天以内")
            state["plan"] = {
                "destination_id": target["id"],
                "destination_name": target["name"],
                "not_before": start,
                "fact_kind": "plan",
            }
        elif kind == "depart":
            if not state.get("place_id") or state.get("journey"):
                raise ValueError("角色未定位或已经在路上")
            if target["id"] == state["place_id"]:
                raise ValueError("角色已在该地点")
            start = by_id[state["place_id"]]
            if doc.get("map_type") == "real":
                from .geography import real_route

                path, duration = real_route(doc, start, target)
            else:
                path, distance = route(doc, start["cell"], target["cell"])
                if len(path) < 2:
                    path = [[start["x"], start["y"]], [target["x"], target["y"]]]
                    distance = math.dist(*path)
                duration = max(60, distance * doc["seconds_per_unit"])
            state["journey"] = {
                "id": uuid.uuid4().hex,
                "origin_id": start["id"],
                "destination_id": target["id"],
                "departed_at": now,
                "arrives_at": now + duration,
                "path": path,
                "route_kind": "straight_line_estimate"
                if doc.get("map_type") == "real"
                else "land_path",
            }
            state["plan"] = None
        elif kind == "cancel" and admin:
            if not state.get("journey") and not state.get("plan"):
                raise ValueError("当前没有需要撤销的行程或计划")
            # Cancellation returns the marker to the last confirmed location,
            # explicitly as an admin correction, never an inferred arrival.
            state.update(journey=None, plan=None)
        else:
            raise ValueError("未知地图操作")
        self._save(db, key, state, revision + 1)
        self._audit(
            db,
            key,
            "admin." + kind if admin else "life." + kind,
            {"target_id": action.get("target_id"), "fact_kind": "fiction"},
            now,
        )
        row = db.execute(
            "SELECT state,revision FROM lives WHERE identity=?", (key,)
        ).fetchone()
        if row:
            life = json.loads(row["state"])
            if kind in {"locate", "depart"} or kind == "cancel" and was_travelling:
                life["activity_revision"] = row["revision"] + 1
            if kind == "depart":
                life.update(
                    activity_code="walking",
                    activity="前往" + target["name"],
                    availability="busy",
                    valid_from=now,
                    valid_until=state["journey"]["arrives_at"],
                    source_ids=[],
                )
            elif kind == "cancel" and was_travelling:
                life.update(
                    activity_code="unknown",
                    activity="位置已纠正",
                    availability="unknown",
                    source_ids=[],
                )
            db.execute(
                "UPDATE lives SET state=?,revision=revision+1,updated=? WHERE identity=?",
                (encode(life), now, key),
            )

    def admin_action(self, scope, action):
        now = self.engine.clock()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self.engine._ensure(db, scope, now)
            self.settle(db, scope, now)
            self.commit(db, scope, action, now, admin=True)
            return self.snapshot(db, scope, now)

    def save_place(self, scope, body):
        name = body.get("name")
        x, y = body.get("x"), body.get("y")
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("地点名称需为 1–60 字")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)):
            raise ValueError("无效坐标")
        with self.engine._db() as db:
            existing = self.document(db, identity(scope))
            if not existing:
                raise ValueError("请先生成地图")
            document = copy.deepcopy(existing)
        if document.get("map_type") == "real":
            from .geography import save_real_place

            return save_real_place(self, scope, document, body)
        if not 0 <= x <= document["width"] or not 0 <= y <= document["height"]:
            raise ValueError("坐标超出地图")
        cell = min(
            range(len(document["graph"]["points"])),
            key=lambda i: math.dist([x, y], document["graph"]["points"][i]),
        )
        if math.dist([x, y], document["graph"]["points"][cell]) > 50:
            raise ValueError("请选择可通行的陆地")
        old_id = body.get("place_id")
        places = document["places"]
        target = (
            next((p for p in places if p["id"] == old_id), None) if old_id else None
        )
        if old_id and target is None:
            raise ValueError("地点已不存在")
        if any(p["name"] == name.strip() and p is not target for p in places):
            raise ValueError("已有同名地点")
        if target is None:
            if len(places) >= 32:
                raise ValueError("地点数量已达 32 个")
            target = {"id": place_id(name)}
            places.append(target)
        target.update(
            name=name.strip(),
            x=document["graph"]["points"][cell][0],
            y=document["graph"]["points"][cell][1],
            cell=cell,
            origin="admin",
        )
        document["roads"] = []
        for destination in places[1:]:
            path, distance = route(document, places[0]["cell"], destination["cell"])
            document["roads"].append(
                {
                    "from": places[0]["id"],
                    "to": destination["id"],
                    "path": path,
                    "distance": distance,
                }
            )
        return self.install(
            scope, document, body.get("expected_revision"), audit_kind="map.edited"
        )

    def pause(self, db, scope, paused, now):
        key = identity(scope)
        revision, state = self._position(db, key)
        if paused and state.get("paused_at") is None:
            state["paused_at"] = now
        elif not paused and state.get("paused_at") is not None:
            if state.get("journey"):
                elapsed = max(0, now - state["paused_at"])
                state["journey"]["departed_at"] += elapsed
                state["journey"]["arrives_at"] += elapsed
            state.pop("paused_at", None)
        else:
            return
        self._save(db, key, state, revision + 1)
        if self.engine.scenes is not None:
            self.engine.scenes.pause(db, scope, paused, now)

    def public_map(self, scope, known_revision=None):
        with self.engine._db() as db:
            doc = self.document(db, identity(scope))
            if not doc:
                return None
            return (
                {"revision": doc["revision"], "unchanged": True}
                if known_revision == doc["revision"]
                else {k: copy.deepcopy(v) for k, v in doc.items() if k != "graph"}
            )

    @staticmethod
    def activity(snapshot, activity):
        if snapshot.get("journey"):
            return "正在前往" + snapshot["journey"]["destination_name"]
        if snapshot.get("place_name"):
            if activity == "抵达" + snapshot["place_name"]:
                return activity
            return "在" + snapshot["place_name"] + "：" + activity
        return activity

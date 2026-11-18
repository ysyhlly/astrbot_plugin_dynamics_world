"""Optional WGS84 maps. Avatars remain fictional, never device GPS tracks."""

import copy
import hashlib
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def coordinate(value, limit, name):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not -limit <= value <= limit
    ):
        raise ValueError(name + "超出范围")
    return float(value)


def timezone(value):
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("无效时区")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("未知时区") from None
    return value


def distance_km(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def real_route(document, start, end):
    a, b = [start["x"], start["y"]], [end["x"], end["y"]]
    if abs(a[0] - b[0]) > 180:
        raise ValueError("本版不支持跨日期变更线行程")
    distance = distance_km(a, b)
    duration = max(60, distance / document.get("walking_kmh", 4.5) * 3600)
    if duration > 86400:
        raise ValueError("请选择更近的地点，本版只支持一天以内的示意步行")
    return [a, b], duration


def switch_mode(spatial, scope, mode, expected_revision, document=None):
    from .spatial import encode, identity

    if mode not in {"virtual", "real"}:
        raise ValueError("未知地图模式")
    key, now = identity(scope), spatial.engine.clock()
    with spatial.engine._db() as db:
        db.execute("BEGIN IMMEDIATE")
        old = spatial.document(db, key)
        old_revision = old["revision"] if old else 0
        if type(expected_revision) is not int or expected_revision != old_revision:
            raise ValueError("地图已变化，请刷新")
        spatial.settle(db, scope, now)
        if spatial.engine.scenes is not None:
            spatial.engine.scenes.settle(db, scope, now)
        position_revision, position = spatial._position(db, key)
        old_mode = old.get("map_type", "virtual") if old else None
        if old_mode == mode and document is None:
            return {"mode": mode, "revision": old_revision}
        if old:
            if spatial.engine.scenes is not None:
                spatial.engine.scenes.pause(db, scope, True, now, old_mode)
            db.execute(
                "INSERT INTO world_mode_saves VALUES(?,?,?,?,?) ON CONFLICT(identity,mode) DO UPDATE SET document=excluded.document,position=excluded.position,suspended=excluded.suspended",
                (key, old_mode, encode(old), encode(position), now),
            )
        if document is None:
            saved = db.execute(
                "SELECT document,position,suspended FROM world_mode_saves WHERE identity=? AND mode=?",
                (key, mode),
            ).fetchone()
            if saved is None:
                raise ValueError(
                    "尚未配置现实地图，请先选择城市或填写坐标"
                    if mode == "real"
                    else "尚无虚拟地图，请先生成"
                )
            import json

            document = json.loads(saved["document"])
            position = json.loads(saved["position"])
            journey = position.get("journey")
            if journey:
                paused = position.get("paused_at")
                elapsed = max(
                    0, now - (paused if paused is not None else saved["suspended"])
                )
                journey["departed_at"] += elapsed
                journey["arrives_at"] += elapsed
        else:
            position = {"place_id": None, "journey": None, "plan": None}
        position.pop("paused_at", None)
        if spatial.engine._paused(db, dict(scope, umo="", platform="")):
            position["paused_at"] = now
        doc = copy.deepcopy(document)
        doc.update(
            revision=old_revision + 1,
            world_id=hashlib.sha256(key.encode()).hexdigest()[:24],
            map_type=mode,
        )
        db.execute(
            "INSERT INTO world_maps VALUES(?,?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,document=excluded.document,created=excluded.created",
            (key, doc["revision"], encode(doc), now),
        )
        db.execute(
            "INSERT INTO world_map_versions VALUES(?,?,?,?)",
            (key, doc["revision"], encode(doc), now),
        )
        spatial._save(db, key, position, position_revision + 1)
        if spatial.engine.scenes is not None:
            spatial.engine.scenes.pause(
                db,
                scope,
                spatial.engine._paused(db, dict(scope, umo="", platform="")),
                now,
                mode,
            )
        spatial._audit(db, key, "map.mode_changed", {"mode": mode}, now)
        row = db.execute(
            "SELECT state,revision FROM lives WHERE identity=?", (key,)
        ).fetchone()
        if row:
            import json

            life = json.loads(row["state"])
            life.update(
                activity_code="unknown",
                activity="地图模式已切换，等待新的生活安排",
                availability="unknown",
                activity_revision=row["revision"] + 1,
                source_ids=[],
                summary="",
                subjective_state="",
            )
            db.execute(
                "UPDATE lives SET state=?,revision=revision+1 WHERE identity=?",
                (encode(life), key),
            )
    spatial._cache.pop(key, None)
    return {"mode": mode, "revision": doc["revision"]}


def configure_real(spatial, scope, body):
    from .spatial import identity, place_id

    lat = coordinate(body.get("latitude"), 85, "纬度")
    lon = coordinate(body.get("longitude"), 180, "经度")
    label = body.get("name", "")
    if not isinstance(label, str) or not label.strip() or len(label) > 60:
        raise ValueError("请填写地点名称")
    zone = timezone(body.get("timezone", "Asia/Shanghai"))
    speed = body.get("walking_kmh", 4.5)
    if type(speed) not in (int, float) or not 1 <= speed <= 15:
        raise ValueError("步行速度需在 1–15 km/h")
    with spatial.engine._db() as db:
        current = spatial.document(db, identity(scope))
        saved = db.execute(
            "SELECT 1 FROM world_mode_saves WHERE identity=? AND mode='real'",
            (identity(scope),),
        ).fetchone()
    if saved and (not current or current.get("map_type") != "real"):
        raise ValueError("已有保存的现实地图，请先切换到现实模式，再修改地图中心")
    if current and current.get("map_type") == "real":
        doc = copy.deepcopy(current)
        doc.update(center=[lon, lat], timezone=zone, walking_kmh=speed)
        return spatial.install(
            scope, doc, body.get("expected_revision"), audit_kind="map.real_configured"
        )
    doc = {
        "schema_version": 1,
        "map_type": "real",
        "generator": "OpenStreetMap",
        "seed": "real-world",
        "center": [lon, lat],
        "timezone": zone,
        "walking_kmh": speed,
        "width": 360,
        "height": 170,
        "seconds_per_unit": 1,
        "places": [
            {
                "id": place_id(label),
                "name": label.strip(),
                "x": lon,
                "y": lat,
                "cell": 0,
                "origin": "admin_real_location",
            }
        ],
        "roads": [],
        "route_kind": "straight_line_estimate",
    }
    return switch_mode(spatial, scope, "real", body.get("expected_revision"), doc)


def save_real_place(spatial, scope, document, body):
    from .spatial import place_id

    name = body.get("name", "")
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise ValueError("地点名称需为 1–60 字")
    lon = coordinate(body.get("x"), 180, "经度")
    lat = coordinate(body.get("y"), 85, "纬度")
    places = document["places"]
    old_id = body.get("place_id")
    target = next((p for p in places if p["id"] == old_id), None) if old_id else None
    if old_id and target is None:
        raise ValueError("地点已不存在")
    if any(p["name"] == name.strip() and p is not target for p in places):
        raise ValueError("已有同名地点")
    if target is None:
        if len(places) >= 32:
            raise ValueError("地点数量已达 32 个")
        target = {"id": place_id(name), "cell": len(places)}
        places.append(target)
    target.update(name=name.strip(), x=lon, y=lat, origin="admin_real_location")
    return spatial.install(
        scope,
        document,
        body.get("expected_revision"),
        audit_kind="map.real_place_edited",
    )

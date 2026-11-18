"""Persistent visual designs, separate from simulation state and generated jobs."""

import hashlib
import json
import re

from .room_design import layout_text
from .spatial import encode
from .style_presets import catalog, selected


class VisualProfiles:
    def __init__(self, engine):
        self.engine = engine
        self.asset_root = engine.path.parent / "visual-assets"
        self._verified = {}
        with engine._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS world_visual_profiles(identity TEXT PRIMARY KEY, revision INTEGER NOT NULL, profile TEXT NOT NULL)"
            )

    def migrate_legacy_style(self):
        """Pin the old global art style only for worlds that already existed."""
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS world_visual_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
            )
            if db.execute(
                "SELECT 1 FROM world_visual_meta WHERE key='style_presets_v1'"
            ).fetchone():
                return
            keys = {
                r[0] for r in db.execute("SELECT identity FROM world_visual_profiles")
            }
            keys.update(
                r[0] for r in db.execute("SELECT identity FROM world_scene_state")
            )
            keys.update(
                owner + "|" + mode
                for owner, mode in db.execute(
                    "SELECT identity,mode FROM world_mode_saves"
                )
            )
            for owner, raw in db.execute("SELECT identity,document FROM world_maps"):
                doc = json.loads(raw)
                keys.add(owner + "|" + doc.get("map_type", "virtual"))
            for key in keys:
                row = db.execute(
                    "SELECT revision,profile FROM world_visual_profiles WHERE identity=?",
                    (key,),
                ).fetchone()
                value = (
                    json.loads(row[1])
                    if row
                    else {"styles": [], "rooms": {}, "items": {}}
                )
                if "style_preset" not in value:
                    value["style_preset"] = "manosaba"
                    db.execute(
                        "INSERT INTO world_visual_profiles VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,profile=excluded.profile",
                        (key, (row[0] if row else 0) + 1, encode(value)),
                    )
            db.execute("INSERT INTO world_visual_meta VALUES('style_presets_v1','1')")

    def assets(self):
        """Only explicitly installed, content-verified files; never fetch on chat."""
        try:
            manifest = self.asset_root / "index.json"
            if manifest.stat().st_size > 65536:
                return {}
            rows = json.loads(manifest.read_text("utf-8"))
            result = {}
            for key, row in list(rows.items())[:32]:
                if not re.fullmatch(r"[a-z0-9_-]{1,64}", key) or not isinstance(
                    row, dict
                ):
                    continue
                filename = row.get("file", "")
                if not isinstance(filename, str) or not re.fullmatch(
                    r"[a-zA-Z0-9_-]+\.(png|jpg|jpeg|webp)", filename
                ):
                    continue
                path = self.asset_root / filename
                if path.is_symlink() or not path.resolve().is_relative_to(
                    self.asset_root.resolve()
                ):
                    continue
                try:
                    stamp = path.stat()
                    if not 0 < stamp.st_size <= 16 * 1024 * 1024:
                        continue
                    check = (
                        str(path),
                        stamp.st_mtime_ns,
                        stamp.st_size,
                        row.get("sha256"),
                    )
                    if check not in self._verified:
                        if hashlib.sha256(path.read_bytes()).hexdigest() != row.get(
                            "sha256"
                        ):
                            continue
                        self._verified = {
                            **dict(list(self._verified.items())[-31:]),
                            check: True,
                        }
                except OSError:
                    continue
                if row.get("role") not in {"style", "layout"}:
                    continue
                result[key] = {
                    "asset_id": key,
                    "role": row["role"],
                    "reference": str(path),
                    "sha256": row["sha256"],
                    "label": str(row.get("label", key))[:100],
                    "source_url": str(row.get("source_url", ""))[:300],
                }
            return result
        except (OSError, ValueError, AttributeError, TypeError):
            return {}

    def load(self, db, scope):
        key = self.engine.scenes.key(db, scope)
        row = db.execute(
            "SELECT revision,profile FROM world_visual_profiles WHERE identity=?",
            (key,),
        ).fetchone()
        return (
            key,
            row[0] if row else 0,
            json.loads(row[1]) if row else {"styles": [], "rooms": {}, "items": {}},
        )

    def admin(self, db, scope):
        key, revision, profile = self.load(db, scope)
        profile["style_preset"] = selected(profile, self.engine.config)
        return {
            "revision": revision,
            "profile": profile,
            "presets": catalog(),
            "mode": key.rsplit("|", 1)[-1],
            "assets": [
                {k: v for k, v in row.items() if k != "reference"}
                for row in self.assets().values()
            ],
        }

    def configure(self, scope, body):
        def text(value, limit):
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                raise ValueError(f"视觉设定需为 1–{limit} 字")
            return value.strip()

        assets = self.assets()
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, revision, profile = self.load(db, scope)
            if (
                type(body.get("expected_revision")) is not int
                or body["expected_revision"] != revision
            ):
                raise ValueError("视觉设定已变化，请刷新")
            _, _, scene = self.engine.scenes.load(db, scope)
            if not scene and body.get("action") != "style":
                raise ValueError("请先初始化场景")
            action = body.get("action")
            target = body.get("target_id")
            if action == "style":
                ids = body.get("asset_ids")
                if (
                    not isinstance(ids, list)
                    or len(ids) > 2
                    or any(
                        not isinstance(i, str)
                        or assets.get(i, {}).get("role") != "style"
                        for i in ids
                    )
                ):
                    raise ValueError("请选择最多 2 张已安装的画风参考图")
                profile["styles"] = list(dict.fromkeys(ids))
                if "preset" in body:
                    if body["preset"] not in {"generic", "manosaba"}:
                        raise ValueError("未知世界预设")
                    profile["style_preset"] = body["preset"]
            elif action == "room":
                if target not in scene["rooms"]:
                    raise ValueError("房间不存在")
                asset = body.get("asset_id")
                if assets.get(asset, {}).get("role") != "layout":
                    raise ValueError("请选择已安装的布局参考图")
                profile["rooms"][target] = {
                    "asset_id": asset,
                    "layout": text(body.get("layout"), 600),
                }
            elif action == "item":
                if target not in scene["items"]:
                    raise ValueError("物品不存在")
                room = body.get("home_room_id")
                if room not in scene["rooms"]:
                    raise ValueError("默认摆放房间不存在")
                profile["items"][target] = {
                    "appearance": text(body.get("appearance"), 200),
                    "home_room_id": room,
                    "placement": text(body.get("placement"), 120),
                }
            elif action == "remove":
                if body.get("kind") not in {"rooms", "items"}:
                    raise ValueError("请选择房间或物品设定")
                profile[body["kind"]].pop(target, None)
            else:
                raise ValueError("未知视觉设定操作")
            db.execute(
                "INSERT INTO world_visual_profiles VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,profile=excluded.profile",
                (key, revision + 1, encode(profile)),
            )
            self.engine.scenes.audit(
                db,
                key,
                "admin.visual",
                self.engine.clock(),
                {"action": action, "target_id": target, "revision": revision + 1},
            )
        return {"saved": True, "revision": revision + 1}

    def project(self, db, scope, scene, spatial):
        _, revision, profile = self.load(db, scope)
        assets = self.assets()
        result = {
            "revision": revision,
            "style_preset": selected(profile, self.engine.config),
            "basis": "persistent_visual_design",
            "references": [],
            "items": [],
            "remove_from_layout": [],
        }
        missing = []

        def add(asset_id):
            if asset_id in assets:
                result["references"].append(
                    {k: v for k, v in assets[asset_id].items() if k != "source_url"}
                )
            else:
                missing.append(asset_id)

        # Layout first: providers commonly prioritize the first image.
        room_id = scene.get("room_id") if spatial.get("phase") == "located" else None
        room = profile["rooms"].get(room_id)
        if room:
            result["layout"] = room["layout"]
            add(room["asset_id"])
        arrangement = next(
            (d for d in scene.get("room_designs", []) if d["room_id"] == room_id), None
        )
        if arrangement:
            result["room_state"] = {
                "revision": arrangement["revision"],
                "lighting": arrangement.get("lighting_label"),
                "curtains": arrangement.get("curtains_label"),
                "changed": bool(arrangement["history"]),
            }
            if arrangement["history"] or not room:
                result["layout"] = layout_text(arrangement)
        for asset_id in profile["styles"]:
            add(asset_id)
        items = {i["id"]: i for i in scene.get("items", [])}
        for removed in scene.get("removed_items", []):
            if removed.get("room_id") == room_id:
                result["remove_from_layout"].append(removed["name"])
        for iid, spec in profile["items"].items():
            item = items.get(iid)
            if not item:
                continue
            if item.get("visible") or item.get("carried"):
                value = {
                    "name": item["name"],
                    "kind": item["kind"],
                    "appearance": spec["appearance"],
                }
                if item.get("carried"):
                    value["placement"] = (
                        "当前随身携带，不留在底图桌面原位，不画重复副本"
                    )
                elif item.get("placement"):
                    value["placement"] = (
                        item["placement"] + "；按已完成的实际摆放覆盖底图原位置。"
                    )
                elif item.get("room_id") == room_id == spec["home_room_id"]:
                    value["placement"] = spec["placement"]
                else:
                    value["placement"] = (
                        "已离开默认摆放位置，按当前所在位置绘制，不套用原房间位置"
                    )
                result["items"].append(value)
            elif room and spec["home_room_id"] == room_id:
                result["remove_from_layout"].append(item["name"])
        # Items added without an appearance profile still have actual positions.
        known = set(profile["items"])
        for iid, item in items.items():
            if iid not in known and item.get("visible") and item.get("placement"):
                result["items"].append(
                    {
                        "name": item["name"],
                        "kind": item["kind"],
                        "appearance": "沿用已有外观，不凭空补正文",
                        "placement": item["placement"],
                    }
                )
        if missing:
            result["missing_assets"] = missing
            # Do not silently make an unanchored picture if a configured file disappeared.
            result["generation_ready"] = False
        else:
            result["generation_ready"] = True
        return result

"""Cozy non-punitive garden flowerbed, vegetable patch and kitchen pantry cycle."""
from __future__ import annotations

import copy
import json
import uuid

from .spatial import encode, identity
from .vitality import cat_state_for, compute_vitality, season_for

ECOLOGY_KINDS = {"water_garden", "harvest_garden", "prepare_meal", "brew_tea", "eat_meal", "drink_tea"}
ECOLOGY_LABELS = {
    "eat_meal": "食用一份已做好的餐食",
    "drink_tea": "饮用一杯已泡好的茶",
    "water_garden": "给花圃与菜畦浇水",
    "harvest_garden": "采收院中成熟蔬果与花草",
    "prepare_meal": "用院中鲜蔬下厨做简餐",
    "brew_tea": "摘薄荷与洋甘菊煮一壶花草茶",
}
ECOLOGY_DURATIONS = {
    "eat_meal": 600,
    "drink_tea": 180,
    "water_garden": 120,
    "harvest_garden": 150,
    "prepare_meal": 420,
    "brew_tea": 180,
}

RECIPES = (
    ("奶油卷心菜浓汤", ("卷心菜",)),
    ("焦糖烤小南瓜配吐司", ("小南瓜",)),
    ("田园南瓜卷心菜温沙拉", ("小南瓜", "卷心菜")),
)
TEAS = (
    ("洋甘菊安神热茶", ("洋甘菊",)),
    ("鲜摘薄荷清茶", ("薄荷叶",)),
    ("甘菊薄荷晚安花茶", ("洋甘菊", "薄荷叶")),
)


def default_ecology(now: float) -> dict:
    return {
        "flowerbed": {
            "stage": "growing",
            "progress": 0.45,
            "watered_at": now - 3600,
            "species": ["洋甘菊", "薄荷", "薰衣草"],
            "bloom_count": 0,
        },
        "veg_patch": {
            "stage": "growing",
            "progress": 0.40,
            "watered_at": now - 3600,
            "crops": ["卷心菜", "小南瓜"],
            "harvest_count": 0,
        },
        "pantry": {
            "卷心菜": 1,
            "小南瓜": 1,
            "洋甘菊": 2,
            "薄荷叶": 2,
        },
        "recent_meals": [],
        "prepared": [],
        "consumed": [],
        "last_settled_at": now,
        "last_auto_care_at": 0.0,
    }


def _stage_for(progress: float, final_name: str) -> str:
    if progress >= 0.85:
        return final_name
    if progress >= 0.35:
        return "growing"
    return "seedling"


def _advance_plot(plot: dict, elapsed_hours: float, raining: bool, now: float, final_name: str) -> bool:
    if elapsed_hours <= 0:
        return False
    watered_recently = (now - float(plot.get("watered_at", 0) or 0)) < 12 * 3600
    rate = 0.045  # ~22h full cycle naturally; faster with rain or watering
    if raining:
        rate += 0.035
        plot["watered_at"] = now
    elif watered_recently:
        rate += 0.025
    before = float(plot.get("progress", 0.0) or 0.0)
    after = min(1.0, round(before + elapsed_hours * rate, 4))
    new_stage = _stage_for(after, final_name)
    changed = abs(after - before) >= 0.01 or plot.get("stage") != new_stage
    plot["progress"] = after
    plot["stage"] = new_stage
    return changed


class EcologyService:
    """Manage zero-token garden growth, pantry harvests, vitality & cat state."""

    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_ecology(
                    identity TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    updated REAL NOT NULL
                );
                """
            )

    def load(self, db, scope) -> tuple[str, int, dict]:
        key = identity(scope)
        row = db.execute("SELECT revision,state FROM world_ecology WHERE identity=?", (key,)).fetchone()
        if row:
            return key, int(row[0]), json.loads(row[1])
        initial = default_ecology(self.engine.clock())
        return key, 0, initial

    def save(self, db, key: str, revision: int, state: dict, now: float, bump: bool = True) -> int:
        next_rev = revision + int(bump)
        db.execute(
            "INSERT INTO world_ecology VALUES(?,?,?,?) "
            "ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,state=excluded.state,updated=excluded.updated",
            (key, next_rev, encode(state), now),
        )
        return next_rev

    def settle(self, db, scope, env: dict | None, scene_state: dict | None, now: float) -> dict:
        key, rev, state = self.load(db, scope)
        if scene_state and scene_state.get("paused_at") is not None:
            return state
        last = float(state.get("last_settled_at", now) or now)
        elapsed_hours = max(0.0, min(48.0, (now - last) / 3600.0))
        if rev == 0:
            state["last_settled_at"] = now
            self.save(db, key, 0, state, now, bump=True)
            return state
        if elapsed_hours < 0.02:
            return state
        raining = bool(
            env
            and env.get("available")
            and not env.get("stale")
            and (env.get("current") or {}).get("effect") in {"rain"}
        )
        c1 = _advance_plot(state["flowerbed"], elapsed_hours, raining, now, "blooming")
        c2 = _advance_plot(state["veg_patch"], elapsed_hours, raining, now, "ripe")

        # Care is proposed through timed world actions; reads never auto-harvest.
        c3 = False
        if not (c1 or c2 or c3):
            return state
        state["last_settled_at"] = now
        self.save(db, key, rev, state, now, bump=True)
        return state

    def check_step(self, db, scope, scene_state: dict, step: dict, actor: dict, now: float) -> int:
        kind = step["kind"]
        if kind not in ECOLOGY_KINDS:
            raise ValueError("未知园艺或餐厨动作")
        home_places = {r["place_id"] for r in scene_state.get("rooms", {}).values()}
        if actor.get("place_id") not in home_places:
            raise ValueError("需要先回到住所才能打理花园或使用厨房")
        _, _, eco = self.load(db, scope)
        room = scene_state.get("rooms", {}).get(scene_state.get("room_id"))
        if kind in {"prepare_meal", "brew_tea"}:
            if not room or not room.get("water"):
                raise ValueError("需要进入带水源的室内房间才能下厨或煮茶")
            pantry = eco.get("pantry", {})
            keys = ("卷心菜", "小南瓜") if kind == "prepare_meal" else ("洋甘菊", "薄荷叶")
            if sum(int(pantry.get(k, 0)) for k in keys) <= 0:
                raise ValueError("厨房篮中暂无对应鲜蔬或花草，可先去花园采收")
        elif kind in {"eat_meal", "drink_tea"}:
            wanted = "meal" if kind == "eat_meal" else "tea"
            if not any(x["kind"] == wanted for x in eco.get("prepared", [])):
                raise ValueError("没有已经完成制作的餐食或茶饮")
        elif kind == "harvest_garden":
            if eco["flowerbed"]["progress"] < 0.65 and eco["veg_patch"]["progress"] < 0.65:
                raise ValueError("花圃与菜畦尚在生长中，再等一等就能采收")
        return ECOLOGY_DURATIONS[kind]

    def apply_step(self, db, scope, scene_state: dict, step: dict, now: float) -> dict:
        key, rev, eco = self.load(db, scope)
        kind = step["kind"]
        pantry = eco.setdefault("pantry", {})
        result = {"operation": kind, "name": ECOLOGY_LABELS[kind]}

        if kind == "water_garden":
            for name in ("flowerbed", "veg_patch"):
                plot = eco[name]
                plot["watered_at"] = now
                plot["progress"] = min(1.0, round(float(plot.get("progress", 0)) + 0.24, 3))
                plot["stage"] = _stage_for(plot["progress"], "blooming" if name == "flowerbed" else "ripe")
            result.update(
                flower_stage=eco["flowerbed"]["stage"],
                veg_stage=eco["veg_patch"]["stage"],
                summary="给花圃与菜畦浇透了水，叶片带着亮晶晶的水珠",
            )
        elif kind == "harvest_garden":
            gained = []
            if eco["veg_patch"]["progress"] >= 0.65:
                pantry["卷心菜"] = min(10, int(pantry.get("卷心菜", 0)) + 1)
                pantry["小南瓜"] = min(10, int(pantry.get("小南瓜", 0)) + 1)
                eco["veg_patch"].update(
                    progress=0.22,
                    stage="seedling",
                    harvest_count=int(eco["veg_patch"].get("harvest_count", 0)) + 1,
                )
                gained.extend(["卷心菜", "小南瓜"])
            if eco["flowerbed"]["progress"] >= 0.65:
                pantry["洋甘菊"] = min(10, int(pantry.get("洋甘菊", 0)) + 2)
                pantry["薄荷叶"] = min(10, int(pantry.get("薄荷叶", 0)) + 2)
                eco["flowerbed"].update(
                    progress=0.42,
                    stage="growing",
                    bloom_count=int(eco["flowerbed"].get("bloom_count", 0)) + 1,
                )
                gained.extend(["洋甘菊", "薄荷叶"])
                if self.engine.keepsakes is not None:
                    self.engine.keepsakes.place_item(
                        db,
                        scope,
                        {
                            "title": "晨露鲜花束",
                            "kind": "bouquet",
                            "summary": "刚从西侧花圃剪下的洋甘菊与薰衣草，插在窗台玻璃瓶里。",
                            "preferred_slot": "windowsill_vase",
                        },
                        now,
                    )
            result.update(gained=gained, summary="采收了" + ("、".join(gained) if gained else "新鲜花叶"))
        elif kind in {"eat_meal", "drink_tea"}:
            wanted = "meal" if kind == "eat_meal" else "tea"
            prepared = eco.setdefault("prepared", [])
            meal = next((x for x in prepared if x["kind"] == wanted), None)
            if meal is None:
                raise ValueError("餐食或茶饮已不存在")
            prepared.remove(meal)
            if self.engine.keepsakes is not None:
                key_ks, rev_ks, slots, archive = self.engine.keepsakes.load_keepsakes(db, scope)
                slots = {k: v for k, v in slots.items() if v.get('id') != meal['id']}
                archive = [a for a in archive if a.get('id') != meal['id']]
                self.engine.keepsakes.save_keepsakes(db, key_ks, rev_ks, slots, archive, now)
            eaten = dict(meal, consumed_at=now)
            eco["consumed"] = (eco.get("consumed", []) + [eaten])[-30:]
            result.update(name=meal["title"], item_id=meal["id"], summary="实际食用了" + meal["title"] if wanted == "meal" else "实际饮用了" + meal["title"])
        elif kind in {"prepare_meal", "brew_tea"}:
            if len(eco.get("prepared", [])) >= 20:
                raise ValueError("已有二十份餐食或茶饮，请先食用")
            catalog = RECIPES if kind == "prepare_meal" else TEAS
            chosen_title, used = "", ()
            for title, ingredients in reversed(catalog):
                if all(int(pantry.get(ing, 0)) > 0 for ing in ingredients):
                    chosen_title, used = title, ingredients
                    break
            if not used:
                raise ValueError("食谱原料不足")
            for ing in used:
                if int(pantry.get(ing, 0)) > 0:
                    pantry[ing] = int(pantry[ing]) - 1
            meal = {
                "id": "food_" + uuid.uuid4().hex,
                "title": chosen_title,
                "kind": "meal" if kind == "prepare_meal" else "tea",
                "ingredients": list(used),
                "at": now,
            }
            eco["recent_meals"] = (list(eco.get("recent_meals") or []) + [dict(meal, status="prepared")])[-6:]
            eco.setdefault("prepared", []).append(meal)
            if self.engine.keepsakes is not None:
                self.engine.keepsakes.place_item(
                    db,
                    scope,
                    {
                        "id": meal["id"],
                        "title": chosen_title,
                        "kind": meal["kind"],
                        "summary": f"用院子里种的{'、'.join(used)}刚做好的{chosen_title}。",
                        "preferred_slot": "table_snack",
                    },
                    now,
                )
            result.update(name=chosen_title, ingredients=list(used), summary=f"做好了热腾腾的{chosen_title}")

        eco["last_settled_at"] = now
        self.save(db, key, rev, eco, now, bump=True)
        return result

    def candidates(self, db, scope, scene_state: dict, actor: dict, now: float) -> list[dict]:
        home_places = {r["place_id"] for r in scene_state.get("rooms", {}).values()}
        if actor.get("place_id") not in home_places:
            return []
        _, _, eco = self.load(db, scope)
        items = []
        if now - float(eco["flowerbed"].get("watered_at", 0) or 0) > 4 * 3600:
            items.append({"kind": "water_garden"})
        if eco["flowerbed"]["progress"] >= 0.75 or eco["veg_patch"]["progress"] >= 0.75:
            items.append({"kind": "harvest_garden"})
        room = scene_state.get("rooms", {}).get(scene_state.get("room_id"))
        if room and room.get("water"):
            pantry = eco.get("pantry", {})
            if sum(int(pantry.get(k, 0)) for k in ("洋甘菊", "薄荷叶")) > 0:
                items.append({"kind": "brew_tea"})
            if sum(int(pantry.get(k, 0)) for k in ("卷心菜", "小南瓜")) > 0:
                items.append({"kind": "prepare_meal"})
        return items

    def snapshot(
        self,
        db,
        scope,
        now: float,
        *,
        life_state: dict | None = None,
        scene_state: dict | None = None,
        env: dict | None = None,
        actor: dict | None = None,
        recent_mail_at: float = 0.0,
    ) -> dict:
        key, rev, eco = self.load(db, scope)
        tz = (env or {}).get("timezone") or "Asia/Shanghai"
        season = season_for(now, tz)
        weather_effect = str(((env or {}).get("current") or {}).get("effect") or "clear")
        home_places = {r["place_id"] for r in (scene_state or {}).get("rooms", {}).values()}
        actor_away = bool(
            (actor or {}).get("phase") == "travelling"
            or (home_places and (actor or {}).get("place_id") not in home_places)
        )
        pose = "sleep" if (life_state or {}).get("availability") == "asleep" else "idle"
        cat = cat_state_for(now, tz, weather_effect, actor_away=actor_away, actor_pose=pose, seed=key)
        vitality = compute_vitality(life_state, scene_state, env, eco, now, recent_mail_at=recent_mail_at)
        if getattr(self.engine, "causal", None) is not None:
            body = self.engine.causal.projection(db, scope, now)["body"]
            vitality.update(energy=body["energy"], mood=(life_state or {}).get("subjective_state") or body["label"],
                            legacy_visual_only=True, tendency="autonomous_choice", basis=body["basis"])
        return {
            "revision": rev,
            "flowerbed": copy.deepcopy(eco["flowerbed"]),
            "veg_patch": copy.deepcopy(eco["veg_patch"]),
            "pantry": dict(eco.get("pantry", {})),
            "recent_meals": copy.deepcopy(eco.get("recent_meals", [])),
            "prepared": copy.deepcopy(eco.get("prepared", [])),
            "consumed": copy.deepcopy(eco.get("consumed", [])),
            "season": season,
            "cat": cat,
            "vitality": vitality,
        }

    def brief(self, snapshot: dict | None) -> str:
        if not snapshot:
            return ""
        vit = snapshot.get("vitality") or {}
        meals = snapshot.get("recent_meals") or []
        parts = []
        if vit.get("mood"):
            parts.append(f"心境：{vit['mood']}")
        if meals:
            parts.append(f"近期饮食：{meals[-1].get('title', '')}")
        return ("（" + "；".join(p for p in parts if p) + "）") if parts else ""

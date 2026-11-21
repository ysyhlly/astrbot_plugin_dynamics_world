import json
from datetime import datetime, timedelta

import pytest
from astrbot_plugin_dynamics_world import cabin_life as home
from astrbot_plugin_dynamics_world.activity_feed import page
from astrbot_plugin_dynamics_world.causal_life import CausalLifeService
from astrbot_plugin_dynamics_world.spatial import encode, identity
from test_avatar_api import avatar_api as dashboard_fixture
from test_scenes import setup, start, finish, item
from test_spatial import SCOPE
from test_world_integration import UMO

dashboard_api = dashboard_fixture

@pytest.fixture
def dwelling(rig):
    engine, clock, _ = rig
    clock[0] = datetime(2026, 11, 21, 8, 0, tzinfo=home.ZONE).timestamp()
    engine, clock, _ = setup(rig)
    engine.causal = CausalLifeService(engine)
    room = item(engine, "notebook")["room_id"]
    start(engine, [{"kind": "enter", "target_id": room}])
    finish(engine, clock)
    return engine, clock, {"home_room_id": room, "garden_room_id": ""}


def choose(engine, clock, binding, style):
    with engine._db() as db:
        key = engine.scenes.key(db, SCOPE)
        expected = home.preference(db, key)["revision"]
        return home.select(db, engine.scenes, SCOPE, style, expected, binding, clock[0])


def tick(engine, clock, when):
    clock[0] = when
    with engine._db() as db:
        home.tick_homes(engine.scenes, db, when)
        return engine.scenes.load(db, SCOPE)[2].get("flow")


@pytest.mark.parametrize("style", ["whale_coast", "witch_court"])
def test_two_real_slots_complete_once_with_receipt_and_diary(dwelling, style):
    engine, clock, binding = dwelling
    result = choose(engine, clock, binding, style)
    slots = result["upcoming"]
    assert len(slots) == 2 and all(
        s["status"] == "planned" and s["start"] > clock[0] for s in slots
    )
    assert choose(engine, clock, binding, style)["upcoming"] == slots
    with engine._db() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM diary WHERE entry_id LIKE 'cabin:%'"
            ).fetchone()[0]
            == 0
        )
        daily = json.loads(
            db.execute(
                "SELECT state FROM lives WHERE identity=?", (identity(SCOPE),)
            ).fetchone()[0]
        )
        assert {a["id"] for a in daily["plan"]} >= {a["id"] for a in slots}
    for i, slot in enumerate(slots):
        assert tick(engine, clock, slot["start"] - 1) is None
        flow = tick(engine, clock, slot["start"])
        assert (
            flow
            and flow["origin"] == "cabin_schedule"
            and flow["steps"][-1]["kind"] == slot["cabin_operation"]
        )
        for _ in range(4):
            if not flow:
                break
            flow = tick(engine, clock, flow["step_ends_at"] + 0.25)
        assert flow is None
        tick(engine, clock, clock[0] + 1)
        with engine._db() as db:
            notes = db.execute(
                "SELECT text,source_ids FROM diary WHERE entry_id LIKE 'cabin:%' ORDER BY occurred"
            ).fetchall()
            assert len(notes) == i + 1
            event = json.loads(notes[-1]["source_ids"])[0]
            evidence = db.execute(
                "SELECT kind,payload FROM world_scene_events WHERE event_id=?", (event,)
            ).fetchone()
            assert (
                evidence["kind"] == "step.completed"
                and json.loads(evidence["payload"])["operation"]
                == slot["cabin_operation"]
            )
            assert notes[-1]["text"] == home.ACTIVITIES[slot["cabin_operation"]].record
            agenda = engine.causal.load(db, SCOPE)[1]["agenda"]
            actual = next(a for a in agenda if a["id"] == slot["id"])
            assert actual["status"] == "completed" and event in actual["receipts"]
            assert any(
                e["title"] == slot["activity"]
                for e in page(engine, db, SCOPE)["events"]
            )
    tomorrow = datetime.fromtimestamp(clock[0], home.ZONE).replace(
        hour=8, minute=0
    ) + timedelta(days=1)
    tick(engine, clock, tomorrow.timestamp())
    with engine._db() as db:
        following = home.view(db, engine.scenes, SCOPE, engine.scenes.key(db, SCOPE))[
            "upcoming"
        ]
        assert len(following) == 2 and set(s["id"] for s in following).isdisjoint(
            s["id"] for s in slots
        )


@pytest.mark.asyncio
async def test_background_clock_starts_activity_without_dashboard(dwelling):
    engine, clock, binding = dwelling
    slot = choose(engine, clock, binding, "whale_coast")["upcoming"][0]
    clock[0] = slot["start"]
    await engine.tick(clock[0])
    with engine._db() as db:
        assert (
            engine.scenes.load(db, SCOPE)[2]["flow"]["steps"][-1]["kind"]
            == slot["cabin_operation"]
        )


def test_theme_change_cancels_only_unfinished_theme_work(dwelling):
    engine, clock, binding = dwelling
    old = choose(engine, clock, binding, "whale_coast")["upcoming"]
    assert tick(engine, clock, old[0]["start"])
    new = choose(engine, clock, binding, "witch_court")
    assert len(new["upcoming"]) == 2
    with engine._db() as db:
        state = engine.scenes.load(db, SCOPE)[2]
        assert state["flow"] is None and state["last_flow"]["status"] == "cancelled"
        assert not db.execute(
            "SELECT 1 FROM diary WHERE entry_id LIKE 'cabin:%'"
        ).fetchone()
        revision = home.preference(db, engine.scenes.key(db, SCOPE))["revision"]
        with pytest.raises(ValueError, match="已改变"):
            home.select(
                db, engine.scenes, SCOPE, "cottage", revision - 1, binding, clock[0]
            )
    back = choose(engine, clock, binding, "whale_coast")
    assert old[1]["id"] in {s["id"] for s in back["upcoming"]}
    assert choose(engine, clock, binding, "cottage")["upcoming"] == []


def test_clashing_plan_sleep_and_late_tick_do_not_invent_results(dwelling):
    engine, clock, binding = dwelling
    base = (
        datetime.fromtimestamp(clock[0], home.ZONE)
        .replace(hour=10, minute=0, second=0, microsecond=0)
        .timestamp()
    )
    with engine._db() as db:
        engine.causal.sync_plan(
            db,
            SCOPE,
            [
                {
                    "start": base,
                    "end": base + 5400,
                    "activity": "已有约定",
                    "fact_kind": "plan",
                }
            ],
            clock[0],
        )
    slot = choose(engine, clock, binding, "whale_coast")["upcoming"][0]
    assert slot["start"] >= base + 5400
    with engine._db() as db:
        document = json.loads(
            db.execute(
                "SELECT state FROM lives WHERE identity=?", (identity(SCOPE),)
            ).fetchone()[0]
        )
        document.update(
            availability="asleep",
            activity_code="sleeping",
            valid_until=slot["end"] + 3600,
        )
        db.execute(
            "UPDATE lives SET state=? WHERE identity=?",
            (encode(document), identity(SCOPE)),
        )
    assert tick(engine, clock, slot["start"]) is None
    assert tick(engine, clock, slot["end"] + 2) is None
    with engine._db() as db:
        assert not db.execute(
            "SELECT 1 FROM diary WHERE entry_id LIKE 'cabin:%'"
        ).fetchone()


@pytest.mark.asyncio
async def test_picker_api_preview_isolation_and_guards(dashboard_api):
    plugin, call = dashboard_api
    first = (await call("cabin_style", umo=""))["data"]
    assert first["style"] == "cottage" and not first["bound"]
    selected = (
        await call(
            "cabin_style",
            body={"umo": "", "style": "whale_coast", "expected_revision": 0},
        )
    )["data"]
    assert selected["style"] == "whale_coast" and selected["upcoming"] == []
    assert (await call("cabin_style", umo=""))["data"]["style"] == "whale_coast"
    assert (await call("cabin_style", umo=UMO))["data"]["style"] == "cottage"
    assert (
        await call(
            "cabin_style",
            body={"umo": "", "style": "witch_court", "expected_revision": 0},
        )
    )["code"] == 409
    assert (
        await call(
            "cabin_style", body={"umo": "", "style": "bad", "expected_revision": 1}
        )
    )["code"] == 400
    plugin.world.web.settings.raw.setdefault("web_panel", {})["allow_write"] = False
    assert (
        await call(
            "cabin_style", body={"umo": "", "style": "cottage", "expected_revision": 1}
        )
    )["code"] == 403


def test_late_selection_plans_tomorrow_without_backfilling(dwelling):
    engine, clock, binding = dwelling
    clock[0] = (
        datetime.fromtimestamp(clock[0], home.ZONE)
        .replace(hour=23, minute=59, second=40)
        .timestamp()
    )
    saved = choose(engine, clock, binding, "witch_court")
    tomorrow = datetime.fromtimestamp(clock[0], home.ZONE).date() + timedelta(days=1)
    assert len(saved["upcoming"]) == 2
    assert all(
        datetime.fromtimestamp(a["start"], home.ZONE).date() == tomorrow
        for a in saved["upcoming"]
    )
    choose(engine, clock, binding, "whale_coast")
    again = choose(engine, clock, binding, "witch_court")
    assert {a["id"] for a in again["upcoming"]} == {a["id"] for a in saved["upcoming"]}


def test_ordinary_plan_cannot_claim_completion_of_named_activity(dwelling):
    engine, clock, binding = dwelling
    slot = choose(engine, clock, binding, "whale_coast")["upcoming"][0]
    with engine._db() as db:
        with pytest.raises(ValueError, match="完成回执"):
            engine.causal.attach_interval(db, SCOPE, slot["id"], {}, clock[0])
        with pytest.raises(ValueError, match="设施行动"):
            engine.causal.attach_action(
                db, SCOPE, slot["id"], "different-action", clock[0]
            )
        engine.causal.sync_plan(
            db,
            SCOPE,
            [
                {
                    "start": slot["start"],
                    "end": slot["end"] + 900,
                    "activity": "已有约定",
                    "fact_kind": "plan",
                }
            ],
            clock[0],
        )
    tick(engine, clock, clock[0] + 1)
    with engine._db() as db:
        entries = engine.causal.load(db, SCOPE)[1]["agenda"]
        moved = next(a for a in entries if a["id"] == slot["id"])
        assert moved["status"] == "planned" and moved["start"] >= slot["end"] + 900
        assert not db.execute(
            "SELECT 1 FROM diary WHERE entry_id LIKE 'cabin:%'"
        ).fetchone()
